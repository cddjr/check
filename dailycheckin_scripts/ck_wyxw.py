# -*- coding: utf-8 -*-
"""
cron: 0 8 * * *
new Env('网易新闻');
"""
from utils import check
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests


class WYXW:
    name = "网易新闻"

    def __init__(self, check_item):
        self.check_item = check_item
        self.session = requests.Session()
        adapter = HTTPAdapter()
        adapter.max_retries = Retry(connect=3, read=3)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def sign(self):
        headers = {
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "NewsApp/88.4 iOS/15.4.1 (iPhone14,3)",
            "User-U": self.user_u
        }
        response = self.session.post(url="https://c.m.163.com/uc/api/sign/v3/commit",
                                     headers=headers, data=self.data, verify=False).json()
        try:
            if response["code"] == 200:
                data = response["data"]
                serialDays = data["serialDays"]
                awardGoldCoin = data["awardGoldCoin"]
                awardScore = data["awardScore"]
                subtitle = data["subtitle"]  # 再签47天得「持之以恒」3级勋章
                msg = f"签到成功, {subtitle}\n奖励金币{awardGoldCoin}，奖励积分{awardScore}\n已连续签到{serialDays}天"
            else:  # 700 重复签到
                msg = response["msg"]
        except Exception as e:
            print(f"签到失败: {e}")
            msg = f"签到失败，请检查接口\n{e}"
        return msg

    def main(self):
        try:
            name = self.check_item.get("name")
            self.user_u = self.check_item.get("user_u")
            self.data = self.check_item.get("data")
            sign_msg = self.sign()
        except Exception as e:
            print(f"获取账号信息失败: {e}")
            sign_msg = f"发生错误\n{e}"
        msg = [
            {"name": "帐号信息", "value": name},
            {"name": "签到信息", "value": sign_msg},
        ]
        msg = "\n".join(
            [f"{one.get('name')}: {one.get('value')}" for one in msg])
        return msg


@check(run_script_name="网易新闻", run_script_expression="WYXW")
def main(*args, **kwargs):
    return WYXW(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
