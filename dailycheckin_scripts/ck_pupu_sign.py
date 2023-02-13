# -*- coding: utf-8 -*-
"""
cron: 0 1,20 * * *
new Env('朴朴签到');

微信登录朴朴app
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token
"""
import asyncio
import sys
from traceback import format_exc

from pupu_api import Client as PClient
from pupu_types import *
from utils import check, log

assert sys.version_info >= (3, 9)


class PUPU:

    __slots__ = ("check_item",
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

            msg += await self.sign()
        except Exception:
            log(f'失败: 请检查接口 {format_exc()}', msg)
        return "\n".join(msg)

    async def sign(self):
        msg: list[str] = []
        async with PClient(self.device_id, self.refresh_token) as api:
            result = await api.InitializeToken(self.check_item.get("addr_filter"),
                                               force_update_receiver=False)
            if isinstance(result, ApiResults.Error):
                if api.nickname:
                    log(f'账号: {api.nickname}', msg)
                log(result, msg)
                return msg
            elif isinstance(result, ApiResults.TokenRefreshed):
                if result.changed:
                    log(f"refresh_token 已更新为: {result.refresh_token}")
                else:
                    log(f"令牌已更新为: {api.access_token}")

            log(f'账号: {api.nickname}', msg)

            # 开始签到
            result = await api.SignIn()
            if isinstance(result, ApiResults.Error):
                if result.code == ERROR_CODE.kRepeatedSignIn:
                    log("重复签到: 忽略", msg)
                else:
                    log(result, msg)
            else:
                log(f'签到成功: 奖励积分+{result.coin} {result.explanation}', msg)

            result = await api.GetSignPeriodInfo()
            if isinstance(result, ApiResults.Error):
                log(result, msg)
            else:
                log(f'签到信息: 本周连续签到{result.days}天', msg)
        return msg


@check(run_script_name="朴朴签到", run_script_expression="pupu")
def main(*args, **kwargs):
    return asyncio.run(PUPU(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
