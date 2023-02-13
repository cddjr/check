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
from math import ceil
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
    alertTitle: str  # "明日07:00可领哦"
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
        def seconds(self) -> int:
            return int(self.countDownTime / 1000)

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


@dataclass
class TownTask:
    class Category(MyStrEnum):
        OPEN = "open_page"
        VIEW = "viewPage"
        TRADE = "trade"
        ANSWER = "questionAnswer"
        SHARE = "share"

    class Status(MyStrEnum):
        WAIT = "-1"
        ING = "0"
        FINISH = "1"

    taskTitle: str
    taskCategory: Category

    taskStatus: Status = Status.ING
    dayRemainingLimit: int = 0  # 当天还可做几次任务

    taskId: Optional[str] = None
    cbdTaskInstanceId: Optional[str] = None
    currentProgress: Optional[int] = None
    totalProgress: Optional[int] = None
    linkUrl: Optional[str] = None


@dataclass
class TownTasks(TownTask):
    taskList: Optional[list[TownTask]] = None


@dataclass
class TownQueryTaskResult:
    actId: str

    @dataclass
    class Attributes:
        # 页面浏览多少秒可得奖励 如"15"
        viewPegeDuration: int
        cbdTaskId: str
        viewPegeUrl: str

    taskAttributes: Attributes
    taskCategory: TownTask.Category
    taskId: str
    taskStatus: TownTask.Status
    taskTitle: str


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

    taskInfoDTOS: list[TownTasks]
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


@dataclass
class TownEventAcceptResult:
    @dataclass
    class Content:
        @dataclass
        class Award:
            awardType: str  # "point"
            awardValue: int
        processCode: list[str]
        awards: list[Award]
    actionCode: str
    actionType: str
    bizUniqueId: str
    content: Content
    contentType: str
    persistent: str


