# -*- coding: utf-8 -*-
"""
cron: 0 1,20 * * *
new Env('朴朴');
"""
from utils import check
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests


class PUPU:
    name = "朴朴"

    userAgent = "Pupumall/3.0.8;iOS 15.4.1"
    api_host = "https://j1.pupuapi.com"

    url_sign = api_host + "/client/game/sign/v2?city_zip=510100&supplement_id="
    url_period_info = api_host + "/client/game/sign/period_info"

    url_get_token = 'https://cauth.pupuapi.com/clientauth/user/refresh_token'

    def __init__(self, check_item):
        self.check_item = check_item
        self.session = requests.Session()
        adapter = HTTPAdapter()
        adapter.max_retries = Retry(connect=3, read=3)
        self.session.mount('http', adapter)
        self.access_token = None

    def __sendRequest(self, method: str, url: str, jsonText=None):
        """
        发起一个POST/GET/PUT请求

        :param jsonText: body体
        :return: 如果成功 返回响应的JSON对象
        """
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "User-Agent": self.userAgent,
            # "Referer": "https://ma.pupumall.com/",
            "Content-Length": str(len(jsonText)) if jsonText is not None else "0",
            "Connection": "keep-alive",
            "Content-Type": "application/json"
        }
        method = method.upper()
        if self.access_token is not None:
            headers["Authorization"] = f'Bearer {self.access_token}'
        if method == 'POST' or method == 'PUT':
            if jsonText is not None:
                headers["Content-Length"] = str(len(jsonText))
                headers["Content-Type"] = "application/json"
            else:
                headers["Content-Length"] = "0"
        response: requests.Response = self.session.request(method,
                                                           url=url, headers=headers, data=jsonText, verify=False)
        return response.json()

    def refreshAccessToken(self):
        """
        获得AccessToken

        有效期通常只有2小时
        """

        """
        正常返回响应体
        {
            "errcode": 0,
            "errmsg": "",
            "data": {
                "access_token": "xxx",
                "refresh_token": "xxx",
                "expires_in": 1660803941123,
                "is_bind_phone": true,
                "user_id": "xx-xx-xx",
                "nick_name": "张三",
                "is_new_user": false
            }
        }
        """
        msg = []
        try:
            self.access_token = None
            obj = self.__sendRequest(
                "put", self.url_get_token, f'{{"refresh_token":"{self.token}"}}')
            if obj["errcode"] == 0:
                data = obj["data"]
                nickname = data.get('nick_name', '未知')
                self.access_token = data.get('access_token', None)
                msg += [{"name": "账号", "value": nickname}]
                print(f'账号: {nickname}')
            else:
                msg += [{"name": "刷新令牌失败",
                         "value": f'code:{obj["errcode"]}, msg:{obj["errmsg"]}'}]
                print(f'刷新令牌失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}')
        except Exception as e:
            print(f"刷新令牌异常: {e}")
            msg += [{"name": "刷新令牌异常", "value": f"请检查接口 {e}"}]
        return msg

    def signIn(self):
        """
        签到
        """
        msg = []
        try:
            obj = self.__sendRequest("post", self.url_sign)
            if obj["errcode"] == 0:
                msg += [{"name": "每日签到", "value": f"成功"}]
                print("签到成功")
                data = obj["data"]
                # 积分
                msg += [{"name": "签到奖励",
                         "value": f'积分+{data["daily_sign_coin"]} {data["reward_explanation"]}'}]
            elif obj["errcode"] == 350011:
                msg += [{"name": "重复签到", "value": f"忽略"}]
                print("重复签到 直接退出")
                exit() #目前没必要执行后续的操作
            else:  # 400000 请求参数不合法
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
            obj = self.__sendRequest("get", self.url_period_info)
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
            self.token: str = self.check_item.get("token", "")
            if len(self.token) < 4:
                raise ValueError("token配置有误")
            msg += self.refreshAccessToken()
            if self.access_token is not None:
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
