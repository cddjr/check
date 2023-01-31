# -*- coding: utf-8 -*-
"""
cron: 0 8,12,17,18,20,22 * * *
new Env('朴朴历史价');

微信登录朴朴app
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token

enabled 是否启用(默认true, 多个账号复用一个数据库)
"""
import asyncio
import sys
from dataclasses import dataclass
from enum import IntEnum
from traceback import format_exc
from typing import Optional, cast  # 确保兼容<=Python3.9

import json_codec

from pupu_api import Client as PClient
from pupu_types import ApiResults, PProduct
from utils import GetScriptConfig, check, log

assert sys.version_info >= (3, 9)

__all__ = [
    "load_database",
    "save_database",
    "RecordPrice",
    "OutputHistoryPrice",

    "PriceRecord",
    "ProductHistory",
    "Days",
]


@dataclass
class PriceRecord:
    create_time: int
    low: int
    high: int


@dataclass
class ProductHistory:
    d3: Optional[PriceRecord] = None
    d7: Optional[PriceRecord] = None
    d15: Optional[PriceRecord] = None
    d30: Optional[PriceRecord] = None

    @property
    def d3_low(self) -> str:
        return f'{self.d3.low/100}元' if self.d3 else "-"

    @property
    def d7_low(self) -> str:
        return f'{self.d7.low/100}元' if self.d7 else "-"

    @property
    def d15_low(self) -> str:
        return f'{self.d15.low/100}元' if self.d15 else "-"

    @property
    def d30_low(self) -> str:
        return f'{self.d30.low/100}元' if self.d30 else "-"

    @property
    def d3_high(self) -> str:
        return f'{self.d3.high/100}元' if self.d3 else "-"

    @property
    def d7_high(self) -> str:
        return f'{self.d7.high/100}元' if self.d7 else "-"

    @property
    def d15_high(self) -> str:
        return f'{self.d15.high/100}元' if self.d15 else "-"

    @property
    def d30_high(self) -> str:
        return f'{self.d30.high/100}元' if self.d30 else "-"


class Days(IntEnum):
    DAY = 24 * 3600 * 1000
    DAYS_3 = 3 * DAY
    DAYS_7 = 7 * DAY
    DAYS_15 = 15 * DAY
    DAYS_30 = 30 * DAY


_database = None
_database_dirty = False
_history = {}


def load_database():
    '''读取数据库'''
    global _database, _history, _database_dirty
    try:
        if _database:
            # 已经读取过数据库
            return True
        _database_dirty = False
        _database = GetScriptConfig("pupu_buy.json")
        _history = json_codec.decode(_database.get_value_2("history") or {} if _database else {},
                                     dict[str, ProductHistory])
        return True
    except BaseException:
        return False


def save_database():
    '''保存数据库'''
    global _database, _history, _database_dirty
    if _database and _database_dirty:
        try:
            _database_dirty = False
            _database.set_value("history", json_codec.encode(_history))
        except BaseException:
            return False
    return True


def RecordPrice(p: PProduct) -> bool:
    '''记录商品价格'''
    global _database, _history, _database_dirty
    dirty = False
    now = PClient.TryGetServerTime() or 0
    history_record = _history.get(
        p.store_product_id) or ProductHistory()

    # d30如果距今超过30天则移除
    # d7如果距今超过7天则移动至d15
    STAGES: list = [("d30", Days.DAYS_30, None), ("d15", Days.DAYS_15, "d30"),
                    ("d7", Days.DAYS_7, "d15"), ("d3", Days.DAYS_3, "d7")]

    # 根据历史价格的最后更新日期进行重新归类
    for f, c, t in STAGES:
        record = cast(Optional[PriceRecord],
                      getattr(history_record, f, None))
        if record is None:
            continue
        if now - record.create_time < c:
            continue
        if t:
            setattr(history_record, t, record)
        setattr(history_record, f, None)
        dirty = True

    record = history_record.d3 or PriceRecord(now,
                                              low=p.price, high=p.price)
    if p.price < record.low:
        record.low = p.price
        dirty = True
    elif p.price > record.high:
        record.high = p.price
        dirty = True
    elif history_record.d3 is None:
        history_record.d3 = record
        dirty = True

    _history[p.store_product_id] = history_record
    if dirty:
        _database_dirty = dirty
    return dirty


def OutputHistoryPrice(p: PProduct) -> list[str]:
    '''
    输出商品的历史价格详情

    ---
    有机番茄:
        历史低价: 7.00, 15.00, 10.00, 1.00
        历史高价: 15.00, 15.00, 16.00, 16.00
    '''
    global _database, _history
    msg: list[str] = []
    history_record = _history.get(p.store_product_id)
    if not history_record:
        # 无记录
        return msg
    log(f"- {p.name}: 当前{p.price/100}元  ", msg)
    log(f"  历史低价: {history_record.d3_low}, {history_record.d7_low}, {history_record.d15_low}, {history_record.d30_low}  ", msg)
    log(f"  历史高价: {history_record.d3_high}, {history_record.d7_high}, {history_record.d15_high}, {history_record.d30_high}  ", msg)
    return msg


async def __RecordCollectionsPrice(check_item):
    '''记录收藏列表中商品的价格'''
    msg: list[str] = []
    try:
        history_cfg = check_item.get("history", {})
        if not bool(history_cfg.get("enabled", True)):
            raise SystemExit("没有启用")
        device_id = check_item.get("device_id", "")
        refresh_token = check_item.get("refresh_token", "")
        if not device_id:
            raise SystemExit("device_id 配置有误")
        if not refresh_token:
            raise SystemExit("refresh_token 配置有误")

        async with PClient(device_id, refresh_token) as api:
            result = await api.InitializeToken(check_item.get("addr_filter"), force_update_receiver=False)
            if isinstance(result, ApiResults.Error):
                log(result, msg)
                raise StopIteration

            load_database()

            PAGE_SIZE = 10
            count = 0
            page = 1  # 从第一页开始拉取
            changed_msg: list[str] = []
            while (True):
                collections = await api.GetProductCollections(page, PAGE_SIZE)
                if isinstance(collections, ApiResults.Error):
                    log(collections, msg)
                    break
                count += len(collections.products)
                for p in collections.products:
                    # 记录价格
                    if RecordPrice(p):
                        changed_msg.extend(OutputHistoryPrice(p))
                if count >= collections.total_count \
                        or collections.total_count < PAGE_SIZE:
                    # 不知朴朴怎么想的 空列表还会下发一个不为零的total_count
                    break
                page += 1

            if changed_msg:
                log("以下商品价格有变化:", msg)
                msg.extend(changed_msg)

    except StopIteration:
        pass
    except Exception:
        log(f'失败: 请检查接口 {format_exc()}', msg)
    finally:
        save_database()
    return "\n".join(msg)


@check(run_script_name="朴朴历史价", run_script_expression="pupu")
def main(*args, **kwargs):
    return asyncio.run(__RecordCollectionsPrice(kwargs.get("value", {})))


if __name__ == "__main__":
    main()
