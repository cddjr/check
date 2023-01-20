# -*- coding: utf-8 -*-
"""
cron: 30 9,23 * * *
new Env('朴朴抽奖');

微信登录朴朴app
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token

lottery_id 手动配置抽奖id 支持字符串数组或单个字符串
find_lottery 是否自动获取抽奖活动, 默认自动(部分藏的很深的抽奖暂时需要手动配置id)
coin_exchange 每个抽奖活动可兑换多少次朴分, 默认0次不兑换
"""
from utils import check, log, aio_randomSleep
from traceback import format_exception
from typing import Iterable
from pupu_api import Client as PClient
from pupu_types import *
import asyncio
import sys
assert sys.version_info >= (3, 10)


class PUPU:

    __slots__ = ("check_item",
                 "device_id",
                 "refresh_token",
                 "exchange_limit",
                 )

    def __init__(self, check_item) -> None:
        self.check_item: dict = check_item

    async def main(self):
        msg: list[str] = []
        try:
            self.device_id = self.check_item.get("device_id", "")
            self.refresh_token = self.check_item.get("refresh_token")
            if not self.device_id:
                raise SystemExit("device_id 配置有误")
            if not self.refresh_token:
                raise SystemExit("refresh_token 配置有误")

            msg += await self.Lottery()
        except Exception as e:
            log(f'失败: 请检查接口 {"".join(format_exception(e))}', msg)
        return "\n".join(msg)

    async def Lottery(self):
        msg: list[str] = []
        async with PClient(self.device_id, self.refresh_token) as api:
            result = await api.InitializeToken(self.check_item.get("addr_filter"))
            if isinstance(result, ApiResults.Error):
                log(result, msg)
                return msg

            log(f'账号: {api.nickname}', msg)

            lottery_ids = set[str]()
            id = self.check_item.get("lottery_id")
            if id:
                if isinstance(id, str):
                    lottery_ids.add(id)
                elif isinstance(id, Iterable):
                    lottery_ids.update(id)

            if self.check_item.get("find_lottery", True):
                banner_result = await api.GetBanner(BANNER_LINK_TYPE.CUSTOM_LOTTERY,
                                                    position_types=[60, 220, 560, 850, 860, 890])
                if isinstance(banner_result, ApiResults.Error):
                    log(banner_result, msg)
                else:
                    for b in banner_result.banners:
                        lottery_ids.add(b.link_id)
                        log(f" 找到抽奖: {b.title}")

            if len(lottery_ids) > 0:
                self.exchange_limit = self.check_item.get("coin_exchange", 0)
                log(f'积分兑换限制数: {self.exchange_limit}次', msg)
                for id in lottery_ids:
                    # 串行抽奖 确保print按顺序执行
                    msg += await self._Lottery(api, id)
            else:
                log("无抽奖活动")
        return msg

    async def _Lottery(self, api: PClient, id: str):
        """抽奖"""
        msg: list[str] = []
        # 首先获取抽奖详情
        info = await api.GetLotteryInfo(id)
        if isinstance(info, ApiResults.Error):
            log(info, msg)
            return msg
        elif info.lottery.type != LOTTERY_TYPE.DRAW:
            log(f'[{info.lottery.name}] 不支持: {info.lottery.type}', msg)
            return msg
        log(f'正在进行 [{info.lottery.name}]', msg)
        # 同时拉取任务列表和抽奖机会兑换列表
        task_groups, chance_info = await asyncio.gather(
            api.GetTaskGroupsData(info.lottery),
            api.GetChanceEntrances(info.lottery))
        if isinstance(task_groups, ApiResults.Error):
            log(task_groups, msg)
        elif not task_groups.tasks:
            log(' 没有配置任务')
        else:
            # 然后开始做任务
            for task in task_groups.tasks:
                if task.task_status == TaskStatus.Undone:
                    # 每个任务至少间隔2~5秒的时间
                    _, task_result = await asyncio.gather(
                        aio_randomSleep(2, 5),
                        api.PostPageTaskComplete(info.lottery, task))
                    if isinstance(task_result, ApiResults.Error):
                        log(task_result)
                    else:
                        log(f'    {task.task_name}: 已完成')

        # 接着尝试积分兑换
        exchange_count = 0
        while (True):
            if isinstance(chance_info, ApiResults.Error):
                # 拉取失败了
                if chance_info.code != ERROR_CODE.kUnk_400k:
                    log(chance_info, msg)
                # 直接尝试抽奖
                _, lottery_msg = await self.__Lottery(api, info)
                msg += lottery_msg
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
                    exchange_result = await api.CoinExchange(info.lottery, entrance)
                    if isinstance(exchange_result, ApiResults.Error):
                        log(exchange_result)
                        break
                    exchange_count += 1
                    log(f'    第{exchange_count}次{entrance.title}: 成功兑换{exchange_result.gain_num}次抽奖机会')
                    # 更新积分余额
                    chance_info = await api.GetChanceEntrances(info.lottery)
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
            # 开始抽奖
            result, lottery_msg = await self.__Lottery(api, info)
            msg += lottery_msg
            if not result:
                break
            # 稍等片刻确保积分余额更新
            await asyncio.sleep(2)
            # 获取积分余额
            chance_info = await api.GetChanceEntrances(info.lottery)
        return msg

    async def __Lottery(self, api: PClient, info: ApiResults.LotteryInfo):
        """抽奖"""
        msg: list[str] = []
        chances_info = await api.GetUserLotteryInfo(info.lottery)
        if isinstance(chances_info, ApiResults.Error):
            log(chances_info, msg)
            return (False, msg)
        elif chances_info.remain_chances <= 0:
            log(' 没有抽奖机会', msg)
            return (False, msg)

        log(f' 当前有{chances_info.remain_chances}次抽奖机会', msg)
        for i in range(chances_info.remain_chances):
            # 每次抽奖至少间隔2~5秒的时间
            _, lottery_result = await asyncio.gather(
                aio_randomSleep(2, 5),
                api.Lottery(info.lottery))
            if isinstance(lottery_result, ApiResults.Error):
                log(f'  第{i+1}次抽奖: {lottery_result}', msg)
            else:
                log(f'  第{i+1}次抽奖: {lottery_result.prize.name}', msg)
        return (True, msg)


@ check(run_script_name="朴朴抽奖", run_script_expression="pupu")
def main(*args, **kwargs):
    return asyncio.run(PUPU(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()