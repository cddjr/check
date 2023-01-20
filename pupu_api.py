from pupu_types import *
from utils import log, GetScriptConfig
from asyncio import sleep as aio_sleep, gather as aio_gather
from aiohttp_retry import RetryClient, JitterRetry
from random import randint
from time import time
from sys import version_info as py_version
assert py_version >= (3, 10)


class ApiBase(object):

    #__slots__ = ("__session", "__receiver")

    def __init__(self, device_id: str):
        assert device_id
        self.__device_id = device_id.upper()
        self.__su_id = self.__access_token = self.__user_id = None
        self.__receiver = None
        self.__server_date_diff = None
        self.__init_http()

    def __init_http(self):
        self.__session = RetryClient(raise_for_status=True,
                                     retry_options=JitterRetry(attempts=3))
        self.__session._client.headers["Accept"] = "application/json, text/plain, */*"
        self.__session._client.headers["Accept-Encoding"] = "gzip, deflate"
        self.__session._client.headers["Accept-Language"] = "zh-CN,zh-Hans;q=0.9"
        self.__session._client.headers["pp-version"] = "2023010301"
        self.__session._client.headers["Connection"] = "keep-alive"

    async def Release(self):
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
    def access_token(self, token: None | str):
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
    def su_id(self, id: None | str):
        self.__su_id = id
        if id:
            self.__session._client.headers["pp-suid"] = id
        elif "pp-suid" in self.__session._client.headers:
            del self.__session._client.headers["pp-suid"]

    @property
    def user_id(self):
        return self.__user_id

    @user_id.setter
    def user_id(self, id: None | str):
        self.__user_id = id
        if id:
            self.__session._client.headers["pp-userid"] = id
        elif "pp-userid" in self.__session._client.headers:
            del self.__session._client.headers["pp-userid"]

    @property
    def receiver(self):
        return self.__receiver

    @receiver.setter
    def receiver(self, receiver: None | PReceiverInfo):
        self.__receiver = receiver
        if receiver and receiver.place_id:
            self.__session._client.headers["pp-placeid"] = receiver.place_id
        elif "pp-placeid" in self.__session._client.headers:
            del self.__session._client.headers["pp-placeid"]
        if receiver and receiver.store_id:
            # 朴朴这里用的下划线
            self.__session._client.headers["pp_storeid"] = receiver.store_id
        elif "pp_storeid" in self.__session._client.headers:
            del self.__session._client.headers["pp_storeid"]

    async def GetServerTime(self):
        """获得与服务器尽可能一致的时间戳"""
        if self.__server_date_diff is None:
            result = await self.ComputeServerTimeDiff()
            if isinstance(result, ApiResults.Error):
                log(result)
                return int(time()*1000)
            else:
                self.__server_date_diff = result
        return int(time()*1000 + self.__server_date_diff)

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
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def _SendRequest(self, method: HttpMethod, url: str,
                           client=ClientType.kNative,
                           headers: None | dict = None,
                           params: None | dict = None, data=None, json=None):
        """发起一个HTTP请求"""
        req_headers = {}
        match client:
            case ClientType.kNative:
                req_headers["User-Agent"] = self.native_user_agent
                req_headers["pp-os"] = "20"  # "0" for wechat
                if self.__receiver and self.__receiver.place_zip:
                    req_headers["pp-placezip"] = str(self.__receiver.place_zip)
            case ClientType.kWeb:
                req_headers["User-Agent"] = self.web_user_agent
                req_headers["pp-os"] = "201"
                if self.__receiver and self.__receiver.city_zip:
                    req_headers["pp-cityzip"] = str(self.__receiver.city_zip)
            case _:
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
                 access_token: None | str, expires_in: None | int):
        if not (device_id and refresh_token):
            raise ValueError("参数没有正确设置")
        super().__init__(device_id=device_id)
        self.__refresh_token: None | str = refresh_token
        self._nickname = self._avatar = None
        self.__expires_in = expires_in or 0
        self.access_token = access_token

    @property
    def nickname(self) -> None | str:
        return self._nickname

    @property
    def avatar(self) -> None | str:
        return self._avatar

    @property
    def refresh_token(self):
        return self.__refresh_token

    @refresh_token.setter
    def refresh_token(self, token: None | str):
        self.__refresh_token = token

    @property
    def expires_in(self):
        return self.__expires_in

    @expires_in.setter
    def expires_in(self, v: None | int):
        self.__expires_in = v or 0

    async def RefreshAccessToken(self):
        """刷新AccessToken 有效期通常只有2小时"""
        initial_tasks = [self.GetServerTime()]
        if not self.su_id:
            initial_tasks.append(self.GetSuID())
        current_time = (await aio_gather(*initial_tasks))[0]
        if self.access_token and current_time + 360_000 < self.expires_in:
            # access_token 有效
            return ApiResults.TokenValid()
        self.access_token = None
        self.user_id = None
        try:
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
                self.__refresh_token = data.get(
                    "refresh_token", self.__refresh_token)
                self.__expires_in = int(data.get('expires_in', 0))
                self._nickname = data.get("nick_name")
                return ApiResults.TokenRefreshed(refresh_token=self.__refresh_token,
                                                 access_expires=self.__expires_in)
            else:
                if obj["errcode"] == 403 \
                        or (obj["errcode"] != 200099 and obj["errcode"] in range(200000, 300000)):
                    self.__refresh_token = None
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

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
        except Exception as e:
            return ApiResults.Error(exception=e)

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
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def GetReceiver(self, filter: None | str = None):
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
                    if r.get("is_default", False) or r.get("time_last_order", 0) > time_last_order:
                        time_last_order = int(r.get("time_last_order", 0))
                        place = r["place"]
                        info = PReceiverInfo(
                            id=str(r["id"]),
                            address=r["address"], room_num=r["building_room_num"],
                            lng_x=place.get(
                                "lng_x", r["lng_x"]),
                            lat_y=place.get(
                                "lat_y", r["lat_y"]),
                            receiver_name=r["name"], phone_number=r["mobile"],
                            store_id=place.get(
                                "service_store_id", r["service_store_id"]),
                            place_id=place["id"],
                            city_zip=place.get("store_city_zip", 0)
                        )
                        self.user_id = r.get("user_id", self.user_id)
                        info.place_zip = int(place.get("zip", info.city_zip))

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
                            time_last_order = 0
                        elif r.get("is_default", False):
                            # 如果是默认地址则直接用(似乎朴朴并没有设置)
                            break
                assert info
                self.receiver = info
                return ApiResults.ReceiverInfo(info)
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def SignIn(self):
        """签到"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                "https://j1.pupuapi.com/client/game/sign/v2",
                params={"city_zip": self.receiver.city_zip if self.receiver else 0,
                        "supplement_id": ""},
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                data = obj["data"]
                # 积分
                return ApiResults.SignIn(coin=data["daily_sign_coin"],
                                         explanation=data["reward_explanation"])
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def GetSignPeriodInfo(self):
        """获得本周连续签到的天数"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                "https://j1.pupuapi.com/client/game/sign/period_info"
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                # 积分
                return ApiResults.SignPeriodInfo(data["signed_days"])
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def GetBanner(self, link_type: BANNER_LINK_TYPE, position_types: None | list[int | str] = None):
        assert self.receiver
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
                        time_open = item.get("time_open", 0)
                        time_close = item.get("time_close", now + 60_000)
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
        except Exception as e:
            return ApiResults.Error(exception=e)

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
                for prize in data.get("prize_info", []):
                    # 解析奖品
                    if "prize_level" in prize and "prize_type" in prize \
                            and "prize_name" in prize:
                        p = PPrize(level=prize["prize_level"],
                                   name=prize["prize_name"],
                                   type=RewardType(prize["prize_type"]))
                        lottery.prizes[p.level] = p
                task_system_link = data.get("task_system_link", {})
                lottery.task_system_link_id = task_system_link.get("link_id")
                if lottery.task_system_link_id:
                    link_type = BANNER_LINK_TYPE(
                        task_system_link.get("link_type"))
                    if link_type != BANNER_LINK_TYPE.USER_TASK:
                        print(f"警告: 抽奖任务遇到了不识别的link_type '{link_type.name}'")
                        lottery.task_system_link_id = None
                return ApiResults.LotteryInfo(lottery)
            else:
                # 获取抽奖信息失败
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def GetUserLotteryInfo(self, lottery: PLotteryInfo):
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{lottery.id}/user_chances",
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                num = obj["data"].get("remain_chance_num", 0)
                return ApiResults.UserLotteryInfo(remain_chances=num)
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def GetTaskGroupsData(self, lottery: PLotteryInfo):
        """获取任务列表"""
        if not lottery.task_system_link_id:
            return ApiResults.TaskGroupsData([])
        try:
            tasks: list[PTask] = []
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/task_system/user_tasks/task_groups/{lottery.task_system_link_id}",
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                data = obj["data"]
                tasks_json: list = data.get("tasks", [])
                for task_json in tasks_json:
                    page_task_rule = task_json.get("page_task_rule")
                    if not page_task_rule:
                        # 忽略非浏览型任务
                        continue
                    if "task_status" not in page_task_rule:
                        continue
                    assert page_task_rule["action_type"] == ActionTYPE.BROWSE.value
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
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def PostPageTaskComplete(self, lottery: PLotteryInfo, task: PTask):
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
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def GetChanceEntrances(self, lottery: PLotteryInfo):
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{lottery.id}/obtain_chance_entrance",
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                data = obj["data"]
                coin_balance = int(data.get("coin_balance", 0))
                entrances: list[PChanceEntrance] = []
                for item in data.get("chance_obtain_entrance", []):
                    if "code" in item and "attend_count" in item \
                            and "limit_count" in item and "gain_num" in item \
                            and "target_value" in item:
                        pitem = PChanceEntrance(
                            type=CHANCE_OBTAIN_TYPE(item["code"]),
                            title=item.get("title", "未知"),
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
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def CoinExchange(self, lottery: PLotteryInfo, entrance: PChanceEntrance):
        """开始积分兑换"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{lottery.id}/coin_exchange",
                params={"lng_x": self.receiver.lng_x if self.receiver else None,
                        "lat_y": self.receiver.lat_y if self.receiver else None},
                json={},
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                entrance.attend_count += 1
                return ApiResults.CoinExchanged(entrance.gain_num)
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def Lottery(self, lottery: PLotteryInfo):
        """开始抽奖"""
        try:
            obj = await self._SendRequest(
                HttpMethod.kPost,
                f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{lottery.id}/lottery",
                params={"lng_x": self.receiver.lng_x if self.receiver else None,
                        "lat_y": self.receiver.lat_y if self.receiver else None},
                json={},
                client=ClientType.kWeb)
            if obj["errcode"] == 0:
                prize = lottery.prizes.get(obj["data"]["prize_level"])
                return ApiResults.LotteryResult(prize)
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def GetProductCollections(self, page: int):
        """获取商品收藏列表"""
        assert self.receiver
        try:
            obj = await self._SendRequest(
                HttpMethod.kGet,
                f"https://j1.pupuapi.com/client/user_behavior/product_collection/store/{self.receiver.store_id}/products",
                params={"page": page, "size": 10}
            )
            if obj["errcode"] == 0:
                data = obj["data"]
                products = []
                # 总共收藏了{total_count}件商品
                total_count: int = data.get("count", 0)
                for p in data.get("products", []):
                    order_remarks = p.get("order_remarks", [])
                    product = PProduct(
                        price=p["price"],
                        product_id=p["product_id"],
                        store_product_id=p["id"],
                        spread_tag=p.get(
                            "spread_tag", SPREAD_TAG.NORMAL_PRODUCT),
                        stock_quantity=p.get("stock_quantity", 0),
                        remark=order_remarks[0] if order_remarks else ""
                    )
                    if p.get("spread_tag") == SPREAD_TAG.FLASH_SALE_PRODUCT:
                        flash_sale_info = p.get("flash_sale_info", {})
                        progress_rate: float = flash_sale_info.get(
                            "progress_rate", 0.0)
                        if flash_sale_info and progress_rate < 1.0:
                            # 限购N件
                            product.quantity_limit = flash_sale_info.get(
                                "quantity_each_person_limit", 1)
                    products.append(product)
                return ApiResults.ProductCollections(total_count, products)
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def GetUsableCoupons(self,  type: DiscountType, products: list[PProduct]):
        """获得可用的优惠券"""
        assert self.receiver
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
                data = obj["data"]
                if data.get("count", 0) > 0:
                    best_discount = data.get("best_discount", {})
                    id = best_discount.get("id")
                    if id:
                        ids.append(id)
                return ApiResults.UsableCoupons(ids)
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def GetDeliveryTime(self, products: list[PProduct], start_hours: int):
        assert self.receiver
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
                dtime_real = dtime_log.get("delivery_time_real", 30)
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
        except Exception as e:
            return ApiResults.Error(exception=e)

    async def CreateOrder(self, pay_type: int, coupons: list[str], products: list[PProduct],
                          dtime_type: DeliveryTimeType, dtime_promise: int):
        """创建订单"""
        assert self.receiver
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
            "discount_entity_ids": coupons,
            "external_payment_amount": 0,  # 总金额(分) 无所谓
            "lat_y": self.receiver.lat_y,
            "lng_x": self.receiver.lng_x,
            "logistics_fee": 0,  # 运费(分) 似乎也无所谓
            "number_protection": 1,
            "order_items": order_items,
            "order_type": 0,
            "pay_type": pay_type,  # 15是云闪付
            "place_id": self.place_id,
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
                rr: ApiResults.Error | ApiResults.OrderCreated = await self.CreateOrder(
                    pay_type, coupons, products, DeliveryTimeType.RESERVE, dtime_promise)
                return rr
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)

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
                total_count: int = obj.get("count", 0)
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
        except Exception as e:
            return ApiResults.Error(exception=e)

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
                enabled: bool = data.get("enabled", True)
                status = SHARE_STATUS(data.get('status', SHARE_STATUS.ERROR))
                best_luck: bool = data.get("best_luck", False)  # 我是否最佳
                reentry: bool = data["reentry"]  # 已领取过该优惠券了哦
                users: list = data.get("list", [])
                rule = data.get("rule", {})  # 我抢到的优惠券 可能为空
                discount_id = rule.get("discount_id")
                if not discount_id:
                    # 我没抢到优惠券
                    discount_rule = None
                    match status:
                        case SHARE_STATUS.NULL:
                            # 红包已经空了
                            log(f"{share.share_id}: status = NULL")
                        case SHARE_STATUS.EXPIRED:
                            # 红包过期了
                            log(f"{share.share_id}: status = EXPIRED")
                        case _:
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
                return ApiResults.WxDiscountShare(
                    best_luck, reentry, len(users),
                    discount=discount_rule,
                    available=status == SHARE_STATUS.NORMAL and enabled)
            else:
                return ApiResults.Error(json=obj)
        except Exception as e:
            return ApiResults.Error(exception=e)


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
        self._config = GetScriptConfig("pupu")
        self._config_dict = {}

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
                "refresh_token_lastest", self._refresh_token_user_specified)

        self.access_token = self._config_dict.get("access_token")
        self.expires_in = self._config_dict.get("access_expires")

        self.user_id = self._config_dict.get("user_id")
        self.su_id = self._config_dict.get("su_id")
        self.receiver = PReceiverInfo(
            self._config_dict.get("recv_id", ""),
            store_id=self._config_dict.get("store_id", ""),
            place_id=self._config_dict.get("place_id", ""),
            city_zip=int(self._config_dict.get("city_zip", 0)),
            place_zip=int(self._config_dict.get("place_zip", 0)))

        self._nickname = self._config_dict.get("nickname")
        self._avatar = self._config_dict.get("avatar")
        return True

    def SaveConfig(self):
        if not self._config:
            return False
        self._config_dict["nickname"] = self.nickname or ""
        self._config_dict["refresh_token_user_specified"] = self._refresh_token_user_specified or ""
        self._config_dict["refresh_token_lastest"] = self.refresh_token or ""
        self._config_dict["access_token"] = self.access_token or ""
        self._config_dict["access_expires"] = self.expires_in
        self._config_dict["su_id"] = self.su_id or ""
        self._config_dict["user_id"] = self.user_id or ""
        self._config_dict["recv_id"] = self.receiver.id if self.receiver else ""
        self._config_dict["store_id"] = self.receiver.store_id if self.receiver else ""
        self._config_dict["place_id"] = self.receiver.place_id if self.receiver else ""
        self._config_dict["city_zip"] = self.receiver.city_zip if self.receiver else 0
        self._config_dict["place_zip"] = self.receiver.place_zip if self.receiver else 0
        self._config_dict["avatar"] = self.avatar or ""
        self._config.set_value(self.device_id, self._config_dict)
        self._saved = True
        return True

    async def InitializeToken(self, address_filter: None | str):
        """初始化"""
        self.LoadConfig(force=True)

        token_result = await self.RefreshAccessToken()
        if isinstance(token_result, ApiResults.Error):
            return token_result

        recv_result = await self.GetReceiver(filter=address_filter)
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
