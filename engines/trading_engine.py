#  Futu Algo: Algorithmic High-Frequency Trading Framework
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#  Written by Bill Chan <billpwchan@hotmail.com>, 2021
#  Copyright (c)  billpwchan - All Rights Reserved


import itertools
import json
import pathlib
import platform
import subprocess
from datetime import date, datetime, timedelta
from multiprocessing import Pool, cpu_count

import pandas as pd
import psutil
from futu import AccumulateFilter, AuType, Currency, KLType, KL_FIELD, Market, MarketState, OpenHKTradeContext, \
    OpenQuoteContext, \
    RET_ERROR, RET_OK, \
    SecurityReferenceType, \
    SecurityType, \
    SimpleFilter, SortDir, StockField, SubType, TradeDateMarket, TrdEnv, SysConfig

import engines
from engines import DataProcessingInterface, HKEXInterface, YahooFinanceInterface
from util import logger
from util.global_vars import *


class FutuTrade:
    def __init__(self):
        """
            Futu Trading Engine Constructor
        """
        self.config = config
        self.default_logger = logger.get_logger("futu_trade")
        self.__init_futu_client()

        rsa_private_key = self.config['FutuOpenD.Config'].get('RsaPrivateKey')
        if rsa_private_key and pathlib.Path(rsa_private_key).is_file():
            # Setting protocol encryption globally
            SysConfig.enable_proto_encrypt(True)
            SysConfig.set_init_rsa_file(rsa_private_key)

        self.quote_ctx = OpenQuoteContext(host=self.config['FutuOpenD.Config'].get('Host'),
                                          port=self.config['FutuOpenD.Config'].getint('Port'))
        self.trade_ctx = OpenHKTradeContext(host=self.config['FutuOpenD.Config'].get('Host'),
                                            port=self.config['FutuOpenD.Config'].getint('Port'))
        self.username = self.config['FutuOpenD.Credential'].get('Username')
        # self.password = self.config['FutuOpenD.Credential'].get('Password')
        self.password_md5 = self.config['FutuOpenD.Credential'].get('Password_md5')
        self.trd_env = TrdEnv.REAL if self.config.get('FutuOpenD.Config', 'TrdEnv') == 'REAL' else TrdEnv.SIMULATE
        self.trading_util = engines.OrderEngine(self.quote_ctx, self.trade_ctx, self.trd_env)
        # Futu-Specific Variables
        self.market_list = [Market.HK, Market.US, Market.SH, Market.SZ, Market.HK_FUTURE, Market.SG, Market.JP]
        self.security_type_list = [SecurityType.BOND, SecurityType.BWRT, SecurityType.STOCK, SecurityType.WARRANT,
                                   SecurityType.IDX, SecurityType.ETF, SecurityType.FUTURE, SecurityType.PLATE,
                                   SecurityType.PLATESET]
        self.reference_type_list = [SecurityReferenceType.WARRANT, SecurityReferenceType.FUTURE]

    def __del__(self):
        """
            Default Cleanup Operations for Futu Trade Engine. Disconnect all Quote & Trade Connections
        """
        self.default_logger.info("Deleting Quote_CTX Connection")
        self.quote_ctx.close()  # 关闭当条连接，FutuOpenD会在1分钟后自动取消相应股票相应类型的订阅
        self.default_logger.info("Deleting Trade_CTX Connection")
        self.trade_ctx.close()  # 关闭当条连接，FutuOpenD会在1分钟后自动取消相应股票相应类型的订阅

    def __init_futu_client(self):
        os_type = platform.system()
        if os_type == 'Windows' and 'FutuOpenD.exe' not in (p.name() for p in psutil.process_iter()):
            opend_dir = Path.home() / 'AppData' / 'Roaming' / 'Futu' / 'FutuOpenD' / 'FutuOpenD.exe'
            try:
                subprocess.Popen([opend_dir])
            except FileNotFoundError:
                self.default_logger.error("Cannot auto-start FutuOpenD due to missing OpenD client, Ignore.")

    def __unlock_trade(self):
        """
        Unlock Trading Account if TrdEnv.REAL
        """
        if self.trd_env == TrdEnv.REAL:
            ret, data = self.trade_ctx.unlock_trade(password_md5=self.password_md5)
            if ret == RET_OK:
                self.default_logger.info("Account Unlock Success.")
            else:
                raise Exception("Account Unlock Unsuccessful: {}".format(data))

    def get_market_state(self):
        return self.quote_ctx.get_global_state()

    def is_normal_trading_time(self, stock_list: list) -> bool:
        """
        MarketState.MORNING            HK and A-share morning
        MarketState.AFTERNOON          HK and A-share afternoon, US opening hours
        MarketState.FUTURE_DAY_OPEN    HK, SG, JP futures day market open
        MarketState.FUTURE_OPEN        US futures open
        MarketState.NIGHT_OPEN         HK, SG, JP futures night market open
        """

        ret, data = self.quote_ctx.get_market_state(stock_list)
        if ret != RET_OK:
            self.default_logger.error('Get market state failed: ', data)
            return False

        if all(market_state == MarketState.MORNING or \
               market_state == MarketState.AFTERNOON or \
               market_state == MarketState.FUTURE_DAY_OPEN or \
               market_state == MarketState.FUTURE_OPEN or \
               market_state == MarketState.NIGHT_OPEN for market_state in data['market_state'].values.tolist()):
            return True
        self.default_logger.error('It is not regular trading hours.')
        return False

    def get_reference_stock_list(self, stock_code: str) -> pd.DataFrame:
        output_df = pd.DataFrame()
        for security_reference_type in self.security_type_list:
            ret, data = self.quote_ctx.get_referencestock_list(stock_code, security_reference_type)
            if ret == RET_OK:
                self.default_logger.info(f"Received Reference Stock List for {stock_code}")
                output_df = pd.concat([output_df, data], ignore_index=True)
            else:
                self.default_logger.error(f"Cannot Retrieve Reference Stock List for {stock_code}")
        return output_df

    def get_filtered_turnover_stocks(self) -> list:
        """
        A quick way to get all stocks with at least 100 million HKD turnover and a stock price >= 1 HKD
        :return:
        """
        simple_filter = SimpleFilter()
        simple_filter.filter_min = 1
        simple_filter.stock_field = StockField.CUR_PRICE
        simple_filter.is_no_filter = False
        financial_filter = AccumulateFilter()
        financial_filter.filter_min = 100000000
        financial_filter.stock_field = StockField.TURNOVER
        financial_filter.is_no_filter = False
        financial_filter.sort = SortDir.ASCEND
        financial_filter.days = 10
        begin_index = 0
        output_list = []

        while True:
            ret, ls = self.quote_ctx.get_stock_filter(market=Market.HK, filter_list=[simple_filter, financial_filter],
                                                      begin=begin_index)  # 对香港市场的股票做简单和财务筛选
            if ret == RET_OK:
                last_page, all_count, ret_list = ls
                output_list.extend([item.stock_code for item in ret_list])
                begin_index += 200
                if begin_index >= all_count:
                    break
            elif ret == RET_ERROR:
                return []
        return output_list

    def get_account_info(self) -> dict:
        """
        Query fund data such as net asset value, securities market value, cash, and purchasing power of trading accounts.
        :return: dictionary for UI Info
        """

        self.__unlock_trade()

        ret, data = self.trade_ctx.accinfo_query(trd_env=self.trd_env, acc_id=0, acc_index=0, refresh_cache=False,
                                                 currency=Currency.HKD)
        if ret == RET_OK:
            self.default_logger.info(f"Received Account Info for Environment: {self.trd_env}")
            # Retrieve the first row as the default account
            data = data.iloc[0]
            account_info = {
                "Net Assets":         data["total_assets"],
                "P/L":                data["realized_pl"],
                "Securities Value":   data["market_val"],
                "Cash":               data["cash"],
                "Buying Power":       data["power"],
                "Short Sell Power":   data["max_power_short"],
                "LMV":                data["long_mv"],
                "SMV":                data["short_mv"],
                "Available Balance":  data["avl_withdrawal_cash"],
                "Maximum Withdrawal": data["max_withdrawal"]
            }
            return {index: str(item) for index, item in account_info.items()}
        else:
            self.default_logger.error(f"Cannot Retrieve Account Info for {self.trd_env}")

    def kline_subscribe(self, stock_list: list, sub_type: SubType = SubType.K_1M) -> bool:
        self.default_logger.info(f'Subscribing to {len(stock_list)} kline...')
        # Maximum subscribe limit is 300
        ret_sub, err_message = self.quote_ctx.subscribe(stock_list[:min(len(stock_list), 150)],
                                                        [sub_type, SubType.ORDER_BOOK])
        if ret_sub != RET_OK:
            self.default_logger.error(f'Cannot subscribe to K-Line: {err_message}')
        return ret_sub == RET_OK

    def get_data_realtime(self, stock_list: list, sub_type: SubType = SubType.K_1M, kline_num: int = 1000) -> dict:
        """
        Receive real-time K-Line data as initial technical indicators observations
        注意：len(code_list) * 订阅的K线类型的数量 <= 100
        :param stock_list: List of selected stocks ['HK.00009', 'HK.00001']
        :param sub_type: Futu subscription type
        :param kline_num: Number of observations (i.e., default to 100)
        :return: dictionary of k-line data
        """
        input_data = {}
        for stock_code in stock_list:
            ret, data = self.quote_ctx.get_cur_kline(stock_code, kline_num, sub_type, AuType.QFQ)
            if ret == RET_OK:
                input_data[stock_code] = input_data.get(stock_code, data)
            else:
                self.default_logger.error(f'Cannot get Real-time K-line data: {data}')
        return input_data

    def update_1M_data(self, stock_code: str, years=2, force_update: bool = False, default_days: int = 30):
        """
            Update 1M Data to ./data/{stock_code} folders for max. 2-years duration
            Assume today is 2022-04-17, the oldest data that can be downloaded is 2020-04-17
        :param stock_code: Stock Code with Format (e.g., HK.00001)
        :param years: 2 years
        :param default_days:
        :param force_update:
        """
        column_names = json.loads(self.config.get('FutuOpenD.DataFormat', 'HistoryDataFormat'))
        history_df = pd.DataFrame(columns=column_names)
        # If force update, update all 2-years 1M data. Otherwise only update the last week's data
        start_date = str((datetime.today() - timedelta(days=round(365 * years))).date()) if force_update else str(
            (datetime.today() - timedelta(days=default_days)).date())
        end_date = str(datetime.today().date())
        # This will give a list of dates between 2-years range
        date_range = pd.date_range(start_date, end_date, freq='d').strftime(DATETIME_FORMAT_DW).tolist()
        # Retrieve the first page
        ret, data, page_req_key = self.quote_ctx.request_history_kline(stock_code,
                                                                       start=start_date,
                                                                       end=end_date,
                                                                       ktype=KLType.K_1M, autype=AuType.QFQ,
                                                                       fields=[KL_FIELD.ALL],
                                                                       max_count=1000, page_req_key=None,
                                                                       extended_time=False)
        if ret == RET_OK:
            history_df = pd.concat([history_df, data], ignore_index=True)
        else:
            self.default_logger.error(f'Cannot get Historical 1M K-line data: {data}')
            return

        # 请求后面的所有结果
        while page_req_key is not None:
            # The inner loop is to ensure that whenever there is an error, we can re-try until it success
            while True:
                original_page_req_key = page_req_key
                ret, data, page_req_key = self.quote_ctx.request_history_kline(stock_code,
                                                                               start=start_date,
                                                                               end=end_date,
                                                                               ktype=KLType.K_1M, autype=AuType.QFQ,
                                                                               fields=[KL_FIELD.ALL],
                                                                               max_count=1000,
                                                                               page_req_key=page_req_key,
                                                                               extended_time=False)
                if ret == RET_OK:
                    history_df = pd.concat([history_df, data], ignore_index=True)
                    break
                self.default_logger.error(f'Cannot get Historical 1M K-line data: {data}')
                # Revert to previous page req key and re-try again
                page_req_key = original_page_req_key
                time.sleep(1)

        for input_date in date_range:
            output_path = PATH_DATA / stock_code / f'{stock_code}_{input_date}_1M.parquet'
            output_df = history_df[history_df['time_key'].str.contains(input_date)]
            if DataProcessingInterface.save_stock_df_to_file(output_df, output_path):
                self.default_logger.info(f'Saved 1M K-line data to {output_path}')
        time.sleep(0.5)

    def update_DW_data(self, stock_code: str, years=10, force_update: bool = False, k_type: KLType = KLType.K_DAY):
        """
            Update 1D Data (365 days per file) to ./data/{stock_code} folders for max. 2-years duration
        :param force_update:
        :param stock_code: Stock Code with Format (e.g., HK.00001)
        :param years: 10 years
        :param k_type: Futu K-Line Type
        """
        for i in range(0, 11 if force_update else (years + 1)):
            start_date = date((datetime.today() - timedelta(days=i * 365)).year, 1, 1)

            DataProcessingInterface.validate_dir(PATH_DATA / stock_code)

            if k_type == KLType.K_DAY:
                output_path = PATH_DATA / stock_code / f'{stock_code}_{start_date.year}_1D.parquet'
            elif k_type == KLType.K_WEEK:
                output_path = PATH_DATA / stock_code / f'{stock_code}_{start_date.year}_1W.parquet'
            else:
                self.default_logger.error('Unsupported KLType. Please try it later.')
                return False

            # Request Historical K-line Data (Daily)
            start_date = start_date.strftime(DATETIME_FORMAT_DW)
            while True:
                ret, data, page_req_key = self.quote_ctx.request_history_kline(stock_code, start=start_date,
                                                                               end=None,
                                                                               ktype=k_type, autype=AuType.QFQ,
                                                                               fields=[KL_FIELD.ALL],
                                                                               max_count=1000, page_req_key=None,
                                                                               extended_time=False)
                if ret == RET_OK:
                    if DataProcessingInterface.save_stock_df_to_file(data, output_path):
                        self.default_logger.info(f'Saved {k_type} K-line data to {output_path}')
                    # Probably empty data during a non-trading date
                    break
                # Retry Storing Data due to too frequent requests (max. 60 requests per 30 seconds)
                time.sleep(1)
                self.default_logger.error(f'{k_type} Historical KLine Store Error: {data}')
            time.sleep(0.6)

    def update_owner_plate(self, stock_list: list):
        """
        Update Owner Plate information for all equities in Hong Kong stock market.
        :param stock_list: A list of all equities (i.e., stock code)
        """
        # Slice the list into 200-elements per list
        stock_lists = [stock_list[i:i + 200] for i in range(0, len(stock_list), 200)]
        output_df = pd.DataFrame()
        for stock_list in stock_lists:
            ret, data = self.quote_ctx.get_owner_plate(stock_list)
            if ret == RET_OK:
                output_df = pd.concat([output_df, data], ignore_index=True)
            else:
                self.default_logger.error(f'Cannot get Owner Plate: {data}')
            time.sleep(3.5)
        output_path = PATH_DATA / 'Stock_Pool' / 'stock_owner_plate.parquet'
        DataProcessingInterface.save_stock_df_to_file(output_df, output_path)
        self.default_logger.info(f'Stock Owner Plate Updated: {output_path}')

    def update_stock_basicinfo(self):
        """
        Update stock static information for all markets and all forms of equities (E.g., Stock, Futures, etc.)
        """
        output_df = pd.DataFrame()
        for market, stock_type in itertools.product(self.market_list, self.security_type_list):
            ret, data = self.quote_ctx.get_stock_basicinfo(market=market, stock_type=stock_type)
            if ret == RET_OK:
                output_df = pd.concat([output_df, data], ignore_index=True)
            else:
                self.default_logger.error(f'Cannot get Stock Basic Info of {market} - {stock_type}: {data}')
        output_path = PATH_DATA / 'Stock_Pool' / 'stock_basic_info.parquet'
        DataProcessingInterface.save_stock_df_to_file(output_df, output_path)
        self.default_logger.info(f'Stock Static Basic Info Updated: {output_path}')

    def update_stock_fundamentals(self):
        """
        Update stock fundamentals information for all equities in Hong Kong stock market.
        """
        pool = Pool(cpu_count())
        output_list = pool.map(YahooFinanceInterface.parse_stock_info, HKEXInterface.get_equity_list_full())
        pool.close()
        pool.join()

        output_dict = {}
        for record in output_list:
            output_dict[record[0]] = output_dict.get(record[0], record[1])
            self.default_logger.info(f"Updated Stock Fundamentals for {record[0]}")

        with open(PATH_DATA / 'Stock_Pool' / 'stock_fundamentals.json', 'w') as f:
            json.dump(output_dict, f)

    def cur_kline_evaluate(self, stock_list: list, strategy_map: dict, sub_type: SubType = SubType.K_1M):
        """
            Real-Time K-Line!
        :param stock_list: A List of Stock Code with Format (e.g., [HK.00001, HK.00002])
        :param strategy_map: Strategies defined in ./strategies class. Should be inherited from based class Strategies
        :param sub_type: Subscription SubType for FuTu (i.e., Trading Frequency)

        """
        self.__unlock_trade()

        input_data = self.get_data_realtime(stock_list, sub_type, 100)
        for stock_code in stock_list:
            strategy_map[stock_code].set_input_data_stock_code(stock_code, input_data[stock_code])
            strategy_map[stock_code].parse_data(stock_list=[stock_code])
            if strategy_map[stock_code].sell(stock_code=stock_code):
                self.trading_util.place_sell_order(stock_code)
            if strategy_map[stock_code].buy(stock_code=stock_code):
                self.trading_util.place_buy_order(stock_code)

    def display_quota(self):
        """
            Display Stock Subscription & Historical K-Line Quota
        """
        ret, data = self.quote_ctx.query_subscription()
        if ret == RET_OK:
            self.default_logger.info(f'Query Subscription Quota: \n{data}')
        ret, data = self.quote_ctx.get_history_kl_quota(get_detail=True)
        if ret == RET_OK:
            self.default_logger.info(f'Historical K-line Quota: \n{data}')

    def request_trading_days(self, start_date: str, end_date: str) -> dict:
        """
        请求交易日，注意该交易日是通过自然日剔除周末和节假日得到，未剔除临时休市数据。
        :param start_date:
        :param end_date:
        :return: [{'time': '2020-04-01', 'trade_date_type': 'WHOLE'}, ...]
        """
        ret, data = self.quote_ctx.request_trading_days(TradeDateMarket.HK, start=start_date, end=end_date)
        if ret == RET_OK:
            self.default_logger.info(f'Trading Days: {data}')
            return data
        self.default_logger.error(f'error: {data}')
        return {}
