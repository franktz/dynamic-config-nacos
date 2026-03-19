from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NacosBackendType(str, Enum):
    AUTO = "auto"
    HTTP = "http"
    SDK_V2 = "sdk_v2"
    SDK_V3 = "sdk_v3"


@dataclass(frozen=True)
class NacosSettings:
    server_addr: str
    namespace: str | None
    data_id: str
    group: str
    username: str | None = None
    password: str | None = None
    backend: NacosBackendType = NacosBackendType.AUTO
    polling_interval_seconds: float = 2.0
    sdk_log_path: str | None = None
    sdk_log_level: int | str | None = None
