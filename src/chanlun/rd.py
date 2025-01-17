import json
import random
import time

import redis
from typing import Dict
from chanlun import config
from chanlun.cl_interface import *

r = None


def Robj():
    global r
    if r is None:
        r = redis.Redis(host=config.REDIS_HOST,
                        port=config.REDIS_PORT, decode_responses=True)
    return r


def save_byte(key, val):
    """
    保存字节数据到 redis 中
    :param key:
    :param val:
    :return:
    """
    robj = redis.Redis(host=config.REDIS_HOST,
                       port=config.REDIS_PORT, decode_responses=False)
    robj.set(key, val)


def get_byte(key):
    """
    读取字节数据
    :param key:
    :return:
    """
    robj = redis.Redis(host=config.REDIS_HOST,
                       port=config.REDIS_PORT, decode_responses=False)
    return robj.get(key)


def strategy_save(key, obj):
    """
    策略回测结果保存
    :param key:
    :param obj:
    :return:
    """
    robj = redis.Redis(host=config.REDIS_HOST,
                       port=config.REDIS_PORT, decode_responses=False)
    return robj.hset('strategy_back', key, obj)


def strategy_get(key):
    """
    策略回测结果读取
    :param key:
    :return:
    """
    robj = redis.Redis(host=config.REDIS_HOST,
                       port=config.REDIS_PORT, decode_responses=False)
    return robj.hget('strategy_back', key)


def strategy_keys():
    """
    获取保存的所有回测结果 key
    :return:
    """
    ks = Robj().hkeys('strategy_back')
    ks.sort(reverse=True)
    return ks


def save_ex(key: str, seconds: int, value: object):
    """
    设置有效期的 Key 并保存 value 值
    """
    return Robj().setex(key, seconds, json.dumps(value))


def get_ex(key: str):
    """
    读取 key，过期无值返回 None
    """
    value = Robj().get(key)
    if value is None:
        return None
    return json.loads(value)


def zx_save(market_type, name, stocks):
    """
    自选列表保存
    """
    Robj().hset(f'zixuan_{market_type}', name, json.dumps(stocks))
    return True


def zx_query(market_type, name):
    """
    查询自选列表
    """
    stocks = Robj().hget(f'zixuan_{market_type}', name)
    stocks = json.loads(stocks) if stocks else []
    return stocks


def jhs_query(market):
    """
    机会列表查询
    :return:
    """
    if market == 'stock':
        hkey = 'stock_jh'
    elif market == 'hk':
        hkey = 'hk_jh'
    elif market == 'us':
        hkey = 'us_jh'
    elif market == 'futures':
        hkey = 'futures_jh'
    elif market == 'currency':
        hkey = 'currency_jh'
    else:
        raise Exception(f'jh save market error {market}')

    jhs = []
    h_keys = Robj().hkeys(hkey)
    for k in h_keys:
        v = Robj().hget(hkey, k)
        if v is not None:
            v = json.loads(v)
            # 时间转换
            v['datetime_str'] = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(v['datetime']))
            jhs.append(v)
    # 按照 datetime 排序
    jhs.sort(key=lambda j: j['datetime'], reverse=True)
    return jhs


def jhs_save(market, code, name, jh: dict):
    """
    机会保存
    """
    if market == 'stock':
        hkey = 'stock_jh'
    elif market == 'hk':
        hkey = 'hk_jh'
    elif market == 'us':
        hkey = 'us_jh'
    elif market == 'futures':
        hkey = 'futures_jh'
    elif market == 'currency':
        hkey = 'currency_jh'
    else:
        raise Exception(f'jh save market error {market}')

    bi: BI = jh.get('bi', None)
    xd: XD = jh.get('xd', None)

    if bi:
        is_done = '笔完成' if bi.is_done() else '笔未完成'
        is_td = ' - TD' if bi.td else '--'
    else:
        is_done = '线段完成' if xd.is_done() else '线段未完成'
        is_td = ''

    frequency = jh['frequency']
    jh_type = jh['type']

    key = f'stock_code:{code}_frequency:{frequency}_jhtype:{jh_type}'
    ex_val = Robj().hget(hkey, key)
    if ex_val is not None:
        ex_val = json.loads(ex_val)
        if 'is_done' in ex_val.keys() and ex_val['is_done'] == is_done and ex_val['is_td'] == is_td:
            # 没有变化，直接返回
            return True

    val = {
        'code': code,
        'name': name,
        'frequency': frequency,
        'jh_type': jh_type,
        'is_done': is_done,
        'is_td': is_td,
        'datetime': int(time.time())
    }
    Robj().hset(hkey, key, json.dumps(val))

    # 检查超过 24 小时的机会
    if random.randint(0, 100) < 10:
        h_keys = Robj().hkeys(hkey)
        for k in h_keys:
            v = Robj().hget(hkey, k)
            if v is not None:
                v = json.loads(v)
                if int(time.time()) - int(v['datetime']) > 24 * 60 * 60:
                    Robj().hdel(hkey, k)

    return False  # False 意思表示有更新


def futures_order_save(symbol, order):
    """
    记录期货的订单信息
    :param symbol:
    :param order:
    :return:
    """
    orders = Robj().hget('futures_orders', symbol)
    orders = [] if orders is None else json.loads(orders)
    orders.append(order)
    Robj().hset('futures_orders', symbol, json.dumps(orders))
    return True


def futures_order_query(symbol):
    """
    期货订单查询
    :param symbol:
    :return:
    """
    orders = Robj().hget('futures_orders', symbol)
    orders = [] if orders is None else json.loads(orders)
    return orders


