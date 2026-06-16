from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class TelemetryConfig(BaseModel):
    sentry: bool | None = None


class ProfilesConfig(BaseModel):
    last_used: str | None = None


class InterfaceConfig(BaseModel):
    window_style: str = ''
    theme_color: str | None = None
    color_scheme: Literal['auto', 'light', 'dark'] = 'auto'


class CustomPushData(BaseModel):
    command: str = ''


class DiscordPushData(BaseModel):
    webhook_url: str = ''


PushData = CustomPushData | DiscordPushData


class PushConfig(BaseModel):
    enabled: bool = False
    type: Literal['custom', 'discord'] = 'custom'
    data: PushData = Field(default_factory=CustomPushData)

    @model_validator(mode='before')
    @classmethod
    def _coerce_data(cls, values: Any) -> Any:
        if isinstance(values, dict):
            push_type = values.get('type', 'custom')
            raw_data = values.get('data')
            if isinstance(raw_data, dict):
                if push_type == 'discord':
                    values['data'] = DiscordPushData(**raw_data)
                else:
                    values['data'] = CustomPushData(**raw_data)
        return values


class NotifyConfig(BaseModel):
    system: bool = True
    push: PushConfig = PushConfig()


class HotkeysConfig(BaseModel):
    start: str | None = None
    stop: str | None = None


class SharedConfig(BaseModel):
    version: int = 1
    profiles: ProfilesConfig = ProfilesConfig()
    telemetry: TelemetryConfig = TelemetryConfig()
    interface: InterfaceConfig = InterfaceConfig()
    notify: NotifyConfig = NotifyConfig()
    hotkeys: HotkeysConfig = HotkeysConfig()
