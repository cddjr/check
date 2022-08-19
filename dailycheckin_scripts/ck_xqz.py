# -*- coding: utf-8 -*-
"""
cron: 2 20 * * *
new Env('闲趣赚3.24');

参考js我改成python了 以下是原文
@肥皂 3.22 闲趣赚  一天0.1-0.4或者更高（根据用户等级增加任务次数）
3.24 更新加入用户余额和信息。。。。
苹果&安卓下载地址：复制链接到微信打开   https://a.jrpub.cn/3345249
新人进去直接秒到账两个0.3.。。。（微信登录）花两分钟再完成下新人任务，大概秒到微信3元左右
感觉看账号等级，我的小号进去只能做五个任务，大号可以做十个。
建议做一下里面的任务，单价还是不错的，做完等级升上来了挂脚本收益也多一点。
抓取域名  wap.quxianzhuan.com  抓取cookie的全部数据。。
青龙变量  xqzck  多账户@隔开
更新加入用户余额和信息。。。。
"""
from utils import check, log, randomSleep, cookie_to_dic
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests


class XQZ:
    name = "闲趣赚3.24"

    userAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 LT-APP/43/242(YM-RT)"

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

        :param text: body体
        :return: requests.Response
        """
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "x-app": "96c1ea5a-9a52-44c9-8ac4-8dceafa065c8",  # 估计是uuid、设备id之类的
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": self.userAgent,
            "Referer": "https://wap.quxianzhuan.com/reward/list/?xapp-target=blank",
            "Connection": "keep-alive"
        }
        method = method.upper()
        response: requests.Response = self.session.request(method,
                                                           url=url, headers=headers, data=data, json=json)
        return response

    def getTaskList(self, page=1):
        """
        获取任务列表 每次拉20个
        """
        msg = []
        browse_list = None
        try:
            obj = self.__sendRequest(
                "get", f"http://wap.quxianzhuan.com/reward/browse/index?page={page}").json()  # &limit={limit}

            if obj["state"] != 1:
                log(f'获取任务列表失败 state={obj["state"]} msg={obj.get("msg", "未知错误")}', msg)
                # return None, msg

            self.formhash = self.session.cookies.get("tzb_formhash_cookie")
            if not self.formhash:
                log("无法获取 tzb_formhash_cookie", msg)
                return None, msg

            browse_list = obj.get("browse_list", [])
            log(f'本次获取到{len(browse_list)}个任务')
        except Exception as e:
            log(f"获取任务列表异常 请检查接口 {e}", msg)
        return browse_list, msg

    def doTask(self, item):
        """
        执行任务 如果失败将抛出StopIteration异常
        """
        msg = []
        try:
            id = item["reward_id"]
            log(f'- 任务ID:{id} {item.get("cat_name", "")}-{item.get("tags_name", "")}-{item.get("reward_title", "")}', msg)
            obj = self.__sendRequest("post", "https://wap.quxianzhuan.com/reward/browse/append/",
                                     data={"reward_id": id, "formhash": self.formhash, "inajax": 1}).json()
            if obj["state"] != 1:
                log(f'任务失败 {obj.get("msg", "未知错误")}', msg)
                raise StopIteration
            log(f'  {obj.get("msg", "已完成")}')
        except StopIteration as e:
            raise e
        except Exception as e:
            log(f"任务异常 请检查接口 {e}", msg)
        return msg

    def userInfo(self):
        msg = []
        try:
            text = self.__sendRequest(
                "get", "https://wap.quxianzhuan.com/user/").text
            # 返回的是html
            available_money = simple_match(text, '"available_money":', ',')
            uid = simple_match(text, 'UID：', '</span>')
            log(f'用户 {uid} - 可提现余额【{available_money}】', msg)
        except Exception as e:
            log(f"查询账号异常 请检查接口 {e}", msg)
        return msg

    def main(self):
        msg = []
        try:
            cookies = self.check_item.get("cookie", "")
            token = cookie_to_dic(cookies).get("tzb_user_cryptograph")
            if not token:
                raise ValueError("Cookie配置有误 必须有 tzb_user_cryptograph")
            # Cookie只需要 tzb_user_cryptograph 即可，只有它是7天有效期
            self.session.cookies.set(
                "tzb_user_cryptograph", token, domain=".quxianzhuan.com")
            curr_page = 1
            total_task = 0
            succ_task = 0
            price = 0.0
            while (True):
                task_list, task_msg = self.getTaskList(page=curr_page)
                msg += task_msg
                if not task_list:
                    break
                total_task += len(task_list)
                try:
                    for task in task_list:
                        self.doTask(task)
                        succ_task += 1
                        try:
                            unit_price = float(task.get("unit_price"))
                            price += unit_price
                        except Exception:
                            pass
                        randomSleep(11, 20)
                except StopIteration:
                    break
                if len(task_list) < 20:
                    # 这已经是最后一页
                    break
                curr_page += 1
            log(f'已成功完成{succ_task}个任务 获得{price}元', msg)
            msg += self.userInfo()
        except Exception as e:
            log(f"失败: 请检查接口{e}", msg)
        msg = "\n".join(msg)
        return msg


def simple_match(s: str, prefix: str, suffix: str):
    pos1 = s.find(prefix)
    if pos1 < 0:
        return None
    pos1 += len(prefix)
    pos2 = s.find(suffix, pos1)
    if pos2 < 0:
        return None
    return s[pos1:pos2]


@check(run_script_name="闲趣赚", run_script_expression="XQZ")
def main(*args, **kwargs):
    return XQZ(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
