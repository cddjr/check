# -*- coding: utf-8 -*-
"""
cron: 0 1,20 * * *
new Env('朴朴');

微信登录朴朴app
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token
"""
from enum import IntEnum, unique
import random
import sys
from time import time, sleep
from utils import check, log, randomSleep, GetScriptConfig
from urllib3 import disable_warnings, Retry
from requests.adapters import HTTPAdapter
import requests


@unique
class BANNER_LINK_TYPE(IntEnum):
    PRODUCT_DETAIL_ACTIVITY = 0
    TOPIC_ACTIVITY = 10
    SEARCH_RESULT_ACTIVITY = 90
    DISCOVERY_DETAIL_ACTIVITY = 220
    COUPON_DETAIL_ACTIVITY = 230
    COUPON_LIST = 231
    GOOD_NEIGHBOR_ACTIVITY = 250
    ACTIVITY_ACTIVITY = 400
    INDEX_TAB_ALL_CATEGORY = 410
    FLASH_SALE_ACTIVITY = 650
    SCENE_PRODUCT_LIST = 700
    COOKBOOK_DETAIL = 900
    COOKBOOK_LIST = 901
    COOKBOOK_CHANNEL = 902
    OPEN_MP_LIVE = 903
    NO_JUMP = 910
    INDEX = 999
    USER_GIFT_CARD = 1000
    MY_USER_GIFT_CARD = 1001
    MY_COIN = 1010
    CUSTOMER_CONTACT = 1011
    DELIVER_ADDRESS = 1012
    INVOICE_EXPENSE = 1013
    DELIVER_BELL = 1014
    MY_COLLECT = 1015
    ABOUT_PUPU = 1016
    SHARE_PUPU = 1017
    USER_TASK = 1022
    CUSTOM_LOTTERY = 1023
    LOGIN_PAGE = 1024
    SHARE_SELF = 1025
    ORDER_DETAIL = 1030
    IMPORTANT_PRODUCT_LIST = 2620
    WEB = 99999


@unique
class ActionTYPE(IntEnum):
    BROWSE = 0
    SHARE = 10


@unique
class TaskRuleType(IntEnum):
    Null = 0
    Popup = 10
    Scenes = 20


@unique
class TaskType(IntEnum):
    FLASH_SALE = 240
    CUSTOM_LOTTERY = 250
    TOPIC = 260
    USER_TASK = 270
    SCENE = 280


@unique
class TaskStatus(IntEnum):
    Undone = 0
    Done = 10
    Expired = 20
    Receive = 30


@unique
class Error(IntEnum):
    ERROR_TASK_NOT_GENERATED = 400104
    ERROR_TASK_DOES_NOT_EXIST = 400106


@unique
class SPREAD_TAG(IntEnum):
    UNKNOWN = -1  # 不限
    NORMAL_PRODUCT = 0
    NEW_PRODUCT = 10  # 新品
    FLASH_SALE_PRODUCT = 20  # 限时购
    DISCOUNT_PRODUCT = 30  # 折扣
    NOVICE_PRODUCT = 40  # 新手专享
    SPECIAL_PRODUCT = 50  # 特价
    HOT_PRODUCT = 60  # 热卖
    YIYUAN_BUTIE = 100
    ZERO_ORDER_EXCLUSIVE = 110
    ONE_ORDER_EXCLUSIVE = 120
    TWO_ORDER_EXCLUSIVE = 130
    THREE_ORDER_EXCLUSIVE = 140


@unique
class DiscountType(IntEnum):
    ALL = -1  # 全部
    ABSOLUTE = 0  # 满减
    PERCENTAGE = 10  # 百分比折扣
    GIFT_PRODUCT = 20  # 买赠
    EACH_GIFT_PRODUCT = 30  # 每买赠
    EACH_GIFT_MONEY = 40  # 每满减
    TRADE_BUY = 50  # 换购


@unique
class PurchaseType(IntEnum):
    ALL = -1  # 不限
    GENERAL = 0  # 普通
    RESERVE = 10  # 预定


