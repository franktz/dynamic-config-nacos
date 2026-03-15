# 使用指南

## 目的

`dynamic-config-nacos` 是一个面向业务项目的动态配置依赖包。

作者：FrankTang（<franktz2003@gmail.com>）

许可证：MIT

它的重点不是构建一个功能庞杂的配置平台，而是提供一层稳定的访问抽象，让业
务代码不需要关心配置到底来自本地 YAML 文件还是 Nacos。

这个包适合以下场景：

- 本地开发使用 YAML 文件
- 测试或生产环境使用 Nacos
- 业务代码希望统一使用一种配置读取方式
- 配置变更后希望尽量自动刷新到进程内存

## 核心能力

- 从本地 YAML 文件加载配置
- 从 Nacos 加载 YAML 配置
- 支持 HTTP、Nacos SDK v2、Nacos SDK v3 三种后端
- 根据探测到的服务端版本自动选择优先 backend
- 在配置变更后刷新当前进程内的配置快照
- 提供 `Conf`，支持路径、属性和索引访问

## 安装与导入

```bash
pip install dynamic-config-nacos
```

```python
from dynamic_config import DynamicConfigProvider
```

说明：

- PyPI 包名是 `dynamic-config-nacos`
- Python 导入名是 `dynamic_config`

## 基础用法

### 仅使用本地配置

```python
from dynamic_config import DynamicConfigProvider

provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
provider.load_initial(None)

print(provider.get("app.name"))
print(provider.get("app.debug", False))
```

### 通过环境变量决定是否启用 Nacos

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

在这种模式下：

- 如果没有 `NACOS_SERVER_ADDR`，则只使用本地 YAML
- 如果设置了 `NACOS_SERVER_ADDR`，则优先尝试 Nacos
- 如果 Nacos 拉取失败或返回非法 YAML 结构，则回退到本地 YAML

## 如何指定本地 YAML 路径

当前版本要求在构造 `DynamicConfigProvider` 时传入 `local_yaml_path`：

```python
provider = DynamicConfigProvider(local_yaml_path="configs/local.yaml")
```

之后在调用 `load_from_env()` 时，库还会检查 `LOCAL_CONFIG_PATH`。如果这个环境
变量存在，就会覆盖构造函数里的路径。

```powershell
$env:LOCAL_CONFIG_PATH = "configs/dev.local.yaml"
```

所以当前有两种指定方式：

- 代码里传入 `local_yaml_path`
- 通过 `LOCAL_CONFIG_PATH` 覆盖

需要注意两点：

- 构造参数现在仍然是必填的
- 路径对应的文件本身不要求一定存在

如果文件缺失，库会记录一条 `warning` 日志，并返回空配置，而不是直接抛出异常。

## 日志如何工作

这个包目前不支持由调用方传入自定义 `logger` 对象。

它内部统一使用 Python 标准库 `logging`，通过
`logging.getLogger(__name__)` 获取模块级 logger，因此日志输出行为由宿主应用
的 logging 配置控制。

一个简单示例：

```python
import logging

logging.basicConfig(level=logging.INFO)
```

当前实现里常见的日志包括：

- `warning`：本地 YAML 文件缺失
- `warning`：Nacos 返回的 YAML 根节点不是映射
- `warning`：非法 backend 值或轮询间隔
- `info`：Nacos 更新已应用
- `info`：自动选择了某个 backend
- `exception`：Nacos 拉取、watcher 启动、HTTP 登录或版本探测失败

## 如何读取配置

### 方式一：`get`

```python
provider.get("app.name")
provider.get("db.host", "127.0.0.1")
```

### 方式二：`Conf`

```python
conf = provider.conf

conf.app.name
conf["app.name"]
conf["servers"][0]["host"]
conf["servers[0].host"]
```

### 缺失值行为

如果路径不存在：

- `get(path, default)` 返回你提供的默认值
- `Conf` 上的属性访问或索引访问会返回 `NULL`

`NULL` 是一个空对象助手，因此链式访问时不会立刻抛异常。

## 内部结构

整体上，这个库主要分成三个模块：

- `provider.py`：协调加载流程、回退逻辑和 watch 启动
- `backends.py`：为不同 backend 实现 Nacos 的拉取与监听
- `view.py`：把原始字典包装成 `Conf` 和 `NullConf`

### 加载流程

典型的加载顺序如下：

1. 创建 `DynamicConfigProvider`
2. 设置本地 YAML 路径
3. 调用 `load_from_env()` 或 `load_initial()`
4. 如果有 Nacos 配置，则创建 backend
5. 优先尝试从 Nacos 拉取文本内容
6. 将 YAML 解析为 Python `dict`
7. 如果远端失败，则回退到本地 YAML
8. 将结果保存到 `_raw`
9. 同时为相同数据构建 `Conf`
10. 如果 backend 支持 watch，则启动监听
11. 当更新到来时，再次替换 `_raw` 和 `Conf`

### 自动 backend 选择

当使用 `NacosBackendType.AUTO` 时，库会先请求 Nacos 服务端状态接口探测主版本，
再按以下优先顺序选择：

- 服务端 2.x：优先 `sdk_v2`
- 服务端 3.x：优先 `sdk_v3`
- 探测失败：先尝试 `sdk_v3`

如果某个 backend 初始化失败，就继续尝试下一个。

### HTTP backend 的工作方式

HTTP backend 会：

- 从 `/nacos/v1/cs/configs` 拉取内容
- 如有需要先登录获取 `accessToken`
- 启动后台守护轮询线程
- 用内容 MD5 判断是否发生更新
- 仅在内容变化时触发更新回调

### SDK backend 的兼容策略

SDK backend 本质上是一个兼容层：

- 尝试多个可能的 SDK 导入路径
- 同时兼容 `get_config` 和 `getConfig`
- 同时兼容 `add_config_watchers`、`add_config_watcher` 和 `add_listener`

这样可以更好地兼容不同 nacos Python SDK 版本和 API 形态。

## 推荐的接入方式

在业务项目里，比较稳妥的接入方式是：

1. 在启动阶段只初始化一次 `DynamicConfigProvider`
2. 在配置模块里集中调用 `load_from_env()`
3. 业务代码统一通过 `provider.get()` 或 `provider.conf` 读取配置
4. 通过部署环境的环境变量决定是否启用 Nacos
5. 在本地开发时保留 YAML 作为默认配置

这样业务代码可以与实际配置来源解耦。

## 对外 API

- `DynamicConfigProvider`
- `Conf`
- `NullConf`
- `NULL`
- `NacosSettings`
- `NacosBackendType`

## 当前限制

- `local_yaml_path` 仍然是必填构造参数
- 调用方目前不能注入自定义 `logger`
- watcher 启动采用尽力而为策略，失败时只记日志，不中断启动
- 测试覆盖了主流程，但 SDK 兼容性和更多边界场景仍有补充空间

## 相关文档

- [README.md](./README.md)
- [README.zh-CN.md](./README.zh-CN.md)
- [how-to-use.md](./how-to-use.md)
- [PUBLISHING.md](./PUBLISHING.md)

## 项目链接

- Homepage：<https://github.com/franktz/dynamic-config-nacos>
- Repository：<https://github.com/franktz/dynamic-config-nacos>
- Issues：<https://github.com/franktz/dynamic-config-nacos/issues>

## 作者信息

- FrankTang
- 邮箱：<franktz2003@gmail.com>
- 许可证：MIT
