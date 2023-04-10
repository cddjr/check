from asyncio import gather as aio_gather
from asyncio import sleep as aio_sleep
from os import path
from random import randint
from sys import version_info as py_version
from time import time
from typing import Any, Optional, Union  # 确保兼容<=Python3.9

import json_codec
from aiohttp import ClientResponse
from aiohttp_retry import JitterRetry, RetryClient

from pupu_types import *
from utils import GetScriptConfig, log

assert py_version >= (3, 9)

server_date_diff = None
server_date_updating = False


class ApiBase(object):

    # __slots__ = ("__session", "__receiver")

    def __init__(self, device_id: str):
        assert device_id
        self.__device_id = device_id.upper()
        self.__su_id = self.__access_token = self.__user_id = None
        self.__receiver = PReceiverInfo("")
        self.__init_http()

    def __init_http(self):
        async def RetryWhenBusy(resp: ClientResponse) -> bool:
            obj = await resp.json()
            code = obj.get("errcode") or 0
            msg = obj.get("errmsg") or ""
            if code == -1 and "稍后再试" in msg:
                # 系统繁忙，请稍后再试。
                return False
            return True
        self.__session = RetryClient(raise_for_status=True,
                                     retry_options=JitterRetry(attempts=3, evaluate_response_callback=RetryWhenBusy))
        self.__session._client.headers["Accept"] = "application/json, text/plain, */*"
        self.__session._client.headers["Accept-Encoding"] = "gzip, deflate"
        self.__session._client.headers["Accept-Language"] = "zh-CN,zh-Hans;q=0.9"
        self.__session._client.headers["pp-version"] = "2023010301"
        self.__session._client.headers["Connection"] = "keep-alive"

    async def Release(self):
        if self.__session._closed:
            return
        await self.__session.close()
        # Wait 250 ms for the underlying SSL connections to close
        await aio_sleep(0.250)

    @property
    def native_user_agent(self):
        if self.__device_id:
            id = f";{self.__device_id}"
        else:
            id = ""
        return f"Pupumall/3.2.3;iOS 15.7.1{id}"

    @property
    def web_user_agent(self):
        if self.__device_id:
            id = f" D/{self.__device_id}"
        else:
            id = ""
        return f"Mozilla/5.0 (iPhone; CPU iPhone OS 15_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148{id}"

    @property
    def access_token(self):
        return self.__access_token

    @access_token.setter
    def access_token(self, token: Optional[str]):
        self.__access_token = token
        if token:
            self.__session._client.headers["Authorization"] = f"Bearer {token}"
        elif "Authorization" in self.__session._client.headers:
            del self.__session._client.headers["Authorization"]

    @property
    def device_id(self):
        return self.__device_id

    @property
    def su_id(self):
        return self.__su_id

    @su_id.setter
    def su_id(self, id: Optional[str]):
        self.__su_id = id
        if id:
            self.__session._client.headers["pp-suid"] = id
        elif "pp-suid" in self.__session._client.headers:
            del self.__session._client.headers["pp-suid"]

    @property
    def user_id(self):
        return self.__user_id

    @user_id.setter
    def user_id(self, id: Optional[str]):
        self.__user_id = id
        if id:
            self.__session._client.headers["pp-userid"] = id
        elif "pp-userid" in self.__session._client.headers:
            del self.__session._client.headers["pp-userid"]

    @property
    def receiver(self):
        return self.__receiver

    @receiver.setter
    def receiver(self, receiver: PReceiverInfo):
        self.__receiver = receiver
        if receiver.place_id:
            self.__session._client.headers["pp-placeid"] = receiver.place_id
        elif "pp-placeid" in self.__session._client.headers:
            del self.__session._client.headers["pp-placeid"]
        if receiver.store_id:
            # 朴朴这里用的下划线
            self.__session._client.headers["pp_storeid"] = receiver.store_id
        elif "pp_storeid" in self.__session._client.headers:
            del self.__session._client.headers["pp_storeid"]

    async def GetServerTime(self, force=False):
        """获得与服务器尽可能一致的时间戳"""
        global server_date_diff, server_date_updating
        while server_date_updating:
            await aio_sleep(0)
        if server_date_diff is None or force:
            try:
                server_date_updating = True
                result = await self.ComputeServerTimeDiff()
            finally:
                server_date_updating = False
            if isinstance(result, ApiResults.Error):
                log(result)
                if server_date_diff is None:
                    return int(time()*1000)
            else:
                server_date_diff = result
        return int(time()*1000 + server_date_diff)

    @staticmethod
    def TryGetServerTime():
        """类似GetServerTime"""
        global server_date_diff
        if server_date_diff is not None:
            return int(time()*1000 + server_date_diff)
        return None

    async def ComputeServerTimeDiff(self):
        """计算本地时间与服务器时间的时间差"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/base/data",
                client=ClientType.kWeb,
                headers={"Origin": "https://ma.pupumall.com",
                         "Referer": "https://ma.pupumall.com/"}
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                if "server_time" not in data:
                    raise ValueError("server_time 没了")
                server_time = int(data["server_time"])
                diff = server_time - int(time() * 1000)
                if diff > 1000:
                    log(f"注意: 本地时间与服务器相差{diff/1000}秒")
                return diff
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def _SendRequest(self, method: HttpMethod, url: str,
                           client=ClientType.kNative,
                           headers: Optional[dict] = None,
                           params: Optional[dict] = None, data=None, json=None):
        """发起一个HTTP请求"""
        req_headers = {}
        if client == ClientType.kNative:
            req_headers["User-Agent"] = self.native_user_agent
            req_headers["pp-os"] = "20"  # "0" for wechat
            if self.__receiver.place_zip:
                req_headers["pp-placezip"] = str(self.__receiver.place_zip)
        elif client == ClientType.kWeb:
            req_headers["User-Agent"] = self.web_user_agent
            req_headers["pp-os"] = "201"
            if self.__receiver.city_zip:
                req_headers["pp-cityzip"] = str(self.__receiver.city_zip)
        else:
            raise NotImplementedError
        if headers:
            req_headers.update(headers)
        async with self.__session.request(
            ssl=False, method=method.value, url=url, headers=req_headers,
            params=params, data=data, json=json
        ) as response:
            # server_date = response.headers.getone("Date", None)
            # if server_date:
            #    from datetime import datetime
            #    from email.utils import parsedate
            #    parsedate(server_date)
            return await response.json()


class Api(ApiBase):

    def __init__(self, device_id: str, refresh_token: str,
                 access_token: Optional[str], expires_in: Optional[int]):
        if not (device_id and refresh_token):
            raise ValueError("参数没有正确设置")
        super().__init__(device_id=device_id)
        self.__refresh_token: Optional[str] = refresh_token
        self._nickname = self._avatar = None
        self.__expires_in = expires_in or 0
        self.access_token = access_token

    @property
    def nickname(self) -> Optional[str]:
        return self._nickname

    @property
    def avatar(self) -> Optional[str]:
        return self._avatar

    @property
    def refresh_token(self):
        return self.__refresh_token

    @refresh_token.setter
    def refresh_token(self, token: Optional[str]):
        self.__refresh_token = token

    @property
    def expires_in(self):
        return self.__expires_in

    @expires_in.setter
    def expires_in(self, v: Optional[int]):
        self.__expires_in = v or 0

    async def RefreshAccessToken(self):
        """刷新AccessToken 有效期通常只有2小时"""
        initial_tasks: list[Any] = [self.GetServerTime()]
        if not self.su_id:
            initial_tasks.append(self.GetSuID())
        current_time = (await aio_gather(*initial_tasks))[0]
        if self.access_token and current_time + 360_000 < self.expires_in:
            # access_token 有效
            return ApiResults.TokenValid()
        self.access_token = None
        self.user_id = None
        try:
            if not self.__refresh_token:
                raise ValueError("没有配置 refresh_token")
            obj = await self._SendRequest(
                HttpMethod.kPut,
                "https://cauth.pupuapi.com/clientauth/user/refresh_token",
                json={"refresh_token": self.__refresh_token}
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                self.access_token = data.get("access_token")
                self.user_id = data.get("user_id")
                # refresh_token 在临期时会更新 我们需要保存新的token 否则很快就得重新登录
                prev_refresh_token = self.__refresh_token
                self.__refresh_token = data.get(
                    "refresh_token") or self.__refresh_token
                self.__expires_in = int(data.get('expires_in') or 0)
                self._nickname = data.get("nick_name")
                return ApiResults.TokenRefreshed(refresh_token=self.__refresh_token,
                                                 access_expires=self.__expires_in,
                                                 changed=self.__refresh_token != prev_refresh_token)
            else:
                if obj["errcode"] == 403 \
                        or (obj["errcode"] != 200099 and obj["errcode"] in range(200000, 300000)):
                    self.__refresh_token = None
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetSuID(self):
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/caccount/user/suid",
                params={"device_id": self.device_id}
            )
            if obj["errcode"] == 0:
                self.su_id = obj["data"]
                return ApiResults.SuId(id=self.su_id)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetUserInfo(self):
        """
        获得自己的头像、手机、昵称
        "user_id": "xxxx-xx-xx-xx-xxxxxx",
        "nick_name": "xxxx",
        "sex": 0,
        "phone": "13800138000",
        "avatar": "https://imgs.static.pupumall.com/NEW_AVATAR_PIC/xxxxx.jpeg",
        "zip": 0,
        "is_novice": false,
        "time_create": 1638444954328,
        "invite_code": "xxxx-xx-xx-xx-xxxxxx",
        "can_delete": false,
        "is_deleted": false
        """
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://cauth.pupuapi.com/clientauth/user/info"
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                self._avatar = data.get("avatar")
                self._nickname = data.get("nick_name")
                return ApiResults.UserInfo(avatar=self._avatar, nickname=self._nickname)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def UpdateReceiver(self, filter: Optional[str] = None):
        """获得收货地址"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/account/receivers"
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                time_last_order: int = -1
                info = None
                for r in data:
                    # r["is_in_service"] 意味地址是否可以配送
                    if r.get("is_default") or int(r.get("time_last_order") or 0) > time_last_order:
                        time_last_order = int(r.get("time_last_order") or 0)
                        place = r["place"]
                        info = PReceiverInfo(
                            id=str(r["id"]),
                            address=r["address"], room_num=r["building_room_num"],
                            lng_x=place.get("lng_x") or r["lng_x"],
                            lat_y=place.get("lat_y") or r["lat_y"],
                            receiver_name=r["name"], phone_number=r["mobile"],
                            store_id=place.get(
                                "service_store_id") or r["service_store_id"],
                            place_id=place["id"],
                            city_zip=place.get("store_city_zip") or 0
                        )
                        self.user_id = r.get("user_id") or self.user_id
                        info.place_zip = int(place.get("zip") or info.city_zip)

                        building_name = None
                        room_num = r.get("room_num")
                        if place.get("have_building", False):
                            place_building = r.get("place_building")
                            if place_building and place_building.get("is_deleted", False) == False:
                                building_name = place_building.get(
                                    "building_name")
                        if building_name and room_num:
                            info.room_num = f'{building_name} {room_num}'

                        if filter:
                            # 配置了地址过滤
                            if info.address.find(filter) != -1:
                                # 匹配上了
                                break
                            info = None  # 不符合筛选条件 需要置空
                            time_last_order = 0
                        elif r.get("is_default"):
                            # 如果是默认地址则直接用(似乎朴朴并没有设置)
                            break
                if not info:
                    if filter:
                        raise ValueError(f"没有符合筛选条件的收货地址, 当前条件`{filter}`")
                    else:
                        raise ValueError("没有收货地址")
                self.receiver = info
                return ApiResults.ReceiverInfo(info)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def SignIn(self):
        """签到"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                "https://j1.pupuapi.com/client/game/sign/v2",
                params={"city_zip": self.receiver.city_zip,
                        "supplement_id": ""},
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                data = obj["data"]
                # 朴分
                return ApiResults.SignIn(coin=data["daily_sign_coin"],
                                         explanation=data["reward_explanation"])
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetSignPeriodInfo(self):
        """获得本周连续签到的天数"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/game/sign/period_info"
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                return ApiResults.SignPeriodInfo(data["signed_days"])
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetCoinConfig(self):
        """朴分下单抽大奖"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/coin/unclaimed/config"
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                return str(data["lottery_id"])
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetCoinList(self):
        """可领取的朴分IDs"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/coin/unclaimed/list"
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                return [str(item["id"]) for item in data]
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def DrawCoin(self, id: str):
        """领取朴分"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                f"https://j1.pupuapi.com/client/coin/unclaimed/{id}"
            )
            # obj["errcode"] == 400000 # 已领取
            if obj["errcode"] == 0:
                data = obj["data"]
                return int(data["coin"])
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetBanner(self, link_type: BANNER_LINK_TYPE, position_types: Optional[list[Union[int, str]]] = None):
        assert not self.receiver.id_empty
        try:
            co_req = self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/marketing/banner/v7",
                params={"position_types": ",".join(str(p) for p in position_types) if position_types else -1,
                        "store_id": self.receiver.store_id})
            now, obj = await aio_gather(self.GetServerTime(), co_req)
            if obj["errcode"] == 0:
                link_ids = set[str]()
                banners = []
                data = obj["data"]
                for item in data:
                    if "link_type" in item \
                            and BANNER_LINK_TYPE(item["link_type"]) == link_type:
                        time_open = item.get("time_open") or 0
                        time_close = item.get("time_close") or (now + 60_000)
                        if now < time_open or now + 60_000 > time_close:
                            # 不在效期内 忽略
                            continue
                        link_id = item.get("link_id")
                        if link_id not in link_ids:
                            # 避免重复
                            link_ids.add(link_id)
                            banners.append(PBanner(
                                title=item.get("title") or item.get("name"),
                                link_id=link_id,
                            ))
                return ApiResults.Banner(banners)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetLotteryInfo(self, id: str):
        """获取抽奖活动的信息"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{id}/element_configuration",
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                data = obj["data"]
                lottery = PLotteryInfo(
                    id=id,
                    name=data["activity_name"],  # 开运新年签
                    type=LOTTERY_TYPE(data["lottery_type"]),
                )
                for prize in data.get("prize_info") or []:
                    # 解析奖品
                    if "prize_level" in prize and "prize_type" in prize \
                            and "prize_name" in prize:
                        p = PPrize(level=prize["prize_level"],
                                   name=prize["prize_name"],
                                   type=RewardType(prize["prize_type"]))
                        lottery.prizes[p.level] = p
                task_system_link = data.get("task_system_link") or {}
                lottery.task_system_link_id = task_system_link.get("link_id")
                if lottery.task_system_link_id:
                    link_type = BANNER_LINK_TYPE(task_system_link["link_type"])
                    if link_type != BANNER_LINK_TYPE.USER_TASK:
                        print(f"警告: 抽奖任务遇到了不识别的link_type '{link_type.name}'")
                        lottery.task_system_link_id = None
                return ApiResults.LotteryInfo(lottery)
            else:
                # 获取抽奖信息失败
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetUserLotteryInfo(self, lottery: PLotteryInfo):
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{lottery.id}/user_chances",
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                num = obj["data"].get("remain_chance_num") or 0
                return ApiResults.UserLotteryInfo(remain_chances=num)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetTaskGroupsData(self, lottery: Union[PLotteryInfo, PCollectCardRule]):
        """获取任务列表"""
        task_id = lottery.task_system_link_id if isinstance(
            lottery, PLotteryInfo) else lottery.card_get_task_id
        if not task_id:
            return ApiResults.TaskGroupsData([])
        try:
            tasks: list[PTask] = []
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/task_system/user_tasks/task_groups/{task_id}",
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                data = obj["data"]
                tasks_json: list = data.get("tasks") or []
                for task_json in tasks_json:
                    page_task_rule = task_json.get("page_task_rule")
                    if not page_task_rule:
                        # 忽略非浏览型任务
                        continue
                    if "task_status" not in page_task_rule:
                        continue
                    # if page_task_rule["action_type"] != ActionTYPE.BROWSE:
                    #    continue
                    tasks.append(PTask(
                        task_name=task_json["task_name"],
                        task_id=page_task_rule["task_id"],
                        skim_time=page_task_rule["skim_time"],
                        activity_id=page_task_rule["activity_id"],
                        task_type=TaskType(
                            page_task_rule["task_type"]),
                        action_type=ActionTYPE(
                            page_task_rule["action_type"]),
                        task_status=TaskStatus(
                            page_task_rule["task_status"]),
                    ))
                return ApiResults.TaskGroupsData(tasks)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def PostPageTaskComplete(self, task: PTask):
        """完成浏览任务"""
        # 此任务从何时完成
        time_end: int = await self.GetServerTime() - randint(1, 8) * 1000
        # 此任务从何时开始
        time_from: int = time_end - task.skim_time * 1000 - randint(1, 20)

        json = {
            "activity_id": task.activity_id,
            "task_type": task.task_type,
            "action_type": task.action_type,
            "task_id": task.task_id,
            "time_from": time_from,
            "time_end": time_end}
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                "https://j1.pupuapi.com/client/game/task_system/user_tasks/page_task_complete",
                json=json,
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                return ApiResults.TaskCompleted()
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetChanceEntrances(self, lottery: PLotteryInfo):
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{lottery.id}/obtain_chance_entrance",
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                data = obj["data"]
                coin_balance = int(data.get("coin_balance") or 0)
                entrances: list[PChanceEntrance] = []
                for item in data.get("chance_obtain_entrance") or []:
                    if "code" in item and "attend_count" in item \
                            and "limit_count" in item and "gain_num" in item \
                            and "target_value" in item:
                        pitem = PChanceEntrance(
                            type=CHANCE_OBTAIN_TYPE(item["code"]),
                            title=item.get("title") or "未知",
                            attend_count=item["attend_count"],
                            limit_count=item["limit_count"],
                            target_value=int(item["target_value"]),
                            gain_num=int(item["gain_num"]))
                        if pitem.attend_count >= pitem.limit_count:
                            # 达到限制量 跳过
                            print(f" {pitem.title} 达到限制 {pitem.limit_count} 跳过")
                            continue
                        entrances.append(pitem)
                return ApiResults.ChanceEntrances(coin_balance, entrances)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def CoinExchange(self, lottery: PLotteryInfo, entrance: PChanceEntrance):
        """开始朴分兑换"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{lottery.id}/coin_exchange",
                params={"lng_x": self.receiver.lng_x,
                        "lat_y": self.receiver.lat_y},
                json={},
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                entrance.attend_count += 1
                return ApiResults.CoinExchanged(entrance.gain_num)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def Lottery(self, lottery: PLotteryInfo):
        """开始抽奖"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{lottery.id}/lottery",
                params={"lng_x": self.receiver.lng_x,
                        "lat_y": self.receiver.lat_y},
                json={},
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                prize = lottery.prizes[obj["data"]["prize_level"]]
                return ApiResults.LotteryResult(prize)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetProductCollections(self, page: int, page_size: int = 10):
        """获取商品收藏列表"""
        assert not self.receiver.id_empty
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/user_behavior/product_collection/store/{self.receiver.store_id}/products",
                params={"page": page, "size": page_size}
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                products = []
                # 总共收藏了{total_count}件商品
                total_count: int = data.get("count") or 0
                for p in data.get("products") or []:
                    # TODO 若 p["sell_batches"] 不为空，则以该数组的最低价作为当前价格
                    product = PProduct(
                        name=p["name"],
                        price=p["price"],
                        product_id=p["product_id"],
                        store_product_id=p["id"],
                        purchase_type=PURCHASE_TYPE(
                            p.get("purchase_type") or PURCHASE_TYPE.GENERAL),
                        spread_tag=SPREAD_TAG(
                            p.get("spread_tag") or SPREAD_TAG.NORMAL_PRODUCT),
                        stock_quantity=p.get("stock_quantity") or 0,
                        order_remarks=p.get("order_remarks") or [],
                    )
                    if product.spread_tag == SPREAD_TAG.FLASH_SALE_PRODUCT:
                        flash_sale_info = p.get("flash_sale_info") or {}
                        progress_rate: float = flash_sale_info.get(
                            "progress_rate") or 0.0
                        if flash_sale_info and progress_rate < 1.0:
                            # 限购N件
                            product.quantity_limit = flash_sale_info.get(
                                "quantity_each_person_limit") or 1
                    products.append(product)
                return ApiResults.ProductCollections(total_count, products)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetUsableCoupons(self,  type: DiscountType, products: list[PProduct]):
        """获得可用的优惠券"""
        assert not self.receiver.id_empty
        try:
            order_items = []
            for pi in products:
                obj = {
                    "price": pi.price,
                    "product_id": pi.product_id,
                    "batch_id": "",
                    "discount_type": DiscountType.ABSOLUTE,  # TODO
                    "store_product_id": pi.store_product_id,
                    "from_module": 0,
                    "is_gift": False,
                    "activity_ids": [],
                    "spread_tag": pi.spread_tag,
                    "count": pi.selected_count,
                    "remark": pi.remark,
                    "gift_belong_to_store_product_ids": []
                }
                order_items.append(obj)
            json = {
                "place_id": self.receiver.place_id,
                "place_zip": self.receiver.place_zip,
                "receiver_id": self.receiver.id,
                "store_id": self.receiver.store_id,
                "order_items": order_items,
            }
            obj = await self._SendRequest(
                HttpMethod.kPost,
                "https://j1.pupuapi.com/client/account/discount",
                params={"discount_type": type},
                json=json
            )
            if obj["errcode"] == 0:
                ids = []
                rules = []
                data = obj["data"]
                if data.get("count"):
                    best_discount = data.get("best_discount") or {}
                    id = best_discount.get("id")
                    rule = best_discount.get("rule") or {}
                    if id:
                        # 超时赔付券，券前金额满8减8元；
                        # content:None|str = rule.get("content")
                        ids.append(id)
                        rules.append(PDiscountRule(
                            id=rule.get("discount_id") or "",
                            type=DiscountType(
                                rule.get("discount_type") or DiscountType.ABSOLUTE),
                            condition_amount=rule.get("condition_amount") or 0,
                            discount_amount=rule.get("discount_amount") or 0))
                return ApiResults.UsableCoupons(coupons=ids, rules=rules)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetDeliveryTime(self, products: list[PProduct], start_hours: int):
        assert not self.receiver.id_empty
        try:
            json = []
            for pi in products:
                obj = {
                    "price": pi.price,
                    "product_id": pi.product_id,
                    "batch_id": "",
                    "discount_type": DiscountType.ABSOLUTE,  # 满减?
                    "is_gift": False,
                    "count": pi.selected_count,
                }
                json.append(obj)
            co_req = self._SendRequest(
                HttpMethod.kPost,
                "https://j1.pupuapi.com/client/deliverytime/v4",
                params={"place_id": self.receiver.place_id,
                        "scene_type": 0,
                        "store_id": self.receiver.store_id},
                json=json)
            now, obj = await aio_gather(self.GetServerTime(), co_req)
            if obj["errcode"] == 0:
                dtime_type = DeliveryTimeType.IMMEDIATE
                data = obj["data"]
                dtime_log = data["delivery_time_log"]
                dtime_real = dtime_log.get("delivery_time_real") or 30
                if "reason_type" in dtime_log:
                    reason_type = DeliveryReasonType(dtime_log["reason_type"])
                    if reason_type == DeliveryReasonType.FUTURE_PRODUCTS:
                        dtime_type = DeliveryTimeType.RESERVE
                time_group: list = data["time_group"]
                date = time_group[0]["date"]  # 1673107200000
                date_start = date + time_group[0]["start_min"] * 60_000
                date_end = date + time_group[0]["end_min"] * 60_000

                cur_date = now + dtime_real * 60_000
                cur_date = min(max(cur_date, date_start), date_end)

                date_limit = min(max(date + start_hours * 3600_000, date_start) +
                                 dtime_real * 60_000, date_end)
                dtime_promise = max(cur_date, date_limit)
                return ApiResults.DeliveryTime(dtime_type, dtime_promise)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def CreateOrder(self, pay_type: int, coupons: Optional[list[str]], products: list[PProduct],
                          dtime_type: DeliveryTimeType, dtime_promise: int):
        """创建订单"""
        assert not self.receiver.id_empty and self.receiver.address and self.receiver.receiver_name
        order_items = []
        for pi in products:
            obj = {
                "activity_ids": [],
                "count": pi.selected_count,
                "is_gift": False,
                "price": pi.price,
                "product_id": pi.product_id,
                "remark": pi.remark,
                "spread_tag": pi.spread_tag,
                "store_product_id": pi.store_product_id,
            }
            order_items.append(obj)
        json = {
            "buyer_id": self.user_id,
            "coin_payment_amount": 0,
            "wallet_payment_amount": 0,
            "delivery_time_type": dtime_type,
            "device_id": self.device_id,
            "device_os": "20",
            "discount_entity_ids": coupons or [],
            "external_payment_amount": 0,  # 总金额(分) 无所谓
            "lat_y": self.receiver.lat_y or 0.0,
            "lng_x": self.receiver.lng_x or 0.0,
            "logistics_fee": 0,  # 运费(分) 似乎也无所谓
            "number_protection": 1,
            "order_items": order_items,
            "order_type": 0,
            "pay_type": pay_type,  # 15是云闪付
            "place_id": self.receiver.place_id,
            "print_order_product_ticket_info": False,  # 是否打印商品详情(所谓环保)
            "put_if_no_answer": False,  # 联系不上是否放门口
            "receiver": {
                "address": self.receiver.address,
                "building_room_num": self.receiver.room_num,
                "mobile": self.receiver.phone_number,
                "name": self.receiver.receiver_name,
                "place_building_id": "",
                "sex": 0,
            },
            "receiver_id": self.receiver.id,
            "remark": "",  # 备注
            "store_id": self.receiver.store_id,
            "time_delivery_promise": str(dtime_promise),
            "time_delivery_promise_end": str(dtime_promise),
            "time_delivery_promise_start": str(dtime_promise),
        }
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                "https://j1.pupuapi.com/client/order/unifiedorder/v2",
                json=json)
            if obj["errcode"] == 0:
                data = obj["data"]
                return ApiResults.OrderCreated(id=data["id"])
            elif dtime_type == DeliveryTimeType.IMMEDIATE and obj["errmsg"].find("重新选择"):
                # 亲，该订单期望送达时间不在我们配送时间范围内，请重新选择送达时间
                rr: Union[ApiResults.Error, ApiResults.OrderCreated] = await self.CreateOrder(
                    pay_type, coupons, products, DeliveryTimeType.RESERVE, dtime_promise)
                return rr
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetOrdersList(self, page: int):
        """获得订单列表"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/order/orders/list/v2",
                params={"page": page, "size": 20, "type": -1}
            )
            if obj["errcode"] == 0:
                orders = []
                # 总共{total_count}件订单
                total_count: int = obj.get("count") or 0
                data = obj["data"]
                for o in data:
                    order = POrder(
                        total_price=o["total_price"],
                        time_create=o["time_create"],
                    )
                    if "discount_share_style" in o:
                        share = o["discount_share_style"]
                        order.discount_share = PDiscountShare(
                            share_id=share["share_id"],
                            index=share["index"],
                            count=share["count"],
                        )
                    orders.append(order)
                return ApiResults.OrdersList(total_count, orders)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetWxDiscountShare(self, share: PDiscountShare):
        """拆微信红包"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/account/discount/wechat_index",
                params={"id": share.share_id})
            # ClientType.kMicroMsg
            if obj["errcode"] == 0:
                data = obj["data"]
                enabled: bool = data.get("enabled") or True
                status = SHARE_STATUS(data.get('status') or SHARE_STATUS.ERROR)
                best_luck: bool = data.get("best_luck") or False  # 我是否最佳
                reentry: bool = data["reentry"]  # 已领取过该优惠券了哦
                rule = data.get("rule") or {}  # 我抢到的优惠券 可能为空
                discount_id = rule.get("discount_id")
                if not discount_id:
                    # 我没抢到优惠券
                    discount_rule = None
                    if status == SHARE_STATUS.NULL:
                        # 红包已经空了
                        log(f"{share.share_id}: status = NULL")
                    elif status == SHARE_STATUS.EXPIRED:
                        # 红包过期了
                        log(f"{share.share_id}: status = EXPIRED")
                    else:
                        # 红包抢太多被限制了吗
                        over_limit: bool = data["over_limit"]
                        log(f"{share.share_id}: over_limit = {over_limit}")
                else:
                    discount_rule = PDiscountRule(
                        id=rule["discount_id"],
                        type=DiscountType(rule["discount_type"]),
                        condition_amount=rule["condition_amount"],
                        discount_amount=rule["discount_amount"],
                    )
                users = [PShareUser(
                    avatar=item.get("avatar"),
                    name=item["name"],
                    best=item["max"],
                    time=item["time"],
                ) for item in data.get("list") or []]
                return ApiResults.WxDiscountShare(
                    best_luck, reentry, users,
                    discount=discount_rule,
                    available=status == SHARE_STATUS.NORMAL and enabled)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetCollectCardRule(self):
        """获得抽卡规则"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/game/collect_card/current_rule",
                ClientType.kWeb,
            )
            if obj["errcode"] == 0:
                return json_codec.decode(obj["data"], PCollectCardRule)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetCollectCardLotteryCount(self, rule: PCollectCardRule):
        """获得抽卡次数"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/collect_card/rule/{rule.id}/lottery_count",
                ClientType.kWeb,
            )
            if obj["errcode"] == 0:
                return int(obj["data"])
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def GetCollectCardEntity(self, rule: PCollectCardRule):
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/collect_card/rule/{rule.id}/card_entity",
                ClientType.kWeb,
            )
            if obj["errcode"] == 0:
                return json_codec.decode(obj["data"], PCollectCardEntity)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def LotteryGetCard(self, rule: PCollectCardRule):
        '''抽卡'''
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/collect_card/rule/{rule.id}/lottery_get_card",
                ClientType.kWeb,
            )
            if obj["errcode"] == 0:
                return json_codec.decode(obj["data"], PCollectCard)
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def PostCompositeCard(self, rule: PCollectCardRule):
        '''合成卡片'''
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                f"https://j1.pupuapi.com/client/game/collect_card/rule/{rule.id}/composite",
                ClientType.kWeb,
            )
            if obj["errcode"] == 0:
                # TODO
                log(obj["data"])
                return obj["data"]
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()

    async def DeleteExpendCardEntity(self, card: PCollectCard):
        '''消耗卡片兑换抽奖机会'''
        try:
            assert card.rule_card_id
            obj = await self._SendRequest(
                HttpMethod.kDelete,
                f"https://j1.pupuapi.com/client/game/collect_card/rule_card/{card.rule_card_id}",
                ClientType.kWeb,
            )
            if obj["errcode"] == 0:
                # 返回抽奖活动id
                return str(obj["data"])
            else:
                return ApiResults.Error(json=obj)
        except Exception:
            return ApiResults.Exception()


