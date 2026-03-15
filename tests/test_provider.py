from __future__ import annotations

from pathlib import Path

from dynamic_config import DynamicConfigProvider, NacosBackendType, NacosSettings


class _StubBackend:
    def __init__(self, initial_content: str | None, update_content: str | None = None):
        self.initial_content = initial_content
        self.update_content = update_content
        self.started = False

    def fetch_content(self) -> str | None:
        return self.initial_content

    def start_watch(self, on_update) -> None:  # type: ignore[no-untyped-def]
        self.started = True
        if self.update_content is not None:
            on_update(self.update_content)


def test_dynamic_config_provider_loads_local_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "local.yaml"
    config_path.write_text("prompts:\n  summary_prefix: '[Local]'\n", encoding="utf-8")

    provider = DynamicConfigProvider(local_yaml_path=str(config_path))
    provider.load_initial(None)

    assert provider.get("prompts.summary_prefix") == "[Local]"


def test_dynamic_config_provider_loads_explicit_http_backend_from_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("NACOS_SERVER_ADDR", "127.0.0.1:8848")
    monkeypatch.setenv("NACOS_BACKEND", "http")
    monkeypatch.setenv("NACOS_POLLING_INTERVAL_SECONDS", "5")

    provider = DynamicConfigProvider(local_yaml_path="unused.yaml")
    provider.load_from_env(default_data_id="demo.yaml")

    assert provider.nacos_settings is not None
    assert provider.nacos_settings.backend == NacosBackendType.HTTP
    assert provider.nacos_settings.polling_interval_seconds == 5.0


def test_dynamic_config_provider_applies_backend_updates(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from dynamic_config import provider as provider_module

    config_path = tmp_path / "local.yaml"
    config_path.write_text("prompts:\n  summary_prefix: '[Local]'\n", encoding="utf-8")

    backend = _StubBackend(
        initial_content="prompts:\n  summary_prefix: '[Initial]'\n",
        update_content="prompts:\n  summary_prefix: '[Updated]'\n",
    )
    monkeypatch.setattr(provider_module, "create_nacos_backend", lambda _settings: backend)

    provider = DynamicConfigProvider(local_yaml_path=str(config_path))
    provider.load_initial(
        NacosSettings(
            server_addr="127.0.0.1:8848",
            namespace=None,
            data_id="demo.yaml",
            group="DEFAULT_GROUP",
            backend=NacosBackendType.SDK_V2,
        )
    )

    assert backend.started is True
    assert provider.get("prompts.summary_prefix") == "[Updated]"
