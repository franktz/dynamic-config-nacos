# Usage Guide

## Purpose

`dynamic-config-nacos` is a dynamic configuration dependency for
application projects.

Author: FrankTang (<franktz2003@gmail.com>)

License: MIT

Its focus is not to build a full-featured configuration platform. Instead, it
provides one stable access layer that hides whether configuration comes from a
local YAML file or from Nacos.

This package is a good fit when:

- local development uses YAML files
- test or production environments use Nacos
- business code should use one consistent read path
- config updates should refresh in memory whenever possible

## Core Capabilities

- Load configuration from a local YAML file
- Load YAML configuration from Nacos
- Support HTTP, Nacos SDK v2, and Nacos SDK v3 backends
- Auto-select a preferred backend based on detected server version
- Refresh the current process snapshot when config changes
- Expose `Conf` for path, attribute, and index-based access

## Install and Import

```bash
pip install dynamic-config-nacos
```

```python
from dynamic_config import DynamicConfigProvider
```

Notes:

- The PyPI package name is `dynamic-config-nacos`
- The Python import name is `dynamic_config`

## Basic Usage

### Local Config Only

```python
from dynamic_config import DynamicConfigProvider

provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
provider.load_initial(None)

print(provider.get("app.name"))
print(provider.get("app.debug", False))
```

### Let Environment Variables Decide Whether Nacos Is Used

```powershell
$env:NACOS_SERVER_ADDR = "127.0.0.1:8848"
$env:NACOS_NAMESPACE = ""
$env:NACOS_DATA_ID = "app.yaml"
$env:NACOS_GROUP = "DEFAULT_GROUP"
$env:NACOS_BACKEND = "auto"
```

```python
from dynamic_config import DynamicConfigProvider

provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
provider.load_from_env()

app_name = provider.get("app.name")
```

In this mode:

- if `NACOS_SERVER_ADDR` is absent, only local YAML is used
- if `NACOS_SERVER_ADDR` is present, Nacos is tried first
- if Nacos fails or returns invalid YAML structure, the library falls back to
  local YAML

## How to Specify the Local YAML Path

The current version requires `local_yaml_path` when constructing
`DynamicConfigProvider`:

```python
provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
```

Later, when `load_from_env()` runs, it also checks `LOCAL_CONFIG_PATH`. If that
environment variable exists, it overrides the constructor path.

```powershell
$env:LOCAL_CONFIG_PATH = "configs/dev.local.yaml"
```

So the library supports two ways to specify the local YAML path:

- pass `local_yaml_path` in code
- override it with `LOCAL_CONFIG_PATH`

Two important details:

- the constructor argument is required today
- the file itself does not need to exist

If the file is missing, the library logs a `warning` and returns an empty
configuration instead of raising an exception.

## How Logging Works

This package does not let callers pass in a custom `logger` object.

It uses Python's standard `logging` module internally through
`logging.getLogger(__name__)`, so the host application's logging setup decides
what gets printed, where it goes, and which log levels are visible.

A simple example:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

Common log events in the current implementation:

- `warning`: local YAML file is missing
- `warning`: Nacos returns a YAML root that is not a mapping
- `warning`: invalid backend value or polling interval
- `info`: watcher startup, including backend details and the polling interval in HTTP mode
- `info`: a Nacos update has been applied
- `info`: a backend was auto-selected
- `exception`: Nacos fetch, watcher startup, HTTP login, or version detection failed

## SDK Compatibility

For current `nacos-sdk-python` 3.x environments:

- `sdk_v3` is the supported SDK-backed mode
- `auto` will prefer `sdk_v3` when only the 3.x SDK import path is available
- `sdk_v2` is only for environments that still ship the legacy `nacos` package

## How to Read Configuration

### Option 1: `get`

```python
provider.get("app.name")
provider.get("db.host", "127.0.0.1")
```

### Option 2: `Conf`

```python
conf = provider.conf

conf.app.name
conf["app.name"]
conf["servers"][0]["host"]
conf["servers[0].host"]
```

### Missing Values

If the path does not exist:

- `get(path, default)` returns the provided default
- attribute or index access on `Conf` returns `NULL`

`NULL` is a null-object helper, so chained attribute and index access can
continue without immediately raising an exception.

## Internal Structure

At a high level the library is split into three main modules:

- `provider.py`: orchestrates loading, fallback, and watch startup
- `backends.py`: implements Nacos fetch and watch behavior for different backends
- `view.py`: wraps raw dictionaries in `Conf` and `NullConf`

### Loading Flow

The typical loading sequence is:

1. Create `DynamicConfigProvider`
2. Set the local YAML path
3. Call `load_from_env()` or `load_initial()`
4. Build a backend if Nacos settings are present
5. Try to fetch text content from Nacos first
6. Parse YAML into a Python `dict`
7. Fall back to local YAML if remote loading fails
8. Store the result in `_raw`
9. Build a `Conf` view for the same data
10. Start watching if the backend supports it
11. Replace `_raw` and `Conf` again when updates arrive

### Auto Backend Selection

When `NacosBackendType.AUTO` is used, the library first calls the Nacos server
state endpoint over HTTP to detect the major version and then picks a preferred
order:

- server 2.x: prefer `sdk_v2`
- server 3.x: prefer `sdk_v3`
- detection failed: try `sdk_v3` first

Before trying that order, the library also checks which SDK import paths are
actually available in the current Python environment:

- if only `v2.nacos` exists, `auto` skips `sdk_v2`
- if only `nacos` exists, `auto` skips `sdk_v3`
- if no SDK path exists, `auto` falls back to `http`

If one backend fails to initialize, the next candidate is tried.

### How the HTTP Backend Works

The HTTP backend:

- fetches content from `/nacos/v1/cs/configs`
- optionally logs in first to obtain `accessToken`
- starts a background daemon polling thread
- logs watcher startup with the active backend and polling interval
- compares content MD5 values to detect updates
- triggers the update callback only when content changes
- logs when updated content has been applied in memory

### How the SDK Backend Stays Compatible

The SDK backend mainly acts as a compatibility layer:

- it tries multiple possible SDK import paths
- it tries both `get_config` and `getConfig`
- it tries `add_config_watchers`, `add_config_watcher`, and `add_listener`

This helps the package work across different nacos Python SDK variants and API
shapes.

## Recommended Integration Pattern

The most practical way to use this library in an application is:

1. Initialize `DynamicConfigProvider` once during startup
2. Centralize `load_from_env()` inside your config module
3. Let business code read only through `provider.get()` or `provider.conf`
4. Decide whether Nacos is enabled through deployment-time environment variables
5. Keep local YAML as the default config for development

That keeps business code independent from the actual config source.

## Public API

- `DynamicConfigProvider`
- `Conf`
- `NullConf`
- `NULL`
- `NacosSettings`
- `NacosBackendType`

## Current Limitations

- `local_yaml_path` is still a required constructor argument
- callers cannot currently inject a custom `logger`
- watcher startup is best-effort and logs failures instead of aborting startup
- tests cover core paths, but SDK compatibility and more edge cases still have
  room for expansion

## Related Docs

- [README.md](./README.md)
- [README.zh-CN.md](./README.zh-CN.md)
- [how-to-use.zh-CN.md](./how-to-use.zh-CN.md)
- [PUBLISHING.md](./PUBLISHING.md)

## Project Links

- Homepage: <https://github.com/franktz/dynamic-config-nacos>
- Repository: <https://github.com/franktz/dynamic-config-nacos>
- Issues: <https://github.com/franktz/dynamic-config-nacos/issues>

## Author

- FrankTang
- Email: <franktz2003@gmail.com>
- License: MIT
