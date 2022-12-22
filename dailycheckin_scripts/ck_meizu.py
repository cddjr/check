# -*- coding: utf-8 -*-
"""
new Env('MEIZU社区');
"""
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests

from utils import check, randomSleep


class Meizu:
    name = "MEIZU社区"

    def __init__(self, check_item):
        self.check_item = check_item
        self.session = requests.Session()
        self.session.verify = False
        adapter = HTTPAdapter()
        adapter.max_retries = Retry(connect=3, read=3, allowed_methods=False)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def user(self, cookie):
        headers = {
            "pragma": "no-cache",
            "cache-control": "no-cache",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36 Edg/88.0.705.74",
            "origin": "https://www.meizu.cn",
            "referer": "https://www.meizu.cn/",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cookie": cookie,
        }
        response = self.session.get(
            url="https://myplus-api.meizu.cn/myplus-muc/u/user/v2", headers=headers).json()
        data = response.get("data", {})
        return data.get("nickname", "-"), data.get("mucUserId", "-")

    def sign(self, cookie):
        headers = {
            "pragma": "no-cache",
            "cache-control": "no-cache",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36 Edg/88.0.705.74",
            "origin": "https://www.meizu.cn",
            "referer": "https://www.meizu.cn/",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cookie": cookie,
        }
        response = self.session.post(
            url="https://myplus-api.meizu.cn/myplus-muc/u/user/signin", headers=headers).json()
        # {"code":1012000000,"msg":"今日已签到","timestamp":1671698782431,"data":null}
        msg = response.get("msg")
        return msg

    def main(self):
        meizu_cookie = self.check_item.get("cookie")
        try:
            draw_count = int(self.check_item.get("draw_count", 0))
        except Exception as e:
            print("初始化抽奖次数失败: 重置为 0 ", str(e))
            draw_count = 0
        sign_msg = self.sign(cookie=meizu_cookie)
        nick, uid = self.user(cookie=meizu_cookie)
        # draw_msg, uid = self.draw(cookie=meizu_cookie, count=draw_count)
        msg = [
            {"name": "帐号ID", "value": uid},
            {"name": "帐号昵称", "value": nick},
            {"name": "签到信息", "value": sign_msg},
        ]  # + draw_msg
        msg = "\n".join(
            [f"{one.get('name')}: {one.get('value')}" for one in msg])
        return msg


@check(run_script_name="MEIZU社区", run_script_expression="meizu")
def main(*args, **kwargs):
    return Meizu(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
