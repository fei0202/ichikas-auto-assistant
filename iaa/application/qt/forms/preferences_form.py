from __future__ import annotations

from iaa.application.framework.dsl import Checkbox, FormPage, FormSpec, Group, Hotkey, Select, Text, bind, custom_ref
from typing import Callable, cast
from .context import PreferencesContext

ctx, ref = bind(PreferencesContext)

_push_command_ref = custom_ref(
    lambda c: c.shared.notify.push.data.command if hasattr(c.shared.notify.push.data, 'command') else '',
    lambda c, v: setattr(c.shared.notify.push.data, 'command', v) if hasattr(c.shared.notify.push.data, 'command') else None,
)
_push_webhook_url_ref = custom_ref(
    lambda c: c.shared.notify.push.data.webhook_url if hasattr(c.shared.notify.push.data, 'webhook_url') else '',
    lambda c, v: setattr(c.shared.notify.push.data, 'webhook_url', v) if hasattr(c.shared.notify.push.data, 'webhook_url') else None,
)


def _on_push_type_changed(context: PreferencesContext, value: str) -> None:
    from iaa.config.shared import CustomPushData, DiscordPushData
    if value == 'discord':
        context.shared.notify.push.data = DiscordPushData()
    else:
        context.shared.notify.push.data = CustomPushData()


def build_preferences_form() -> tuple[FormSpec[PreferencesContext], list[Callable[[PreferencesContext], None]]]:
    with FormPage('设置') as page:
        with Group('数据收集'):
            Checkbox(
                key='telemetry.sentry',
                label='自动发送匿名错误报告',
                ref=ref(ctx.shared.telemetry.sentry),
            )

        with Group('界面'):
            Select(
                key='interface.window_style',
                label='窗口背景样式',
                ref=ref(ctx.shared.interface.window_style),
                options=[
                    {'value': '', 'label': '自动'},
                    {'value': 'mica', 'label': 'Mica（仅 Win 11）'},
                    {'value': 'blur', 'label': '模糊背景'},
                    {'value': 'acrylic', 'label': '亚克力（Win 10 1803+）'},
                    {'value': 'solid', 'label': '纯色背景'},
                ],
            )
            Select(
                key='interface.color_scheme',
                label='色彩方案',
                ref=ref(ctx.shared.interface.color_scheme),
                options=[
                    {'value': 'auto', 'label': '跟随系统'},
                    {'value': 'light', 'label': '浅色'},
                    {'value': 'dark', 'label': '深色'},
                ],
            )
            Select(
                key='interface.theme_color',
                label='主题色',
                ref=ref(ctx.shared.interface.theme_color).map(
                    to_ui=lambda v: '' if v is None else str(v),
                    from_ui=lambda v: (str(v).strip() or None),
                ),
                options=[
                    {'value': '', 'label': '跟随系统'},
                    {'value': '#0078d4', 'label': '蓝色（#0078D4）'},
                    {'value': '#e81123', 'label': '红色（#E81123）'},
                    {'value': '#107c10', 'label': '绿色（#107C10）'},
                    {'value': '#ff8c00', 'label': '橙色（#FF8C00）'},
                    {'value': '#5c2d91', 'label': '紫色（#5C2D91）'},
                    {'value': '#00b7c3', 'label': '青色（#00B7C3）'},
                    {'value': '#6b69d6', 'label': '靛蓝（#6B69D6）'},
                    {'value': '#4a5459', 'label': '石墨灰（#4A5459）'},
                ],
            )

        with Group('通知'):
            Checkbox(
                key='notify.system',
                label='系统通知',
                ref=ref(ctx.shared.notify.system),
            )
            Checkbox(
                key='notify.push.enabled',
                label='推送通知',
                ref=ref(ctx.shared.notify.push.enabled),
            )
            Select(
                key='notify.push.type',
                label='推送类型',
                ref=ref(ctx.shared.notify.push.type),
                options=[
                    {'value': 'custom', 'label': '自定义命令'},
                    {'value': 'discord', 'label': 'Discord Webhook'},
                ],
                visible=lambda ctx: ctx.shared.notify.push.enabled,
                on_change=_on_push_type_changed,
            )
            Text(
                key='notify.push.data.command',
                label='自定义命令',
                ref=_push_command_ref,
                placeholder='任务完成后执行的命令',
                visible=lambda ctx: ctx.shared.notify.push.enabled and ctx.shared.notify.push.type == 'custom',
            )
            Text(
                key='notify.push.data.webhook_url',
                label='Webhook URL',
                help_text='<a href="https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks">如何获取 Discord Webhook URL？</a>',
                ref=_push_webhook_url_ref,
                placeholder='https://discord.com/api/webhooks/...',
                visible=lambda ctx: ctx.shared.notify.push.enabled and ctx.shared.notify.push.type == 'discord',
            )

        with Group('快捷键'):
            Hotkey(
                key='hotkeys.start',
                label='启动脚本',
                ref=ref(ctx.shared.hotkeys.start).map(
                    to_ui=lambda v: '' if v is None else v,
                    from_ui=lambda v: None if not v else v,
                ),
            )
            Hotkey(
                key='hotkeys.stop',
                label='停止脚本',
                ref=ref(ctx.shared.hotkeys.stop).map(
                    to_ui=lambda v: '' if v is None else v,
                    from_ui=lambda v: None if not v else v,
                ),
            )

    return (
        cast(FormSpec[PreferencesContext], page.spec),
        cast(list[Callable[[PreferencesContext], None]], page.hooks),
    )
