#!/usr/bin/env python3
"""
20220822 适配check仓库
20220916 适配青龙2.13.9+
:author @night-raise  from github
cron: 0 0 * * *
new Env('随机定时');
"""

from abc import ABC
from random import randrange
from typing import Dict, List

import requests

from utils import check, log


class ClientApi(ABC):
    def __init__(self):
        self.cid = ""
        self.sct = ""
        self.url = "http://localhost:5700/"
        self.twice = False
        self.token = ""
        self.cron: List[Dict] = []
        self.excluded: List[str] = []
        self.required: List[str] = []

    def init_cron(self):
        raise NotImplementedError

    def shuffle_cron(self):
        raise NotImplementedError

    def run(self):
        self.init_cron()
        self.shuffle_cron()

    @staticmethod
    def get_ran_min() -> str:
        return str(randrange(0, 60))

    def get_ran_hour(self, is_api: bool = False) -> str:
        if is_api:
            return str(randrange(7, 9))
        if self.twice:
            start = randrange(0, 12)
            return f"{start},{start + randrange(6, 12)}"
        # 由于部分脚本耗时可能超过30分钟
        # 为了避免跨越0点 限制时间在晚上23点前
        return str(randrange(0, 23))

    def random_time(self, origin_time: str, command: str):
        if not any(kw in command for kw in self.required):
            # 不是必须随机的任务
            if any(kw in command for kw in self.excluded):
                # 在黑名单中
                return origin_time
            if command.find("ran_time") != -1 or command.find(" now") != -1:
                # 排除自身或者明确定义了now参数的任务
                return origin_time
        time = origin_time.split(" ")
        # 兼容带秒的定时
        ofst_hour = 1 if len(time) <= 5 else 2
        ofst_day = 2 if len(time) <= 5 else 3
        if command.find("rssbot") != -1 or command.find("hax") != -1:
            return ClientApi.get_ran_min() + " " + " ".join(time[ofst_hour:])
        if command.find("api") != -1:
            return (
                ClientApi.get_ran_min()
                + " "
                + self.get_ran_hour(True)
                + " "
                + " ".join(time[ofst_day:])
            )
        return (
            ClientApi.get_ran_min()
            + " "
            + self.get_ran_hour()
            + " "
            + " ".join(time[ofst_day:])
        )


class QLClient(ClientApi):
    def __init__(self, client_info: Dict):
        super().__init__()
        if (
            not client_info
            or not (cid := client_info.get("client_id"))
            or not (sct := client_info.get("client_secret"))
            or not (keywords := client_info.get("keywords"))
        ):
            raise ValueError("无法获取 client 相关参数")
        else:
            self.cid = cid
            self.sct = sct
            self.keywords = keywords
        self.excluded = client_info.get("excluded", [])
        self.required = client_info.get("required", [])
        self.url = client_info.get("url", self.url).rstrip("/") + "/"
        self.twice = client_info.get("twice", False)
        self.token = requests.get(
            url=self.url + "open/auth/token",
            params={"client_id": self.cid, "client_secret": self.sct},
        ).json()["data"]["token"]
        if not self.token:
            raise ValueError("无法获取 token")

    def init_cron(self):
        data = requests.get(
            url=self.url + "open/crons",
            headers={"Authorization": f"Bearer {self.token}"},
        ).json()["data"]
        if isinstance(data, dict):
            # 兼容 v2.13.9+ 青龙
            data = data["data"]
        self.cron: List[Dict] = list(
            filter(
                lambda x: not x.get("isDisabled", 1)
                and x.get("command", "").find(self.keywords) != -1,
                data,
            )
        )

    def shuffle_cron(self):
        for c in self.cron:
            json = {
                "labels": c.get("labels", None),
                "command": c["command"],
                "schedule": self.random_time(c["schedule"], c["command"]),
                "name": c["name"],
                "id": c["id"],
            }
            requests.put(
                url=self.url + "open/crons",
                json=json,
                headers={"Authorization": f"Bearer {self.token}"},
            )


@check(run_script_name="随机定时", run_script_expression="RANDOM", interval_max=0)
def main(*args, **kwargs):
    msg = []
    try:
        QLClient(client_info=kwargs.get("value", {})).run()
        log("处于启动状态的任务定时修改成功", msg)
    except ValueError as e:
        log(f"配置错误，{e},请检查你的配置文件", msg)
    except AttributeError:
        log("你的系统不支持运行随机定时", msg)
    return "\n".join(msg)


if __name__ == "__main__":
    main()
