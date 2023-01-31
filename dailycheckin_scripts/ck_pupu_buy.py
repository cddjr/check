# -*- coding: utf-8 -*-
"""
cron: 56 59 17,21 * * *
new Env('朴朴抢购');

微信登录朴朴app
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token

goods 检测商品收藏列表中的哪些商品 数组对象
    keyword 商品名关键字 用于匹配收藏列表中的商品
    price 预期价位 当商品降价到预期价位以内将执行后续操作
    quantity 抢购数量(可选)
buy 如果降价是否抢购 默认False只发送降价通知
addr_filter 限定用哪个收货地址(可选) 默认用最近下单地址
push_key 降价时用的ServerJ推送key(可选)
"""
import asyncio
import sys
from traceback import format_exc
from typing import Optional  # 确保兼容<=Python3.9

import ck_pupu_history
from aiohttp import ClientSession, ClientTimeout

from pupu_api import Client as PClient
from pupu_types import *
from utils import check, log

assert sys.version_info >= (3, 9)


@dataclass
class Goods:
    keyword: str
    price: int
    quantity: int


class PUPU:

    __slots__ = ("check_item",
                 "device_id",
                 "refresh_token",
                 "_goods",
                 "_buy",
                 "_push_key",
                 )

    def __init__(self, check_item) -> None:
        self.check_item: dict = check_item

    async def main(self):
        msg: list[str] = []
        try:
            self._buy = bool(self.check_item.get("buy", False))
            self._push_key: Optional[str] = self.check_item.get("push_key")
            self.device_id = self.check_item.get("device_id", "")
            self.refresh_token = self.check_item.get("refresh_token", "")
            if not self.device_id:
                raise SystemExit("device_id 配置有误")
            if not self.refresh_token:
                raise SystemExit("refresh_token 配置有误")

            self._goods = self.ParseGoods()
            if len(self._goods) > 0:
                log(f'配置了{len(self._goods)}件商品的价格检测', msg)
            else:
                raise SystemExit("没有配置需要检测的商品 跳过")

            ck_pupu_history.load_database()

            msg += await self.Entry()
        except Exception:
            log(f'失败: 请检查接口 {format_exc()}', msg)
        finally:
            ck_pupu_history.save_database()

        return "\n".join(msg)

    async def DetectProducts(self, api: PClient):
        """检测商品是否降价"""
        # TODO 多页
        collections = await api.GetProductCollections(page=1)
        log(f'  当前服务器时间: {PClient.TryGetServerTime() or 0}')
        if isinstance(collections, ApiResults.Error):
            return collections
        msg: list[str] = []
        price_reduction = 0
        order_items: list[PProduct] = []
        for p in collections.products:
            # 记录价格
            ck_pupu_history.RecordPrice(p)
            for goods in self._goods:
                if p.name.find(goods.keyword) == -1:
                    # 排除不关心价格的
                    continue
                if p.stock_quantity <= 0:
                    # 排除没货的
                    log(f'  缺货: {p.name}')
                    continue
                if p.sell_batches:
                    # TODO 以该数组的最低价作为当前价格
                    pass
                if p.price > goods.price:
                    # 排除价格高于预期的
                    # log(f'  价格高于预期: {p.name} {p.price/100}元 > {goods.price/100}元')
                    continue
                log(f'价格低于预期: {p.name} {p.price/100}元', msg)
                price_reduction += 1
                if not self._buy or goods.quantity <= 0:
                    continue
                # p = copy.deepcopy(p)
                # 计算采购量
                p.selected_count = min(goods.quantity,
                                       p.stock_quantity,
                                       p.quantity_limit or p.stock_quantity)
                # [杀(清洗), 杀(不清洗), 不杀]
                p.remark = p.order_remarks[0] if p.order_remarks else ""
                order_items.append(p)
        return (msg, collections, price_reduction, order_items)

    async def Entry(self):
        msg: list[str] = []
        async with PClient(self.device_id, self.refresh_token) as api:
            result = await api.InitializeToken(self.check_item.get("addr_filter"))
            if isinstance(result, ApiResults.Error):
                log(result, msg)
                return msg
            results = await self.DetectProducts(api)
            if isinstance(results, ApiResults.Error):
                log(results, msg)
                return msg
            sub_msg, collections, price_reduction, order_items = results
            msg += sub_msg
            log(f'总共收藏了{collections.total_count}件商品')
            if price_reduction <= 0:
                # 第1次检测没有降价 等待片刻
                await asyncio.sleep(0.5)
                # 开始第2次检测 总共3次
                retry = 2
                while (retry <= 3):
                    log(f'第{retry}次尝试...')
                    _, results = await asyncio.gather(
                        asyncio.sleep(0.5),
                        self.DetectProducts(api))
                    if isinstance(results, ApiResults.Error):
                        log(results, msg)
                        break
                    sub_msg, collections, price_reduction, order_items = results
                    msg += sub_msg
                    if price_reduction > 0:
                        # 存在降价商品 不再尝试检测
                        break
                    retry += 1
            if order_items:
                # 并行获得加购商品可用的优惠券和派送时间
                coupons_result, dtime_result, now = await asyncio.gather(
                    api.GetUsableCoupons(DiscountType.ALL, order_items),
                    api.GetDeliveryTime(order_items, 10),
                    api.GetServerTime()
                )
                if isinstance(coupons_result, ApiResults.Error):
                    log(coupons_result, msg)
                    coupons = None
                else:
                    log(f'可用{len(coupons_result.coupons)}张优惠券')
                    coupons = coupons_result
                if isinstance(dtime_result, ApiResults.Error):
                    log(dtime_result, msg)
                    dtime = None
                else:
                    dtime = dtime_result
                order_result = await api.CreateOrder(
                    pay_type=15,  # 云闪付
                    coupons=coupons.coupons if coupons else None,
                    products=order_items,
                    dtime_type=dtime.type if dtime else DeliveryTimeType.IMMEDIATE,
                    dtime_promise=dtime.dtime_promise if dtime else now + 1800_000)
                if isinstance(order_result, ApiResults.Error):
                    log(order_result, msg)
                else:
                    log(f'订单创建成功 {order_result.id}', msg)
                    log(f'当前服务器时间: {PClient.TryGetServerTime() or 0}')
                    msg += await self.ServerJ("朴朴降价了", f"{order_result.id}")
            elif price_reduction <= 0:
                log('无降价', msg)
            else:
                log('有降价 快去下单吧~', msg)
            log(f'当前服务器时间: {PClient.TryGetServerTime() or 0}')
        return msg

    def ParseGoods(self):
        """解析商品配置"""
        goods_list: list[Goods] = []
        for goods in self.check_item.get("goods", []):
            if not isinstance(goods, dict):
                continue
            keyword = goods.get("keyword")
            if not isinstance(keyword, str):
                continue
            price = goods.get("price")
            if not isinstance(price, (int, float)):
                continue
            goods_list.append(Goods(
                keyword,
                price=int(price*100),  # 转换为分
                quantity=int(goods.get("quantity", 0))
            ))
        return goods_list

    async def ServerJ(self, title: str, content: str):
        """通过 ServerJ 推送消息"""
        if not self._push_key:
            return []
        msg: list[str] = []
        log("serverJ 服务启动")

        data = {"text": title, "desp": content.replace("\n", "\n\n")}
        if self._push_key.index("SCT") != -1:
            url = f'https://sctapi.ftqq.com/{self._push_key}.send'
        else:
            url = f'https://sc.ftqq.com/${self._push_key}.send'

        async with ClientSession(raise_for_status=True,
                                 timeout=ClientTimeout(total=15)) as session:
            async with session.post(url, data=data, ssl=False) as req:
                datas = await req.json()
                if datas.get("errno") == 0 or datas.get("code") == 0:
                    log("serverJ 推送成功!", msg)
                elif datas.get("code") == 40001:
                    log("serverJ 推送失败! PUSH_KEY 错误。", msg)
                else:
                    log(f'serverJ 推送失败! 错误码：{datas.get("message")}', msg)
        return msg


@check(run_script_name="朴朴抢购", run_script_expression="pupu", interval_max=0)
def main(*args, **kwargs):
    return asyncio.run(PUPU(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
