from dataclasses import dataclass, field
from enum import IntEnum, Enum
from utils import default
from traceback import format_exception
from sys import _getframe as getframe, version_info as py_version
assert py_version >= (3, 10)


@default()
class BANNER_LINK_TYPE(IntEnum):
    kUnknown = -0xdeadbeef
    RECOMMEND = -10
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
    NOVICE = 1027
    GIFT_CARD_STORE_H5 = 1029
    ORDER_DETAIL = 1030
    kUnk_1032 = 1032
    IMPORTANT_PRODUCT_LIST = 2620
    WEB = 99999


@default()
class DiscountType(IntEnum):
    kUnknown = -0xdeadbeef
    ALL = -1  # 全部
    ABSOLUTE = 0  # 满减
    PERCENTAGE = 10  # 百分比折扣
    GIFT_PRODUCT = 20  # 买赠
    EACH_GIFT_PRODUCT = 30  # 每买赠
    EACH_GIFT_MONEY = 40  # 每满减
    TRADE_BUY = 50  # 换购


@default()
class DeliveryReasonType(IntEnum):
    kUnknown = -0xdeadbeef
    WEATHER = 0
    PEAK = 1  # 因配送高峰, 配送时间有调整, 请耐心等待
    OTHER = 2
    PROLONG = 4
    EXHAUSTED = 5  # 没有骑手?
    FUTURE_PRODUCTS = 6
    PROPERTY_PROBLEM = 100
    TRAFFIC_PROBLEM = 200
    LONG_DISTANCE = 300


@default()
class DeliveryTimeType(IntEnum):
    kUnknown = -0xdeadbeef
    IMMEDIATE = 0
    RESERVE = 10


@default()
class LOTTERY_TYPE(IntEnum):
    kUnknown = -0xdeadbeef
    SLOT = 10
    FLOP = 20
    DRAW = 30


@default()
class CHANCE_OBTAIN_TYPE(IntEnum):
    kUnknown = -0xdeadbeef
    RECEIVE_ORGER = 10
    INVITE_NEW_USER = 20
    COIN_EXCHANGE = 30  # 积分兑换
    SIGN_IN = 40
    INVITE_FRIEND_BOOST = 60  # 邀请助力
    GO_TO_BOOST = 70


@default()
class RewardType(IntEnum):
    kUnknown = -0xdeadbeef
    Coupon = 10
    PuPoint = 20
    GiftCard = 30
    Sunrise = 40


@default()
class ActionTYPE(IntEnum):
    kUnknown = -0xdeadbeef
    BROWSE = 0
    SHARE = 10


@default()
class TaskType(IntEnum):
    kUnknown = -0xdeadbeef
    FLASH_SALE = 240
    CUSTOM_LOTTERY = 250
    TOPIC = 260
    USER_TASK = 270
    SCENE = 280


@default()
class TaskStatus(IntEnum):
    kUnknown = -0xdeadbeef
    Undone = 0
    Done = 10
    Expired = 20
    Receive = 30


@default()
class SPREAD_TAG(IntEnum):
    kUnknown = -0xdeadbeef
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


@default()
class SHARE_STATUS(IntEnum):
    kUnknown = -0xdeadbeef
    UNKNOWN = 0
    ERROR = 1
    EXPIRED = 2
    NULL = 3
    NORMAL = 4


class ERROR_CODE(IntEnum):
    CODE_SUCCESS = 0

    # COMMENT_ERROR_CODE
    ERR_COMMENT_PUSH = 13000  # 写评论失败
    ERR_COMMENT_HIT_KEYWORD_INTERCEPT = 13001
    ERR_COMMENT_HIT_FREQ_LIMIT = 13002  # 操作太过频繁，请1分钟后再试
    ERR_COMMENT_IS_BAN = 13004
    ERR_COMMENT_HIT_KEYWORD_BUSINESS_INTERCEPT = 13005
    ERR_COMMENT_HIT_COMMENT_DISCARD = 13006

    # LOTTERY_TEAM
    ERR_GET_TEAM_NO_EXIST = 32002
    ERR_GET_TEAM_FAIL = 33001
    ERR_JOIN_TEAM_FAIL = 33002
    ERR_CHANGE_TEAM_FAIL = 33003
    ERR_DO_NOT_JOIN_TEAM = 33004
    ERR_JOIN_LOTTERY_FAIL = 33005

    # LOGIN 403, [200000, 300000), exinclude 200099
    kForbidden = 403
    OUT_TOKEN = 200001
    kUnauthorized = 200208
    EXPIRED_TOKEN = 200304

    kRepeatedSignIn = 350011

    ERROR_TASK_NOT_GENERATED = 400104
    ERROR_TASK_DOES_NOT_EXIST = 400106

    CODE_PRODUCT_UPDATE = 500001


