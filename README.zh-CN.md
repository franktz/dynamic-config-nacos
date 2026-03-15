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

## 相关文档

- 英文说明：[README.md](./README.md)
- 详细英文使用指南：[how-to-use.md](./how-to-use.md)
- 详细中文使用指南：[how-to-use.zh-CN.md](./how-to-use.zh-CN.md)
- 发布说明：[PUBLISHING.md](./PUBLISHING.md)

## 项目链接

- Homepage：<https://github.com/franktz/dynamic-config-nacos>
- Repository：<https://github.com/franktz/dynamic-config-nacos>
- Issues：<https://github.com/franktz/dynamic-config-nacos/issues>

## 作者信息

- FrankTang
- 邮箱：<franktz2003@gmail.com>
- 许可证：MIT
