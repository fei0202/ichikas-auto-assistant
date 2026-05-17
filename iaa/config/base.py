from pydantic import BaseModel

from .schemas import (
    ChallengeLiveConfig,
    CmConfig,
    DeviceConfig,
    DeveloperConfig,
    EventStoreConfig,
    GameConfig,
    LiveConfig,
    SchedulerConfig,
)

CONFIG_VERSION_CODE = 3

class IaaBaseTaskConfig(BaseModel):
    enabled: bool = False

class IaaConfig(BaseModel):
    version: int = CONFIG_VERSION_CODE
    name: str
    description: str
    device: DeviceConfig = DeviceConfig()
    game: GameConfig
    live: LiveConfig
    challenge_live: ChallengeLiveConfig = ChallengeLiveConfig()
    cm: CmConfig = CmConfig()
    event_shop: EventStoreConfig = EventStoreConfig()
    developer: DeveloperConfig = DeveloperConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
