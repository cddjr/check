# -*- coding: utf-8 -*-
"""
cron: 30 8,22 * * *
new Env('盒马小镇');

找到请求https://market.m.taobao.com/app/ha/town/index.html
复制所有Cookies

TODO 优化、整理代码
"""
import asyncio
import json
from dataclasses import dataclass
from hashlib import md5
from http.cookies import SimpleCookie
from time import time
from traceback import format_exc
from typing import Optional, cast

import json_codec
from aiohttp import ClientResponse
from aiohttp_retry import JitterRetry, RetryClient
from yarl import URL

from utils import GetScriptConfig, MyStrEnum, aio_randomSleep, check, log


@dataclass
class TownLotus:
    id: str
    pickedByBuddy: bool
    point: int
    pointPlant: int
    status: int
    title: str

    @property
    def valid(self) -> bool:
        return self.status == 3


@dataclass
class TownRetentionBottle:
    title: str
    point: int
    valid: bool
    # 以下仅在valid为True时有效
    rewardId: Optional[str] = None
    taskInstanceId: Optional[str] = None

    @dataclass
    class CountDown:
        countDownTime: int
        rewardTarget: int
        taskInstanceId: str

        @property
        def valid(self) -> bool:
            return self.countDownTime <= 0
    countDownTaskModel: Optional[CountDown] = None


@dataclass
class TownCropInfo:
    class CropStatus(MyStrEnum):
        UNK01 = "1"
        CLOSEOVER = "4"
        OVERDATE = "5"
        FINISH = "6"

    class FundsType(MyStrEnum):
        MARKET = "1"
        PURCHASE = "2"

    actId: str
    actInstanceId: str
    cropStatus: CropStatus
    fundsType: FundsType
    currentLevel: int
    maxedLevel: int
    singleStep: int  # 每次消耗量
    progress: int
    totalProgress: int
    totalPercentage: str  # "1.76%"
    progressDesc: str  # "再喂养11次，就能变大鸡了"
    ratioValue: int = 1


@dataclass
class TownHomeInfo:
    balance: int
    cropInfoModels: list[TownCropInfo]
    dailyVisited: bool
    lotusModels: list[TownLotus]
    signed: bool
    retentionBottleModel: Optional[TownRetentionBottle] = None


@dataclass
class TownPickup:
    @dataclass
    class Model:
        balance: int
        # lotusId: str
        # point: int
    model: Model


class TownTaskCategory(MyStrEnum):
    OPEN = "open_page"
    VIEW = "viewPage"
    TRADE = "trade"
    ANSWER = "questionAnswer"
    SHARE = "share"


class TownTaskStatus(MyStrEnum):
    WAIT = "-1"
    ING = "0"
    FINISH = "1"


@dataclass
class TownTaskCenter:
    @dataclass
    class ActDetail:
        actId: str
    actDetail: ActDetail

    @dataclass
    class SignInModel:
        mainTitle: str
        showed: bool
        signed: bool
        signedDays: int
    signInModel: SignInModel

    @dataclass
    class TaskInfo:
        taskTitle: str
        taskStatus: TownTaskStatus
        taskCategory: TownTaskCategory

        _actId: str = ""
        taskId: Optional[str] = None
        cbdTaskInstanceId: Optional[str] = None
        currentProgress: Optional[int] = None
        totalProgress: Optional[int] = None
        linkUrl: Optional[str] = None

    taskInfoDTOS: list[TaskInfo]
    userSerialNo: str


@dataclass
class TownQuestion:
    @dataclass
    class Answer:
        answer: str
        id: str
        type: str

        @property
        def _right(self):
            '''是否正确答案'''
            return self.type == "right"
    answers: list[Answer]
    cbdTaskInstanceId: str
    currentProgress: int
    id: str
    question: str
    totalProgress: int

    _taskId: str = ""


@dataclass
class TownAnswerResult:
    currentProgress: int
    totalProgress: int
    result: bool  # 是否回答正确
    rewardValue: Optional[int] = None  # 答错的情况忘记抓包了 稳妥处理

    @property
    def more(self):
        '''是否还有题目'''
        return self.currentProgress < self.totalProgress


