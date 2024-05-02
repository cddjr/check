# -*- coding: utf-8 -*-
"""
cron: 25 0 * * *
new Env('慢慢买');

签到、补签等逻辑可看这个js
https://apph5.manmanbuy.com/renwu/js/common.js

"""
import asyncio
import urllib.parse
from traceback import format_exc

from utils import check, log
from aiohttp_retry import JitterRetry, RetryClient



class ManManBuy:
    # UA和devid都可以根据情况随机生成
    UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 - mmbWebBrowse - ios"

    API_HOST = 'https://apph5.manmanbuy.com'
    URL_INDEX = API_HOST + '/renwu/index.aspx?m_from=my_daka'
    URL_LOGIN = API_HOST + '/taolijin/login.aspx'
    URL_TASK = API_HOST + '/renwu/index.aspx'

    __slots__ = ("check_item",
                 "session",
                 "u_name",
                 "u_token",
                 "c_devid",
                 "username",
                 )

    def __init__(self, check_item):
        self.check_item = check_item

    async def InitSession(self):
        self.session = RetryClient(raise_for_status=True,
                                   retry_options=JitterRetry(attempts=3))
        self.session._client.headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        self.session._client.headers["Accept-Language"] = "zh-CN,zh-Hans;q=0.9"
        self.session._client.headers["f-refer"] = "wv_h5"
        self.session._client.headers["User-Agent"] = self.UA
        self.session._client.headers["X-Requested-With"] = "XMLHttpRequest"
        self.session._client.headers["Referer"] = self.URL_INDEX
        self.session._client.headers["Connection"] = "keep-alive"

    async def ajax(self, method: str, url: str, data=None, json=None):
        '''发起一个ajax请求'''
        method = method.upper()
        if method not in ("GET", "HEAD"):
            headers = {"Origin": self.API_HOST}
        else:
            headers = None
        async with self.session.request(method=method, url=url, headers=headers,
                                        ssl=False, data=data, json=json) as response:
            return await response.json()

    async def checkin(self):
        '''立即签到'''
        msg = []
        try:
            obj = await self.ajax("post", self.URL_TASK,
                                  data={'action': 'checkin',
                                        'username': self.u_name,
                                        'c_devid': self.c_devid,
                                        'isAjaxInvoke': 'true'})
            if int(obj["code"]) == 1:
                data = obj["data"]
                log(f'签到成功: 奖励积分+{data["jifen"]}', msg)
                log(f'已连续签到: {data["zt"]}天', msg)
            elif int(obj["code"]) == 0 and '签到失败' == obj["msg"]:
                log('重复签到: 忽略', msg)
                exit()  # 目前没必要执行后续的操作
            else:
                log(f'签到失败: code:{obj["code"]}, msg:{obj["msg"]}', msg)
        except Exception:
            log(f'签到异常: {format_exc()}', msg)
        return msg

    async def login(self):
        msg = []
        log(f'账号: {self.username}', msg)
        try:
            obj = await self.ajax("post", self.URL_LOGIN,
                                  data={'action': 'newtokenlogin',
                                        'u_name': self.u_name,
                                        'u_token': self.u_token})
            if int(obj["code"]) == 1:
                log('登录成功')
            else:
                raise Exception(obj)
        finally:
            return msg

    async def main(self):
        msg = []
        try:
            info = urllib.parse.parse_qs(self.check_item.get("login"))
            u_name = info.get('u_name') or info.get('u')
            u_token = info.get('u_token') or info.get('sign')
            if not (u_name and u_token):
                raise SystemExit("login配置有误 必须包含u_name和u_token")
            self.u_name: str = u_name[0]
            self.u_token: str = u_token[0]
            # 设备id可以不同账号随机分配一个guid
            self.c_devid = self.check_item.get("devid") \
                or "43D5701C-AD8F-4503-BCA4-58C1D4EF42C9"
            self.username = self.check_item.get("name") or self.c_devid

            await self.InitSession()

            msg += await self.login()
            msg += await self.checkin()
        except Exception:
            log(f'失败: 请检查接口 {format_exc()}', msg)
        finally:
            await asyncio.gather(self.session.close(),
                                 asyncio.sleep(0.25))
        msg = "\n".join(msg)
        return msg


@check(run_script_name="慢慢买", run_script_expression="manmanbuy")
def main(*args, **kwargs):
    return asyncio.run(ManManBuy(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