@unique
class CART_ITEM_TYPE(IntEnum):
    USUAL = 0
    FREE_GIFT = 1
    EXCHANGE = 2


class PItem:
    price: int
    product_id: str
    store_product_id: str
    remark: str
    spread_tag: int
    selected_count: int


class PTask:
    task_id: str
    task_name: str  # 每日打卡
    activity_id: str
    task_type: int
    action_type: int
    skim_time: int  # 浏览多少秒
    task_status: int  # 0未完成 30已浏览


class PUPU:
    version = "2023010301"
    # 随机生成的guid
    device_id = "8C249B81-0974-4922-B512-53C4045C9851"
    # 根据device_id生成的账户ID，在不同平台如微信小程序内也会返回相同账户ID
    # 获取方式 GET https://j1.pupuapi.com/client/caccount/user/suid?device_id={device_id}
    # {"errcode":0,"errmsg":"","data":"59754a9d-89b6-4f9e-9d9f-4f0c7287bd65"}
    su_id = "59754a9d-89b6-4f9e-9d9f-4f0c7287bd65"
    userAgent = f"Pupumall/3.2.3;iOS 15.4.1;{device_id}"

    api_host = "https://j1.pupuapi.com"
    url_period_info = api_host + "/client/game/sign/period_info"

    url_get_token = 'https://cauth.pupuapi.com/clientauth/user/refresh_token'

    refresh_token: str = None
    access_token: str = None

    store_id: str = None
    place_id: str = None
    user_id: str = None
    store_city_zip: int = 0
    zip: int = 0
    lngX: float = 0
    latY: float = 0
    receiver_id: str = None
    recv_addr: str = ""
    recv_room_num: str = ""
    recv_name: str = ""
    recv_phone: str = ""

    watch: bool = False
    PUSH_KEY: str = None

    """
    [[鱼, 10, 2], [瓜, 5, 3]]
    鱼如果低于10元买2条
    瓜如果低于5元买3个
    """
    goods = []

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
            "User-Agent": self.userAgent,
            "pp-version": self.version,
            "pp-os": "20",
            # "Referer": "https://ma.pupumall.com/",
            "Connection": "keep-alive"
        }
        method = method.upper()
        if self.access_token:
            headers["Authorization"] = f'Bearer {self.access_token}'
        if self.place_id:
            headers["pp-placeid"] = self.place_id
        if self.zip != 0:
            headers["pp-placezip"] = str(self.zip)
        if self.user_id:
            headers["pp-userid"] = self.user_id
        if self.store_id:
            headers["pp_storeid"] = self.store_id
        if self.su_id:
            headers["pp-suid"] = self.su_id

        response: requests.Response = self.session.request(method,
                                                           url=url, headers=headers, data=data, json=json)
        return response.json()

    def serverJ(self, title: str, content: str):
        """
        通过 serverJ 推送消息。
        """
        if not self.PUSH_KEY:
            return []
        msg = []
        log("serverJ 服务启动")

        data = {"text": title, "desp": content.replace("\n", "\n\n")}
        if self.PUSH_KEY.index("SCT") != -1:
            url = f'https://sctapi.ftqq.com/{self.PUSH_KEY}.send'
        else:
            url = f'https://sc.ftqq.com/${self.PUSH_KEY}.send'

        datas = self.session.post(url, data=data, timeout=15).json()
        if datas.get("errno") == 0 or datas.get("code") == 0:
            log("serverJ 推送成功！", msg)
        elif datas.get("code") == 40001:
            log("serverJ 推送失败！PUSH_KEY 错误。", msg)
        else:
            log(f'serverJ 推送失败！错误码：{datas.get("message")}', msg)
        return msg

    def get_receivers(self):
        """
        获得收货地址
        """
        msg = []
        try:
            obj = self.__sendRequest(
                "get", "https://j1.pupuapi.com/client/account/receivers")
            if obj["errcode"] == 0:
                data = obj["data"]
                time_last_order: int = -1
                for r in data:
                    # r["is_in_service"] 意味地址是否可以配送
                    if r.get("is_default", False) or r.get("time_last_order", 0) > time_last_order:
                        time_last_order = int(r.get("time_last_order", 0))
                        self.store_id = str(r["service_store_id"])
                        self.receiver_id = str(r["id"])
                        self.user_id = str(r.get("user_id", self.user_id))
                        self.recv_addr = str(r["address"])
                        self.recv_room_num = str(r["building_room_num"])
                        self.lngX = float(r["lng_x"])
                        self.latY = float(r["lat_y"])
                        place = r["place"]
                        self.place_id = str(place["id"])
                        self.store_id = str(
                            place.get("service_store_id", self.store_id))
                        self.lngX = float(place.get("lng_x", self.lngX))
                        self.latY = float(place.get("lat_y", self.latY))
                        self.store_city_zip = int(
                            place.get("store_city_zip", 0))
                        self.zip = int(place.get("zip", self.store_city_zip))

                        self.recv_name = str(r["name"])
                        self.recv_phone = str(r["mobile"])

                        building_name: str = None
                        room_num: str = r.get("room_num", None)

                        if place.get("have_building", False):
                            place_building = r.get("place_building", None)
                            if place_building and place_building.get("is_deleted", False) == False:
                                building_name = place_building.get(
                                    "building_name", None)
                        if building_name and room_num:
                            self.recv_room_num = f'{building_name} {room_num}'
                        if r.get("is_default", False):
                            # 如果是默认地址则直接用(似乎朴朴并没有设置)
                            break

                log(f'收货地址: {self.recv_addr} {self.recv_room_num}')
                log(f'仓库ID: {self.store_id}')
            else:
                log(
                    f'get_receivers 失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'get_receivers 异常: 请检查接口 {e}', msg)
        return msg

    def product_to_pitem(self, product, count: int) -> PItem:
        pitem = PItem()
        pitem.price = int(product["price"])
        pitem.product_id = str(product["product_id"])
        pitem.store_product_id = str(product["id"])
        pitem.spread_tag = int(product.get(
            "spread_tag", SPREAD_TAG.NORMAL_PRODUCT.value))
        pitem.selected_count = count
        rms = product.get("order_remarks", [])
        if len(rms) > 0:  # [杀(清洗), 杀(不清洗), 不杀
            pitem.remark = str(rms[0])
        else:
            pitem.remark = ""
        return pitem

    def add_cart(self, product, count: int):
        """
        加购物车(暂时用不上这个功能，弃用)
        """
        pitem: PItem = None
        json = {
            "store_product_id": product["id"],
            "selected_count": count,
            "current_price": int(product["price"]),
            "type": CART_ITEM_TYPE.USUAL.value,
            "is_selected": True,
            "product_tag": int(product.get("spread_tag", SPREAD_TAG.NORMAL_PRODUCT.value)),
            "product_id": product["product_id"],
        }
        ids = product.get("activity_ids", [])
        if len(ids) > 0:
            json["activity_id"] = ids[0]
        rms = product.get("order_remarks", [])
        if len(rms) > 0:  # [杀(清洗), 杀(不清洗), 不杀
            json["remark"] = rms[0]
        msg = []
        try:
            obj = self.__sendRequest(
                "post", "https://j1.pupuapi.com/client/shopping_cart/shopping_cart_item/purchasing_product", json=json)
            if obj["errcode"] == 0:
                data = obj["data"]
                # TODO
                for p in data["product_group_list"]:
                    if p.get("is_deleted", False):
                        continue
                    items = p.get("cart_item_list", [])
                    if len(items) == 0:
                        continue
                    # TODO: 目前只处理第一个item
                    item = items[0]
                    pitem = PItem()
                    pitem.price = int(item["current_price"])
                    pitem.product_id = str(item["product_id"])
                    pitem.store_product_id = str(item["store_product_id"])
                    pitem.spread_tag = int(item["product_tag"])
                    pitem.selected_count = int(item["selected_count"])
                    pitem.remark = str(item.get("remark", ""))
                    break
            else:
                log(f'加购失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'加购异常: 请检查接口 {e}', msg)
        return (msg, pitem)

    def get_delivery_time(self, pitems: list, min_hours: int):
        delivery_time_type = 0
        def_date = (time() + 1800) * 1000
        msg = []
        try:
            json = []
            for item in pitems:
                if not isinstance(item, PItem):
                    continue
                pi: PItem = item
                obj = {
                    "price": pi.price,
                    "product_id": pi.product_id,
                    "batch_id": "",
                    "discount_type": DiscountType.ABSOLUTE.value,  # 满减?
                    "is_gift": False,
                    "count": pi.selected_count,
                }
                json.append(obj)

            obj = self.__sendRequest(
                "post", f"https://j1.pupuapi.com/client/deliverytime/v4?place_id={self.place_id}&scene_type=0&store_id={self.store_id}", json=json)
            if obj["errcode"] == 0:
                data = obj["data"]
                delivery_time_log = data["delivery_time_log"]
                delivery_time_real: int = delivery_time_log.get(
                    "delivery_time_real", 30)
                reason_type = delivery_time_log.get("reason_type", 0)
                if reason_type == 6:
                    delivery_time_type = 10
                time_group: list = data["time_group"]
                date: int = time_group[0]["date"]  # 1673107200000
                date_start: int = date + time_group[0]["start_min"] * 60000
                date_end: int = date + time_group[0]["end_min"] * 60000

                cur_date = time() * 1000 + delivery_time_real*60000
                cur_date = min(max(cur_date, date_start), date_end)

                limit_date = min(max(date + min_hours * 3600000, date_start) +
                                 delivery_time_real * 60000, date_end)

                def_date = max(cur_date, limit_date)
            else:
                log(
                    f'get_delivery_time 失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'get_delivery_time 异常: 请检查接口 {e}', msg)
        return (int(delivery_time_type), int(def_date))

    def make_order(self, pay_type: int, coupon_ids: list, pitems: list, delivery_time_type: int, time_delivery_promise: int):
        order_items = []
        for item in pitems:
            if not isinstance(item, PItem):
                continue
            pi: PItem = item
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
            "delivery_time_type": delivery_time_type,
            "device_id": self.device_id,
            "device_os": "20",
            "discount_entity_ids": coupon_ids,
            "external_payment_amount": 0,  # 总金额(分) 无所谓
            "lat_y": self.latY,
            "lng_x": self.lngX,
            "logistics_fee": 0,  # 运费(分) 似乎也无所谓
            "number_protection": 1,
            "order_items": order_items,
            "order_type": 0,
            "pay_type": pay_type,  # 15是云闪付
            "place_id": self.place_id,
            "print_order_product_ticket_info": False,  # 是否打印商品详情(所谓环保)
            "put_if_no_answer": False,  # 联系不上是否放门口
            "receiver": {
                "address": self.recv_addr,
                "building_room_num": self.recv_room_num,
                "mobile": self.recv_phone,
                "name": self.recv_name,
                "place_building_id": "",
                "sex": 0,
            },
            "receiver_id": self.receiver_id,
            "remark": "",  # 备注
            "store_id": self.store_id,
            "time_delivery_promise": str(time_delivery_promise),
            "time_delivery_promise_end": str(time_delivery_promise),
            "time_delivery_promise_start": str(time_delivery_promise),
        }

        msg = []
        try:
            obj = self.__sendRequest(
                "post", "https://j1.pupuapi.com/client/order/unifiedorder/v2", json=json)
            if obj["errcode"] == 0:
                data = obj["data"]
                log(f'订单创建成功 {data["id"]}', msg)
            elif delivery_time_type == 0 and obj["errmsg"].find("重新选择"):
                # 亲，该订单期望送达时间不在我们配送时间范围内，请重新选择送达时间
                return self.make_order(pay_type, coupon_ids, pitems, delivery_time_type=10, time_delivery_promise=time_delivery_promise)
            else:
                log(f'订单创建失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'订单创建异常: 请检查接口 {e}', msg)
        return msg

    def checkGoods(self, retry_count: int):
        """
        从商品收藏列表中检测价格（根据收货地址判断库存）
        https://j1.pupuapi.com/client/user_behavior/product_collection/store/{store_id}/products?page=1&size=10
        """
        order_items = []
        msg = []
        price_msg = []
        try:
            obj = self.__sendRequest(
                "get", f"https://j1.pupuapi.com/client/user_behavior/product_collection/store/{self.store_id}/products?page=1&size=10")
            if obj["errcode"] == 0:
                data = obj["data"]
                count: int = data.get("count", 0)
                products: list = data.get("products", [])
                log(f'总共收藏了{count}件商品')

                cart_msg = []
                for p in products:
                    for gn in self.goods:
                        if p["name"].find(gn[0]) == -1:
                            # 排除不关心价格的
                            continue
                        sq: int = p.get("stock_quantity", 0)
                        if sq <= 0:
                            # 排除没货的
                            continue
                        # TODO: 若 p["sell_batches"] 不为空，则以该数组的最低价作为当前价格
                        price: float = p["price"] / 100
                        if price > gn[1]:
                            # 排除价格高于预期的
                            # log(f'价格高于预期: {p["name"]} {price}元 > {gn[1]}元')
                            continue
                        log(f'检测到低价: {p["name"]} {price}元', price_msg)
                        if not self.buy:
                            continue
                        count = 1
                        if len(gn) >= 3:
                            count = max(1, min(int(gn[2]), sq))
                        if p.get("spread_tag", SPREAD_TAG.NORMAL_PRODUCT.value) == SPREAD_TAG.FLASH_SALE_PRODUCT.value:
                            flash_sale_info = p.get("flash_sale_info", {})
                            progress_rate: float = flash_sale_info.get(
                                "progress_rate", 0.0)
                            if flash_sale_info and progress_rate < 1.0:
                                # 限购N件
                                limit: int = flash_sale_info.get(
                                    "quantity_each_person_limit", 1)
                                # 不能超过限购数
                                count = min(count, limit)
                        """
                        add_msg, pitem = self.add_cart(p, count=count)
                        cart_msg += add_msg
                        """
                        pitem = self.product_to_pitem(p, count=count)
                        if pitem:
                            order_items.append(pitem)

                msg += price_msg
                msg += cart_msg
                if len(price_msg) == 0:
                    if retry_count <= 1:
                        log('无降价')
                        exit()
                    else:
                        sleep(0.5)
                        return self.checkGoods(retry_count=retry_count-1)
            else:
                log(f'checkGoods 失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'checkGoods 异常: 请检查接口 {e}', msg)
        return (msg, order_items, price_msg)

    def discount(self, type: DiscountType, items: list):
        """
        获得最佳折扣
        """
        ids = []
        msg = []
        try:
            order_items = []
            for p in items:
                if not isinstance(p, PItem):
                    continue
                pi: PItem = p
                obj = {
                    "price": pi.price,
                    "product_id": pi.product_id,
                    "batch_id": "",
                    "discount_type": DiscountType.ABSOLUTE.value,  # TODO
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
                "place_id": self.place_id,
                "place_zip": self.zip,
                "receiver_id": self.receiver_id,
                "store_id": self.store_id,
                "order_items": order_items,
            }
            obj = self.__sendRequest(
                "post", f"https://j1.pupuapi.com/client/account/discount?discount_type={type.value}", json=json)
            if obj["errcode"] == 0:
                data = obj["data"]
                if data.get("count", 0) > 0:
                    best_discount = data.get("best_discount", {})
                    id = best_discount.get("id", None)
                    if id:
                        ids.append(id)
            else:
                log(f'获取折扣失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'获取折扣异常: 请检查接口 {e}', msg)
        return (msg, ids)

    def refreshAccessToken(self):
        """
        获得AccessToken

        有效期通常只有2小时
        """

        """
        正常返回响应体
        {
            "errcode": 0,
            "errmsg": "",
            "data": {
                "access_token": "xxx",
                "refresh_token": "xxx",
                "expires_in": 1660803941123,
                "is_bind_phone": true,
                "user_id": "xx-xx-xx",
                "nick_name": "张三",
                "is_new_user": false
            }
        }
        """
        msg = []
        try:
            obj = self.__sendRequest("put", self.url_get_token,
                                     json={"refresh_token": self.refresh_token})
            if obj["errcode"] == 0:
                data = obj["data"]
                nickname: str = data.get('nick_name', '未知')
                self.access_token: str = data.get('access_token', None)
                self.user_id: str = data.get("user_id", "")
                token: str = data.get('refresh_token', None)
                self.config_dict["access_expires"] = int(
                    data.get('expires_in', 0))
                log(f'账号: {nickname}', msg)
                log(f'access_token:{self.access_token}')
                if self.refresh_token == token:
                    log('refresh_token没有变化')
                else:
                    self.refresh_token = token
                    log(f'新的refresh_token:{self.refresh_token}', msg)
            else:
                # 200208 登录已失效，请重新登录
                self.access_token = None
                log(f'刷新令牌失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'刷新令牌异常: 请检查接口 {e}', msg)
        return msg

    def signIn(self):
        """
        签到
        """
        msg = []
        try:
            obj = self.__sendRequest(
                "post", f"https://j1.pupuapi.com/client/game/sign/v2?city_zip={self.store_city_zip}&supplement_id=")
            if obj["errcode"] == 0:
                data = obj["data"]
                # 积分
                log(f'签到成功: 奖励积分+{data["daily_sign_coin"]} {data["reward_explanation"]}', msg)
            elif obj["errcode"] == 350011:
                log("重复签到: 忽略", msg)
                # exit()  # 目前没必要执行后续的操作
            else:  # 400000 请求参数不合法
                log(f'签到失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'签到异常: 请检查接口 {e}', msg)
        return msg

    def getPeriod(self):
        """
        获得本周连续签到的天数
        """
        msg = []
        try:
            obj = self.__sendRequest("get", self.url_period_info)
            if obj["errcode"] == 0:
                data = obj["data"]
                log(f'签到信息: 本周连续签到{data["signed_days"]}天', msg)
            else:
                log(f'getPeriod失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}', msg)
        except Exception as e:
            log(f'getPeriod异常: 请检查接口 {e}', msg)
        return msg

    def parse_goods(self):
        """
        解析商品配置 {name, 价格(元)}
        """
        msg = []
        self.goods.clear()
        for key in self.check_item:
            if not key.startswith("goods"):
                continue
            value = self.check_item.get(key, None)
            if not isinstance(value, list):
                continue
            if not len(value) >= 2:
                continue
            if not isinstance(value[0], str):
                continue
            if not isinstance(value[1], int | float):
                continue
            self.goods.append(value)
        log(f'配置了{len(self.goods)}件商品的价格检测', msg)
        return msg

    def get_lottery_info(self, id: str):
        """
        获得抽奖活动的信息
        返回(名称, 任务列表)
        """
        activity_name: str = ""
        tasks = []
        try:
            obj = self.__sendRequest(
                "get", f'https://j1.pupuapi.com/client/game/custom_lottery/activities/{id}/element_configuration')
            if obj["errcode"] == 0:
                data = obj["data"]
                activity_name = data["activity_name"]  # 开运新年签
                task_system_link = data.get("task_system_link", {})
                link_id = task_system_link.get("link_id", None)
                if link_id:
                    # self.session.proxies["https"] = "127.0.0.1:8888"
                    obj = self.__sendRequest(
                        "get", f'https://j1.pupuapi.com/client/game/task_system/user_tasks/task_groups/{link_id}')
                    if obj["errcode"] == 0:
                        data = obj["data"]
                        tasks_json: list = data.get("tasks", [])
                        for task_json in tasks_json:
                            page_task_rule = task_json.get(
                                "page_task_rule", None)
                            if not page_task_rule:
                                # 忽略非浏览型任务
                                continue
                            if not "task_status" in page_task_rule:
                                continue
                            task = PTask()
                            task.task_name: str = task_json["task_name"]
                            task.task_id: str = page_task_rule["task_id"]
                            task.skim_time: int = page_task_rule["skim_time"]
                            task.activity_id: str = page_task_rule["activity_id"]
                            task.task_type: int = page_task_rule["task_type"]
                            task.action_type: int = page_task_rule["action_type"]
                            task.task_status: int = page_task_rule["task_status"]
                            # 任务进度 [{finish_progress_value}/{task_progress_value}]
                            # task_progress_value为0说明这个任务没有进度，一次即可
                            tasks.append(task)
                    else:
                        log(
                            f'{activity_name} 获取任务列表失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}')
                else:
                    log(f'{activity_name}: 无 link_id')
            else:
                log(
                    f'get_lottery_info 失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}')
        except Exception as e:
            log(f'get_lottery_info 异常: 请检查接口 {e}')
        return (activity_name, tasks)

    def get_lottery_chances(self, id: str) -> int:
        """
        获得抽奖次数
        """
        num: int = 0
        try:
            obj = self.__sendRequest(
                "get", f'https://j1.pupuapi.com/client/game/custom_lottery/activities/{id}/user_chances')
            if obj["errcode"] == 0:
                num = obj["data"].get("remain_chance_num", 0)
            else:
                log(
                    f'get_lottery_chances 失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}')
        except Exception as e:
            log(f'get_lottery_chances 异常: 请检查接口 {e}')
        return num

    def do_lottery_task(self, task: PTask):
        """
        完成抽奖的任务
        """
        # 此任务从何时完成
        time_end: int = (time() - random.randint(1, 8)) * 1000
        # 此任务从何时开始
        time_from: int = time_end - task.skim_time * \
            1000 - random.randint(1, 20)

        json = {
            "activity_id": task.activity_id,
            "task_type": task.task_type,
            "action_type": task.action_type,
            "task_id": task.task_id,
            "time_from": time_from,
            "time_end": time_end, }
        try:
            obj = self.__sendRequest(
                "post", "https://j1.pupuapi.com/client/game/task_system/user_tasks/page_task_complete", json=json)
            if obj["errcode"] == 0:
                return True
            else:
                log(
                    f'任务 {task.task_name} 失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}')
        except Exception as e:
            log(f'任务 {task.task_name} 异常: 请检查接口 {e}')
        return False

    def do_lottery(self, id: str) -> str:
        """
        开始抽奖
        """
        try:
            obj = self.__sendRequest(
                "post", f"https://j1.pupuapi.com/client/game/custom_lottery/activities/{id}/lottery?lng_x={self.lngX}&lat_y={self.latY}", json={})
            if obj["errcode"] == 0:
                return obj["data"].get("prize_remark", "Unknown")
            else:
                log(f'do_lottery 失败: code:{obj["errcode"]}, msg:{obj["errmsg"]}')
        except Exception as e:
            log(f'do_lottery 异常: 请检查接口 {e}')
        return None

    def lottery(self, id: str):
        """
        每日抽奖
        """
        msg = []
        # 首先获取每日任务
        activity_name, tasks = self.get_lottery_info(id)
        if not activity_name:
            log(f'抽奖异常: 拉取不到活动', msg)
            return msg
        # 然后开始做每日任务
        log(f'正在进行 [{activity_name}]', msg)
        # log(f'{activity_name} 任务数量: {len(tasks)}', msg)
        for task in tasks:
            ptask: PTask = task
            if ptask.task_status == TaskStatus.Undone:
                randomSleep(2, 5)
                if self.do_lottery_task(task):
                    log(f'    {ptask.task_name}: 已完成')
        randomSleep(2, 5)
        # 接着获取有多少次抽奖机会
        changes = self.get_lottery_chances(id)
        if changes > 0:
            log(f' 当前有{changes}次抽奖机会', msg)
            for i in range(changes):
                randomSleep(1, 5)
                prize = self.do_lottery(id)
                if not prize:
                    prize = "获得未知"
                log(f'  第 {i+1}/{changes} 次抽奖: {prize}', msg)
        else:
            log(' 没有抽奖机会', msg)
        return msg

    def LoadConfig(self):
        self.config_dict: dict = self.config.get_value_2(self.refresh_token)
        self.access_expires = int(
            self.config_dict.get("access_expires", 0))
        if (time() + 3600.0) * 1000.0 > self.access_expires:
            self.access_token = ""
        else:
            self.access_token = str(self.config_dict.get(
                "access_token", self.access_token))
        self.nickname = str(self.config_dict.get("nickname", ""))
        self.su_id = str(self.config_dict.get("su_id", self.su_id))
        self.store_id = str(self.config_dict.get(
            "store_id", self.store_id))
        self.place_id = str(self.config_dict.get(
            "place_id", self.place_id))
        self.user_id = str(self.config_dict.get("user_id", self.user_id))
        self.store_city_zip = int(self.config_dict.get(
            "store_city_zip", self.store_city_zip))

    def SaveConfig(self):
        self.config_dict["access_token"] = self.access_token
        self.config_dict["nickname"] = self.nickname
        self.config_dict["su_id"] = self.su_id
        self.config_dict["store_id"] = self.store_id
        self.config_dict["place_id"] = self.place_id
        self.config_dict["user_id"] = self.user_id
        self.config_dict["store_city_zip"] = self.store_city_zip
        self.config.set_value(self.refresh_token, self.config_dict)

    def main(self):
        msg = []
        try:
            # 是否要检测价格
            if len(sys.argv) >= 2 and sys.argv[1] == "extra":
                self.watch: bool = self.check_item.get("watch", False)
                self.buy: bool = self.check_item.get("buy", False)
                if not (self.watch or self.buy):
                    log("忽略")
                    exit()
                self.config = GetScriptConfig("_extra")
            else:
                self.watch = False
                self.buy = False
                self.config = GetScriptConfig()

            self.refresh_token: str = self.check_item.get("refresh_token", "")
            if len(self.refresh_token) < 4:
                raise SystemExit("refresh_token配置有误")
            self.PUSH_KEY = self.check_item.get("PUSH_KEY", None)

            self.LoadConfig()

            if not self.access_token:
                self.user_id = ""
                msg += self.refreshAccessToken()
            else:
                log(f'账号: {self.nickname}', msg)
            if self.access_token:
                if self.watch or self.buy:
                    msg += self.parse_goods()
                    if len(self.goods) == 0:
                        raise SystemExit("没有正确配置需要检测的商品")
                    msg += self.get_receivers()
                    if self.store_id and self.receiver_id and self.place_id:
                        goods_msg, items, price_msg = self.checkGoods(
                            retry_count=10)
                        msg += goods_msg
                        if len(items) > 0:
                            dis_msg, dis_ids = self.discount(
                                DiscountType.ALL, items)
                            msg += dis_msg
                            # 不考虑了
                            # if len(dis_ids) == 0:
                            #    dis_msg, dis_ids = self.discount(DiscountType.EACH_GIFT_PRODUCT, items)
                            #    msg += dis_msg
                            delivery_time_type, time_delivery_promise = self.get_delivery_time(
                                items, 10)
                            msg += self.make_order(15, dis_ids, items,
                                                   delivery_time_type, time_delivery_promise)
                        if len(price_msg) > 0:
                            # 消息推送改到最后再发，避免错过机会
                            price_text = "\n".join(price_msg)
                            msg += self.serverJ("朴朴降价了", price_text)
                else:
                    # 非价格检测模式，开始签到
                    msg += self.get_receivers()  # 用于确定一些坐标、市场信息，后续一些操作可能需要用到
                    msg += self.signIn()
                    msg += self.getPeriod()
                    lottery_id = self.check_item.get("lottery_id", None)
                    if lottery_id:
                        # 抽奖
                        msg += self.lottery(id=lottery_id)

            self.SaveConfig()
        except Exception as e:
            log(f'失败: 请检查接口 {e}', msg)
        msg = "\n".join(msg)
        return msg


@check(run_script_name="朴朴", run_script_expression="pupu", interval_max=0)
def main(*args, **kwargs):
    return PUPU(check_item=kwargs.get("value")).main()


if __name__ == "__main__":
    disable_warnings()
    main()
