# -*- coding: utf-8 -*-
"""
cron: 0 1,20 * * *
new Env('朴朴');

微信登录朴朴app
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token
"""
from time import time, sleep
from utils import check, log, aio_randomSleep, GetScriptConfig
from traceback import format_exception
from pupu_api import Api
from pupu_types import *
import asyncio
import random
import sys
assert sys.version_info >= (3, 10)


class PUPU:
    __slots__ = ("api", "config_dict")

    nickname: str | None = None
    avatar: str | None = None

    def __init__(self, check_item) -> None:
        self.check_item: dict = check_item
        self.api = None
        self.config = self.config_dict = None
        self.refresh_token_user_specified = None

    def LoadConfig(self):
        if not self.config:
            return
        self.config_dict = self.config.get_value_2(self.device_id) or {}

        self.refresh_token_user_specified = self.check_item.get(
            "refresh_token")
        refresh_token_prev_spec = self.config_dict.get(
            "refresh_token_user_specified")

        if not self.refresh_token_user_specified \
                or self.refresh_token_user_specified != refresh_token_prev_spec:
            # 说明用户手动修改了token 以用户的为准
            self.refresh_token = self.refresh_token_user_specified
        else:
            self.refresh_token = self.config_dict.get(
                "refresh_token_lastest", self.refresh_token_user_specified)

        if not self.refresh_token:
            raise SystemExit("refresh_token 配置有误")

        self.api = Api(self.device_id,
                       self.refresh_token,
                       self.config_dict.get("access_expires", 0))

        if (time() + 360.0) * 1000.0 > self.api.expires_in:
            self.api.access_token = None
        else:
            self.api.access_token = self.config_dict.get("access_token")

        self.api.su_id = self.config_dict.get("su_id")
        self.api.receiver = PReceiverInfo(
            self.config_dict.get("recv_id", ""),
            store_id=self.config_dict.get("store_id", ""),
            place_id=self.config_dict.get("place_id", ""),
            city_zip=int(self.config_dict.get("city_zip", 0)),
            place_zip=int(self.config_dict.get("place_zip", 0)))
        self.api.user_id = self.config_dict.get("user_id")

        self.nickname = self.config_dict.get("nickname")
        self.avatar = self.config_dict.get("avatar")

    def SaveConfig(self):
        if not self.config:
            return
        if self.config_dict is None:
            self.config_dict = {}
        self.config_dict["nickname"] = self.nickname or ""
        self.config_dict["refresh_token_user_specified"] = self.refresh_token_user_specified or ""
        self.config_dict["refresh_token_lastest"] = self.api.refresh_token or ""
        self.config_dict["access_token"] = self.api.access_token or ""
        self.config_dict["access_expires"] = self.api.expires_in
        self.config_dict["su_id"] = self.api.su_id or ""
        self.config_dict["user_id"] = self.api.user_id or ""
        self.config_dict["recv_id"] = self.api.receiver.id if self.api.receiver else ""
        self.config_dict["store_id"] = self.api.receiver.store_id if self.api.receiver else ""
        self.config_dict["place_id"] = self.api.receiver.place_id if self.api.receiver else ""
        self.config_dict["city_zip"] = self.api.receiver.city_zip if self.api.receiver else 0
        self.config_dict["place_zip"] = self.api.receiver.place_zip if self.api.receiver else 0
        self.config_dict["avatar"] = self.avatar or ""
        self.config.set_value(self.device_id, self.config_dict)

    class Leave(BaseException):
        pass

    async def Lottery(self, id: str):
        """抽奖"""
        msg: list[str] = []
        # 首先获取每日任务
        info = await self.api.GetLotteryInfo(id)
        if isinstance(info, ApiResults.Error):
            log(info, msg)
            return msg
        elif info.lottery.type != LOTTERY_TYPE.DRAW:
            log(f'活动类型不支持: {info.lottery.type}', msg)
            return msg
        log(f'正在进行 [{info.lottery.name}]', msg)
        # 同时拉取任务列表和抽奖机会兑换列表
        task_groups, chance_info = await asyncio.gather(
            self.api.GetTaskGroupsData(info.lottery),
            self.api.GetChanceEntrances(info.lottery))
        if isinstance(task_groups, ApiResults.Error):
            log(task_groups, msg)
        elif not task_groups.tasks:
            log(f'{info.lottery.name}: 没有配置任务')
        else:
            # 然后开始做任务
            for task in task_groups.tasks:
                if task.task_status == TaskStatus.Undone:
                    # 每个任务至少间隔2~5秒的时间
                    _, task_result = await asyncio.gather(
                        aio_randomSleep(2, 5),
                        self.api.PostPageTaskComplete(info.lottery, task))
                    if isinstance(task_result, ApiResults.Error):
                        log(task_result)
        # 接着尝试积分兑换
        exchange_count = 0
        while (True):
            if isinstance(chance_info, ApiResults.Error):
                # 拉取失败了 直接退出兑换循环
                log(chance_info, msg)
                break
            for entrance in chance_info.entrances:
                if entrance.type == CHANCE_OBTAIN_TYPE.COIN_EXCHANGE:
                    # 目前只支持积分兑换
                    break
            else:
                # 没有可用的积分兑换入口
                entrance = None
            if entrance:
                while chance_info.coin_balance >= entrance.target_value \
                        and exchange_count < self.exchange_limit:
                    # 积分足够、兑换次数没超过限制
                    exchange_result = await self.api.CoinExchange(info.lottery, entrance)
                    if isinstance(exchange_result, ApiResults.Error):
                        log(exchange_result)
                        break
                    exchange_count += 1
                    log(f'    第{exchange_count}次{entrance.title}: 成功兑换{exchange_result.gain_num}次抽奖机会')
                    # 更新积分余额
                    chance_info = await self.api.GetChanceEntrances(info.lottery)
                    if isinstance(chance_info, ApiResults.Error):
                        # 拉取失败了
                        log(chance_info)
                        break
                else:
                    if chance_info.coin_balance < entrance.target_value:
                        log(f" 当前积分{chance_info.coin_balance}少于{entrance.target_value}, 放弃兑换")
                if exchange_count > 0:
                    # 成功兑换了积分后需要等待2秒确保抽奖机会数更新
                    await asyncio.sleep(2)
            # 接着获取有多少次抽奖机会
            chances_info = await self.api.GetUserLotteryInfo(info.lottery)
            if isinstance(chances_info, ApiResults.Error):
                log(chances_info, msg)
                break
            if chances_info.remain_chances > 0:
                log(f' 当前有{chances_info.remain_chances}次抽奖机会', msg)
                for i in range(chances_info.remain_chances):
                    # 每次抽奖至少间隔1~5秒的时间
                    _, lottery_result = await asyncio.gather(
                        aio_randomSleep(1, 5),
                        self.api.Lottery(info.lottery))
                    if isinstance(lottery_result, ApiResults.Error):
                        log(f'  第{i+1}次抽奖: {lottery_result}', msg)
                    else:
                        log(f'  第{i+1}次抽奖: {lottery_result.prize.name}', msg)
                # 稍等片刻确保积分余额更新
                await asyncio.sleep(2)
            else:
                log(' 没有抽奖机会', msg)
                break
            # 获取积分余额
            chance_info = await self.api.GetChanceEntrances(info.lottery)
        return msg

    async def main(self):
        msg: list[str] = []
        try:
            # 是否要检测价格
            if len(sys.argv) >= 2 and sys.argv[1] == "extra":
                self.watch = self.check_item.get("watch", False)
                self.buy = self.check_item.get("buy", False)
                if not (self.watch or self.buy):
                    log("当前账号没有启用价格监控或自动下单")
                    exit()
            else:
                self.watch = False
                self.buy = False

            self.device_id = self.check_item.get("device_id", "").upper()
            if not self.device_id:
                raise SystemExit("device_id 配置有误")

            self.config = GetScriptConfig("pupu")
            self.PUSH_KEY = self.check_item.get("PUSH_KEY")
            self.addr_filter = self.check_item.get("addr_filter")

            self.LoadConfig()

            if not self.api.access_token:
                log("重新获取 access_token")
                self.api.user_id = None
                result = await self.api.RefreshAccessToken()
                if isinstance(result, ApiResults.Error):
                    log(result, msg)
                    raise self.Leave
                elif result.refresh_token != self.refresh_token:
                    self.refresh_token = result.refresh_token
                    log(f"令牌已更新为: {result.refresh_token}")
                self.nickname = self.api.nickname

            log(f'账号: {self.nickname}', msg)

            # 确保收货地址总是最新的
            initial_tasks = [self.api.GetReceiver(filter=self.addr_filter)]
            if not self.api.su_id:
                initial_tasks.append(self.api.GetSuID())
            result = (await asyncio.gather(*initial_tasks))[0]
            if isinstance(result, ApiResults.Error):
                log(result, msg)
                raise self.Leave
            assert isinstance(result, ApiResults.ReceiverInfo)
            log(f'收货地址: {result.receiver.address} {result.receiver.room_num}')
            log(f'仓库ID: {result.receiver.store_id}')

            if self.watch or self.buy:
                # TODO 价格监控
                raise NotImplementedError
            else:
                # 开始签到
                result = await self.api.SignIn()
                if isinstance(result, ApiResults.Error):
                    if result.code == ERROR_CODE.kRepeatedSignIn:
                        log("重复签到: 忽略", msg)
                    else:
                        log(result, msg)
                else:
                    log(f'签到成功: 奖励积分+{result.coin} {result.explanation}', msg)

                async def __GetSignPeriodInfo():
                    """和 GetBanner 并行发送"""
                    result = await self.api.GetSignPeriodInfo()
                    if isinstance(result, ApiResults.Error):
                        log(result, msg)
                    else:
                        log(f'签到信息: 本周连续签到{result.days}天', msg)

                find_lottery = self.check_item.get("find_lottery", True)
                lottery_ids: list[str] = []
                if find_lottery:
                    _, banner_result = await asyncio.gather(
                        __GetSignPeriodInfo(),
                        self.api.GetBanner(BANNER_LINK_TYPE.CUSTOM_LOTTERY,
                                           position_types=[60, 220, 560, 850, 860, 890]))
                    if isinstance(banner_result, ApiResults.Error):
                        log(banner_result, msg)
                    else:
                        for b in banner_result.banners:
                            lottery_ids.append(b.link_id)
                            log(f" 找到抽奖: {b.title}")
                else:
                    await __GetSignPeriodInfo()
                    id = self.check_item.get("lottery_id")
                    if id:
                        if isinstance(id, str):
                            lottery_ids.append(id)
                        elif isinstance(id, list[str]):
                            lottery_ids = id
                if len(lottery_ids) > 0:
                    self.exchange_limit = self.check_item.get(
                        "coin_exchange", 0)
                    log(f'积分兑换限制数: {self.exchange_limit}次', msg)
                    for id in lottery_ids:
                        # 串行抽奖 确保print按顺序执行
                        msg += await self.Lottery(id)
                else:
                    log("无抽奖活动")
        except self.Leave:
            pass
        except Exception as e:
            log(f'失败: 请检查接口 {"".join(format_exception(e))}', msg)
        finally:
            self.SaveConfig()
            if self.api:
                await self.api.Release()
                self.api = None
        return "\n".join(msg)


@check(run_script_name="朴朴", run_script_expression="pupu", interval_max=0)
def main(*args, **kwargs):
    return asyncio.run(PUPU(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