@dataclass
class TownGeneralReward:
    rewardId: str
    rewardType: str  # "pointAccount"
    rewardValue: int


@dataclass
class TownRewardResult:
    generalRewardModels: list[TownGeneralReward]


@dataclass
class TownIrrigateResult:
    balance: int
    cropInfoModel: TownCropInfo
    generalRewardModels: list[TownGeneralReward]
    retentionBottleModel: Optional[TownRetentionBottle] = None


class AliMTOP:
    __slots__ = ("_token",
                 "session",
                 )

    MTOP_SMT = "_m_h5_smt"
    MTOP_CODE = "_m_h5_c"
    MTOP_KEY = "_m_h5_tk"
    MTOP_KEY_ENC = "_m_h5_tk_enc"

    HOST = "https://h5api.m.taobao.com"
    VER = "2.6.1"
    APP_KEY = "12574478"
    API_VER = "1.0"

    class Error(Exception):
        pass

    class TokenError(Error):
        pass

    def __init__(self, cookies: SimpleCookie[str]):
        async def RetryWhenBusy(resp: ClientResponse) -> bool:
            obj = await resp.json()
            for r in obj.get("ret") or []:
                if cast(str, r).startswith("5000::"):
                    # 系统繁忙，请稍后再试
                    return False
            return True
        self.session = RetryClient(raise_for_status=True,
                                   retry_options=JitterRetry(attempts=3, evaluate_response_callback=RetryWhenBusy))
        self.session._client.headers["Accept"] = "*/*"
        self.session._client.headers["Accept-Encoding"] = "gzip, deflate"
        self.session._client.headers["Accept-Language"] = "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
        self.session._client.headers["X-Requested-With"] = "com.wudaokou.hippo"
        self.session._client.headers["User-Agent"] = "Mozilla/5.0 (Linux; Android 13; MyAndroid Build/230208.01; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/106.0.5249.126 Mobile Safari/537.36 AliApp(wdkhema/5.57.0) TTID/10004819@hmxs_android_5.57.0 WindVane/8.5.0 A2U/x"
        self.session._client.headers["Referer"] = "https://market.m.taobao.com/app/ha/town/index.html?_hema_title_bar=false&_hema_hide_status_bar=true&source=tab"
        self.session._client.headers["Connection"] = "keep-alive"

        # 初始化Cookies
        self._token = None
        self.session._client.cookie_jar.update_cookies(cookies)

    @property
    def token(self) -> Optional[str]:
        '''从Cookie中获取令牌'''
        if self._token is None:
            # key形如"4b98c94ac23f6c38b34bdd8d9b001ed0_1673345602074"
            key = self.session._client.cookie_jar.filter_cookies(
                URL(AliMTOP.HOST)).get(AliMTOP.MTOP_KEY)
            if key and (arr := key.value.split("_")):
                self._token = arr[0]
        return self._token

    def ClearToken(self):
        '''清除令牌'''
        self._token = None
        self.session._client.cookie_jar.clear(
            lambda x: x.key in [AliMTOP.MTOP_KEY,
                                AliMTOP.MTOP_KEY_ENC,
                                AliMTOP.MTOP_CODE])
        pass

    async def Request(self, api: str, data, ext={}, *, retry_if_token_expired=True):
        if not isinstance(data, str):
            data = json.dumps(json_codec.encode(data), separators=(',', ':'))
        # 拼接请求网址
        url = URL(AliMTOP.HOST).with_path(
            f"/h5/{api.lower()}/{AliMTOP.API_VER.lower()}")
        # 当前时间戳
        t = str(int(time() * 1000))
        # 计算签名
        sign = md5(f"{self.token}&{t}&{AliMTOP.APP_KEY}&{data}"
                   .encode(encoding="utf-8")).hexdigest()
        # 消息体
        params = {
            "jsv": AliMTOP.VER,
            "appKey": AliMTOP.APP_KEY,
            "t": t,
            "sign": sign,
            "api": api,
            "v": AliMTOP.API_VER,
            "type": "json",
            "dataType": "json",
            "data": data,
        }
        params.update(ext)

        async with self.session.request("GET", url, params=params) as response:
            obj = await response.json()
            if any("TOKEN_EMPTY" in r or "TOKEN_EXOIRED" in r
                   for r in obj.get("ret") or []):
                if retry_if_token_expired:
                    key = response.cookies.get(AliMTOP.MTOP_KEY)
                    if key and key.value:
                        # 令牌更新了 需要重试
                        self._token = None
                        log(f"新令牌: {self.token}")
                        return await self.Request(api, data, retry_if_token_expired=False)
                self.ClearToken()
                raise AliMTOP.TokenError(obj)
            if any("SUCCESS" in r for r in obj.get("ret") or []):
                return obj.get("data")
            else:
                raise AliMTOP.Error(obj)


