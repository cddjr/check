# -*- coding: utf-8 -*-
"""
cron: 10 8,22 * * *
new Env('多多视频');
"""
from utils import check, randomSleep, log
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests


class RRTV:
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

    def __postRequest(self, url: str, data=None, json=None):
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
            "Connection": "keep-alive"
        }
        response: requests.Response = self.session.post(
            url=url, headers=headers, data=data, json=json)
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
                log("礼盒中的奖品列表")
                for reward in obj.get("data", []):
                    code = reward.get("code", "unknown")
                    name = f'{reward.get("text1")}{reward.get("text2")}'
                    rewards += [{"code": code, "name": name}]
                    log(f'- {name}')
            else:
                log(f'获取奖品列表失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            log(f'获取奖品列表异常: {e}')
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
                self.taskcenter_url_openbox, data={"boxId": id})
            if obj["code"] == "0000":
                box = obj["data"]["boxs"][0]
                reward = f'{box.get("rewardName")}+{box.get("rewardNum")}'
                log(f'- 开{name}: {reward}', msg)
            else:
                log(f'- 开{name}失败: code:{obj["code"]}, msg:{obj["msg"]}', msg)
        except Exception as e:
            log(f'- 开{name}异常: 请检查接口 {e}', msg)
        return msg

    def openAllBoxes(self):
        """
        开启所有可开的宝箱
        """
        msg = []
        empty = False
        try:
            obj = self.__postRequest(self.taskcenter_url_listbox)
            if obj["code"] == "0000":
                ap = obj["data"]["activePoint"]
                log(f'今日活跃度: {ap}', msg)
                if ap is None:
                    return msg
                availBoxes = []
                boxes = obj["data"]["box"]
                for box in boxes:
                    id = str(box["id"])
                    name = box.get("name", id)
                    if not box.get("enabled", 0) == 1:
                        log(f'- {name} 没有启用')
                        continue
                    if not box.get("status", 1) == 0:
                        log(f'- {name} 已开过 忽略')
                        continue
                    availBoxes += [{"id": id, "name": name}]
                log(f'可开宝箱: {len(availBoxes)}/{len(boxes)}个', msg)
                for box in availBoxes:
                    randomSleep(max=3)
                    msg += self.__openBox(box["id"], box["name"])
                empty = not availBoxes
                msg += ['\n']  # md缩进后需要一个换行结束缩进
            else:
                log(f'开宝箱失败: code:{obj["code"]}, msg:{obj["msg"]}', msg)
        except Exception as e:
            log(f'获取宝箱异常: 请检查接口 {e}', msg)
        return (msg, empty)

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
                        log(f'- 礼盒抽中: {reward["name"]} 请到App中查收', msg)
                        break
            else:
                log(f'- 抽奖失败: code:{obj["code"]}, msg:{obj["msg"]}', msg)
        except Exception as e:
            log(f'- 抽奖异常: 请检查接口 {e}', msg)
        return msg

    def __getCheckinInfo(self):
        try:
            obj = self.__postRequest(self.activity_url_getinfo)
            if obj["code"] == "0000":
                return obj["data"]
            else:
                log(f'获取签到信息失败: code:{obj["code"]}, msg:{obj["msg"]}')
        except Exception as e:
            log(f'获取签到信息异常: {e}')
        return {}

    def __resetCard(self, id):
        """
        重置剧本
        """
        msg = []
        try:
            obj = self.__postRequest(
                self.activity_url_reflashCard, data={"cardDetailId": id})
            if obj["code"] == "0000":
                log(f'- 重置剧本{id}成功', msg)
                return True, msg
            else:
                log(f'- 重置剧本{id}失败: code:{obj["code"]}, msg:{obj["msg"]}', msg)
        except Exception as e:
            log(f'- 重置剧本{id}异常: {e}', msg)
        return False, msg

    def getSignInfo(self):
        """
        获取当前签到的信息

        :return: (msg, 是否能抽奖)
        """
        msg = []
        canDraw = False
        try:
            weekNum = -1
            data = self.__getCheckinInfo()
            signDetailList = data.get("signDetailList", [])
            if len(signDetailList) > 0:
                continueDays = str(signDetailList[0].get("continueDays", "-1"))
                log(f'已连续签到: {continueDays}天', msg)
                weekNum = int(signDetailList[0].get('weekNum', 0))
            else:
                # 本周没有签到
                pass
            log(f'当前骰子: {data.get("diceCount")}个', msg)
            while weekNum == 7 and data.get("canOpenBag") == False and int(data.get("diceCount", 0)) > 0:
                # 剧本不满足抽奖条件，但可以用骰子重置剧本
                randomSleep(max=3)
                resetSucc = False
                for card in data.get("cardDetailList", []):
                    if card.get("showDice") == True:
                        # 这个剧本可以用骰子换一个
                        resetSucc, resetMsg = self.__resetCard(card["id"])
                        msg += resetMsg
                        break
                if not resetSucc:
                    break
                # 重置成功 则再循环一次判断
                data = self.__getCheckinInfo()
                log(f'- 剩余骰子: {data.get("diceCount")}个', msg)
            canOpenBag = data.get("canOpenBag")
            isOpenBag = data.get("isOpenBag")
            if canOpenBag == True:
                if isOpenBag == False:
                    # 本周礼盒可以抽奖了
                    canDraw = True
                    log('本周礼盒: 可以抽奖', msg)
                else:
                    log('本周礼盒: 开过的旧盒子', msg)
            else:
                log('本周礼盒: 尚未获得', msg)
        except Exception as e:
            log(f'解析签到异常: 请检查接口 {e}', msg)

        return msg, canDraw

    def vipSignIn(self):
        """
        VIP打卡

        """
        msg = []
        try:
            obj = self.__postRequest(self.vip_url_clock)
            if obj["code"] == "0000":
                log(f'打卡成功: 当前V力值{obj["data"]["changedValue"]}', msg)
            elif obj["code"] == "9999":
                log('重复打卡: 忽略', msg)
            else:
                log(f'打卡失败: code:{obj["code"]}, msg:{obj["msg"]}', msg)
        except Exception as e:
            log(f'打卡异常: 请检查接口 {e}', msg)
        return msg

    def signIn(self):
        """
        签到

        0点容易失败 避开签到高峰
        """
        msg = []
        repeated = False
        try:
            obj = self.__postRequest(self.activity_url_sign, {"dayOffset": 0})
            if obj["code"] == "0000":  # 8650应该是补签成功的返回码 8751是补签条件不满足
                log(f'每日签到: 成功', msg)
                data = obj["data"]
                # 剧本
                for card in data.get("cardList", []):
                    log(f'获得剧本: {card.get("type")} {card.get("name")}', msg)
                # 经验值
                for jyz in data.get("jyzList", []):
                    log(f'签到奖励: 经验值+{jyz}', msg)
                # 每周连续签到第3、6天将分别获得一个骰子
                for dice in data.get("diceList", []):
                    log(f'签到奖励: 骰子+{dice}', msg)
                # 这是签到获得的勋章
                for medal in data.get("medalList", []):
                    log(str(medal))
                    # medal == '2_7'
                    # 至少目前客户端是这样写死只有小蜜蜂
                    log('签到奖励: 勋章 小蜜蜂7天', msg)
            elif obj["code"] == "8750":
                log('重复签到: 忽略', msg)
                repeated = True
            else:
                log(f'签到失败: code:{obj["code"]}, msg:{obj["msg"]}', msg)
        except Exception as e:
            log(f'签到异常: 请检查接口 {e}', msg)
        return (msg, repeated)

    def main(self):
        msg = []
        try:
            self.token: str = self.check_item.get("token", "")
            if not self.token.startswith('rrtv-'):
                raise SystemExit('token配置有误 必须rrtv-开头')
            sign_msg, sign_repeated = self.signIn()
            msg += sign_msg
            # 无论签到是否成功，我们继续执行，也许能抽奖
            info_msg, canDraw = self.getSignInfo()
            msg += info_msg
            if canDraw == True:
                # 可以抽奖
                randomSleep()
                msg += self.giftDraw()
            # 尝试开宝箱
            randomSleep()
            boxes_msg, boxes_empty = self.openAllBoxes()
            msg += boxes_msg
            # 尝试VIP打卡
            randomSleep()
            vsign_msg, vsign_repeated = self.vipSignIn()
            msg += vsign_msg
            if all([sign_repeated, vsign_repeated, not canDraw, boxes_empty]):
                exit()  # 目前没必要执行后续的操作
        except Exception as e:
            log(f'失败: 请检查接口{e}', msg)
        msg = "\n".join(msg)
        return msg


@check(run_script_name="多多视频", run_script_expression="rrtv")
def main(*args, **kwargs):
    return RRTV(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
