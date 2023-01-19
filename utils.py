from checksendNotify import send
import json
import os
import sys
import platform
import random
import re
import sqlite3
import time
import traceback
from functools import wraps
from typing import Any, BinaryIO
from fasteners.process_lock import InterProcessReaderWriterLock
from enum import Enum
from asyncio import sleep as aio_sleep


def pip_install():
    print("正在安装依赖")
    os.system(
        "pip3 install requests rsa tomli tomli_w beautifulsoup4 aiohttp aiohttp_retry")


try:
    import tomli
    import tomli_w
except ModuleNotFoundError:
    pip_install()
    import tomli
    import tomli_w


# def toml_to_json(toml_path, to_json_path):
#     """
#     :param toml_path: 需要转换的toml文件的路径
#     :param to_json_path: 需要输出的json文件路径
#     :return: None
#     """
#     with open(toml_path, "rb") as f:
#         toml_dict = tomli.load(f)
#         json_date = json.dumps(toml_dict, indent=4, ensure_ascii=False)
#         with open(to_json_path, 'w', encoding="utf8") as s:
#             s.write(json_date)


# def json_to_toml(json_path, to_toml_path):
#     with open(json_path, "r", encoding="utf8") as f:
#         json_dict = json.load(f)
#         with open(to_toml_path, "wb") as f:
#             tomli_w.dump(json_dict, f)

class config_get(object):
    def __init__(self, custom_path=None):
        """
        config_path: 自定义配置文件路径
        config_file: 实际使用的配置文件路径
        config_format: 实际使用的配置文件格式
        """
        if custom_path is None:
            self.config_path = self.get_config_path()
            self.config_file = self.get_config_file()
            self.config_format = self.get_config_format()
        else:
            self.config_file = custom_path
            self.config_format = self.get_config_format()
        self.lock_ = InterProcessReaderWriterLock(f'{self.config_file}.lock')

    def get_config_format(self):
        if self.config_file.endswith('.toml'):
            return "toml"
        else:
            return "json"

    @staticmethod
    def get_config_path():
        ql_old = "/ql/config/"
        ql_new = "/ql/data/config/"
        if os.path.isdir(ql_new):
            print('成功 当前环境为青龙面板v2.12+ 继续执行\n')
            return ql_new
        elif os.path.isdir(ql_old):
            print('成功 当前环境为青龙面板v2.12- 继续执行\n')
            return ql_old
        else:
            if platform.system() == "Windows":
                return ""
            print('失败 请检查环境')
            exit(0)

    def get_config_file(self):
        toml_file = f"{self.config_path}check.toml"
        json_file = f"{self.config_path}check.json"
        if os.path.exists(toml_file):
            print(f"启用了toml配置文件\n路径为{toml_file}\n")
            return toml_file
        elif os.path.exists(json_file):
            print(f"启用了json配置文件\n路径为{json_file}\n")
            return json_file
        else:
            print("未找到配置文件")
            self.move_config_file()
            return toml_file

    def move_config_file(self):
        print("尝试移动配置文件到目录")
        if self.config_path == "/ql/config/":
            self.move_configuration_file_old()
        else:
            self.move_configuration_file_new()

    def get_real_key(self, expression):
        """
        从配置文件中获取，re表达式想要的KEY
        :return:
        """
        pattern = re.compile(expression, re.I)
        real_key = ''
        with self.lock_.read_lock():
            if self.config_format == "toml":
                for key in self.get_key_for_toml(self.config_file):
                    if pattern.match(key) is not None:
                        real_key = key
            else:
                for key in self.get_key_for_json(self.config_file):
                    if pattern.match(key) is not None:
                        real_key = key
        if real_key != '':
            return real_key
        else:
            print("啊哦没有找到")
            exit(1)

    def get_value(self, expression):
        real_key = self.get_real_key(expression)
        return self.get_value_2(real_key)

    def get_value_2(self, real_key: str):
        with self.lock_.read_lock():
            if self.config_format == "toml":
                return self.get_value_for_toml(self.config_file, real_key)
            else:
                return self.get_value_for_json(self.config_file, real_key)

    def set_value(self, key: str, value: Any):
        with self.lock_.write_lock():
            if self.config_format == "toml":
                return self.set_value_for_toml(self.config_file, key, value)
            else:
                raise NotImplementedError

    @staticmethod
    def move_configuration_file_old():
        print("移动配置文件")
        os.system("cp /ql/repo/cddjr_check/check.sample.toml /ql/config/check.toml")

    @staticmethod
    def move_configuration_file_new():
        print("移动配置文件")
        os.system(
            "cp /ql/data/repo/cddjr_check/check.sample.toml /ql/data/config/check.toml")

    @staticmethod
    def get_value_for_toml(toml_path, key):
        with open(toml_path, "rb") as f:
            try:
                toml_dict = tomli.load(f)
                return toml_dict.get(key)
            except tomli.TOMLDecodeError:
                print(
                    f"错误：配置文件 {toml_path} 格式不对，请学习 https://toml.io/cn/v1.0.0\n错误信息：\n{traceback.format_exc()}"
                )
                exit(1)

    @staticmethod
    def set_value_for_toml(toml_path, key: str, value: Any):
        f: BinaryIO = None
        try:
            with open(toml_path, "rb") as f:
                try:
                    toml_dict = tomli.load(f)
                except tomli.TOMLDecodeError:
                    print(
                        f"错误：配置文件 {toml_path} 格式不对\n{traceback.format_exc()}")
                    toml_dict = {}
        except OSError:
            toml_dict = {}
        if isinstance(value, dict):
            if key not in toml_dict:
                toml_dict[key] = value
            else:
                toml_dict[key].update(value)
        elif value is not None:
            toml_dict[key] = value
        elif key in toml_dict:
            del toml_dict[key]
        try:
            with open(toml_path, "wb") as f:
                tomli_w.dump(toml_dict, f)
        except:
            print(f"修改配置文件 {toml_path} 失败\n{traceback.format_exc()}")

    @staticmethod
    def get_value_for_json(json_path, key):
        with open(json_path, "r", encoding="utf8") as f:
            try:
                json_dict = json.load(f)
                return json_dict.get(key)
            except json.decoder.JSONDecodeError:
                print(f"错误：配置文件 {json_path} 格式不对，错误信息{traceback.format_exc()}")

    @staticmethod
    def get_key_for_toml(toml_path):
        with open(toml_path, "rb") as f:
            try:
                toml_dict = tomli.load(f)
                return toml_dict.keys()
            except tomli.TOMLDecodeError:
                print(
                    f"错误：配置文件 {toml_path} 格式不对，请学习 https://toml.io/cn/v1.0.0\n错误信息：\n{traceback.format_exc()}"
                )
                exit(1)

    @staticmethod
    def get_key_for_json(json_path):
        with open(json_path, "r", encoding="utf8") as f:
            try:
                json_dict = json.load(f)
                return json_dict.keys()
            except json.decoder.JSONDecodeError:
                print(f"错误：配置文件 {json_path} 格式不对，错误信息{traceback.format_exc()}")


