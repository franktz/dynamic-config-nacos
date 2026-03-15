# dynamic-config-nacos

[English](./README.md) | [简体中文](./README.zh-CN.md)

`dynamic-config-nacos` is a small reusable Python package for dynamic
configuration loading.

Its goal is to give application projects one consistent way to read
configuration, whether the source is a local YAML file or a Nacos server.

Author: FrankTang (<franktz2003@gmail.com>)

License: MIT

## What This Library Does

- Uses local YAML as a fallback configuration source
- Fetches remote configuration from Nacos
- Supports automatic backend selection across `http`, `sdk_v2`, and `sdk_v3`
- Refreshes in-memory configuration on updates on a best-effort basis
- Provides a lightweight `Conf` object for dot-path and index-based access

## Install

```bash
pip install dynamic-config-nacos
```

The Python import name remains `dynamic_config`:

```python
from dynamic_config import DynamicConfigProvider
```

For local workspace development with `uv`, downstream projects can also use a
path dependency to this package.

## Quick Start

```python
from dynamic_config import DynamicConfigProvider

provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
provider.load_from_env()

app_name = provider.get("app.name")
```

## Usage

### Local YAML Only

```python
from dynamic_config import DynamicConfigProvider

provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
provider.load_initial(None)

debug = provider.get("app.debug", False)
```

### Enable Nacos with Environment Variables

```powershell
$env:NACOS_SERVER_ADDR = "127.0.0.1:8848"
$env:NACOS_DATA_ID = "app.yaml"
$env:NACOS_GROUP = "DEFAULT_GROUP"
```

```python
from dynamic_config import DynamicConfigProvider

provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
provider.load_from_env()

app_name = provider.get("app.name")
```

### Override the Local YAML Path

`DynamicConfigProvider` currently requires a `local_yaml_path` value during
construction, but `load_from_env()` will override it if `LOCAL_CONFIG_PATH` is
set.

```powershell
$env:LOCAL_CONFIG_PATH = "configs/dev.local.yaml"
```

After `load_from_env()`, the library will use the path from
`LOCAL_CONFIG_PATH`.

### Read Values Through `Conf`

```python
conf = provider.conf

value1 = conf["a.b[0].c"]
value2 = conf.a.b[0].c
value3 = conf.get("a.x", "fallback")
```

## Logging

This package uses the standard library `logging` module and does not currently
accept a custom logger object from callers.

Internally it uses module-level loggers like this:

```python
logger = logging.getLogger(__name__)
```

That means the host application controls log output, handlers, formatting, and
log levels:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

Typical log events include:

- `warning` when the local YAML file is missing
- `warning` when Nacos returns a non-mapping YAML root
- `warning` for invalid backend or polling interval values
- `info` when a watcher has started, including the backend and polling interval for HTTP mode
- `info` when a Nacos update has been applied
- `info` when a backend is auto-selected
- `exception` when Nacos fetch, watcher startup, login, or version detection fails

## SDK Compatibility Note

If you install the current `nacos-sdk-python` 3.x line, the supported SDK path
in this package is `sdk_v3`.

In `auto` mode, the package now prefers `sdk_v3` when that is the only
installed SDK-backed import path available. `sdk_v2` is retained for older
environments that still provide the legacy `nacos` package import.

## Does the Local YAML File Need to Exist?

- `local_yaml_path` is currently a required constructor argument
- The file itself does not need to exist
- If the file is missing, the library logs a warning and falls back to an empty
  config `{}`
- If Nacos successfully returns a config, the local YAML file is not used for
  that load

In practice, the path behaves more like a local fallback location than a strict
required input file.

## Internal Design Overview

The library's loading flow looks like this:

1. Create `DynamicConfigProvider` with a local YAML path.
2. Call `load_from_env()` to read Nacos-related environment variables.
3. If `NACOS_SERVER_ADDR` is present, build a `NacosSettings` object.
4. Create a Nacos backend using explicit configuration or auto-detection.
5. Try to fetch YAML content from Nacos first.
6. If Nacos fails, returns empty content, or returns a non-mapping YAML root,
   fall back to the local YAML file.
7. Store the final raw dictionary and wrap it in a `Conf` object.
8. If the backend supports watching, start a watcher and refresh the in-memory
   config on updates.

### Auto Backend Selection

When `backend=AUTO`, the package first tries to detect the Nacos server major
version over HTTP and then picks a preferred order:

- Nacos 2.x: `sdk_v2` -> `sdk_v3` -> `http`
- Nacos 3.x: `sdk_v3` -> `sdk_v2` -> `http`
- Detection failed: `sdk_v3` -> `sdk_v2` -> `http`

After building that preferred order, the package filters out SDK paths that are
not actually importable in the current Python environment. For example, if only
`v2.nacos` is installed, `auto` skips `sdk_v2` and goes straight to `sdk_v3`.

### HTTP Mode

- Fetches config through the Nacos HTTP API
- Optionally logs in first to obtain an `accessToken`
- Starts a background polling thread
- Logs watcher startup with the active backend and polling interval
- Uses content MD5 to detect changes
- Logs when an updated config has been applied

### SDK Mode

- Tries multiple SDK import paths
- Tries both `get_config` and `getConfig`
- Tries `add_config_watchers`, `add_config_watcher`, and `add_listener`

## Public API

- `DynamicConfigProvider`
- `Conf`
- `NullConf`
- `NULL`
- `NacosSettings`
- `NacosBackendType`

## Additional Docs

- English usage guide: [how-to-use.md](./how-to-use.md)
- Chinese usage guide: [how-to-use.zh-CN.md](./how-to-use.zh-CN.md)
- Chinese overview: [README.zh-CN.md](./README.zh-CN.md)
- Changelog: [CHANGELOG.md](./CHANGELOG.md)

## Project Links

- Homepage: <https://github.com/franktz/dynamic-config-nacos>
- Repository: <https://github.com/franktz/dynamic-config-nacos>
- Issues: <https://github.com/franktz/dynamic-config-nacos/issues>

## Author

- FrankTang
- Email: <franktz2003@gmail.com>
- License: MIT
