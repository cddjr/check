# -*- coding: utf-8 -*-
"""
cron: 0 8 * * *
new Env('网易新闻');
"""
from utils import check, log
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests


class WYXW:
    def __init__(self, check_item):
        self.check_item = check_item
        self.session = requests.Session()
        self.session.verify = False
        adapter = HTTPAdapter()
        adapter.max_retries = Retry(connect=3, read=3, allowed_methods=False)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def sign(self):
        msg = []
        headers = {
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",  # 因为data传入的是字符串，必须由调用者指定类型
            "User-Agent": "NewsApp/88.4 iOS/15.4.1 (iPhone14,3)",
            "User-U": self.user_u
        }
        response = self.session.post(url="https://c.m.163.com/uc/api/sign/v3/commit",
                                     headers=headers, data=self.data).json()
        try:
            if response["code"] == 200:
                data = response["data"]
                serialDays = data["serialDays"]
                awardGoldCoin = data["awardGoldCoin"]
                awardScore = data["awardScore"]
                subtitle = data["subtitle"]  # 再签47天得「持之以恒」3级勋章
                log(f'签到成功: {subtitle}', msg)
                log(f'签到奖励: 金币+{awardGoldCoin} 积分+{awardScore}', msg)
                log(f'连续签到: {serialDays}天', msg)
            else:  # 700 重复签到
                log(response["msg"], msg)
        except Exception as e:
            log(f'签到失败，请检查接口 {e}', msg)
        return msg

    def main(self):
        msg = []
        try:
            name = self.check_item.get("name")
            self.user_u = self.check_item.get("user_u")
            self.data = self.check_item.get("data")
            if not (self.user_u and self.data):
                raise SystemExit('user_u和data均要配置')
            log(f'帐号信息: {name}', msg)
            msg += self.sign()
        except Exception as e:
            log(f'失败: 请检查接口 {e}', msg)
        msg = "\n".join(msg)
        return msg


@check(run_script_name="网易新闻", run_script_expression="WYXW")
def main(*args, **kwargs):
    return WYXW(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