class check(object):
    def __init__(self, run_script_name, run_script_expression, Configuration_flag=False, interval_min=5, interval_max=10):
        """
        :param run_script_name: 执行脚本的说明
        :param run_script_expression: 需要获取的配置键的re表达式
        :param Configuration_flag: 是否只检测True或False(默认为False)
        :param interval_min: 多账号执行的最小间隔时间(默认为5秒)
        :param interval_max: 多账号执行的最大间隔时间(默认为10秒 设置0代表无间隔)
        """
        self.run_script_name = run_script_name
        self.run_script_expression = run_script_expression
        self.Configuration_flag = Configuration_flag
        self.interval_min = interval_min
        self.interval_max = interval_max

    @staticmethod
    def other_task():
        # change_db()
        pass

    def __call__(self, func):
        @wraps(func)
        def wrapper():
            if not self.Configuration_flag:
                config = config_get()
                value_list = config.get_value(self.run_script_expression)
                push_message = ""
                num = 0
                for value in value_list:
                    num += 1
                    print(f"<----------------账号【{num}】---------------->")
                    username = value.get('username') or value.get(
                        'name') or value.get('email') or value.get('phone')
                    if not username:
                        username = str(value)[:32] + "..."
                    print(f"获取到的账号信息为:{username}\n")
                    try:
                        result = func(value=value) + '\n\n'
                        # print(f"执行结果:\n{result}")
                        push_message += result
                    except IndexError:
                        print("可能是示例格式被运行\n错误信息:")
                        print(f"{traceback.format_exc()}")
                        push_message += ''
                    except AttributeError:
                        print("可能是配置文件的键名出现问题\n"
                              "例如:在此次更新中什么值得买的键名从smzdm_cookie变成了cookie\n")
                        print(f"{traceback.format_exc()}")
                        push_message += ''
                    except TypeError:
                        print(f"{traceback.format_exc()}")
                        push_message += ''
                    except SystemExit as e:
                        # 脚本中执行exit不要影响其它账号的运行
                        print(e)
                        push_message += ''
                    except BaseException:
                        # 未知异常，打印调用栈，继续执行下一个账号
                        print(f"{traceback.format_exc()}")
                        push_message += ''
                    if self.interval_max > 0 and num < len(value_list):
                        randomSleep(self.interval_min, self.interval_max)
                send(self.run_script_name, push_message)
            else:
                config = config_get()
                flag = config.get_value(self.run_script_expression)
                if flag is not None and flag:
                    print(f"开始执行{self.run_script_name}")
                    func()
                else:
                    print(f"设置为不执行{self.run_script_name}")

        return wrapper


