"""
cron: 0 1,20 * * *
new Env('叮咚买菜-签到');


"""
import asyncio
from traceback import format_exc
from typing import Optional

from aiohttp_retry import JitterRetry, RetryClient

from utils import check, log


class DingDong:
    __slots__ = ("check_item",
                 "token",
                 )

    def __init__(self, check_item):
        self.check_item: dict = check_item

    async def main(self):
        msg: list[str] = []
        try:
            self.token = self.check_item.get("token", "")
            if not self.token:
                raise SystemExit("token 配置有误")

            msg += await self.sign()
        except Exception:
            log(f'失败: 请检查接口 {format_exc()}', msg)
        return "\n".join(msg)

    async def sign(self):
        """签到 测试"""
        msg: list[str] = []
        try:
            async with RetryClient(raise_for_status=True, retry_options=JitterRetry(attempts=3)) as client:
                async with client.post(
                    url="https://sunquan.api.ddxq.mobi/api/v2/user/signin/",
                    headers={"Referer": "https://activity.m.ddxq.mobi/",
                             "Cookie": f"DDXQSESSID={self.token}",
                             "Accept-Encoding": "gzip, deflate",
                             "ddmc-api-version": "9.7.3",
                             "ddmc-app-client-id": "3",
                             "ddmc-build-version": "10.3.0",
                             "Connection": "keep-alive",
                             "Accept-Language": "zh-CN,zh-Hans;q=0.9",
                             "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 xzone/10.3.0"},
                    data={"api_version": "9.7.3",
                          "app_version": "1.0.0",
                          "app_client_id": "3",
                          "native_version": "10.3.0"},
                    ssl=False
                ) as req:
                    obj = await req.json()
                    if obj["code"] == 0:
                        data = obj["data"]
                        new_sign_series: Optional[int] = data.get(
                            "new_sign_series")
                        sign_series: Optional[int] = data.get("sign_series")
                        point: Optional[int] = data.get("point")
                        log(f'签到成功: 奖励积分+{point}', msg)
                        log(f'连续签到: {sign_series or 0}({new_sign_series or 0})天', msg)
                    else:
                        log(f'签到失败: code={obj["code"]}, msg={obj["msg"]}')
        except Exception:
            log(f'签到异常: {format_exc()}', msg)
        return msg


@check(run_script_name="叮咚买菜-签到", run_script_expression="dingdong")
def main(*args, **kwargs):
    return asyncio.run(DingDong(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