@dataclass
class PReceiverInfo:
    id: str
    address: str = ""
    room_num: str = ""
    lng_x: None | float = 0
    lat_y: None | float = 0
    receiver_name: str = ""
    phone_number: str = ""
    store_id: str = ""
    place_id: str = ""
    place_zip: int = 0
    city_zip: int = 0


@dataclass
class PPrize:
    level: int
    name: str
    type: RewardType


@dataclass
class PItem:
    price: int
    product_id: str
    store_product_id: str
    remark: str
    spread_tag: int
    selected_count: int


@dataclass
class PTask:
    task_id: str
    task_name: str  # 每日打卡
    activity_id: str
    task_type: TaskType
    action_type: ActionTYPE
    skim_time: int  # 浏览多少秒
    task_status: TaskStatus


@dataclass
class PLotteryInfo:
    id: str
    name: str
    type: LOTTERY_TYPE
    prizes: dict[int, PPrize] = field(default_factory=dict)
    task_system_link_id: None | str = None


@dataclass
class PChanceEntrance:
    type: CHANCE_OBTAIN_TYPE
    title: str
    attend_count: int  # 已获得次数
    limit_count: int  # 最大获得次数
    gain_num: int  # 每次完成可增加的次数
    target_value: int  # 需要的数量


@dataclass
class PProduct:
    # 价格 分
    price: int
    product_id: str
    store_product_id: str
    remark: str  # 商品备注
    spread_tag: SPREAD_TAG
    stock_quantity: int  # 库存
    quantity_limit: None | int = None  # 限购数量
    selected_count: int = 0  # 选购几件


@dataclass
class PDiscountShare:
    index: int  # 第{index}个领取的人得最大优惠券
    count: int  # 共{count}张优惠券
    share_id: str  # 红包ID


@dataclass
class PDiscountRule:
    id: str
    type: DiscountType
    condition_amount: int  # 6900
    discount_amount: int  # 700 满69减7元


@dataclass
class POrder:
    total_price: int
    time_create: int  # 1673265913282
    # TODO items
    discount_share: None | PDiscountShare = None  # 红包


@dataclass
class PBanner:
    title: str
    link_id: str


class ApiResults:
    class Error:
        def __init__(self,
                     func_name: str | None = None,
                     json: None | dict = None,
                     exception: None | Exception = None):
            if json:
                self.code = json.get("errcode")
                self.msg = json.get("errmsg", "")
                self.exception = None
            elif exception:
                self.code = self.msg = None
                self.exception = exception
            else:
                raise ValueError("参数无效")
            self.func_name = func_name or getframe(1).f_code.co_name

        def __str__(self) -> str:
            if self.exception:
                return f'{self.func_name} 异常: {"".join(format_exception(self.exception))}'
            else:
                return f'{self.func_name} 失败: code={self.code}, msg={self.msg}'

    @dataclass
    class RefreshToken:
        refresh_token: str
        access_expires: int

    @dataclass
    class SuId:
        id: str

    @dataclass
    class UserInfo:
        avatar: str
        nickname: str

    @dataclass
    class ReceiverInfo:
        receiver: PReceiverInfo

    @dataclass
    class SignIn:
        coin: int
        explanation: str

    @dataclass
    class SignPeriodInfo:
        days: int

    @dataclass
    class Banner:
        banners: list[PBanner]

    @dataclass
    class LotteryInfo:
        lottery: PLotteryInfo

    @dataclass
    class TaskGroupsData:
        tasks: list[PTask]

    @dataclass
    class TaskCompleted:
        pass

    @dataclass
    class ChanceEntrances:
        coin_balance: int
        entrances: list[PChanceEntrance]

    @dataclass
    class CoinExchanged:
        gain_num: int

    @dataclass
    class UserLotteryInfo:
        remain_chances: int

    @dataclass
    class LotteryResult:
        prize: PPrize

    @dataclass
    class ProductCollections:
        total_count: int
        products: list[PProduct]

    @dataclass
    class UsableCoupons:
        coupons: list[str]

    @dataclass
    class DeliveryTime:
        type: DeliveryTimeType
        dtime_promise: int

    @dataclass
    class OrderCreated:
        id: str

    @dataclass
    class OrdersList:
        total_count: int
        orders: list[POrder]

    @dataclass
    class WxDiscountShare:
        best_luck: bool
        reentry: bool
        user_count: int
        discount: None | PDiscountRule
        available: bool


class HttpMethod(Enum):
    kPut = "PUT"
    kGet = "GET"
    kPost = "POST"


class ClientType(IntEnum):
    kNative = 0
    kWeb = 1
    kMicroMsg = 2


if __name__ == "__main__":
    pass
