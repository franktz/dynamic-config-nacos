from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.util
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from urllib.parse import urlparse

import requests

from .models import NacosBackendType, NacosSettings

logger = logging.getLogger(__name__)

UpdateCallback = Callable[[str], None]


class NacosBackendError(RuntimeError):
    pass


class NacosConfigBackend(ABC):
    def __init__(self, settings: NacosSettings):
        self.settings = settings

    @abstractmethod
    def fetch_content(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def start_watch(self, on_update: UpdateCallback) -> None:
        raise NotImplementedError


class HttpNacosBackend(NacosConfigBackend):
    backend_type = NacosBackendType.HTTP

    def __init__(self, settings: NacosSettings):
        super().__init__(settings)
        self._watch_started = False
        self._last_content_md5: str | None = None
        self._access_token: str | None = None
        self._access_token_expire_at = 0.0

    def fetch_content(self) -> str | None:
        try:
            response = requests.get(
                self._config_url(),
                params=self._query_params(with_auth=True),
                timeout=5,
            )
            response.raise_for_status()
        except Exception as exc:
            raise NacosBackendError("failed to load config from nacos over http") from exc
        content = response.text
        return content if content.strip() else None

    def start_watch(self, on_update: UpdateCallback) -> None:
        if self._watch_started:
            return
        self._watch_started = True

        def _poll() -> None:
            while True:
                try:
                    content = self.fetch_content()
                    if not content:
                        time.sleep(self.settings.polling_interval_seconds)
                        continue
                    content_md5 = self._content_md5(content)
                    if content_md5 == self._last_content_md5:
                        time.sleep(self.settings.polling_interval_seconds)
                        continue
                    self._last_content_md5 = content_md5
                    on_update(content)
                except Exception:
                    logger.exception(
                        "failed to apply nacos config update",
                        extra={"backend": NacosBackendType.HTTP.value, "data_id": self.settings.data_id},
                    )
                time.sleep(self.settings.polling_interval_seconds)

        threading.Thread(
            target=_poll,
            name=f"nacos-http-watch-{self.settings.data_id}",
            daemon=True,
        ).start()
        logger.info(
            "started nacos watcher via http backend for data_id=%s group=%s interval=%.3fs",
            self.settings.data_id,
            self.settings.group,
            self.settings.polling_interval_seconds,
            extra={
                "backend": self.backend_type.value,
                "data_id": self.settings.data_id,
                "group": self.settings.group,
                "polling_interval_seconds": self.settings.polling_interval_seconds,
            },
        )

    def mark_content(self, content: str) -> None:
        self._last_content_md5 = self._content_md5(content)

    def _config_url(self) -> str:
        server_addr = self._normalize_server_addr()
        return f"{server_addr.rstrip('/')}/nacos/v1/cs/configs"

    def _login_url(self) -> str:
        server_addr = self._normalize_server_addr()
        return f"{server_addr.rstrip('/')}/nacos/v1/auth/users/login"

    def _normalize_server_addr(self) -> str:
        server_addr = self.settings.server_addr
        if not server_addr.startswith("http://") and not server_addr.startswith("https://"):
            server_addr = f"http://{server_addr}"
        return server_addr

    def _query_params(self, *, with_auth: bool) -> dict[str, str]:
        params = {
            "dataId": self.settings.data_id,
            "group": self.settings.group,
        }
        if self.settings.namespace:
            params["tenant"] = self.settings.namespace
        if with_auth:
            access_token = self._get_access_token()
            if access_token:
                params["accessToken"] = access_token
        return params

    def _get_access_token(self) -> str | None:
        if not self.settings.username or not self.settings.password:
            return None
        now = time.time()
        if self._access_token and now < self._access_token_expire_at - 60:
            return self._access_token
        try:
            response = requests.post(
                self._login_url(),
                data={
                    "username": self.settings.username,
                    "password": self.settings.password,
                },
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            token = payload.get("accessToken")
            ttl = float(payload.get("tokenTtl", 18000) or 18000)
            if isinstance(token, str) and token:
                self._access_token = token
                self._access_token_expire_at = now + ttl
                return token
        except Exception:
            logger.exception("failed to login to nacos")
        return None

    @staticmethod
    def _content_md5(content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()


class LegacySdkNacosBackend(NacosConfigBackend):
    def __init__(self, settings: NacosSettings, *, sdk_version: NacosBackendType):
        super().__init__(settings)
        self._sdk_version = sdk_version
        self.backend_type = sdk_version
        self._client = self._build_client()
        self._watch_started = False

    def fetch_content(self) -> str | None:
        try:
            content = self._call_fetch()
        except Exception as exc:
            raise NacosBackendError(
                f"failed to load config from nacos via {self._sdk_version.value}"
            ) from exc
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        return content if isinstance(content, str) and content.strip() else None

    def start_watch(self, on_update: UpdateCallback) -> None:
        if self._watch_started:
            return
        self._register_listener(on_update)
        self._watch_started = True
        logger.info(
            "started nacos watcher via %s backend for data_id=%s group=%s",
            self.backend_type.value,
            self.settings.data_id,
            self.settings.group,
            extra={
                "backend": self.backend_type.value,
                "data_id": self.settings.data_id,
                "group": self.settings.group,
            },
        )

    def _build_client(self) -> object:
        client_specs = ((("nacos", "NacosClient"),),)[0]
        last_error: Exception | None = None
        for module_name, class_name in client_specs:
            try:
                module = importlib.import_module(module_name)
                client_cls = getattr(module, class_name, None)
                if client_cls is None:
                    continue
                kwargs = {
                    "server_addresses": self.settings.server_addr,
                    "namespace": self.settings.namespace,
                    "username": self.settings.username,
                    "password": self.settings.password,
                }
                return client_cls(**{k: v for k, v in kwargs.items() if v is not None})
            except Exception as exc:
                last_error = exc
        raise NacosBackendError(f"{self._sdk_version.value} client is not available") from last_error

    def _call_fetch(self) -> str | bytes | None:
        params = {
            "data_id": self.settings.data_id,
            "group": self.settings.group,
        }
        fetch_methods = ("get_config", "getConfig")
        for method_name in fetch_methods:
            method = getattr(self._client, method_name, None)
            if callable(method):
                return method(**params)
        raise NacosBackendError(
            f"{self._sdk_version.value} client does not expose get_config/getConfig"
        )

    def _register_listener(self, on_update: UpdateCallback) -> None:
        def _listener(*args: object, **kwargs: object) -> None:
            content = kwargs.get("content")
            if content is None and args:
                content = args[-1]
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            if isinstance(content, str):
                on_update(content)

        subscribe_methods = ("add_config_watchers", "add_config_watcher", "add_listener")
        for method_name in subscribe_methods:
            method = getattr(self._client, method_name, None)
            if not callable(method):
                continue
            try:
                method(self.settings.data_id, self.settings.group, _listener)
                return
            except TypeError:
                try:
                    method(data_id=self.settings.data_id, group=self.settings.group, listener=_listener)
                    return
                except TypeError:
                    continue
        raise NacosBackendError(
            f"{self._sdk_version.value} client does not expose a supported listener API"
        )


class AsyncSdkV3NacosBackend(NacosConfigBackend):
    backend_type = NacosBackendType.SDK_V3

    def __init__(self, settings: NacosSettings):
        super().__init__(settings)
        self._watch_started = False
        self._module = self._import_sdk_module()

    def fetch_content(self) -> str | None:
        try:
            return asyncio.run(self._fetch_content_async())
        except Exception as exc:
            raise NacosBackendError("failed to load config from nacos via sdk_v3") from exc

    def start_watch(self, on_update: UpdateCallback) -> None:
        if self._watch_started:
            return
        self._watch_started = True

        ready = threading.Event()
        error_holder: list[Exception] = []

        def _runner() -> None:
            try:
                asyncio.run(self._watch_async(on_update, ready))
            except Exception as exc:  # pragma: no cover - thread safety path
                error_holder.append(exc)
                ready.set()

        threading.Thread(
            target=_runner,
            name=f"nacos-sdk-v3-watch-{self.settings.data_id}",
            daemon=True,
        ).start()

        ready.wait(timeout=10)
        if error_holder:
            raise NacosBackendError("failed to start nacos watcher via sdk_v3") from error_holder[0]
        logger.info(
            "started nacos watcher via sdk_v3 backend for data_id=%s group=%s",
            self.settings.data_id,
            self.settings.group,
            extra={
                "backend": self.backend_type.value,
                "data_id": self.settings.data_id,
                "group": self.settings.group,
            },
        )

    def _import_sdk_module(self) -> object:
        try:
            return importlib.import_module("v2.nacos")
        except Exception as exc:
            raise NacosBackendError("sdk_v3 client is not available") from exc

    async def _fetch_content_async(self) -> str | None:
        service = await self._create_config_service()
        try:
            content = await service.get_config(self._config_param())
        finally:
            await service.shutdown()
        return content if isinstance(content, str) and content.strip() else None

    async def _watch_async(self, on_update: UpdateCallback, ready: threading.Event) -> None:
        service = await self._create_config_service()

        async def _listener(*args: object, **kwargs: object) -> None:
            content = kwargs.get("content")
            if content is None and args:
                content = args[-1]
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            if isinstance(content, str):
                on_update(content)

        await service.add_listener(self.settings.data_id, self.settings.group, _listener)
        ready.set()

        # Keep the listener alive for the lifetime of the process, matching the
        # best-effort daemon-thread behavior used by the HTTP backend.
        await asyncio.Event().wait()

    async def _create_config_service(self) -> object:
        builder = self._module.ClientConfigBuilder()
        builder.server_address(self.settings.server_addr)
        if self.settings.namespace:
            builder.namespace_id(self.settings.namespace)
        if self.settings.username:
            builder.username(self.settings.username)
        if self.settings.password:
            builder.password(self.settings.password)
        client_config = builder.build()
        return await self._module.NacosConfigService.create_config_service(client_config)

    def _config_param(self) -> object:
        return self._module.ConfigParam(
            data_id=self.settings.data_id,
            group=self.settings.group,
        )


def create_nacos_backend(settings: NacosSettings) -> NacosConfigBackend:
    if settings.backend == NacosBackendType.HTTP:
        return HttpNacosBackend(settings)
    if settings.backend == NacosBackendType.SDK_V2:
        return LegacySdkNacosBackend(settings, sdk_version=NacosBackendType.SDK_V2)
    if settings.backend == NacosBackendType.SDK_V3:
        return AsyncSdkV3NacosBackend(settings)

    server_major = detect_nacos_server_major_version(settings)
    preferred_backends = _preferred_auto_backends(server_major, available_backends=_available_sdk_backends())

    for backend_type in preferred_backends:
        try:
            if backend_type == NacosBackendType.HTTP:
                backend = HttpNacosBackend(settings)
            elif backend_type == NacosBackendType.SDK_V3:
                backend = AsyncSdkV3NacosBackend(settings)
            else:
                backend = LegacySdkNacosBackend(settings, sdk_version=backend_type)
            logger.info(
                "selected nacos backend=%s for data_id=%s",
                backend_type.value,
                settings.data_id,
                extra={"backend": backend_type.value, "data_id": settings.data_id},
            )
            return backend
        except Exception:
            logger.exception(
                "failed to initialize nacos backend",
                extra={"backend": backend_type.value, "data_id": settings.data_id},
            )
    raise NacosBackendError("no nacos backend is available")


def detect_nacos_server_major_version(settings: NacosSettings) -> int | None:
    server_addr = settings.server_addr
    if not server_addr.startswith(("http://", "https://")):
        server_addr = f"http://{server_addr}"
    parsed = urlparse(server_addr)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    try:
        response = requests.get(f"{base_url}/nacos/v1/console/server/state", timeout=5)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.exception("failed to detect nacos server version")
        return None
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        return None
    try:
        return int(version.split(".", 1)[0])
    except ValueError:
        return None


def _available_sdk_backends() -> tuple[NacosBackendType, ...]:
    available: list[NacosBackendType] = []
    if importlib.util.find_spec("v2.nacos") is not None:
        available.append(NacosBackendType.SDK_V3)
    if importlib.util.find_spec("nacos") is not None:
        available.append(NacosBackendType.SDK_V2)
    return tuple(available)


def _preferred_auto_backends(
    server_major: int | None,
    *,
    available_backends: tuple[NacosBackendType, ...] | None = None,
) -> tuple[NacosBackendType, ...]:
    if available_backends is None:
        available_backends = (NacosBackendType.SDK_V2, NacosBackendType.SDK_V3)
    if server_major == 2:
        preferred = (NacosBackendType.SDK_V2, NacosBackendType.SDK_V3)
    elif server_major == 3:
        preferred = (NacosBackendType.SDK_V3, NacosBackendType.SDK_V2)
    else:
        preferred = (NacosBackendType.SDK_V3, NacosBackendType.SDK_V2)
    filtered = tuple(backend for backend in preferred if backend in available_backends)
    return (*filtered, NacosBackendType.HTTP)
