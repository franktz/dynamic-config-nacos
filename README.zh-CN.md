# dynamic-config-nacos

[English](./README.md) | [简体中文](./README.zh-CN.md)

`dynamic-config-nacos` 是一个小型、可复用的 Python 动态配置库。

作者：FrankTang（<franktz2003@gmail.com>）

许可证：MIT

它的目标是为业务项目提供一层统一的配置访问接口，让项目既可以从本地 YAML
读取配置，也可以从 Nacos 拉取配置。

## 这个库能做什么

- 支持本地 YAML 作为兜底配置
- 支持从 Nacos 拉取远端配置
- 支持在 `http`、`sdk_v2`、`sdk_v3` 之间自动选择后端
- 支持在配置更新时尽力刷新内存中的配置视图
- 提供轻量的 `Conf` 访问对象，支持点路径和下标访问

## 安装

```bash
pip install dynamic-config-nacos
```

安装后的导入包名仍然是 `dynamic_config`：

```python
from dynamic_config import DynamicConfigProvider
```

## 快速开始

```python
from dynamic_config import DynamicConfigProvider

provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
provider.load_from_env()

app_name = provider.get("app.name")
```

## 使用方式

### 只使用本地 YAML

```python
from dynamic_config import DynamicConfigProvider

provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
provider.load_initial(None)

debug = provider.get("app.debug", False)
```

### 通过环境变量启用 Nacos

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

### 指定本地 YAML 路径

构造 `DynamicConfigProvider` 时必须传入 `local_yaml_path`，但调用
`load_from_env()` 时，如果存在 `LOCAL_CONFIG_PATH` 环境变量，它会覆盖构造时
传入的路径。

```powershell
$env:LOCAL_CONFIG_PATH = "configs/dev.local.yaml"
```

## 日志行为

这个库使用标准库 `logging` 输出日志，目前不支持由调用方直接传入自定义
`logger` 对象。

库内部使用模块级 logger：

```python
logger = logging.getLogger(__name__)
```

因此是否输出日志、输出到哪里、显示哪些级别，都是由宿主应用的 logging 配置
统一控制的。

当前常见日志包括：

- `warning`：本地 YAML 文件缺失
- `warning`：Nacos 返回的 YAML 根节点不是映射
- `warning`：backend 值或轮询间隔非法
- `info`：watcher 已启动，HTTP 模式会带上轮询间隔
- `info`：Nacos 配置更新已经应用到内存
- `info`：自动选择了某个 backend
- `exception`：Nacos 拉取、watcher 启动、登录或版本探测失败

### 单独输出 `nacos-python-sdk` 日志

如果你使用的是 `sdk_v2` 或 `sdk_v3`，现在可以把 SDK 自己的日志单独输出到指定路径，
而不影响应用主日志的 `logging` 配置。

例如：

```python
from dynamic_config import DynamicConfigProvider, NacosBackendType, NacosSettings

provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
provider.load_initial(
    NacosSettings(
        server_addr="127.0.0.1:8848",
        namespace=None,
        data_id="app.yaml",
        group="DEFAULT_GROUP",
        backend=NacosBackendType.SDK_V3,
        sdk_log_level="ERROR",
        sdk_log_path="logs/nacos.log",
    )
)
```

也可以通过环境变量配置：

```powershell
$env:NACOS_SDK_LOG_LEVEL = "ERROR"
$env:NACOS_SDK_LOG_PATH = "logs/nacos.log"
```

说明：

- `sdk_log_path` 可以传目录，也可以传明确的日志文件路径
- 例如传入 `logs/nacos.log` 时，SDK 日志会写入这个文件
- 这项配置只对 `sdk_v2` 和 `sdk_v3` 生效；`http` backend 不会使用 `nacos-python-sdk`

## 内部实现概览

整体流程大致如下：

1. 创建 `DynamicConfigProvider`
2. 读取环境变量并构造 `NacosSettings`
3. 优先尝试从 Nacos 拉取配置
4. 如果远端失败，则回退到本地 YAML
5. 将结果包装成 `Conf`
6. 如果 backend 支持 watch，则在配置更新时刷新内存数据

自动 backend 选择逻辑：

- Nacos 2.x：`sdk_v2` -> `sdk_v3` -> `http`
- Nacos 3.x：`sdk_v3` -> `sdk_v2` -> `http`
- 无法探测时：`sdk_v3` -> `sdk_v2` -> `http`

这里的“探测”是先通过 HTTP 请求 Nacos 的服务端状态接口拿主版本，再决定优先顺
序。随后库还会再判断当前 Python 环境里到底有哪些 SDK 导入路径可用：

- 如果只有 `v2.nacos`，会跳过 `sdk_v2`
- 如果只有 `nacos`，会跳过 `sdk_v3`
- 如果两个 SDK 路径都不可用，就直接回退到 `http`

HTTP backend 的 watch 不是一次性读取，而是会启动后台轮询线程，按配置的轮询间
隔持续拉取，并通过内容 MD5 判断是否发生变更。只有内容真的变化时，才会刷新内
存配置并输出更新日志。

## 相关文档

- 英文说明：[README.md](./README.md)
- 详细英文使用指南：[how-to-use.md](./how-to-use.md)
- 详细中文使用指南：[how-to-use.zh-CN.md](./how-to-use.zh-CN.md)
- 变更日志：[CHANGELOG.md](./CHANGELOG.md)
- 发布说明：[PUBLISHING.md](./PUBLISHING.md)

## 项目链接

- Homepage：<https://github.com/franktz/dynamic-config-nacos>
- Repository：<https://github.com/franktz/dynamic-config-nacos>
- Issues：<https://github.com/franktz/dynamic-config-nacos/issues>

## 作者信息

- FrankTang
- 邮箱：<franktz2003@gmail.com>
- 许可证：MIT