@dataclass
class TownLoginData:
    autoLoginToken: str
    expires: int
    cookies: list[str]
    sid: str
    nick: str
    uidDigest: str
    userId: int
    autoLoginToken_expire_in: int


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

    def __init__(self):
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
        self._token = None

    @property
    def cookies(self) -> list[str]:
        return [k.OutputString() for k in self.session._client.cookie_jar]

    @cookies.setter
    def cookies(self, cookies: list[str]):
        for c in cookies:
            self.session._client.cookie_jar.update_cookies(SimpleCookie(c))

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
        # 拼接请求网址
        api = params["api"].lower()
        v = params["v"].lower()
        url = URL(AliMTOP.HOST).with_path(f"/h5/{api}/{v}")

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
                 "data",
                 "shopIds",
                 )

    def __init__(self, check_item) -> None:
        self.check_item: dict = check_item

    async def main(self):
        msg: list[str] = []
        database = None
        login_data = None
        self.data = {}

        user_id = self.check_item.get("user_id")
        if not user_id:
            raise SystemExit("user_id 配置有误")
        login_token = self.check_item.get("token")
        if not login_token:
            raise SystemExit("token 配置有误")
        umid = self.check_item.get("umidToken")
        if not umid:
            raise SystemExit("umidToken 配置有误")
        wua = self.check_item.get("wua")
        if not wua:
            raise SystemExit("wua 配置有误")

        self.mtop = AliMTOP()

        try:
            database = GetScriptConfig("hema_town.json")
            self.data = database.get_value_2(user_id) or {} if database else {}

            login_data = json_codec.decode(
                self.data["autologin"], TownLoginData) if "autologin" in self.data else None

            nick = login_data.nick if login_data else self.check_item.get(
                "name") or user_id
            log(f"账号: {nick}", msg)

            if self.data.get("token_user_specified") != login_token \
                    or login_data is None:
                # token手动更新了
                self.data["token_user_specified"] = login_token
                if "autologin" in self.data:
                    del self.data["autologin"]
                token = login_token
            else:
                self.mtop.cookies = login_data.cookies
                token = login_data.autoLoginToken

            log(f"当前MTOP令牌: {self.mtop.token}")

            self.shopIds = self.check_item.get("shopIds") or "no-store"

            for _ in "_":
                if login_result := await self.AutoLogin(user_id, token, umid, wua):
                    # 更新Cookie
                    login_data = login_result
                    self.mtop.cookies = login_data.cookies
                else:
                    log("自动登录失败", msg)
                    break

                # 部分任务依赖shopIds 不配置就不会下发
                tasks = await self.GetTasks()
                if not tasks:
                    log("获取任务失败", msg)
                    break
                if not tasks.signInModel.signed:
                    # 去签到
                    await aio_randomSleep(max=1.5)
                    if await self.SignIn():
                        tasks.signInModel.signed = True
                        tasks.signInModel.signedDays += 1
                        log(f"签到成功: 已签{tasks.signInModel.signedDays}天", msg)
                else:
                    log(f"重复签到: 已签{tasks.signInModel.signedDays}天", msg)
                for task in tasks.taskInfoDTOS:
                    if task.taskStatus != TownTask.Status.ING:
                        continue
                    if task.taskCategory == TownTask.Category.OPEN:
                        # 浏览任务
                        taskList = task.taskList or [task]
                        for sub_task in taskList:
                            if sub_task.taskStatus != TownTask.Status.ING:
                                continue
                            if sub_task.taskCategory != TownTask.Category.OPEN:
                                # 这种情况可能吗
                                log(
                                    f"遇到特例 sub_task.taskCategory={sub_task.taskCategory}", msg)
                                continue
                            log(f"正在浏览: {sub_task.taskTitle}...")
                            await aio_randomSleep(max=1.5)
                            # 查询需要浏览多少秒等配置
                            if task_options := await self.QueryTask(tasks, sub_task):
                                await aio_randomSleep(min=task_options.taskAttributes.viewPegeDuration,
                                                      max=task_options.taskAttributes.viewPegeDuration+3)
                            else:
                                await aio_randomSleep(min=3, max=5)
                            if result := await self.EventAccept(tasks, sub_task):
                                total_points = sum(a.awardValue for a in sum(
                                    [r.content.awards for r in result], []))
                                log(f"已完成: 可领取{total_points}盒花")
                        continue
                    elif task.taskCategory != TownTask.Category.ANSWER:
                        # TODO 其它任务待研究
                        continue
                    # 答题任务
                    await aio_randomSleep(max=1.5)
                    while True:
                        q = await self.GetQuestionTask(tasks, task)
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
                                    print(f"答对了，奖励: {r.rewardValue}盒花")
                                await aio_randomSleep(min=0.5, max=1.0)
                                if r.more:
                                    # 拉取下一题
                                    continue
                        break
                # 任务全部完成
                # 接着尝试刷新盒花数量、领取所有盒花奖励
                await aio_randomSleep(min=0.5, max=1.0)
                info = await self.GetHomeInfo()
                if not info:
                    log("获取小镇信息失败", msg)
                    break
                if not info.cropInfoModels:
                    # TODO 没有养东西?
                    log("解析错误: 没有配置cropInfoModels", msg)
                    break
                summay_points: dict[str, int] = {}
                for lotus in info.lotusModels:
                    if not lotus.valid:
                        continue
                    await aio_randomSleep(min=2, max=4)
                    if result := await self.PickupLotus(lotus):
                        info.balance = result.model.balance
                        summay_points[lotus.title] = summay_points.get(
                            lotus.title, 0) + lotus.point
                for k, v in summay_points.items():
                    log(f"成功领取: [{k}]{v}盒花", msg)

                if info.retentionBottleModel:
                    result = await self.ProcessBottle(info.retentionBottleModel)
                    msg.extend(result[0])
                    info.balance += result[1]

                if len(info.cropInfoModels) > 1:
                    log("遇到特例 cropInfoModels数量超过1个", msg)
                    log(info.cropInfoModels)
                crop = info.cropInfoModels[0]
                if info.balance < crop.singleStep:
                    log(f"盒花少于{crop.singleStep}, 放弃养成", msg)
                # 盒花养成
                while info.balance >= crop.singleStep:
                    # 盒花余额足够本次养成
                    await aio_randomSleep(min=3, max=5)
                    if crop_result := await self.IrrigateCrop(crop):
                        crop = crop_result.cropInfoModel
                        info.balance = crop_result.balance
                        info.cropInfoModels[0] = crop_result.cropInfoModel
                        log(f"养成操作成功: 当前进度{crop.totalPercentage}")
                        if crop_result.retentionBottleModel:
                            await aio_randomSleep(max=3)
                            result = await self.ProcessBottle(crop_result.retentionBottleModel)
                            msg.extend(result[0])
                            info.balance += result[1]
                        if crop_result.generalRewardModels:
                            # 升级奖励
                            await aio_randomSleep(max=3)
                            if info_refresh := await self.GetHomeInfo():
                                info = info_refresh
                                for lotus in info.lotusModels:
                                    if not lotus.valid:
                                        continue
                                    await aio_randomSleep(min=2, max=4)
                                    if pickup_result := await self.PickupLotus(lotus):
                                        info.balance = pickup_result.model.balance
                                        log(f"成功领取: [{lotus.title}]{lotus.point}盒花", msg)
                    else:
                        break
                log(f"盒花: {info.balance}", msg)
                log(f"进度: {crop.totalPercentage}", msg)
                log(f"等级: {crop.currentLevel}", msg)
                log(crop.progressDesc, msg)
                msg += self.EstimatedRemainingTime(crop)
        except Exception:
            log(f'失败: 请检查接口 {format_exc()}', msg)
        finally:
            if database:
                try:
                    if login_data:
                        if self.mtop:
                            login_data.cookies = self.mtop.cookies
                        self.data["autologin"] = json_codec.encode(login_data)
                    database.set_value(user_id, self.data)
                except:
                    log(f'保存Cookie失败: {format_exc()}', msg)
            if self.mtop:
                await asyncio.gather(self.mtop.session.close(),
                                     asyncio.sleep(0.25))

        return "\n".join(msg)

    def EstimatedRemainingTime(self, crop: TownCropInfo):
        @dataclass
        class CropRecord:
            actId: str
            actInstanceId: str
            progress: int
            datestamp: int
            estimated: Optional[int]

        msg: list[str] = []
        crops = json_codec.decode(self.data.get("crops") or {},
                                  dict[str, CropRecord])
        estimated = None
        for _ in "_":
            # "1.41%" -> 141
            # 0~10000
            curr_progress = int(
                float(crop.totalPercentage.rstrip("%")) * 100.0)
            curr_time = int(time()*1000)
            if prev_record := crops.get(crop.actInstanceId):
                estimated = prev_record.estimated
                time_diff = curr_time - prev_record.datestamp
                if time_diff < 86400_000:
                    # 不足24小时 不计算
                    break
                # 0~10000
                progress_diff = curr_progress - prev_record.progress
                if progress_diff < 0:
                    log(f"遇到特例 养成进度{progress_diff/100.0}%", msg)
                    break
                if progress_diff == 0:
                    # 进度超过一天没有增加
                    if prev_record.estimated is None:
                        break
                    # 增加上次预估的时间
                    prev_record.estimated += int(time_diff / 86400_000)
                else:
                    prev_record.estimated = ceil(
                        (10000 - curr_progress) / (progress_diff / time_diff * 86400_000))
                prev_record.datestamp = curr_time
                prev_record.progress = curr_progress
                estimated = prev_record.estimated
            else:
                crops[crop.actInstanceId] = CropRecord(
                    actId=crop.actId,
                    actInstanceId=crop.actInstanceId,
                    progress=curr_progress,
                    datestamp=curr_time,
                    estimated=None,
                )
        else:
            # 数据有改动
            self.data["crops"] = json_codec.encode(crops)
        if estimated is not None:
            log(f"预计还需{estimated}天实现目标", msg)
        return msg

    async def ProcessBottle(self, bottle: TownRetentionBottle):
        '''次留瓶任务、倒计时任务'''
        total_points = 0
        msg: list[str] = []
        if bottle.valid:
            # 可以领取次留瓶任务
            await aio_randomSleep(min=2, max=4)
            if await self.PickupBottle(bottle):
                total_points += bottle.point
                log(f"成功领取: [次留瓶任务奖励]{bottle.point}盒花", msg)
        else:
            log(f"{bottle.alertTitle}: [次留瓶]{bottle.point}盒花")
        if count_down := bottle.countDownTaskModel:
            if count_down.countDownTime > 0:
                if count_down.seconds < 60:
                    # 60秒内的倒计时 我们尝试等
                    log(f"等待{count_down.seconds}秒后领取[倒计时任务奖励]")
                    await aio_randomSleep(min=2+count_down.seconds,
                                          max=6+count_down.seconds)
                    count_down.countDownTime = 0

            if count_down.countDownTime <= 0:
                # 可以领取倒计时任务
                await aio_randomSleep(min=2, max=4)
                if result := await self.ComputeTaskAndReward(count_down):
                    point = sum(r.rewardValue
                                for r in result.generalRewardModels)
                    log(f"成功领取: [倒计时任务奖励]{point}盒花", msg)
                    total_points += point
            else:
                log(f"{count_down.seconds}秒后可领{count_down.rewardTarget}盒花")
        return (msg, total_points)

    async def GetHomeInfo(self):
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.homeInfo",
                                           data={"shopIds": self.shopIds},
                                           ext={"dip": 211427})
            return json_codec.decode(data, TownHomeInfo)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def PickupLotus(self, lotus: TownLotus):
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
        try:
            _ = await self.mtop.Request("mtop.wdk.hippotown.point.sign",
                                        data={})
            return True
        except:
            log(f'失败: {format_exc()}')
            return None

    async def PickupBottle(self, bottle: TownRetentionBottle):
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
            return True
        except:
            log(f'失败: {format_exc()}')
            return None

    async def GetTasks(self):
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.querytaskcenterpage",
                                           data={"shopIds": self.shopIds})
            return json_codec.decode(data, TownTaskCenter)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def GetQuestionTask(self, task_center: TownTaskCenter, task: TownTask):
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.acquireAndQueryQuestionTask",
                                           data={"shopIds": self.shopIds,
                                                 "taskId": task.taskId,
                                                 "actId": task_center.actDetail.actId,
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
        '''养成'''
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.irrigateCrop",
                                           data={"actInstanceId": crop.actInstanceId})
            return json_codec.decode(data, TownIrrigateResult)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def QueryIrrigateLadder(self, crop: TownCropInfo):
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.queryIrrigateLadder",
                                           data={"actId": crop.actId})
            return json.dumps(data, indent=4)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def ComputeTaskAndReward(self, count_down: TownRetentionBottle.CountDown):
        try:
            data = await self.mtop.Request("mtop.wdk.fission.hippotown.computeTaskAndReward",
                                           data={"factType": "count_down",
                                                 "taskInstanceId": count_down.taskInstanceId,
                                                 "shopIds": self.shopIds})
            return json_codec.decode(data, TownRewardResult)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def QueryTask(self, task_center: TownTaskCenter, task: TownTask):
        try:
            data = await self.mtop.Request("mtop.wdk.energy.task.query",
                                           data={"actId": task_center.actDetail.actId,
                                                 "taskId": task.taskId,
                                                 })
            return json_codec.decode(data, TownQueryTaskResult)
        except:
            log(f'失败: {format_exc()}')
            return None

    async def EventAccept(self, task_center: TownTaskCenter, task: TownTask):
        '''上报页面浏览完成事件'''
        try:
            content = json.dumps({"actId": task_center.actDetail.actId,
                                  "taskId": task.taskId,
                                  }, separators=(',', ':'))
            data = await self.mtop.Request(
                api="mtop.wdk.mimir.event.accept",
                ext={"v": "1.3"},
                data={
                    "eventId": "1",
                    "gmtModified": "0",
                    "bizUniqueId": str(int(time() * 1000)),
                    "eventType": "3",
                    "gmtCreate": "0",
                    "version": "1",
                    "content": content,
                    "eventCode": "1001",
                    "asyncProcess": "false",
                    "name": "用户浏览会场事件",
                    "asac": "2A20A099MA1XU8I8UC66B5",
                    "bizIdentity": '{"bizId":"3","tenantID":"hm"}',
                    "persistent": "-1",
                    "contentType": "1"
                })

            @dataclass
            class _Result:
                @dataclass
                class Content:
                    processCode: str
                    awards: str
                actionCode: str
                actionType: str
                bizUniqueId: str
                content: Content
                contentType: str
                persistent: str

            result: list[TownEventAcceptResult] = []
            for item in data.get("result") or []:
                raw = json_codec.decode(item, _Result)
                processCode = json_codec.decode(
                    json.loads(raw.content.processCode), list[str])
                awards = json_codec.decode(json.loads(
                    raw.content.awards), list[TownEventAcceptResult.Content.Award])
                result.append(TownEventAcceptResult(
                    actionCode=raw.actionCode,
                    actionType=raw.actionType,
                    bizUniqueId=raw.bizUniqueId,
                    contentType=raw.contentType,
                    persistent=raw.persistent,
                    content=TownEventAcceptResult.Content(
                        processCode,
                        awards,
                    ),
                ))
            return result
        except:
            log(f'失败: {format_exc()}')
            return None

    async def AutoLogin(self, user: str, token: str, umid: str, wua: str):
        '''
        获取最新的Cookie 暂时写死一些数据
        http://acs.m.taobao.com/gw/com.taobao.mtop.mloginunitservice.autologin/1.0/
        '''
        try:
            content = {
                "userId": user,
                "tokenInfo": json.dumps({"appName": "23228014",
                                        "token": token}, separators=(',', ':')),
                "riskControlInfo": json.dumps({"umidToken": umid,
                                               "wua": wua}, separators=(',', ':')),
            }
            data = await self.mtop.Request("com.taobao.mtop.mloginunitservice.autologin", content)

            @dataclass
            class LoginResult:
                data: str
                displayNick: str
                hid: str
                sid: str
                site: str

                @dataclass
                class Ext:
                    encryptUserId: str
                    biometricId: str
                extMap: Ext
            if data := data.get("returnValue"):
                result = json_codec.decode(data, LoginResult)
            else:
                raise ValueError

            return json_codec.decode(json.loads(result.data), TownLoginData)
        except:
            log(f'失败: {format_exc()}')
            return None


@check(run_script_name="盒马小镇", run_script_expression="hema_town")
def main(*args, **kwargs):
    return asyncio.run(TOWN(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
