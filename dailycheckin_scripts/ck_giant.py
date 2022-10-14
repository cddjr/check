# -*- coding: utf-8 -*-
"""
cron: 0 1,20 * * *
new Env('捷安特');
"""
from utils import check, log
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests


class GIANT:

    def __init__(self, check_item):
        self.check_item = check_item
        self.session = requests.Session()
        self.session.verify = False
        adapter = HTTPAdapter()
        adapter.max_retries = Retry(connect=3, read=3, allowed_methods=False)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def __sendRequest(self, method: str, url: str, data=None, json=None):
        """
        发起一个POST/GET/PUT请求

        :param jsonText: body体
        :return: 如果成功 返回响应的JSON对象
        """
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 _giantapp/3.2.0",
            "Referer": "https://found.giant.com.cn/",
            "Connection": "keep-alive"
        }
        method = method.upper()
        response: requests.Response = self.session.request(method,
                                                           url=url, headers=headers, data=data, json=json)
        return response.json()

    def sign(self):
        """
        签到
        """
        msg = []
        try:
            obj = self.__sendRequest("post", "https://opo.giant.com.cn/opo/index.php/day_pic/do_app_pic",
                                     {"type": 1, "user_id": self.user_id})
            if obj["status"] == 1:
                log(f'签到成功', msg)
            elif obj["status"] == 4:
                log("重复签到: 忽略", msg)
            else:  # 400000 请求参数不合法
                log(f'签到失败: status:{obj["status"]}, msg:{obj["msg"]}', msg)
        except Exception as e:
            log(f'签到异常: 请检查接口 {e}', msg)
        return msg

    def getPoints(self):
        """
        获得当前积分
        """
        msg = []
        try:
            obj = self.__sendRequest("post", "https://e-gw.giant.com.cn/index.php/point_api/get_user_points",
                                     {"user_id": self.user_id})
            if obj["status"] == 1:
                points = obj["data"]
                log(f'当前积分: {points}', msg)
            else:
                log(f'getPoints 失败: status:{obj["status"]}, msg:{obj["msg"]}', msg)
        except Exception as e:
            log(f'getPoints 异常: 请检查接口 {e}', msg)
        return msg

    def main(self):
        msg = []
        try:
            self.user_id: str = self.check_item.get("user_id", "").strip()
            if len(self.user_id) < 4:
                raise SystemExit("user_id 配置有误")
            msg += self.sign()
            msg += self.getPoints()
        except Exception as e:
            log(f'失败: 请检查接口 {e}', msg)
        msg = "\n".join(msg)
        return msg


@check(run_script_name="捷安特", run_script_expression="giant")
def main(*args, **kwargs):
    return GIANT(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
