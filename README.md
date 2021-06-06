<div align="center">
  <img alt="FutuAlgo Logo" src="https://raw.githubusercontent.com/billpwchan/futu_algo/master/images/logo.png" width="400px" />

**billpwchan/futu-algo API Reference Documentation**

[![Issues](https://img.shields.io/github/issues/billpwchan/futu_algo?style=for-the-badge)](https://github.com/billpwchan/futu_algo/issues)
[![License](https://img.shields.io/github/license/billpwchan/futu_algo?style=for-the-badge)](https://github.com/billpwchan/futu_algo/blob/master/LICENSE)
[![LastCommit](https://img.shields.io/github/last-commit/billpwchan/futu_algo?style=for-the-badge)](https://github.com/billpwchan/futu_algo/blob/master/LICENSE)
[![CommitActivity](https://img.shields.io/github/commit-activity/y/billpwchan/futu_algo?style=for-the-badge)](https://github.com/billpwchan/futu_algo/commits/master)
[![WorkflowStatus](https://img.shields.io/github/workflow/status/billpwchan/futu_algo/CodeQL?style=for-the-badge)](https://github.com/billpwchan/futu_algo/commits/master)
[![RepoSize](https://img.shields.io/github/repo-size/billpwchan/futu_algo?style=for-the-badge)](https://github.com/billpwchan/futu_algo)
[![Languages](https://img.shields.io/github/languages/top/billpwchan/futu_algo?style=for-the-badge)](https://github.com/billpwchan/futu_algo)

</div>

## Highlights

- **Supported Platforms and Markets**: Futu_algo is a algorithmic trading solution developed based on FutuOpenD and
  FutuOpenAPI. Fully support FutuNiuNiu and FutuMooMoo users in Hong Kong stock market. *(More market support is coming
  soon)*
- **Historical K-Line Data**: Allow users to automatically downloading historical data for your interested stocks into
  CSV and storing to SQLite database for backtesting. *(up to 1M level for max. 2 years, or 1D level for max. 10 years)*
- **Backtesting Trading Strategies (BETA)**: Backtest your own trading strategies on historical data with a summarized
  reports and visualizations using Pyfolio. For more demanding users, feel free to other commercial solutions such as
  Amibroker for backtesting.
- **High-Frequency Trading**: Real-time low-latency trading features that allows applying your own basket of trading
  strategies on your stock pool. User can specify the trading strategy to be used for each stock based on their
  preference. *(up to 1M level)*
- **Advanced Stock Screener**: Screens high-quality stocks using your own stock screening strategies, and notify your
  friends using the email subscription feature.
- **Trading Strategy Editor**: Write your own trading strategy following a simple template (buy, sell, calculate
  technical indicators). Common strategies such as MACD and KDJ-based trading rules are provided as guidelines.
- **GUI Support (Upcoming)**: Easy-to-use GUI for users to adjust their configurations, trading, downloading data and
  filtering stocks within one application. No longer need to type any command for trading!

## Version Guidance

| FutuAlgo Release | Futu OpenAPI Specification |
|:-----------------|:---------------------------|
| 0.0.2-alpha.x    | 5.3                        |

## Deployment

### Pre-Requisite: Configuration File (Config.ini)

```ini
[FutuOpenD.Config]
Host = <OpenD Host>
Port = <OpenD Port>
WebSocketPort = <OpenD WebSocketPort>
WebSocketKey = <OpenD WebSocketKey>
TrdEnv = <SIMULATE or REAL>

[FutuOpenD.Credential]
Username = <Futu Login Username>
Password_md5 = <Futu Login Password Md5 Value>

[FutuOpenD.DataFormat]
HistoryDataFormat = ["code","time_key","open","close","high","low","pe_ratio","turnover_rate","volume","turnover","change_rate","last_close"]
SubscribedDataFormat = None

[Database]
Database_path = <Your SQLite Database File Path>

[TradePreference]
LotSizeMultiplier = <# of Stocks to Buy per Signal>
MaxPercPerAsset = <Maximum % of Capital Allocated per Asset>
StockList = <Subscribed Stocks in List Format>

[Backtesting.Commission.HK]
FixedCharge = <Fixed Transaction Fee and Tax in HKD - 15.5>
PercCharge = <Percentage Transaction Fee in % - 0.1097>

[Email]
Port = <Server SMTP Setting>
SmtpServer = <Server SMTP Setting>
Sender = <Sender Email Address - account1@example.com>
Login = <Sender Email Address - account1@example.com>
Password = <Sender Email Password>
SubscriptionList = ["account1@example.com", "account2@example.com"]
```

**IMPORTANT NOTE:** The format may be changed in later commits. Please refer to this README if exception is raised.

### 1. Install Dependencies

Install using [conda](https://docs.conda.io/en/latest/):

    conda create --name <env> --file requirements.txt

### 2. Install FutuOpenD

For **Windows/MacOS/CentOS/Ubuntu**:

https://www.futunn.com/download/OpenAPI

Please do make sure that you have at least a LV1 subscription level on your interested quotes. For details, please refer
to https://openapi.futunn.com/futu-api-doc/qa/quote.html

**MAKE SURE YOU LOGIN TO FUTU OPEND FIRST BEFORE STARTING FUTU_ALGO!**

### 3. Initialize SQLite Database

Go to [SQLite official website](https://www.sqlite.org/quickstart.html) and follow the QuickStart instruction to install
SQLite tools in the device.

Create a folder named 'database' in the root folder, and execute the SQLite DDL file stored in *./util/database_ddl.sql*
.

```
./
  ├── database
  │       └── stock_data.sqlite
```

### 4. Download Data (e.g. 1M Data for max. 2 Years)

For **Windows**:

    python main_backend.py -u

For **MacOS/Linux**:

    python3 main_backend.py -u

### 4. Enjoy :smile:

## Command-line Interface Usages

Update all `K_1M` and `K_DAY` interval historical K-line data

    python main_backend.py -u   /   python main_backend.py --update

**IMPORTANT NOTE:** This will not override existing historical data if the file exists.

If you want to refresh all data, use the following command instead (WITH CAUTION!)

    python main_backend.py -fu  /   python main_backend.py --force_update

Store all data from CSV to SQLite Database *(Currently the database isn't used for any feature)*

    python main_backend.py -d   /   python main_backend.py --database

Execute High-Frequency Trading (HFT) with a Pre-defined Strategy

    python main_backend.py -s MACD_Cross    /   python main_backend.py --strategy MACD_Cross

Execute Stock Filtering with Pre-defined Filtering Strategies

    python main_backend.py -f Volume_Threshold Price_Threshold   /   python main_backend.py --filter Volume_Threshold Price_Threshold

## Future Plans

- [ ] [NEED A GREAT NAME FOR THIS ALGO TRADE!!](https://github.com/billpwchan/futu_algo/issues/23)
- [ ] [Custom Backtesting Time Interval]()
- [ ] [Dynamic Instantiation](https://github.com/billpwchan/futu_algo/issues/18)

-----------

## Contributor

[Bill Chan -- Main Developer](https://github.com/billpwchan/)

## Disclaimer

Futures, stocks and options trading involves substantial risk of loss and is not suitable for every investor. The
valuation of futures, stocks and options may fluctuate, and, as a result, clients may lose more than their original
investment. The impact of seasonal and geopolitical events is already factored into market prices. The highly leveraged
nature of futures trading means that small market movements will have a great impact on your trading account and this
can work against you, leading to large losses or can work for you, leading to large gains.

If the market moves against you, you may sustain a total loss greater than the amount you deposited into your account.
You are responsible for all the risks and financial resources you use and for the chosen trading system. You should not
engage in trading unless you fully understand the nature of the transactions you are entering into and the extent of
your exposure to loss. If you do not fully understand these risks you must seek independent advice from your financial
advisor.

All trading strategies are used at your own risk.

Any content in this repository should not be relied upon as advice or construed as providing recommendations of any
kind. It is your responsibility to confirm and decide which trades to make. Trade only with risk capital; that is, trade
with money that, if lost, will not adversely impact your lifestyle and your ability to meet your financial obligations.
Past results are no indication of future performance. In no event should the content of this correspondence be construed
as an express or implied promise or guarantee.

This repository and its author are not responsible for any losses incurred as a result of using any of our trading
strategies. Loss-limiting strategies such as stop loss orders may not be effective because market conditions or
technological issues may make it impossible to execute such orders. Likewise, strategies using combinations of options
and/or futures positions such as “spread” or “straddle” trades may be just as risky as simple long and short positions.
Information provided in this correspondence is intended solely for informational purposes and is obtained from sources
believed to be reliable. Information is in no way guaranteed. No guarantee of any kind is implied or possible where
projections of future conditions are attempted.
