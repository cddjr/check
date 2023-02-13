# -*- coding: utf-8 -*-
"""
cron: 0 8 * * *
new Env('网易新闻');
"""
import asyncio
from dataclasses import dataclass
from traceback import format_exc

import json_codec
from aiohttp_retry import JitterRetry, RetryClient

from utils import check, log


@dataclass
class SignResult:
    awardGoldCoin: int  # 10
    awardScore: int  # 5
    serialDays: int  # 142
    subtitle: str  # "签满168天得重磅好礼"


class WYXW:
    __slots__ = ("check_item",
                 "user_u",
                 "data",
                 )

    def __init__(self, check_item):
        self.check_item = check_item

    async def sign(self):
        msg = []
        headers = {
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",  # 因为data传入的是字符串，必须由调用者指定类型
            "User-Agent": "NewsApp/88.4 iOS/15.4.1 (iPhone14,3)",
            "User-U": self.user_u
        }
        try:
            async with RetryClient(raise_for_status=True,  retry_options=JitterRetry(attempts=3)) as session:
                async with session.post(url="https://c.m.163.com/uc/api/sign/v3/commit",
                                        data=self.data, ssl=False,
                                        headers=headers) as response:
                    response = await response.json()
                    if response["code"] == 200 and "data" in response:
                        result = json_codec.decode(await response["data"], SignResult)
                        # 再签47天得「持之以恒」3级勋章
                        log(f'签到成功: {result.subtitle}', msg)
                        log(f'签到奖励: 金币+{result.awardGoldCoin} 积分+{result.awardScore}', msg)
                        log(f'连续签到: {result.serialDays}天', msg)
                    else:
                        log(response["msg"], msg)
                        if response["code"] == 700:
                            # 重复签到
                            exit()  # 目前没必要执行后续的操作
        except Exception:
            log(f'签到失败: 请检查接口 {format_exc()}', msg)
        return msg

    async def main(self):
        msg = []
        try:
            name = self.check_item.get("name")
            self.user_u = self.check_item.get("user_u")
            self.data = self.check_item.get("data")
            if not (self.user_u and self.data):
                raise SystemExit('user_u和data均要配置')
            log(f'帐号信息: {name}', msg)
            msg += await self.sign()
        except Exception:
            log(f'失败: 请检查接口 {format_exc()}', msg)
        finally:
            await asyncio.sleep(0.25)
        msg = "\n".join(msg)
        return msg


@check(run_script_name="网易新闻", run_script_expression="WYXW")
def main(*args, **kwargs):
    return asyncio.run(WYXW(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
