import hashlib

from chanlun import cl
from chanlun.cl_interface import *

# 缓存计算好的缠论数据，第二次则不用重新计算了，减少计算消耗的时间
_global_cache_day = datetime.datetime.now().strftime('%Y%m%d')
_global_caches: Dict[str, ICL] = {}


def batch_cls(code, klines: Dict[str, pd.DataFrame], config: dict = None) -> List[ICL]:
    """
    批量计算并获取 缠论 数据
    :param code: 计算的标的
    :param klines: 计算的 k线 数据，每个周期对应一个 k线DataFrame，例如 ：{'30m': klines_30m, '5m': klines_5m}
    :param config: 缠论配置
    :return: 返回计算好的缠论数据对象，List 列表格式，按照传入的 klines.keys 顺序返回 如上调用：[0] 返回 30m 周期数据 [1] 返回 5m 数据
    """
    global _global_cache_day, _global_caches
    # 只记录当天的缓存，第二天缓存清空
    if _global_cache_day != datetime.datetime.now().strftime('%Y%m%d'):
        _global_cache_day = datetime.datetime.now().strftime('%Y%m%d')
        _global_caches = {}

    cls = []
    for f, k in klines.items():
        key = hashlib.md5(f'{code}_{f}_{config}'.encode('UTF-8')).hexdigest()
        if key in _global_caches.keys():
            # print('使用缓存')
            cls.append(_global_caches[key].process_klines(k))
        else:
            # print('重新计算')
            _global_caches[key] = cl.CL(code, f, config)
            cls.append(_global_caches[key].process_klines(k))
    return cls


def cal_line_macd_infos(line: LINE, cd: ICL) -> MACD_INFOS:
    """
    计算线中macd信息
    """
    infos = MACD_INFOS()

    idx = cd.get_idx()
    dea = np.array(idx['macd']['dea'][line.start.k.k_index:line.end.k.k_index + 1])
    dif = np.array(idx['macd']['dif'][line.start.k.k_index:line.end.k.k_index + 1])
    if len(dea) < 2 or len(dif) < 2:
        return infos
    zero = np.zeros(len(dea))

    infos.dif_up_cross_num = len(up_cross(dif, zero))
    infos.dif_down_cross_num = len(down_cross(dif, zero))
    infos.dea_up_cross_num = len(up_cross(dea, zero))
    infos.dea_down_cross_num = len(down_cross(dea, zero))
    infos.gold_cross_num = len(up_cross(dif, dea))
    infos.die_cross_num = len(down_cross(dif, dea))
    infos.last_dif = dif[-1]
    infos.last_dea = dea[-1]
    return infos


def cal_zs_macd_infos(zs: ZS, cd: ICL) -> MACD_INFOS:
    """
    计算中枢的macd信息
    """
    infos = MACD_INFOS()
    dea = np.array(cd.get_idx()['macd']['dea'][zs.start.k.k_index:zs.end.k.k_index + 1])
    dif = np.array(cd.get_idx()['macd']['dif'][zs.start.k.k_index:zs.end.k.k_index + 1])
    if len(dea) < 2 or len(dif) < 2:
        return infos
    zero = np.zeros(len(dea))

    infos.dif_up_cross_num = len(up_cross(dif, zero))
    infos.dif_down_cross_num = len(down_cross(dif, zero))
    infos.dea_up_cross_num = len(up_cross(dea, zero))
    infos.dea_down_cross_num = len(down_cross(dea, zero))
    infos.gold_cross_num = len(up_cross(dif, dea))
    infos.die_cross_num = len(down_cross(dif, dea))
    infos.last_dif = dif[-1]
    infos.last_dea = dea[-1]
    return infos


def up_cross(one_list: np.array, two_list: np.array):
    """
    获取上穿信号列表
    """
    assert len(one_list) == len(two_list), '信号输入维度不相等'
    if len(one_list) < 2:
        return []
    cross = []
    for i in range(1, len(two_list)):
        if one_list[i - 1] < two_list[i - 1] and one_list[i] > two_list[i]:
            cross.append(i)
    return cross


def down_cross(one_list: np.array, two_list: np.array):
    """
    获取下穿信号列表
    """
    assert len(one_list) == len(two_list), '信号输入维度不相等'
    if len(one_list) < 2:
        return []
    cross = []
    for i in range(1, len(two_list)):
        if one_list[i - 1] > two_list[i - 1] and one_list[i] < two_list[i]:
            cross.append(i)
    return cross
