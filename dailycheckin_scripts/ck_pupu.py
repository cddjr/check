# -*- coding: utf-8 -*-
"""
cron: 0 1,20 * * *
new Env('朴朴');
"""
from utils import check
from time import sleep
from urllib3 import disable_warnings
import requests


class PUPU:
    name = "朴朴"

    userAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    # "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 D/8C249B81-0974-4922-B512-53C4045C9851"
    api_host = "https://j1.pupuapi.com"

    url_sign = api_host + "/client/game/sign/v2?city_zip=510100&supplement_id="
    url_period_info = api_host + "/client/game/sign/period_info"

    token = ""  # Bearer 开头

    def __init__(self, check_item):
        self.check_item = check_item

    def __postRequest(self, url: str, jsonText=None):
        """
        发起一个POST请求

        :param jsonText: body体
        :return: 如果成功 返回响应的JSON对象
        """
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Authorization": self.token,
            "User-Agent": self.userAgent,
            # "Referer": "https://ma.pupumall.com/",
            "Content-Length": "0" if jsonText is None else str(len(jsonText)),
            "Connection": "keep-alive",
            "Content-Type": "application/json"
        }
        response: requests.Response = requests.post(
            url=url, headers=headers, data=jsonText, verify=False)
        return response.json()

    def __getRequest(self, url: str):
        """
        发起一个GET请求

        :return: 如果成功 返回响应的JSON对象
        """
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Authorization": self.token,
            "User-Agent": self.userAgent,
            "Connection": "keep-alive"
        }
        response: requests.Response = requests.get(
            url=url, headers=headers, verify=False)
        return response.json()

    def signIn(self):
        """
        签到
        """
        msg = []
        try:
            obj = self.__postRequest(self.url_sign)
            if obj["errcode"] == 0:
                msg += [{"name": "每日签到", "value": f"成功"}]
                print("签到成功")
                data = obj["data"]
                # 积分
                msg += [{"name": "签到奖励",
                         "value": f'积分+{data["daily_sign_coin"]} {data["reward_explanation"]}'}]
            else:  # 350011 重复签到  400000 请求参数不合法
                msg += [{"name": "签到失败",
                         "value": f'code:{obj["errcode"]}, msg:{obj["errmsg"]}'}]
                print(f'签到失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}')
        except Exception as e:
            print(f"签到异常: {e}")
            msg += [{"name": "签到异常", "value": f"请检查接口 {e}"}]
        return msg

    def getPeriod(self):
        """
        获得连续签到的天数
        """
        msg = []
        try:
            obj = self.__getRequest(self.url_period_info)
            if obj["errcode"] == 0:
                data = obj["data"]
                msg += [{"name": "连续签到", "value": f'{data["signed_days"]}天'}]
                print(f'连续签到{data["signed_days"]}天')
            else:  # 350011 重复签到  400000 请求参数不合法
                msg += [{"name": "getPeriod失败",
                         "value": f'code:{obj["errcode"]}, msg:{obj["errmsg"]}'}]
                print(
                    f'getPeriod失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}')
        except Exception as e:
            print(f"getPeriod异常: {e}")
            msg += [{"name": "getPeriod异常", "value": f"请检查接口 {e}"}]
        return msg

    def main(self):
        msg = []
        try:
            self.token = self.check_item.get("token", "")
            if not self.token.startswith('Bearer '):
                raise Exception("token 必须以 Bearer 开头")
            msg += self.signIn()
            msg += self.getPeriod()
        except Exception as e:
            print(f"失败: 请检查接口{e}")
            msg += [{"name": "失败", "value": f"请检查接口 {e}"}]
        msg = "\n".join(
            [f"{one.get('name')}: {one.get('value')}" for one in msg])
        return msg


@check(run_script_name="朴朴", run_script_expression="pupu")
def main(*args, **kwargs):
    return PUPU(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
