from __future__ import annotations

from dynamic_config.backends import _preferred_auto_backends, detect_nacos_server_major_version
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
