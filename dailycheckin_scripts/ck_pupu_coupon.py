# -*- coding: utf-8 -*-
"""
cron: 0 7,9,13,15,19 * * *
new Env('朴朴领券');

微信登录朴朴app
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token

coupon_center.enabled 是否启用领券(默认true)
"""
import asyncio
import sys
from traceback import format_exc

from pupu_api import Client as PClient
from pupu_types import *
from utils import aio_randomSleep, check, log

import json_codec

assert sys.version_info >= (3, 9)


@dataclass
class PCouponCenterItem:
    discount_id: str
    discount_group_id: str
    condition_amount: int
    discount_amount: int
    is_finished: bool = True
    received: int = 0
    received_limit: int = 0

    @property
    def is_received(self):
        """是否已领取"""
        return self.received > 0

    @property
    def can_received(self):
        """是否可以领取"""
        return not self.is_finished and self.received < self.received_limit


class PUPU:

    __slots__ = (
        "check_item",
        "device_id",
        "refresh_token",
    )

    def __init__(self, check_item) -> None:
        self.check_item: dict = check_item

    async def main(self):
        msg: list[str] = []
        try:
            self.device_id = self.check_item.get("device_id", "")
            self.refresh_token = self.check_item.get("refresh_token", "")
            if not self.device_id:
                raise SystemExit("device_id 配置有误")
            if not self.refresh_token:
                raise SystemExit("refresh_token 配置有误")

            coupon_center = self.check_item.get("coupon_center", {})
            if not coupon_center.get("enabled", True):
                raise SystemExit("没有启用")

            msg += await self.CollectCoupons()
        except Exception:
            log(f"失败: 请检查接口 {format_exc()}", msg)
        return "\n".join(msg)

    async def _ReceiveCoupon(self, api: PClient, coupon: PCouponCenterItem):
        try:
            obj = await api._SendRequest(
                HttpMethod.kPost,
                "https://j1.pupuapi.com/client/coupon/entity",
                ClientType.kWeb,
                json={
                    "discount": coupon.discount_id,
                    "discount_group": coupon.discount_group_id,
                    "place_id": api.receiver.place_id,
                    "store_id": api.receiver.store_id,
                    "time_type": 1,
                },
            )
            if obj["errcode"] == 0:
                # 领取成功
                return
            else:
                return ApiResults.Error(obj)
        except:
            return ApiResults.Exception()

    async def CollectCoupons(self):
        msg: list[str] = []
        try:
            async with PClient(self.device_id, self.refresh_token) as api:
                result = await api.InitializeToken(
                    self.check_item.get("addr_filter"), force_update_receiver=False
                )
                if isinstance(result, ApiResults.Error):
                    if api.nickname:
                        log(f"账号: {api.nickname}", msg)
                    log(result, msg)
                    return msg

                log(f"账号: {api.nickname}", msg)

                obj = await api._SendRequest(
                    HttpMethod.kGet,
                    "https://j1.pupuapi.com/client/coupon",
                    ClientType.kWeb,
                    params={"store_id": api.receiver.store_id, "type": 1},
                )
                if obj["errcode"] == 0:
                    data = obj["data"]
                    items = json_codec.decode(
                        data.get("items") or [], list[PCouponCenterItem]
                    )
                    if not any(item.can_received for item in items):
                        log("没有优惠券，领取失败", msg)
                        exit()  # 目前没必要执行后续的操作
                        return msg
                    for coupon in items:
                        result, _ = await asyncio.gather(
                            self._ReceiveCoupon(api, coupon), aio_randomSleep()
                        )
                        if isinstance(result, ApiResults.Error):
                            log(result, msg)
                        else:
                            log(
                                f"成功领取: 满{coupon.condition_amount/100}减{coupon.discount_amount/100}元",
                                msg,
                            )
                else:
                    log(ApiResults.Error(obj), msg)
        except Exception:
            log(ApiResults.Exception(), msg)
        finally:
            return msg


@check(run_script_name="朴朴领券", run_script_expression="pupu")
def main(*args, **kwargs):
    return asyncio.run(PUPU(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
