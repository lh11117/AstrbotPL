from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import re


@register("group_mute", "YourName", "群聊禁言示例插件", "1.0.0")
class GroupMutePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("禁言")
    async def mute(self, event: AstrMessageEvent, duration: int = 60):
        """
        用法：/禁言 <秒数>（需要 @ 某人）
        例：/禁言 300 @张三
        """
        # 1. 确认是群聊
        if not event.get_group_id():
            yield event.plain_result("这个指令只能在群聊里用哦～")
            return

        group_id = event.get_group_id()

        # 2. 从消息链里找到被 @ 的人
        target_id = None
        match = re.search(r'attinyid=(\d+)', event.message_str)
        if match:
            target_id = match.group(1)
                
        if target_id is None:
            yield event.plain_result(f"请 @ 要禁言的人，例如：/禁言 300 @张三(\n{event.message_str}\n)")
            return

        # 3. 调用平台 API 禁言
        try:
            await event.bot.set_group_ban(
                group_id=int(group_id),
                user_id=target_id,
                duration=duration,   # 单位：秒
            )
            yield event.plain_result(f"已禁言 {duration} 秒 ✅")
        except Exception as e:
            logger.error(f"禁言失败: {e}")
            yield event.plain_result(f"禁言失败：{e}")

    @filter.command("解禁")
    async def unmute(self, event: AstrMessageEvent):
        """用法：/解禁 @某人"""
        if not event.get_group_id():
            yield event.plain_result("只能在群聊使用")
            return

        target_id = None
        for comp in event.get_messages():
            if comp.__class__.__name__ == "At" and comp.qq != "all":
                target_id = int(comp.qq)
                break

        if target_id is None:
            yield event.plain_result("请 @ 要解禁的人")
            return

        try:
            await event.bot.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=target_id,
                duration=0,          # 0 = 解除禁言
            )
            yield event.plain_result("已解除禁言 ✅")
        except Exception as e:
            yield event.plain_result(f"解禁失败：{e}")

    @filter.command("ping")
    async def p(self, event: AstrMessageEvent):
        
                yield event.plain_result(f"pong")