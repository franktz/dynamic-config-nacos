from __future__ import annotations

import asyncio

from dynamic_config.backends import (
    AsyncSdkV3NacosBackend,
    HttpNacosBackend,
    LegacySdkNacosBackend,
    _preferred_auto_backends,
    create_nacos_backend,
    detect_nacos_server_major_version,
)
from dynamic_config.models import NacosBackendType, NacosSettings


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):  # type: ignore[no-untyped-def]
        return self._payload


def test_detect_nacos_server_major_version(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from dynamic_config import backends as backend_module

    monkeypatch.setattr(
        backend_module.requests,
        "get",
        lambda *_args, **_kwargs: _Response({"version": "2.5.1"}),
    )

    major = detect_nacos_server_major_version(
        NacosSettings(
            server_addr="127.0.0.1:8848",
            namespace=None,
            data_id="demo.yaml",
            group="DEFAULT_GROUP",
        )
    )

    assert major == 2


def test_preferred_auto_backends_follow_server_major() -> None:
    assert _preferred_auto_backends(2) == (
        NacosBackendType.SDK_V2,
        NacosBackendType.SDK_V3,
        NacosBackendType.HTTP,
    )
    assert _preferred_auto_backends(3) == (
        NacosBackendType.SDK_V3,
        NacosBackendType.SDK_V2,
        NacosBackendType.HTTP,
    )


def test_preferred_auto_backends_skip_unavailable_sdk() -> None:
    assert _preferred_auto_backends(
        2,
        available_backends=(NacosBackendType.SDK_V3,),
    ) == (
        NacosBackendType.SDK_V3,
        NacosBackendType.HTTP,
    )
    assert _preferred_auto_backends(
        None,
        available_backends=(),
    ) == (NacosBackendType.HTTP,)


def test_create_nacos_backend_prefers_sdk_v3_when_only_v3_is_available(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from dynamic_config import backends as backend_module

    class _StubV3Backend:
        def __init__(self, settings):
            self.settings = settings

    monkeypatch.setattr(backend_module, "detect_nacos_server_major_version", lambda _settings: 2)
    monkeypatch.setattr(
        backend_module,
        "_available_sdk_backends",
        lambda: (NacosBackendType.SDK_V3,),
    )
    monkeypatch.setattr(backend_module, "AsyncSdkV3NacosBackend", _StubV3Backend)

    backend = create_nacos_backend(
        NacosSettings(
            server_addr="127.0.0.1:8848",
            namespace=None,
            data_id="demo.yaml",
            group="DEFAULT_GROUP",
        )
    )

    assert isinstance(backend, _StubV3Backend)


def test_http_backend_logs_watcher_start(monkeypatch, caplog) -> None:  # type: ignore[no-untyped-def]
    from dynamic_config import backends as backend_module

    started = {"value": False}

    class _FakeThread:
        def __init__(self, *, target, name, daemon):
            self._target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            started["value"] = True

    monkeypatch.setattr(backend_module.threading, "Thread", _FakeThread)

    backend = HttpNacosBackend(
        NacosSettings(
            server_addr="127.0.0.1:8848",
            namespace=None,
            data_id="demo.yaml",
            group="DEFAULT_GROUP",
            backend=NacosBackendType.HTTP,
            polling_interval_seconds=5.0,
        )
    )

    caplog.set_level("INFO")
    backend.start_watch(lambda _content: None)

    assert started["value"] is True
    assert "started nacos watcher via http backend" in caplog.text
    assert "interval=5.000s" in caplog.text


def test_legacy_sdk_backend_logs_watcher_start(monkeypatch, caplog) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(LegacySdkNacosBackend, "_build_client", lambda self: object())
    monkeypatch.setattr(LegacySdkNacosBackend, "_register_listener", lambda self, _on_update: None)

    backend = LegacySdkNacosBackend(
        NacosSettings(
            server_addr="127.0.0.1:8848",
            namespace=None,
            data_id="demo.yaml",
            group="DEFAULT_GROUP",
            backend=NacosBackendType.SDK_V2,
        ),
        sdk_version=NacosBackendType.SDK_V2,
    )

    caplog.set_level("INFO")
    backend.start_watch(lambda _content: None)

    assert "started nacos watcher via sdk_v2 backend" in caplog.text


def test_async_sdk_v3_backend_uses_current_nacos_sdk_shape(monkeypatch, caplog) -> None:  # type: ignore[no-untyped-def]
    from dynamic_config import backends as backend_module

    updates: list[str] = []

    class _FakeConfigParam:
        def __init__(self, *, data_id: str, group: str):
            self.data_id = data_id
            self.group = group

    class _FakeService:
        async def get_config(self, param):
            return f"loaded:{param.data_id}:{param.group}"

        async def add_listener(self, _data_id, _group, listener):
            await listener("tenant", "DEFAULT_GROUP", "demo.yaml", "updated")

        async def shutdown(self):
            return None

    class _FakeBuilder:
        def server_address(self, _value):
            return self

        def namespace_id(self, _value):
            return self

        def username(self, _value):
            return self

        def password(self, _value):
            return self

        def build(self):
            return object()

    class _FakeNacosConfigService:
        @staticmethod
        async def create_config_service(_client_config):
            return _FakeService()

    class _FakeModule:
        ClientConfigBuilder = _FakeBuilder
        NacosConfigService = _FakeNacosConfigService
        ConfigParam = _FakeConfigParam

    monkeypatch.setattr(backend_module.importlib, "import_module", lambda _name: _FakeModule)

    backend = AsyncSdkV3NacosBackend(
        NacosSettings(
            server_addr="127.0.0.1:8848",
            namespace="public",
            data_id="demo.yaml",
            group="DEFAULT_GROUP",
            username="u",
            password="p",
            backend=NacosBackendType.SDK_V3,
        )
    )

    assert backend.fetch_content() == "loaded:demo.yaml:DEFAULT_GROUP"

    caplog.set_level("INFO")
    backend.start_watch(updates.append)

    for _ in range(20):
        if updates:
            break
        asyncio.run(asyncio.sleep(0.01))

    assert updates == ["updated"]
    assert "started nacos watcher via sdk_v3 backend" in caplog.text
