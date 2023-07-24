# -*- coding: utf-8 -*-
"""
cron: 13 6,20 * * *
new Env('PT签到');

"""
import asyncio
import sys
from dataclasses import dataclass
from datetime import date
from time import time
from traceback import format_exc

import json_codec
from aiohttp_retry import JitterRetry, RetryClient

from utils import GetScriptConfig, check, log

assert sys.version_info >= (3, 9)

"""
https://pt.btschool.club/index.php?action=addbonus
成功    “今天签到您获得XXX点魔力值”
失败    无提示语

https://www.pttime.org/attendance.php
“签到成功” “这是你的第 <b>XX</b> 次签到，已连续签到 <b>XX</b> 天，本次签到获得 <b>XXX</b> 个魔力值。”
"已经签到过了"

https://hdfun.me/attendance.php
“签到成功” “这是您的第 <b>XX</b> 次签到，已连续签到 <b>XX</b> 天，本次签到获得 <b>XXX</b> 个魔力值。”
“已经签到过了”
"""


@dataclass
class PT_Record:
    timestamp: int = 0
    moli: int = -1
    can_retry: bool = True


class PT:
    def __init__(self, check_item) -> None:
        self.check_item: dict = check_item
        self.database = None
        self.database_dirty = False
        self.records = {}
        self.header_base = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6.3 Mobile/15E148 Safari/604.1",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Accept-Language": "zh-CN,zh-Hans;q=0.9", }

    async def main(self):
        msg: list[str] = []
        try:
            self.load_database()
            co_tasks = []
            # 学校单独处理
            btschool_cookie = self.check_item.get("btschool", "")
            if btschool_cookie and self.is_sign_needed("btschool"):
                co_tasks.append(self.btschool_sign(btschool_cookie))
            # 好大单独处理
            hdarea_cookie = self.check_item.get("hdarea", "")
            if hdarea_cookie and self.is_sign_needed("hdarea"):
                co_tasks.append(self.hdarea_sign(hdarea_cookie))
            # 以下使用通用流程处理签到
            for (tag, host) in [("pttime", "www.pttime.org"),
                                ("hdzone", "hdfun.me"),
                                # TODO ...
                                ]:
                cookie = self.check_item.get(tag, "")
                if cookie and self.is_sign_needed(tag):
                    co_tasks.append(self.common_attendance(host, tag, cookie))
            if not co_tasks:
                raise SystemExit

            for info in await asyncio.gather(*co_tasks):
                msg += info
        except Exception:
            log(f'失败: 请检查接口 {format_exc()}', msg)
        finally:
            self.save_database()
        return "\n".join(msg)

    def __get_or_create_record(self, tag: str):
        if tag not in self.records:
            self.records[tag] = PT_Record()
        return self.records[tag]

    def __on_sign_succ(self, tag: str, moli: int):
        msg: list[str] = []
        record = self.__get_or_create_record(tag)
        record.timestamp = int(time())
        record.moli = moli
        record.can_retry = False
        self.database_dirty = True
        log(f"{tag}: 签到成功，获得{moli}魔力", msg)
        return msg

    def __on_sign_fail(self, tag: str):
        msg: list[str] = []
        record = self.__get_or_create_record(tag)
        record.timestamp = int(time())
        record.moli = 0
        record.can_retry = False
        self.database_dirty = True
        log(f"{tag}: 重复签到", msg)
        return msg

    def __on_sign_err(self, tag: str):
        msg: list[str] = []
        record = self.__get_or_create_record(tag)
        record.timestamp = int(time())
        record.moli = -1
        record.can_retry = True
        self.database_dirty = True
        log(f"{tag}: 请检查接口", msg)
        return msg

    def is_sign_needed(self, tag: str) -> bool:
        record = self.records.get(tag)
        if not record:
            return True
        time_diff = date.fromtimestamp(time()) \
            - date.fromtimestamp(record.timestamp)
        if time_diff.days < 1:
            # 按自然日计算不足一天
            return record.can_retry
        else:
            return True

    async def btschool_sign(self, cookie: str):
        TAG = "btschool"
        try:
            print(f"--- {TAG} 流程开始 ---")
            header = self.header_base
            header["Referer"] = "https://pt.btschool.club/torrents.php"
            header["Cookie"] = cookie
            async with RetryClient(raise_for_status=True,
                                   retry_options=JitterRetry(attempts=3)) as session:
                async with session.get("https://pt.btschool.club/index.php?action=addbonus",
                                       headers=header, ssl=False
                                       ) as response:
                    text = await response.text()
                    PATTERN = "今天签到您获得"
                    pos = text.find(PATTERN)
                    if pos >= 0:
                        try:
                            pos += len(PATTERN)
                            moli = int(text[pos:text.find("点魔力值", pos)])
                            return self.__on_sign_succ(TAG, moli)
                        except:
                            return self.__on_sign_succ(TAG, moli=-1)
                    elif "魔力值" in text:
                        return self.__on_sign_fail(TAG)
                    else:
                        print(TAG)
                        print(text)
                        return self.__on_sign_err(TAG)
        except Exception:
            print(f'异常: 请检查接口 {format_exc()}')
            return self.__on_sign_err(TAG)
        finally:
            print(f"--- {TAG} 流程结束 ---")

    async def hdarea_sign(self, cookie: str):
        TAG = "hdarea"
        try:
            print(f"--- {TAG} 流程开始 ---")
            header = self.header_base
            header["Referer"] = "https://hdarea.club/"
            header["Cookie"] = cookie
            async with RetryClient(raise_for_status=True,
                                   retry_options=JitterRetry(attempts=3)) as session:
                async with session.post("https://hdarea.club/sign_in.php",
                                        data={"action": "sign_in"},
                                        headers=header, ssl=False
                                        ) as response:
                    text = await response.text()
                    # 已连续签到2天，此次签到您获得了12魔力值奖励!
                    PATTERN = "获得了"
                    pos = text.find(PATTERN)
                    if pos >= 0:
                        try:
                            pos += len(PATTERN)
                            moli = int(text[pos:text.find("魔力值", pos)])
                            return self.__on_sign_succ(TAG, moli)
                        except:
                            return self.__on_sign_succ(TAG, moli=-1)
                    elif "重复签到" in text:
                        # 请不要重复签到哦！
                        return self.__on_sign_fail(TAG)
                    else:
                        print(TAG)
                        print(text)
                        return self.__on_sign_err(TAG)
        except Exception:
            print(f'异常: 请检查接口 {format_exc()}')
            return self.__on_sign_err(TAG)
        finally:
            print(f"--- {TAG} 流程结束 ---")

    async def common_attendance(self, host: str, tag: str, cookie: str):
        try:
            print(f"--- {tag} 流程开始 ---")
            header = self.header_base
            header["Cookie"] = cookie
            async with RetryClient(raise_for_status=True,
                                   retry_options=JitterRetry(attempts=3)) as session:
                async with session.get(f"https://{host}/attendance.php",
                                       headers=header, ssl=False
                                       ) as response:
                    text = await response.text()
                    if "签到成功" in text:
                        try:
                            PATTERN = "签到获得 <b>"
                            pos = text.find(PATTERN)
                            pos += len(PATTERN)
                            moli = int(text[pos:text.find("</b> 个魔力值", pos)])
                            return self.__on_sign_succ(tag, moli)
                        except:
                            return self.__on_sign_succ(tag, moli=-1)
                    elif "签到过了" in text or "今天已签到" in text:
                        return self.__on_sign_fail(tag)
                    else:
                        print(tag)
                        print(text)
                        return self.__on_sign_err(tag)
        except Exception:
            print(f'异常: 请检查接口 {format_exc()}')
            return self.__on_sign_err(tag)
        finally:
            print(f"--- {tag} 流程结束 ---")

    def load_database(self):
        '''读取数据库'''
        try:
            if self.database:
                # 已经读取过数据库
                return True
            self.database_dirty = False
            self.database = GetScriptConfig("pt_sign.json")
            self.records = json_codec.decode(self.database.get_value_2("records") or {} if self.database else {},
                                             dict[str, PT_Record])
            return True
        except BaseException:
            return False

    def save_database(self):
        '''保存数据库'''
        if self.database and self.database_dirty:
            try:
                self.database_dirty = False
                self.database.set_value(
                    "records", json_codec.encode(self.records))
            except BaseException:
                return False
        return True


@check(run_script_name="PT签到", run_script_expression="ptsign")
def main(*args, **kwargs):
    return asyncio.run(PT(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