def currency_order_save(symbol, order):
    """
    记录币种订单信息
    :param symbol:
    :param order:
    :return:
    """
    orders = Robj().hget('currency_orders', symbol)
    orders = [] if orders is None else json.loads(orders)
    orders.append(order)
    Robj().hset('currency_orders', symbol, json.dumps(orders))
    return True


def currency_order_query(symbol):
    """
    数字货币订单查询
    :param symbol:
    :return:
    """
    orders = Robj().hget('currency_orders', symbol)
    orders = [] if orders is None else json.loads(orders)
    return orders


def currency_opt_record_save(symbol, info):
    """
    数字货币操盘记录
    :param symbol:
    :param info:
    :return:
    """
    global r
    record = {
        'symbol': symbol,
        'info': info,
        'datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    Robj().lpush('currency_opt_records', json.dumps(record))
    return True


def currency_opt_record_query(num=100):
    """
    数字货币操作记录查询
    :return:
    """
    global r
    res = Robj().lrange('currency_opt_records', 0, num)
    return [json.loads(_r) for _r in res]


def dl_hy_rank_query():
    """
    查询行业动量排行
    :return:
    """
    res = Robj().get('dl_ranks')
    if res is None:
        return {}
    res = json.loads(res)
    return res


def dl_hy_rank_save(ranks: Dict[str, dict]):
    """
    行业动量排行保存
    :param ranks:
    :return:
    """
    # 只保留倒数5天的数据
    days = sorted(ranks.keys())
    save_ranks = {day: ranks[day] for day in days[-5:]}
    Robj().set('dl_ranks', json.dumps(save_ranks))
    return True


def dl_gn_rank_query():
    """
    查询概念动量排行
    :return:
    """
    res = Robj().get('dl_gn_ranks')
    if res is None:
        return {}
    res = json.loads(res)
    return res


def dl_gn_rank_save(ranks: Dict[str, dict]):
    """
    概念动量排行保存
    :param ranks:
    :return:
    """
    days = sorted(ranks.keys())
    save_ranks = {}
    for day in days[-5:]:
        save_ranks[day] = ranks[day]
    Robj().set('dl_gn_ranks', json.dumps(ranks))
    return True


def stock_order_save(code, order):
    """
    记录股票交易订单信息
    {
        "code": "HK.02382",
        "name": "\u821c\u5b87\u5149\u5b66\u79d1\u6280",
        "datetime": "2021-10-19 10:09:51",
        "type": "buy",
        "price": 205.8,
        "amount": 300.0,
        "info": ""
    }
    :param code:
    :param order:
    :return:
    """
    orders = Robj().hget('stock_orders', code)
    orders = {} if orders is None else json.loads(orders)
    key = order['datetime']
    orders[key] = order
    Robj().hset('stock_orders', code, json.dumps(orders))
    return True


def stock_order_query(code):
    """
    股票订单查询
    :param code:
    :return:
    """
    orders = Robj().hget('stock_orders', code)
    orders = {} if orders is None else json.loads(orders)
    orders = orders.values()
    return orders


def task_config_query(task_name, return_obj=True):
    """
    任务配置读取
    """
    task_config: str = Robj().get(f'task_{task_name}')
    task_config: dict = {} if task_config is None else json.loads(task_config)
    if return_obj is False:
        return task_config

    # 检查并设置默认值
    keys = ['is_run', 'is_send_msg', 'no_bi', 'no_xd', 'fx_baohan']
    for key in keys:
        if key in task_config and task_config[key] == '' or key not in task_config.keys():
            task_config[key] = False
        else:
            task_config[key] = bool(int(task_config[key]))
    # 默认的整形参数
    default_int_keys = {
        'interval_minutes': 5,
        'idx_macd_fast': 12,
        'idx_macd_slow': 26,
        'idx_macd_signal': 9
    }
    for _k, _v in default_int_keys.items():
        task_config[_k] = int(task_config[_k]) if _k in task_config else _v
    if 'zixuan' not in task_config.keys():
        task_config['zixuan'] = None

    default_cl_keys = {
        # 分型默认配置
        'fx_qj': Config.FX_QJ_K.value,
        'fx_bh': Config.FX_BH_DINGDI.value,
        # 笔默认配置
        'bi_type': Config.BI_TYPE_NEW.value,
        'bi_qj': Config.BI_QJ_CK.value,
        'bi_bzh': Config.BI_BZH_YES.value,
        'bi_fx_cgd': Config.BI_FX_CHD_NO,
        # 线段默认配置
        'xd_bzh': Config.XD_BZH_YES.value,
        'xd_qj': Config.XD_QJ_DD.value,
        # 'xd_split': Config.XD_SPLIT_YES,
        # 走势段默认配置
        'zsd_bzh': Config.ZSD_BZH_YES.value,
        'zsd_qj': Config.ZSD_QJ_DD.value,
        # 中枢默认配置
        'zs_bi_type': Config.ZS_TYPE_DN.value,  # 笔中枢类型
        'zs_xd_type': Config.ZS_TYPE_DN.value,  # 走势中枢类型
        'zs_qj': Config.ZS_QJ_DD.value,
        'zs_wzgx': Config.ZS_WZGX_ZGD.value,
    }
    for _k in default_int_keys:
        if _k not in task_config.keys():
            task_config[_k] = default_cl_keys[_k]

    arr_keys = ['frequencys', 'check_beichi', 'check_mmd', 'check_beichi_xd', 'check_mmd_xd']
    for ak in arr_keys:
        task_config[ak] = task_config[ak].split(',') if ak in task_config else []
    return task_config


def task_config_save(task_name, task_config: dict):
    """
    任务配置的保存
    """
    task_config = json.dumps(task_config, ensure_ascii=False)
    return Robj().set(f'task_{task_name}', task_config)
