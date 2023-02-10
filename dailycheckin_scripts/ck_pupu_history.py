# -*- coding: utf-8 -*-
"""
cron: 33 7-23/4 * * *
new Env('朴朴历史价');

微信登录朴朴app
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token

enabled 是否启用(默认true, 多个账号复用一个数据库)
"""
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime
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
    # 价格波动发生在何时
    update_time: Optional[int] = None


@dataclass
class ProductHistory:
    viewed: bool = False
    name: Optional[str] = None
    d3: Optional[PriceRecord] = None
    d6: Optional[PriceRecord] = None
    d9: Optional[PriceRecord] = None
    d12: Optional[PriceRecord] = None

    @property
    def d3_low(self) -> str:
        return f'{self.d3.low/100}元' if self.d3 else "-"

    @property
    def d6_low(self) -> str:
        return f'{self.d6.low/100}元' if self.d6 else "-"

    @property
    def d9_low(self) -> str:
        return f'{self.d9.low/100}元' if self.d9 else "-"

    @property
    def d12_low(self) -> str:
        return f'{self.d12.low/100}元' if self.d12 else "-"

    @property
    def d3_high(self) -> str:
        return f'{self.d3.high/100}元' if self.d3 else "-"

    @property
    def d6_high(self) -> str:
        return f'{self.d6.high/100}元' if self.d6 else "-"

    @property
    def d9_high(self) -> str:
        return f'{self.d9.high/100}元' if self.d9 else "-"

    @property
    def d12_high(self) -> str:
        return f'{self.d12.high/100}元' if self.d12 else "-"


class Days(IntEnum):
    DAY = 24 * 3600 * 1000
    DAYS_3 = 3 * DAY
    DAYS_6 = DAYS_3 + DAYS_3
    DAYS_9 = DAYS_6 + DAYS_3
    DAYS_12 = DAYS_9 + DAYS_3


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
    # TODO 改用sqlite3详细记录
    global _database, _history, _database_dirty
    dirty = False
    now = PClient.TryGetServerTime() or 0
    history_record = _history.get(
        p.store_product_id) or ProductHistory()

    if history_record.name is None or history_record.name != p.name:
        # 230208: 商品名称也需要记录 方便调试
        history_record.name = p.name
        dirty = True

    STAGES: list = [("d12", Days.DAYS_12, None), ("d9", Days.DAYS_9, "d12"),
                    ("d6", Days.DAYS_6, "d9"), ("d3", Days.DAYS_3, "d6")]

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

    record = history_record.d3 or PriceRecord(create_time=now,
                                              low=p.price, high=p.price)
    if p.price < record.low:
        record.low = p.price
        record.update_time = now
        dirty = True
    elif p.price > record.high:
        record.high = p.price
        record.update_time = now
        dirty = True
    elif history_record.d3 is None:
        history_record.d3 = record
        dirty = True

    _history[p.store_product_id] = history_record
    if dirty:
        history_record.viewed = False
        _database_dirty = dirty
    return not history_record.viewed


def OutputHistoryPrice(p: PProduct) -> list[str]:
    '''
    输出商品的历史价格详情

    ---
    有机番茄:
        历史低价: 7.00, 15.00, 10.00, 1.00
        历史高价: 15.00, 15.00, 16.00, 16.00
    '''
    global _database, _history, _database_dirty
    msg: list[str] = []
    history_record = cast(Optional[ProductHistory],
                          _history.get(p.store_product_id))
    if not history_record:
        # 无记录
        return msg
    log(f"- {p.name}: 当前{p.price/100}元  ", msg)
    log(f"  历史低价: {history_record.d3_low}, {history_record.d6_low}, {history_record.d9_low}, {history_record.d12_low}  ", msg)
    log(f"  历史高价: {history_record.d3_high}, {history_record.d6_high}, {history_record.d9_high}, {history_record.d12_high}  ", msg)
    if time := history_record.d3.update_time if history_record.d3 else None:
        d = datetime.fromtimestamp(time / 1000).strftime("%Y-%m-%d %H:%M:%S")
        log(f"  变动时间: {d}", msg)
    if not history_record.viewed:
        history_record.viewed = True
        _database_dirty = True
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
                if api.nickname:
                    log(f'账号: {api.nickname}', msg)
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
                log(f'账号: {api.nickname}', msg)
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
