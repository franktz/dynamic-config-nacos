from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


def _segments(path: str) -> list[str]:
    normalized = re.sub(r"\[(\d+)\]", r".\1", path)
    return [seg for seg in normalized.split(".") if seg]


@dataclass(frozen=True)
class NullConf:
    def __getattr__(self, _name: str) -> "NullConf":
        return self

    def __getitem__(self, _key: Any) -> "NullConf":
        return self

    def get(self, _path: str, default: Any = None) -> Any:
        return default

    @property
    def value(self) -> None:
        return None

    def __bool__(self) -> bool:
        return False


NULL = NullConf()


@dataclass(frozen=True)
class Conf:
    _value: Any

    def _wrap(self, value: Any) -> Any:
        if value is None:
            return NULL
        if isinstance(value, (Mapping, list, tuple)):
            return Conf(value)
        return value

    def __getattr__(self, name: str) -> Any:
        if isinstance(self._value, Mapping):
            return self._wrap(self._value.get(name))
        return NULL

    def __getitem__(self, key: Any) -> Any:
        value = self._value
        if isinstance(key, str) and ("." in key or "[" in key):
            return self._wrap(self.get(key))
        if isinstance(value, Mapping):
            return self._wrap(value.get(key))
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            if isinstance(key, int) and 0 <= key < len(value):
                return self._wrap(value[key])
        return NULL

    def get(self, path: str, default: Any = None) -> Any:
        current = self._value
        for seg in _segments(path):
            if isinstance(current, Mapping):
                current = current.get(seg)
                if current is None:
                    return default
                continue
            if isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
                try:
                    idx = int(seg)
                except ValueError:
                    return default
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return default
                continue
            return default
        return current if current is not None else default

    @property
    def value(self) -> Any:
        return self._value
