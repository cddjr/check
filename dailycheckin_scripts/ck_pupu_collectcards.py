# -*- coding: utf-8 -*-
"""
cron: 15 8,23 25-31,1-10 1,2 *
new Env('朴朴集卡');

微信登录朴朴app
找到请求https://cauth.pupuapi.com/clientauth/user/society/wechat/login?user_society_type=11
在json响应里有refresh_token

enabled 是否启用集卡(默认true)
lottery 是否抽奖(会消耗一张卡 默认false)
keep_cards 抽奖保留几张卡片(默认1)
"""
import asyncio
import sys
from traceback import format_exc

from pupu_api import Client as PClient
from pupu_types import *
from utils import aio_randomSleep, check, log

assert sys.version_info >= (3, 9)


class PUPU:
    __slots__ = (
        "check_item",
        "device_id",
        "refresh_token",
        "_lottery",
        "_keep_cards",
    )

    def __init__(self, check_item) -> None:
        self.check_item: dict = check_item

    async def main(self):
        msg: list[str] = []
        try:
            self.device_id = self.check_item.get("device_id", "")
            self.refresh_token = self.check_item.get("refresh_token", "")
            if not self.device_id:
                raise SystemExit("device_id 配置有误")
            if not self.refresh_token:
                raise SystemExit("refresh_token 配置有误")

            collect_cards = self.check_item.get("collect_cards", {})
            if not collect_cards.get("enabled", True):
                raise SystemExit("没有启用")

            self._lottery = bool(collect_cards.get("lottery", False))
            self._keep_cards = int(self.check_item.get("keep_cards", 1))

            msg += await self.CollectCards()
        except Exception:
            log(f"失败: 请检查接口 {format_exc()}", msg)
        return "\n".join(msg)

    async def CollectCards(self):
        """开始集卡"""
        msg: list[str] = []
        async with PClient(self.device_id, self.refresh_token) as api:
            result = await api.InitializeToken(
                self.check_item.get("addr_filter"), force_update_receiver=False
            )
            if isinstance(result, ApiResults.Error):
                if api.nickname:
                    log(f"账号: {api.nickname}", msg)
                log(result, msg)
                return msg

            log(f"账号: {api.nickname}", msg)

            rule = await api.GetCollectCardRule()
            if isinstance(rule, ApiResults.Error):
                log(rule, msg)
                return msg
            elif rule.status == COLLECT_CARD_STATUS.FINISHED:
                # 活动已结束
                log(f"{rule.name} 已结束", msg)
                return msg

            log(f"本期活动: {rule.name}", msg)

            task_groups, lottery_info = await asyncio.gather(
                api.GetTaskGroupsData(rule),
                api.GetLotteryInfo(rule.card_lottery_activity_id),
            )
            if isinstance(task_groups, ApiResults.Error):
                log(task_groups, msg)
                return msg
            elif not task_groups.tasks:
                log(" 没有配置任务")

            # 同时拉取抽奖详情
            if isinstance(lottery_info, ApiResults.Error):
                log(lottery_info, msg)
                return msg

            # 然后开始做任务
            for task in task_groups.tasks:
                if task.task_status != TaskStatus.Undone:
                    continue
                if task.page_rule:
                    # 每个任务至少间隔2~5秒的时间
                    task_result, _ = await asyncio.gather(
                        api.PostPageTaskComplete(task),
                        aio_randomSleep(2, 5),
                    )
                    if isinstance(task_result, ApiResults.Error):
                        log(task_result)
                    else:
                        log(f"    {task.task_name}: 已完成")
                elif task.answer_rule:
                    """
                    TODO 答题任务 采集题库
                    """
                    questionnaire, _ = await asyncio.gather(
                        api.GetQuestionnaire(task),
                        aio_randomSleep(2, 5),
                    )
                    if isinstance(questionnaire, ApiResults.Error):
                        log(questionnaire)
                    else:
                        answer = False
                        for q in questionnaire.questions:
                            if q.id == "8d133804-64cc-4ae4-aacf-e4a0d55c8182":
                                for options in q.options:
                                    if options.name == "车厘子":
                                        options.selected = 1
                                        answer = True
                            elif q.id == "0c1da1e8-50e8-40b0-8e0d-43496996c928":
                                for options in q.options:
                                    if options.name == "月中13-16日":
                                        options.selected = 1
                                        answer = True
                            else:
                                print(q)
                        if answer:
                            succ, _ = await asyncio.gather(
                                api.SubmitQuestionnaire(questionnaire),
                                aio_randomSleep(2, 5),
                            )
                            if isinstance(succ, ApiResults.Error):
                                log(succ)
                            elif succ:
                                log(f"    {task.task_name}: 已提交", msg)
                                continue
                        log(f"    {task.task_name}: 未提交")

            # 获取抽卡次数
            await aio_randomSleep(2, 3)
            remain_chances = await api.GetCollectCardLotteryCount(rule)
            if isinstance(remain_chances, ApiResults.Error):
                log(remain_chances, msg)
                remain_chances = 0
            elif remain_chances <= 0:
                log(" 没有抽卡机会", msg)
            else:
                log(f" 当前有{remain_chances}次抽卡机会", msg)

            # 开始抽卡
            for i in range(remain_chances):
                # 每次抽卡至少间隔4~8秒的时间
                getcard_result, _ = await asyncio.gather(
                    api.LotteryGetCard(rule),
                    aio_randomSleep(4, 8),
                )
                if isinstance(getcard_result, ApiResults.Error):
                    log(f"  第{i+1}次抽卡: {getcard_result}", msg)
                else:
                    log(
                        f"  第{i+1}次抽卡: {getcard_result.name}, 类型: {getcard_result.card_type}",
                        msg,
                    )

            # 获取卡片数量
            info = await api.GetCollectCardEntity(rule)
            if isinstance(info, ApiResults.Error):
                log(info, msg)
                return msg
            else:
                for card in info.already_get:
                    log(f" {card.name}: {card.have_count}张")
                log(f" 可合成{info.can_composite_count}张 {info.already_get[0].name}", msg)
                if info.can_composite_count:
                    unk = await api.PostCompositeCard(rule)
                    if isinstance(unk, ApiResults.Error):
                        log(unk, msg)
                    else:
                        # TODO 尚不清楚合成的返回结构 猜测是 PCollectCard
                        log(" 已自动合成", msg)
                        log(unk)
                        # 再更新一次卡片数量
                        info = await api.GetCollectCardEntity(rule)
                        if isinstance(info, ApiResults.Error):
                            log(info, msg)
                            return msg

            if not self._lottery:
                # 不抽奖 流程结束
                return msg

            c = 1
            # 开始消耗卡片去抽奖(规则每日最多3次)
            for card in info.already_get:
                if card.have_count is None:
                    continue
                if card.have_count <= self._keep_cards:
                    continue
                for i in range(card.have_count - self._keep_cards):
                    # 用卡片兑换一次抽奖机会
                    result = await api.DeleteExpendCardEntity(card)
                    if isinstance(result, ApiResults.Error):
                        log(result)
                        continue
                    log(f"  消耗了1张 {card.name}")
                    if result != lottery_info.lottery.id:
                        # FIXME 不应该
                        log(f"断言不满足 {result} != {lottery_info.lottery.id}", msg)
                    # 每次抽奖至少间隔4~8秒的时间
                    lottery_result, _ = await asyncio.gather(
                        api.Lottery(lottery_info.lottery),
                        aio_randomSleep(4, 8),
                    )
                    if isinstance(lottery_result, ApiResults.Error):
                        log(f"  第{c}次抽奖: {lottery_result}", msg)
                    else:
                        log(f"  第{c}次抽奖: {lottery_result.prize.name}", msg)
                    c += 1

        return msg


@check(run_script_name="朴朴集卡", run_script_expression="pupu")
def main(*args, **kwargs):
    return asyncio.run(PUPU(check_item=kwargs.get("value")).main())


if __name__ == "__main__":
    main()