class Client(Api):
    __slots__ = ("_config",
                 "_config_dict",
                 "_saved",
                 "_refresh_token_user_specified",
                 )

    def __init__(self, device_id: str, refresh_token: str):
        super().__init__(device_id, refresh_token, None, None)
        self._refresh_token_user_specified = refresh_token
        self._saved = False
        self._config = GetScriptConfig("pupu.json")
        self._config_dict = {}
        if self._config and not path.exists(self._config.config_file):
            if (old_database := GetScriptConfig("pupu")) \
                    and (keys := old_database.get_key_for_toml(old_database.config_file)):
                # 从toml迁移至json
                for k in keys:
                    v = old_database.get_value_2(k)
                    self._config.set_value(k, v)

    def LoadConfig(self, force: bool = False):
        """加载朴朴配置"""
        if not self._config:
            return False
        if not force and self._config_dict:
            return True
        self._config_dict = self._config.get_value_2(self.device_id) or {}
        refresh_token_prev_spec = self._config_dict.get(
            "refresh_token_user_specified")

        if not self._refresh_token_user_specified \
                or self._refresh_token_user_specified != refresh_token_prev_spec:
            # 说明用户手动修改了token 以用户的为准
            self.refresh_token = self._refresh_token_user_specified
        else:
            self.refresh_token = self._config_dict.get(
                "refresh_token_lastest") or self._refresh_token_user_specified

        self.access_token = self._config_dict.get("access_token")
        self.expires_in = self._config_dict.get("access_expires")

        self.user_id = self._config_dict.get("user_id")
        self.su_id = self._config_dict.get("su_id")
        self.receiver = PReceiverInfo(
            self._config_dict.get("recv_id") or "",
            store_id=self._config_dict.get("store_id") or "",
            place_id=self._config_dict.get("place_id") or "",
            city_zip=int(self._config_dict.get("city_zip") or 0),
            place_zip=int(self._config_dict.get("place_zip") or 0))

        self._nickname = self._config_dict.get("nickname")
        self._avatar = self._config_dict.get("avatar")
        return True

    def SaveConfig(self):
        if not self._config:
            return False
        self._config_dict["nickname"] = self.nickname
        self._config_dict["refresh_token_user_specified"] = self._refresh_token_user_specified
        self._config_dict["refresh_token_lastest"] = self.refresh_token
        self._config_dict["access_token"] = self.access_token
        self._config_dict["access_expires"] = self.expires_in
        self._config_dict["su_id"] = self.su_id
        self._config_dict["user_id"] = self.user_id
        self._config_dict["recv_id"] = self.receiver.id
        self._config_dict["store_id"] = self.receiver.store_id
        self._config_dict["place_id"] = self.receiver.place_id
        self._config_dict["city_zip"] = self.receiver.city_zip
        self._config_dict["place_zip"] = self.receiver.place_zip
        self._config_dict["avatar"] = self.avatar
        self._config.set_value(self.device_id, self._config_dict)
        self._saved = True
        return True

    async def InitializeToken(self, address_filter: Optional[str] = None,
                              force_update_receiver: bool = True):
        """初始化"""
        self.LoadConfig(force=True)

        token_result = await self.RefreshAccessToken()
        if isinstance(token_result, ApiResults.Error):
            return token_result
        elif isinstance(token_result, ApiResults.TokenRefreshed):
            # 确保及时保存
            self.SaveConfig()

        if force_update_receiver or self.receiver.id_empty:
            recv_result = await self.UpdateReceiver(filter=address_filter)
            if isinstance(recv_result, ApiResults.Error):
                return recv_result
        return token_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, type, value, trace):
        self.SaveConfig()
        await self.Release()

    def __del__(self):
        if getattr(self, "_saved", None) is None:
            # __init__ 出错了
            return
        if not self._saved:
            log("警告: 没有执行 SaveConfig")


if __name__ == "__main__":
    pass