class TOWN:
    __slots__ = ("check_item",
                 "cookie",
                 "mtop",
                 "shopIds",
                 )

    def __init__(self, check_item) -> None:
        self.check_item: dict = check_item
        self.mtop = None

    async def main(self):
        database = None
        data = {}
        name = self.check_item.get("name") or "default"
        msg: list[str] = []
        try:
            database = GetScriptConfig("hema_town.json")
            data = database.get_value_2(name) or {} if database else {}

            cookie = self.check_item.get("cookie")
            if not cookie:
                raise SystemExit("cookie 配置有误")

            cookie_lastest = data.get("cookie_lastest")
            if data.get("cookie_user_specified") != cookie \
                    or not cookie_lastest:
                # cookie手动更新了
                data["cookie_user_specified"] = cookie
                data["cookie_lastest"] = None
                self.mtop = AliMTOP(SimpleCookie(cookie))
            else:
                ss = "\n".join(cookie_lastest)
                self.mtop = AliMTOP(SimpleCookie(ss))

            if tracknick := self.mtop.session._client.cookie_jar.filter_cookies(URL()).get("tracknick"):
                log(f"账号: {tracknick.value}", msg)

            token = self.mtop.token
            log(f"当前令牌: {token}")

            self.shopIds = self.check_item.get("shopIds") or "no-store"

            for _ in "_":
                # 部分任务依赖shopIds 不配置就不会下发
                tasks = await self.QueryTasks()
                if not tasks:
                    log("获取任务失败", msg)
                    break
                if not tasks.signInModel.signed:
                    # 去签到
                    await aio_randomSleep(max=1.5)
                    if await self.SignIn():
                        tasks.signInModel.signed = True
                        tasks.signInModel.signedDays += 1
                        log(f"签到成功，已签{tasks.signInModel.signedDays}天", msg)
                else:
                    log(f"重复签到，已签{tasks.signInModel.signedDays}天", msg)
                for task in tasks.taskInfoDTOS:
                    if task.taskCategory != TownTaskCategory.ANSWER:
                        # TODO 其它任务待研究
                        continue
                    # 答题任务
                    if task.taskStatus != TownTaskStatus.ING:
                        continue
                    await aio_randomSleep(max=1.5)
                    while True:
                        q = await self.QueryQuestionTask(task)
                        if not q:
                            break
                        log(f"答题赚盒花({q.currentProgress+1}/{q.totalProgress})")
                        print(q.question)
                        # 筛选出正确答案(做好三长一短选最短的AI答题功能...)
                        if answer := next((a for a in q.answers if a._right), None):
                            # 假装思考3秒以上
                            await aio_randomSleep(min=3)
                            print(answer.answer)
                            if r := await self.AnswerQuestion(q, answer):
                                if r.result:
                                    print(f"答对了，奖励:{r.rewardValue}盒花")
                                await aio_randomSleep(min=0.5, max=1.0)
                                if r.more:
                                    # 拉取下一题
                                    continue
                        break
                # 任务全部完成
                # 接着尝试刷新盒花数量、领取所有盒花
                await aio_randomSleep(min=0.5, max=1.0)
                info = await self.GetHomeInfo()
                if not info:
                    log("获取小镇信息失败", msg)
                    break
                for lotus in info.lotusModels:
                    if not lotus.valid:
                        continue
                    log(f"可领取: [{lotus.title}]{lotus.point}盒花")
                    await aio_randomSleep(min=2, max=4)
                    if result := await self.PickupLotus(lotus):
                        info.balance = result.model.balance
                        log(f"成功领取了[{lotus.title}]{lotus.point}盒花", msg)
                if bottle := info.retentionBottleModel:
                    if bottle.valid:
                        # 可以领取
                        log(f"可领取: {bottle.point}盒花")
                        await aio_randomSleep(min=2, max=4)
                        if result := await self.PickupBottle(bottle):
                            info = result
                            log(f"成功领取了{bottle.point}盒花", msg)
                    else:
                        log(f"{bottle.title}: {bottle.point}盒花")
                    if count_down := bottle.countDownTaskModel:
                        if count_down.valid:
                            # 可以领取
                            log(f"可领取: {count_down.rewardTarget}盒花")
                            await aio_randomSleep(min=2, max=4)
                            if result := await self.ComputeTaskAndReward(count_down):
                                point = sum(
                                    r.rewardValue for r in result.generalRewardModels)
                                log(f"成功领取了{point}盒花", msg)
                        else:
                            log(f"还需等待{count_down.countDownTime}秒才能领取{count_down.rewardTarget}盒花")

                log(f"当前盒花: {info.balance}", msg)
                # 喂养、浇水 等...
                if not info.cropInfoModels:
                    log("解析错误: 没有配置cropInfoModels", msg)
                    break
                if len(info.cropInfoModels) > 1:
                    log("遇到特例 cropInfoModels数量超过1个", msg)
                    log(info.cropInfoModels)
                crop = info.cropInfoModels[0]
                if info.balance < crop.singleStep:
                    log(f"盒花少于{crop.singleStep}, 放弃操作", msg)
                # print(await self.QueryIrrigateLadder(crop))
                retentionBottleModel = None
                while info.balance >= crop.singleStep:
                    # 盒花余额足够本次操作
                    await aio_randomSleep(min=3, max=5)
                    if result := await self.IrrigateCrop(crop):
                        crop = result.cropInfoModel
                        info.balance = result.balance
                        info.cropInfoModels[0] = result.cropInfoModel
                        retentionBottleModel = result.retentionBottleModel
                        log(f" 操作成功: 总进度{crop.totalPercentage}")
                    else:
                        break
                log(f"进度: {crop.totalPercentage}", msg)
                log(f"等级: {crop.currentLevel}", msg)
                log(crop.progressDesc, msg)
                # TODO 如果前面没有领取info.retentionBottleModel 那么操作后会返回什么
                if bottle := retentionBottleModel:
                    if bottle.valid:
                        # 可以领取
                        log(f"可领取: {bottle.point}")
                        await aio_randomSleep(min=2, max=4)
                        if result := await self.PickupBottle(bottle):
                            info = result
                            log(f"成功领取了{bottle.point}盒花", msg)
                    else:
                        log(f"{bottle.title}: {bottle.point}盒花")
                    if count_down := bottle.countDownTaskModel:
                        if count_down.valid:
                            # 可以领取
                            log(f"可领取: {count_down.rewardTarget}盒花")
                            await aio_randomSleep(min=2, max=4)
                            if result := await self.ComputeTaskAndReward(count_down):
                                point = sum(
                                    r.rewardValue for r in result.generalRewardModels)
                                log(f"成功领取了{point}盒花", msg)
                        else:
                            log(f"还需等待{count_down.countDownTime}秒才能领取{count_down.rewardTarget}盒花")

        except Exception:
            log(f'失败: 请检查接口 {format_exc()}', msg)
        finally:
            if database:
                try:
                    if self.mtop:
                        data["cookie_lastest"] = [k.OutputString()
                                                  for k in self.mtop.session._client.cookie_jar]
                    database.set_value(name, data)
                except:
                    log(f'保存Cookie失败: {format_exc()}', msg)
            if self.mtop:
                await asyncio.gather(self.mtop.session.close(),
                                     asyncio.sleep(0.25))

        return "\n".join(msg)

    async def GetHomeInfo(self):
        assert self.mtop
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.homeInfo",
                                           data={"shopIds": self.shopIds},
                                           ext={"dip": 211427})
            return json_codec.decode(data, TownHomeInfo)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def PickupLotus(self, lotus: TownLotus):
        assert self.mtop
        try:
            data = await self.mtop.Request("mtop.wdk.hippotown.lotus.pickup",
                                           data={"lotusId": lotus.id},
                                           ext={"dip": 24529})
            return json_codec.decode(data, TownPickup)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def SignIn(self):
        '''签到'''
        assert self.mtop
        try:
            _ = await self.mtop.Request("mtop.wdk.hippotown.point.sign",
                                        data={})
            return True
        except:
            log(f'失败: {format_exc()}')
            return None

    async def PickupBottle(self, bottle: TownRetentionBottle):
        assert self.mtop
        assert bottle.valid
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.retentionReward",
                                           data={"rewardId": bottle.rewardId,
                                                 "taskInstanceId": bottle.taskInstanceId,
                                                 "shopIds": self.shopIds,
                                                 },
                                           ext={"dip": 211432})
            if data.get("result") != "true":
                raise AliMTOP.Error(data)
            await aio_randomSleep(max=1.5)
            return await self.GetHomeInfo()
        except:
            log(f'失败: {format_exc()}')
            return None

    async def QueryTasks(self):
        assert self.mtop
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.querytaskcenterpage",
                                           data={"shopIds": self.shopIds})
            task_center = json_codec.decode(data, TownTaskCenter)
            for task in task_center.taskInfoDTOS:
                task._actId = task_center.actDetail.actId
            return task_center
        except:
            log(f'失败: {format_exc()}')
            return None

    async def QueryQuestionTask(self, task: TownTaskCenter.TaskInfo):
        assert self.mtop
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.acquireAndQueryQuestionTask",
                                           data={"shopIds": self.shopIds,
                                                 "taskId": task.taskId,
                                                 "actId": task._actId,
                                                 "cbdTaskInstanceId": task.cbdTaskInstanceId})
            q = json_codec.decode(data, TownQuestion)
            assert task.taskId
            q._taskId = task.taskId
            task.currentProgress = q.currentProgress
            task.totalProgress = q.totalProgress
            task.cbdTaskInstanceId = q.cbdTaskInstanceId
            return q
        except:
            log(f'失败: {format_exc()}')
            return None

    async def AnswerQuestion(self, question: TownQuestion, answer: TownQuestion.Answer):
        assert self.mtop
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.answerQuestionTask",
                                           data={"shopIds": self.shopIds,
                                                 "taskId": question._taskId,
                                                 "questionId": question.id,
                                                 "answerId": answer.id,
                                                 "cbdTaskInstanceId": question.cbdTaskInstanceId})
            return json_codec.decode(data, TownAnswerResult)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def IrrigateCrop(self, crop: TownCropInfo):
        '''喂鸡、浇水等操作'''
        assert self.mtop
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.irrigateCrop",
                                           data={"actInstanceId": crop.actInstanceId})
            return json_codec.decode(data, TownIrrigateResult)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def QueryIrrigateLadder(self, crop: TownCropInfo):
        assert self.mtop
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.queryIrrigateLadder",
                                           data={"actId": crop.actId})
            return json.dumps(data, indent=4)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def ComputeTaskAndReward(self, count_down: TownRetentionBottle.CountDown):
        assert self.mtop
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.computeTaskAndReward",
                                           data={"factType": "count_down",
                                                 "taskInstanceId": count_down.taskInstanceId,
                                                 "shopIds": self.shopIds})
            return json_codec.decode(data, TownRewardResult)
        except:
            log(f'失败: {format_exc()}')
            return None


@check(run_script_name="盒马小镇", run_script_expression="hema_town")
def main(*args, **kwargs):
    return asyncio.run(TOWN(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
