import ccxt
import pymysql.err

from chanlun import config
from chanlun.exchange.exchange import *
from chanlun.exchange.exchange_db import ExchangeDB

# 全局配置，避免多次请求api
g_all_stocks = []


class ExchangeBinance(Exchange):
    """
    数字货币交易所接口
    """

    def __init__(self):
        params = {}

        # 设置是否使用代理
        if config.PROXY_HOST != '':
            params['proxies'] = {
                'https': f"http://{config.PROXY_HOST}:{config.PROXY_PORT}",
                'http': f"http://{config.PROXY_HOST}:{config.PROXY_PORT}"
            }

        # 设置是否设置交易 api
        if config.BINANCE_APIKEY != '':
            params['apiKey'] = config.BINANCE_APIKEY
            params['secret'] = config.BINANCE_SECRET

        self.exchange = ccxt.binanceusdm(params)

        self.db_exchange = ExchangeDB('currency')

    def now_trading(self):
        """
        返回交易时间，数字货币 24 小时可交易
        """
        return True

    def stock_info(self, code: str) -> [Dict, None]:
        """
        数字货币全部返回 code 值
        """
        return {'code': code, 'name': code}

    def all_stocks(self):
        """
        返回所有交易对儿
        """
        global g_all_stocks
        if len(g_all_stocks) > 0:
            return g_all_stocks

        markets = self.exchange.load_markets()
        for s in markets:
            if '/' in s:
                g_all_stocks.append({'code': s, 'name': s})
        return g_all_stocks

    def klines(self, code: str, frequency: str,
               start_date: str = None, end_date: str = None,
               args=None) -> [pd.DataFrame, None]:
        """
        返回 k 线数据
        优先从数据库中获取，在进行 api 请求，合并数据，并更新数据库，之后返回k线行情
        可以减少网络请求，优化 vpn 使用流量
        """
        if args is None:
            args = {}
        try:
            if start_date is not None or end_date is not None:
                online_klines = self.__online_klines(code, frequency, start_date, end_date, args)
                self.db_exchange.insert_klines(code, frequency, online_klines)
                return online_klines

            db_klines = self.db_exchange.klines(code, frequency)
            if len(db_klines) == 0:
                online_klines = self.__online_klines(code, frequency, start_date, end_date, args)
                self.db_exchange.insert_klines(code, frequency, online_klines)
                return online_klines

            last_datetime = db_klines.iloc[-1]['date'].strftime('%Y-%m-%d %H:%M:%S')
            online_klines = self.__online_klines(code, frequency, start_date=last_datetime)
            self.db_exchange.insert_klines(code, frequency, online_klines)
            if len(online_klines) == 1500:
                online_klines = self.__online_klines(code, frequency, start_date, end_date, args)
                self.db_exchange.insert_klines(code, frequency, online_klines)
                return online_klines

            klines = db_klines.append(online_klines)
            klines.drop_duplicates(subset=['date'], keep='last', inplace=True)
            return klines[-2500::]
        except pymysql.err.ProgrammingError:
            self.db_exchange.create_tables([code])
            return self.klines(code, frequency, start_date, end_date, args)
        except Exception as e:
            print(e)

        return []

    def __online_klines(self, code: str, frequency: str,
                        start_date: str = None, end_date: str = None,
                        args=None) -> [pd.DataFrame, None]:
        """
        api 接口请求行情数据
        """
        # 1m  3m  5m  15m  30m  1h  2h  4h  6h  8h  12h  1d  3d  1w  1M
        if args is None:
            args = {}
        frequency_map = {'w': '1w', 'd': '1d', '4h': '4h', '60m': '1h',
                         '30m': '30m', '15m': '15m', '5m': '5m', '1m': '1m'}
        if frequency not in frequency_map.keys():
            raise Exception(f'不支持的周期: {frequency}')

        if start_date is not None:
            start_date = int(
                datetime.datetime.timestamp(datetime.datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S'))) * 1000
        if end_date is not None:
            end_date = int(
                datetime.datetime.timestamp(datetime.datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S'))) * 1000

        kline = self.exchange.fetchOHLCV(symbol=code, timeframe=frequency_map[frequency], limit=1500,
                                         params={'startTime': start_date, 'endTime': end_date})
        kline_pd = pd.DataFrame(kline, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        kline_pd.loc[:, 'code'] = code
        kline_pd.loc[:, 'date'] = kline_pd['date'].apply(lambda x: datetime.datetime.fromtimestamp(x / 1e3))
        # kline_pd['date'] = pd.to_datetime(kline_pd['date'].values / 1000, unit='s', utc=True).tz_convert(
        # 'Asia/Shanghai')
        return kline_pd[['code', 'date', 'open', 'close', 'high', 'low', 'volume']]

    def ticks(self, codes: List[str]) -> Dict[str, Tick]:
        res_ticks = {}
        for code in codes:
            _t = self.exchange.fetch_ticker(code)
            res_ticks[code] = Tick(
                code=code, last=_t['last'], buy1=_t['bid'], sell1=_t['ask'], high=_t['high'], low=_t['low'],
                open=_t['open'], volume=_t['quoteVolume'])
        return res_ticks

    def ticker24HrRank(self, num=20):
        """
        获取24小时交易量排行前的交易对儿
        :param num:
        :return:
        """
        tickers = self.exchange.fapiPublicGetTicker24hr()
        tickers = sorted(tickers, key=lambda d: float(d['quoteVolume']), reverse=True)
        codes = []
        for t in tickers:
            if t['symbol'][-4:] == 'USDT':
                codes.append(t['symbol'][:-4] + '/' + t['symbol'][-4:])
            if len(codes) >= num:
                break
        return codes

    def balance(self):
        b = self.exchange.fetch_balance()
        balances = {
            'total': b['USDT']['total'],
            'free': b['USDT']['free'],
            'used': b['USDT']['used'],
            'profit': b['info']['totalUnrealizedProfit']
        }
        for asset in b['info']['assets']:
            balances[asset['asset']] = {
                'total': asset['availableBalance'],
                'profit': asset['unrealizedProfit'],
            }
        return balances

    def positions(self, code: str = ''):
        position = self.exchange.fetch_positions(symbols=[code] if code != '' else None)
        """
        symbol 标的
        entryPrice 价格
        contracts 持仓数量
        side 方向 long short
        leverage 杠杠倍数
        unrealizedPnl 未实现盈亏
        initialMargin 占用保证金
        percentage 盈亏百分比
        """
        return [p for p in position if p['entryPrice'] != 0.0]

    # 撤销所有挂单
    def cancel_all_order(self, code):
        self.exchange.cancel_all_orders(symbol=code)
        return True

    def order(self, code: str, o_type: str, amount: float, args=None):
        trade_maps = {
            'open_long': {'side': 'BUY', 'positionSide': 'LONG'},
            'open_short': {'side': 'SELL', 'positionSide': 'SHORT'},
            'close_long': {'side': 'SELL', 'positionSide': 'LONG'},
            'close_short': {'side': 'BUY', 'positionSide': 'SHORT'},
        }
        if 'open' in o_type:
            self.exchange.fapiPrivate_post_leverage(
                params={'symbol': code.replace('/', ''), 'leverage': args['leverage']})
        return self.exchange.create_order(
            symbol=code, type='MARKET',
            side=trade_maps[o_type]['side'],
            amount=amount,
            params={'positionSide': trade_maps[o_type]['positionSide']}
        )

    def stock_owner_plate(self, code: str):
        raise Exception('交易所不支持')

    def plate_stocks(self, code: str):
        raise Exception('交易所不支持')
