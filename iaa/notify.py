import json
import logging
import subprocess
import urllib.request

from iaa.config.shared import NotifyConfig

logger = logging.getLogger(__name__)

_DISCORD_COLOR_SUCCESS = 0x57F287  # green
_DISCORD_COLOR_FAILURE = 0xED4245  # red
_DISCORD_COLOR_DEFAULT = 0x5865F2  # blurple

_FAILURE_KEYWORDS = ('失败', '错误', '失敗', '錯誤', 'fail', 'error', 'failed')
_SUCCESS_KEYWORDS = ('完成', '成功', 'done', 'success', 'finished', 'complete')


def _infer_discord_color(title: str, message: str) -> int:
    text = (title + ' ' + message).lower()
    if any(k in text for k in _FAILURE_KEYWORDS):
        return _DISCORD_COLOR_FAILURE
    if any(k in text for k in _SUCCESS_KEYWORDS):
        return _DISCORD_COLOR_SUCCESS
    return _DISCORD_COLOR_DEFAULT


def _send_discord(webhook_url: str, title: str, message: str) -> None:
    if not webhook_url:
        logger.warning('Discord webhook URL is empty')
        return
    color = _infer_discord_color(title, message)
    payload = json.dumps(
        {'embeds': [{'title': title, 'description': message, 'color': color}]}
    ).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        logger.debug('Discord webhook response: %s', resp.status)


def send_notification(title: str, message: str, config: NotifyConfig) -> None:
    if config.system:
        try:
            from plyer import notification
            notification.notify(title=title, message=message)  # type: ignore
            logger.debug('System notification sent: %s - %s', title, message)
        except Exception:
            logger.exception('Failed to send system notification')

    if config.push.enabled:
        if config.push.type == 'custom':
            from iaa.config.shared import CustomPushData
            data = config.push.data
            command = data.command if isinstance(data, CustomPushData) else ''
            if not command:
                logger.warning('Push notification enabled but command is empty')
                return
            try:
                subprocess.Popen(command, shell=True)
                logger.debug('Push notification command executed: %s', command)
            except Exception:
                logger.exception('Failed to execute push notification command')
        elif config.push.type == 'discord':
            from iaa.config.shared import DiscordPushData
            data = config.push.data
            if not isinstance(data, DiscordPushData):
                logger.warning('Discord push type set but data is not DiscordPushData')
                return
            try:
                _send_discord(data.webhook_url, title, message)
                logger.debug('Discord notification sent: %s - %s', title, message)
            except Exception:
                logger.exception('Failed to send Discord webhook notification')
