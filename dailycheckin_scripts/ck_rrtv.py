# -*- coding: utf-8 -*-
"""
cron: 30 10 8,22 * * *
new Env('多多视频');
"""
from utils import check, randomSleep
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests


class RRTV:
    name = "多多视频"

    clientVersion = "5.19.1"
    clientType = "ios_zyb"  # android | android_Meizu
    userAgent = "PPVideo/1.12 (iPhone; iOS 15.4.1; Scale/3.00)"
    # activity_userAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 App/RRSPApp platform/iPhone AppVersion/1.12"
    api_host = "https://api.rr.tv"

    activity_url_sign = api_host + "/rrtv-activity/sign/sign"
    activity_url_getinfo = api_host + "/rrtv-activity/sign/getInfo"
    activity_url_openBag = api_host + "/rrtv-activity/sign/openBag"
    activity_url_listreward = api_host + "/rrtv-activity/sign/getAllBagItemMaterial"
    activity_url_reflashCard = api_host + "/rrtv-activity/sign/reflashUserCard"

    taskcenter_url_openbox = api_host + "/v3plus/taskCenter/openBox"
    taskcenter_url_listbox = api_host + "/v3plus/taskCenter/index"

    vip_url_clock = api_host + "/vip/experience/clock"

    """
    API定义     https://img.rr.tv/rrsp/0.1.0/js/main.1641814753479.js
    逻辑处理    https://img.rr.tv/rrsp/0.1.0/js/checkin.1641814753479.js
    """

    def __init__(self, check_item):
        self.check_item = check_item
        self.session = requests.Session()
        self.session.verify = False
        adapter = HTTPAdapter()
        adapter.max_retries = Retry(connect=3, read=3, allowed_methods=False)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def __postRequest(self, url: str, text: str = None):
        """
        发起一个POST请求

        :param text: body体
        :return: 如果成功 返回响应的JSON对象
        """
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "clientVersion": self.clientVersion,
            "token": self.token,
            # "Origin": "https://mobile.rr.tv",
            "clientType": self.clientType,
            "User-Agent": self.userAgent,
            # "Referer": "https://mobile.rr.tv/",
            "Content-Length": str(len(text)) if text is not None else "0",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }
        response: requests.Response = self.session.post(
            url=url, headers=headers, data=text)
        return response.json()

    def __getRewardList(self):
        """
        获取礼盒中的奖品列表
        """
        rewards = []  # {"code":"x", "name":"apple"}
        try:
            obj = self.__postRequest(self.activity_url_listreward)
            if obj["code"] == "0000":
                # isinstance(data, list)
                print("礼盒中的奖品列表")
                for reward in obj.get("data", []):
                    code = reward.get("code", "unknown")
                    name = f'{reward.get("text1")}{reward.get("text2")}'
                    rewards += [{"code": code, "name": name}]
                    print(f"\t{name}")
            else:
                print(f'获取奖品列表失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            print(f"获取奖品列表异常: {e}")
        return rewards

    def __openBox(self, id: str, name: str):
        """
        开启宝箱

        :param id: 宝箱id
        :param name: 宝箱名
        """
        msg = []
        try:
            obj = self.__postRequest(
                self.taskcenter_url_openbox, f"boxId={id}")
            if obj["code"] == "0000":
                box = obj["data"]["boxs"][0]
                reward = f'{box.get("rewardName")}+{box.get("rewardNum")}'
                msg += [{"name": f"\t开{name}", "value": reward}]
                print(f'\t开{name}: {reward}')
            else:
                msg += [{"name": f"\t开{name}失败",
                         "value": f'code:{obj["code"]}, msg:{obj["msg"]}'}]
                print(f'\t开{name}失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            print(f"\t开{name}异常: {e}")
            msg += [{"name": f"\t开{name}异常", "value": f"请检查接口 {e}"}]
        return msg

    def openAllBoxes(self):
        """
        开启所有可开的宝箱
        """
        msg = []
        try:
            obj = self.__postRequest(self.taskcenter_url_listbox)
            if obj["code"] == "0000":
                ap = obj["data"]["activePoint"]
                msg += [{"name": "今日活跃度", "value": ap}]
                print(f'今日活跃度: {ap}')
                if ap is None:
                    return msg
                availBoxes = []
                boxes = obj["data"]["box"]
                for box in boxes:
                    id = str(box["id"])
                    name = box.get("name", id)
                    if not box.get("enabled", 0) == 1:
                        print(f"\t{name} 没有启用")
                        continue
                    if not box.get("status", 1) == 0:
                        print(f"\t{name} 已开过 忽略")
                        continue
                    availBoxes += [{"id": id, "name": name}]
                msg += [{"name": "可开宝箱",
                         "value": f"{len(availBoxes)}/{len(boxes)}个"}]
                print(f'可开宝箱: {len(availBoxes)}/{len(boxes)}个')
                for box in availBoxes:
                    randomSleep(max=3)
                    msg += self.__openBox(box["id"], box["name"])
            else:
                msg += [{"name": "开宝箱失败",
                         "value": f'code:{obj["code"]}, msg:{obj["msg"]}'}]
                print(f'开宝箱失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            print(f"获取宝箱异常: {e}")
            msg += [{"name": "获取宝箱异常", "value": f"请检查接口 {e}"}]
        return msg

    def giftDraw(self):
        """
        礼盒抽奖
        """
        msg = []
        rewards = self.__getRewardList()
        try:
            obj = self.__postRequest(self.activity_url_openBag)
            if obj["code"] == "0000":
                materialCode = obj["data"]["materialCode"]
                for reward in rewards:
                    if reward["code"] == materialCode:
                        # 中奖
                        msg += [{"name": "\t礼盒抽中",
                                 "value": f'{reward["name"]} 请到App中查收'}]
                        print(f'\t礼盒抽中: {reward["name"]} 请到App中查收')
                        break
            else:
                msg += [{"name": "\t抽奖失败",
                         "value": f'code:{obj["code"]}, msg:{obj["msg"]}'}]
                print(f'\t抽奖失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            print(f"\t抽奖异常: {e}")
            msg += [{"name": "\t抽奖异常", "value": f"请检查接口 {e}"}]
        return msg

    def __getCheckinInfo(self):
        try:
            obj = self.__postRequest(self.activity_url_getinfo)
            if obj["code"] == "0000":
                return obj["data"]
            else:
                print(f'获取签到失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            print(f"获取签到异常: {e}")
        return {}

    def __resetCard(self, id):
        """
        重置剧本
        """
        try:
            obj = self.__postRequest(
                self.activity_url_reflashCard, f"cardDetailId={id}")
            if obj["code"] == "0000":
                print(f'重置剧本{id}成功')
                return True
            else:
                print(f'重置剧本{id}失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            print(f"重置剧本{id}异常: {e}")
        return False

    def getSignInfo(self):
        """
        获取当前签到的信息

        :return: (msg, 是否能抽奖)
        """
        msg = []
        canDraw = False
        try:
            data = self.__getCheckinInfo()
            signDetailList = data.get("signDetailList", [])
            if len(signDetailList) > 0:
                continueDays = str(signDetailList[0].get("continueDays", "-1"))
                msg += [{"name": "已连续签到", "value": f"{continueDays}天"}]
            while data.get("canOpenBag") == False and int(data.get("diceCount", 0)) > 0:
                # 剧本不满足抽奖条件，但可以用骰子重置剧本
                msg += [{"name": "当前骰子", "value": f'{data.get("diceCount")}个'}]
                print(f'当前骰子: {data.get("diceCount")}个')
                randomSleep(max=3)
                resetSucc = False
                for card in data.get("cardDetailList", []):
                    if card.get("showDice") == True:
                        # 这个剧本可以用骰子换一个
                        resetSucc = self.__resetCard(card["id"])
                        break
                msg += [{"name": "重置剧本", "value": "成功" if resetSucc else "失败"}]
                if resetSucc:
                    # 如果重置成功 则再循环一次判断
                    data = self.__getCheckinInfo()
                else:
                    # 重置失败 放弃
                    break
            if data.get("canOpenBag") == True and data.get("isOpenBag") == False:
                # 本周没有抽过，可以抽奖
                canDraw = True
            msg += [{"name": "是否可抽奖", "value": "是" if canDraw else "否"}]
            print(f'是否可抽奖: {"是" if canDraw else "否"}')
        except Exception as e:
            print(f"获取签到异常: {e}")
            msg += [{"name": "获取签到异常", "value": f"请检查接口 {e}"}]

        return msg, canDraw

    def vipSignIn(self):
        """
        VIP打卡

        """
        msg = []
        try:
            obj = self.__postRequest(self.vip_url_clock)
            if obj["code"] == "0000":
                msg += [{"name": "每日打卡",
                         "value": f'成功 当前V力值{obj["data"]["changedValue"]}'}]
                print(f'打卡成功: 当前V力值:{obj["data"]["changedValue"]}')
            else:  # 9999 重复打卡
                msg += [{"name": "打卡失败",
                         "value": f'code:{obj["code"]}, msg:{obj["msg"]}'}]
                print(f'打卡失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            print(f"打卡异常: {e}")
            msg += [{"name": "打卡异常", "value": f"请检查接口 {e}"}]
        return msg

    def signIn(self):
        """
        签到

        0点容易失败 避开签到高峰
        """
        msg = []
        try:
            obj = self.__postRequest(self.activity_url_sign, "dayOffset=0")
            if obj["code"] == "0000":  # 8650应该是补签成功的返回码 8751是补签条件不满足
                msg += [{"name": "每日签到", "value": f"成功"}]
                print("签到成功")
                data = obj["data"]
                # 剧本
                for card in data.get("cardList", []):
                    msg += [{"name": "获得剧本",
                             "value": f'{card.get("type")} {card.get("name")} '}]
                # 经验值
                for jyz in data.get("jyzList", []):
                    msg += [{"name": "签到奖励", "value": f"经验值+{jyz}"}]
                # 每周连续签到第3、6天将分别获得一个骰子
                # 应该和jyzList一样是数值
                for dice in data.get("diceList", []):
                    msg += [{"name": "签到奖励", "value": f"骰子+{dice}"}]
                # 这是签到获得的勋章
                for medal in data.get("medalList", []):
                    print(str(medal))
                    # 至少目前客户端是这样写死只有小蜜蜂
                    msg += [{"name": "签到奖励", "value": "勋章 小蜜蜂7天"}]
            elif obj["code"] == "8750":
                msg += [{"name": "重复签到", "value": f"忽略"}]
                print("重复签到")
            else:
                msg += [{"name": "签到失败",
                         "value": f'code:{obj["code"]}, msg:{obj["msg"]}'}]
                print(f'签到失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            print(f"签到异常: {e}")
            msg += [{"name": "签到异常", "value": f"请检查接口 {e}"}]
        return msg

    def main(self):
        msg = []
        try:
            self.token: str = self.check_item.get("token", "")
            if not self.token.startswith('rrtv-'):
                raise ValueError('token配置有误 必须rrtv-开头')
            msg += self.signIn()
            # 无论签到是否成功，我们继续执行，也许能抽奖
            info_msg, canDraw = self.getSignInfo()
            msg += info_msg
            if canDraw == True:
                # 可以抽奖
                randomSleep()
                msg += self.giftDraw()
            # 尝试开宝箱
            randomSleep()
            msg += self.openAllBoxes()
            # 尝试VIP打卡
            randomSleep()
            msg += self.vipSignIn()
        except Exception as e:
            print(f"失败: 请检查接口{e}")
            msg += [{"name": "失败", "value": f"请检查接口 {e}"}]
        msg = "\n".join(
            [f"{one.get('name')}: {one.get('value')}" for one in msg])
        return msg


@check(run_script_name="多多视频", run_script_expression="rrtv")
def main(*args, **kwargs):
    return RRTV(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