def change_cron_new(cron_file_path="/ql/data/db/database.sqlite", repositories="cddjr_check"):
    print("尝试修改定时时间")
    os.system(f"cp {cron_file_path} {cron_file_path}.back")
    con = sqlite3.connect(cron_file_path)
    cur = con.cursor()

    def change_time(time_str: str):
        words = re.sub("\\s+", " ", time_str).split()
        words[0] = str(random.randrange(60))
        words[1] = str(random.randrange(22))
        return " ".join(words)

    cur.execute("select id,name,command,schedule from Crontabs")
    res = cur.fetchall()
    for line in res:
        if line[2].find(repositories) != -1:
            sql = f" UPDATE Crontabs SET schedule = \"{change_time(line[3])}\" WHERE id = {line[0]}"
            print(f"任务名称 {line[1]} 修改为{sql}")
            cur.execute(sql)

    con.commit()
    con.close()


def change_cron_old(cron_file_path="/ql/db/crontab.db", repositories="cddjr_check"):
    print("尝试修改定时时间")

    def change_time(time_str: str):
        words = re.sub("\\s+", " ", time_str).split()
        words[0] = str(random.randrange(60))
        words[1] = str(random.randrange(22))
        return " ".join(words)

    time_str = time.strftime("%Y-%m-%d", time.localtime())
    os.system(f"cp /ql/db/crontab.db /ql/db/crontab.db.{time_str}.back")
    lines = []
    with open(cron_file_path, "r", encoding="UTF-8") as f:
        for i in f.readlines():
            # print(record.get("command"))
            if i.find(repositories) != -1:
                record = json.loads(i)
                record["schedule"] = change_time(record["schedule"])
                lines.append(json.dumps(record, ensure_ascii=False) + "\n")
            else:
                lines.append(i)

    with open(cron_file_path, "w", encoding="UTF-8") as f:
        f.writelines(lines)


def randomSleep(min=1, max=6):
    interval = random.randint(min, max)
    print(f"随机等待{interval}秒...")
    time.sleep(interval)


async def aio_randomSleep(min=1, max=6):
    interval = random.randint(min, max)
    print(f"随机等待{interval}秒...")
    await aio_sleep(interval)


def log(s: object, msg_list: None | list[str] = None):
    print(s)
    if msg_list is not None:
        msg_list += [str(s)]


def GetScriptConfig(filename: str):
    """
    获得当前脚本对应的配置文件
    """
    try:
        dirname = os.path.dirname(os.path.abspath(sys.argv[0]))
        cache_dir = os.path.join(dirname, ".cache")
        try:
            os.makedirs(cache_dir)
        except OSError:
            if not os.path.isdir(cache_dir):
                raise
        config = config_get(os.path.join(cache_dir, f"{filename}.toml"))
        config.set_value("Version", 1)
        return config
    except:
        print(traceback.format_exc())
        return None


def cookie_to_dic(cookie: str):
    if not cookie:
        return {}
    return {item.split('=')[0]: item.split('=')[1] for item in cookie.split('; ')}


class default:
    """给Enum添加默认值"""

    def __init__(self, **kwargs):
        if "value" in kwargs:
            self.__default = kwargs["value"]

    def __call__(self, cls):
        if issubclass(cls, Enum):
            @classmethod
            def missing(cls, value):
                if hasattr(self, "__default"):
                    assert value != self.__default
                    log(f"警告: {cls.__name__} 没有定义 '{value}', 使用默认值'{self.__default}'替代")
                    return cls(self.__default)
                else:
                    for index, member in enumerate(cls):
                        if index == 0:
                            log(f"警告: {cls.__name__} 没有定义 '{value}', 使用第{index+1}个枚举值'{member.name}({member.value})'替代")
                            return member
                    return None

            cls._missing_ = missing
        return cls


if __name__ == "__main__":
    pip_install()
    if platform.system() == "Windows":
        exit()
    config = config_get()
    if config.config_path == "/ql/config/":
        if os.path.isfile("/ql/db/database.sqlite"):
            change_cron_new(cron_file_path="/ql/db/database.sqlite")
        else:
            change_cron_old()
    else:
        change_cron_new()
        print("修改完成请重启容器")
