# -*- coding: utf-8 -*-
"""
cron: 25 0 * * *
new Env('慢慢买');

签到、补签等逻辑可看这个js
https://apph5.manmanbuy.com/renwu/js/common.js

"""
import traceback
from utils import check, log
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
import requests
import urllib.parse


class ManManBuy:
    # UA和devid都可以根据情况随机生成
    userAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 - mmbWebBrowse - ios"
    c_devid = "43D5701C-AD8F-4503-BCA4-58C1D4EF42C9"

    api_host = 'https://apph5.manmanbuy.com'
    url_index = api_host + '/renwu/index.aspx?m_from=my_daka'
    url_login = api_host + '/taolijin/login.aspx'
    url_task = api_host + '/renwu/index.aspx'

    def __init__(self, check_item):
        self.check_item = check_item
        self.session = requests.Session()
        self.session.verify = False
        adapter = HTTPAdapter()
        adapter.max_retries = Retry(connect=3, read=3, allowed_methods=False)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def ajax(self, method: str, url: str, data=None, json=None):
        headers = CaseInsensitiveDict()
        headers['X-Requested-With'] = 'XMLHttpRequest'
        headers['Referer'] = self.url_index
        if method.upper() not in ("GET", "HEAD"):
            headers['Origin'] = self.api_host
        return self.request(method, url, data=data, json=json, headers=headers).json()

    def request(self, method: str, url: str, data=None, json=None, headers: CaseInsensitiveDict = None) -> requests.Response:
        """
        发起一个http请求

        :return: 如果成功 返回response对象
        """
        base_headers = CaseInsensitiveDict()
        base_headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
        base_headers['Accept-Language'] = 'zh-CN,zh-Hans;q=0.9'
        base_headers['f-refer'] = 'wv_h5'
        base_headers['User-Agent'] = self.userAgent
        base_headers['Connection'] = 'keep-alive'
        if headers:
            base_headers.update(headers)
        response = self.session.request(
            method, url=url, headers=base_headers, data=data, json=json)
        return response

    def checkin(self):
        """
        立即签到
        """
        msg = []
        try:
            obj = self.ajax("post", self.url_task,
                            data={'action': 'checkin', 'username': self.u_name, 'c_devid': self.c_devid, 'isAjaxInvoke': 'true'})
            if int(obj["code"]) == 1:
                data = obj["data"]
                log(f'签到成功: 奖励积分+{data["jifen"]}', msg)
                log(f'已连续签到: {data["zt"]}天', msg)
            elif int(obj["code"]) == 0 and '签到失败' == obj["msg"]:
                log('重复签到: 忽略', msg)
                exit()  # 目前没必要执行后续的操作
            else:
                log(f'签到失败: code:{obj["code"]}, msg:{obj["msg"]}', msg)
        except Exception as e:
            log(f'签到异常: {e}', msg)
        return msg

    def login(self):
        msg = []
        try:
            log(f'账号: {self.username}', msg)
            obj = self.ajax("post", self.url_login,
                            data={'action': 'newtokenlogin', 'u_name': self.u_name, 'u_token': self.u_token})
            if int(obj["code"]) == 1:
                log('登录成功')
            else:
                raise Exception(obj)
        except Exception as e:
            raise Exception(f'登录异常: {e}')
        return msg

    def main(self):
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
            self.c_devid = self.check_item.get("devid") or self.c_devid
            self.username = self.check_item.get("name") or self.c_devid

            msg += self.login()
            msg += self.checkin()
        except Exception as e:
            traceback.print_exception(e)
            log(f'失败: {e}', msg)
        msg = "\n".join(msg)
        return msg


@check(run_script_name="慢慢买", run_script_expression="manmanbuy")
def main(*args, **kwargs):
    return ManManBuy(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
