from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .backends import HttpNacosBackend, create_nacos_backend
from .models import NacosBackendType, NacosSettings
from .view import Conf

logger = logging.getLogger(__name__)

__all__ = ["DynamicConfigProvider", "NacosBackendType", "NacosSettings"]


class DynamicConfigProvider:
    def __init__(self, *, local_yaml_path: str):
        self._local_yaml_path = Path(local_yaml_path)
        self._raw: dict[str, Any] = {}
        self._conf = Conf({})
        self._nacos_settings: NacosSettings | None = None
        self._nacos_backend = None

    def load_from_env(
        self,
        *,
        local_path_env: str = "LOCAL_CONFIG_PATH",
        server_addr_env: str = "NACOS_SERVER_ADDR",
        namespace_env: str = "NACOS_NAMESPACE",
        data_id_env: str = "NACOS_DATA_ID",
        group_env: str = "NACOS_GROUP",
        username_env: str = "NACOS_USERNAME",
        password_env: str = "NACOS_PASSWORD",
        backend_env: str = "NACOS_BACKEND",
        polling_interval_env: str = "NACOS_POLLING_INTERVAL_SECONDS",
        default_data_id: str = "app.yaml",
        default_group: str = "DEFAULT_GROUP",
    ) -> None:
        local_path = os.getenv(local_path_env)
        if local_path:
            self._local_yaml_path = Path(local_path)
        server_addr = os.getenv(server_addr_env)
        nacos = None
        if server_addr:
            nacos = NacosSettings(
                server_addr=server_addr,
                namespace=os.getenv(namespace_env),
                data_id=os.getenv(data_id_env, default_data_id),
                group=os.getenv(group_env, default_group),
                username=os.getenv(username_env),
                password=os.getenv(password_env),
                backend=self._parse_backend(os.getenv(backend_env)),
                polling_interval_seconds=self._parse_polling_interval(os.getenv(polling_interval_env)),
            )
        self.load_initial(nacos)

    def load_initial(self, nacos: NacosSettings | None) -> None:
        self._nacos_settings = nacos
        self._nacos_backend = create_nacos_backend(nacos) if nacos is not None else None
        content = self._load_nacos_content()
        raw = self._parse_yaml_mapping(content) if content else None
        if raw is None:
            raw = self._load_from_local()
        self._apply_raw(raw)
        if content and isinstance(self._nacos_backend, HttpNacosBackend):
            self._nacos_backend.mark_content(content)
        if self._nacos_backend is not None:
            self._start_watchers_best_effort()

    def get(self, path: str, default: Any = None) -> Any:
        return self._conf.get(path, default)

    @property
    def conf(self) -> Conf:
        return self._conf

    @property
    def nacos_settings(self) -> NacosSettings | None:
        return self._nacos_settings

    @property
    def local_yaml_path(self) -> Path:
        return self._local_yaml_path

    def snapshot(self) -> dict[str, Any]:
        return dict(self._raw)

    def _load_from_local(self) -> dict[str, Any]:
        try:
            content = self._local_yaml_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("local config not found: %s", self._local_yaml_path)
            return {}
        data = yaml.safe_load(content) or {}
        if not isinstance(data, dict):
            raise TypeError("config root must be mapping")
        return data

    def _load_nacos_content(self) -> str | None:
        if self._nacos_backend is None:
            return None
        try:
            return self._nacos_backend.fetch_content()
        except Exception:
            logger.exception("failed to load config from nacos")
            return None

    def _start_watchers_best_effort(self) -> None:
        if self._nacos_backend is None:
            return

        def _on_update(content: str) -> None:
            data = self._parse_yaml_mapping(content)
            if data is None:
                return
            self._apply_raw(data)
            logger.info(
                "applied nacos config update",
                extra={
                    "data_id": self._nacos_settings.data_id if self._nacos_settings else None,
                    "group": self._nacos_settings.group if self._nacos_settings else None,
                    "backend": self._nacos_settings.backend.value if self._nacos_settings else None,
                },
            )

        try:
            self._nacos_backend.start_watch(_on_update)
        except Exception:
            logger.exception("failed to start nacos watcher")

    def _apply_raw(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self._conf = Conf(raw)

    def _parse_yaml_mapping(self, content: str) -> dict[str, Any] | None:
        data = yaml.safe_load(content) or {}
        if not isinstance(data, dict):
            logger.warning(
                "ignored non-mapping nacos config from %s",
                self._nacos_settings.data_id if self._nacos_settings else "unknown",
            )
            return None
        return data

    @staticmethod
    def _parse_backend(value: str | None) -> NacosBackendType:
        if not value:
            return NacosBackendType.AUTO
        try:
            return NacosBackendType(value.strip().lower())
        except ValueError:
            logger.warning("unknown nacos backend %s, fallback to auto", value)
            return NacosBackendType.AUTO

    @staticmethod
    def _parse_polling_interval(value: str | None) -> float:
        if not value:
            return 2.0
        try:
            parsed = float(value)
        except ValueError:
            logger.warning("invalid nacos polling interval %s, fallback to 2.0", value)
            return 2.0
        return parsed if parsed > 0 else 2.0
