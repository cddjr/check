# -*- coding: utf-8 -*-
"""
cron: 0 1,20 * * *
new Env('朴朴');

微信登录朴朴app 
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token
"""
from utils import check, log
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests


class PUPU:
    userAgent = "Pupumall/3.2.3;iOS 15.4.1"
    api_host = "https://j1.pupuapi.com"

    url_sign = api_host + "/client/game/sign/v2?city_zip=510100&supplement_id="
    url_period_info = api_host + "/client/game/sign/period_info"

    url_get_token = 'https://cauth.pupuapi.com/clientauth/user/refresh_token'

    def __init__(self, check_item):
        self.check_item = check_item
        self.session = requests.Session()
        self.session.verify = False
        adapter = HTTPAdapter()
        adapter.max_retries = Retry(connect=3, read=3, allowed_methods=False)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.access_token = None

    def __sendRequest(self, method: str, url: str, data=None, json=None):
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
            "Connection": "keep-alive"
        }
        method = method.upper()
        if self.access_token is not None:
            headers["Authorization"] = f'Bearer {self.access_token}'
        response: requests.Response = self.session.request(method,
                                                           url=url, headers=headers, data=data, json=json)
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
            obj = self.__sendRequest("put", self.url_get_token,
                                     json={"refresh_token": self.token})
            if obj["errcode"] == 0:
                data = obj["data"]
                nickname = data.get('nick_name', '未知')
                self.access_token = data.get('access_token', None)
                self.refresh_token = data.get('refresh_token', None)
                log(f'账号: {nickname}', msg)
                log(f'access_token:{self.access_token}')
                if self.refresh_token == self.token :
                    log('token没有变化')
                else:
                    log(f'新的token:{self.token}', msg)
            else:
                # 200208 登录已失效，请重新登录
                log(f'刷新令牌失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'刷新令牌异常: 请检查接口 {e}', msg)
        return msg

    def signIn(self):
        """
        签到
        """
        msg = []
        try:
            obj = self.__sendRequest("post", self.url_sign)
            if obj["errcode"] == 0:
                data = obj["data"]
                # 积分
                log(f'签到成功: 奖励积分+{data["daily_sign_coin"]} {data["reward_explanation"]}', msg)
            elif obj["errcode"] == 350011:
                log("重复签到: 忽略", msg)
                exit()  # 目前没必要执行后续的操作
            else:  # 400000 请求参数不合法
                log(f'签到失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'签到异常: 请检查接口 {e}', msg)
        return msg

    def getPeriod(self):
        """
        获得本周连续签到的天数
        """
        msg = []
        try:
            obj = self.__sendRequest("get", self.url_period_info)
            if obj["errcode"] == 0:
                data = obj["data"]
                log(f'签到信息: 本周连续签到{data["signed_days"]}天', msg)
            else:
                log(f'getPeriod失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'getPeriod异常: 请检查接口 {e}', msg)
        return msg

    def main(self):
        msg = []
        try:
            self.token: str = self.check_item.get("token", "")
            if len(self.token) < 4:
                raise SystemExit("token配置有误")
            msg += self.refreshAccessToken()
            if self.access_token:
                msg += self.signIn()
                msg += self.getPeriod()
        except Exception as e:
            log(f'失败: 请检查接口 {e}', msg)
        msg = "\n".join(msg)
        return msg


@check(run_script_name="朴朴", run_script_expression="pupu")
def main(*args, **kwargs):
    return PUPU(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
