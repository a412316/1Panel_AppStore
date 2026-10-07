# 1PanelAppStore - 自用1Panel应用商店

> 🚀 **企业级应用商店自动更新工具** - 高性能、高可用、易维护

## 📋 项目简介

1PanelAppStore是一个专业的1Panel应用商店自动管理工具，用于自动检测Docker应用更新，生成新的版本目录，并提交推送到Git远程仓库。

### ✨ 核心特性

- 🔄 **自动版本检测**: 支持Docker Hub和GitHub作为版本源
- ⚡ **并行处理**: 高效的并行版本检查和应用更新
- 🛡️ **健壮性**: 完善的错误处理、重试机制和故障恢复
- 🎨 **用户友好**: 彩色日志输出、进度显示和详细的状态反馈
- 🔧 **配置管理**: 统一的配置管理和验证机制
- 📊 **操作审计**: 详细的操作日志和结果统计

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Git（推送到GitHub远程仓库，认证依赖运行环境的SSH密钥或credential helper）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 基本用法

```bash
# 执行完整更新流程
python main.py

# 仅检查版本，不执行更新
python main.py --check-only

# 启用并行更新（推荐用于多应用）
python main.py --parallel

# 设置详细日志级别
python main.py --log-level DEBUG

# 查看帮助信息
python main.py --help
```

## 📁 项目结构

```
1PanelAppStore/
├── auto_action/                 # 核心功能模块
│   ├── core/                   # 核心架构
│   │   ├── interfaces.py       # 抽象接口定义
│   │   ├── config_manager.py   # 配置管理器
│   │   ├── logger.py           # 增强日志系统
│   │   ├── retry.py            # 重试与熔断机制
│   │   ├── version_checkers.py # 版本检查器（多数据源fallback）
│   │   ├── git_repository.py   # Git仓库操作
│   │   ├── app_manager.py      # 应用管理器
│   │   └── config.json         # 应用配置文件（实际生效）
├── apps/                       # 应用定义目录
│   └── [app_name]/             # 各应用目录
├── tests/                      # 测试文件
├── docs/                       # 文档目录（重构说明等）
├── main.py                     # 主入口
├── update.sh                   # 手动部署脚本
├── requirements.txt            # Python依赖
└── README.md                   # 项目说明文档
```

## ⚙️ 配置说明

配置目录为 `auto_action/core/`（默认读取位置，`--config-dir` 可覆盖）。

### 应用配置 (auto_action/core/config.json)

```json
{
  "nginx": {
    "type": "docker",
    "image": "nginx",
    "version": "1.21.6",
    "prefix": true
  },
  "tailscale": {
    "type": "github",
    "image": "tailscale/tailscale",
    "version": "1.42.2",
    "prefix": true
  }
}
```

| 字段 | 说明 |
|------|------|
| `type` | `docker`（查 Docker Hub 标签）或 `github`（查 GitHub Releases） |
| `image` | 镜像名（docker）或 `owner/repo`（github） |
| `version` | 当前版本；`latest` 表示跳过自动更新 |
| `prefix` | 为 `true` 时更新 compose 里的镜像标签会加 `v` 前缀 |
| `tag_scheme` | 可选。特殊标签匹配方案，不填走默认语义版本匹配；`minio_release` 用于 `RELEASE.<时间戳>[-变体]` 格式标签（如 silo/MinIO 的 `RELEASE.2026-09-16T00-00-00Z-distroless`），变体后缀跟随当前版本 |

> 注意：`version` 必须与 `apps/<应用名>/` 下的版本目录名一致（完整 tag 作为目录名），否则更新时找不到源目录。

## 🔧 高级功能

### 命令行选项

| 选项 | 说明 |
|------|------|
| `--check-only` | 仅检查版本，不执行更新 |
| `--parallel` | 启用并行处理 |
| `--config-dir PATH` | 指定配置目录 |
| `--log-level LEVEL` | 设置日志级别 (DEBUG/INFO/WARNING/ERROR) |
| `--version` | 显示版本信息 |
| `--help` | 显示帮助信息 |

### 编程接口

#### 新版本推荐用法

```python
from auto_action.core import AppManager, get_config_manager
from main import ApplicationStoreUpdater

# 简单用法
updater = ApplicationStoreUpdater()
result = updater.run_update()

# 或使用AppManager进行细粒度控制
app_manager = AppManager()
apps_to_update = app_manager.get_apps_needing_update()
results = app_manager.update_apps(apps_to_update)
app_manager.commit_and_push()
```

## 📊 性能特性

### 处理机制

- **版本检查**: 批量检查，同类检查器复用实例（重试与熔断状态全程累积）
- **数据源fallback**: Docker Hub官方API → 镜像加速站（1ms.run/dockerproxy.net）→ 自建代理，任一源可用即返回
- **应用更新**: 支持串行/并行两种模式

## 🛡️ 可靠性保障

### 错误处理机制

- **分层异常体系**: 6种专门的异常类型
- **自动重试**: 指数退避 + 随机抖动
- **熔断器保护**: 防止雪崩效应
- **优雅降级**: 单个组件失败不影响整体流程

### 数据安全

- **原子操作**: 配置文件原子性保存
- **自动备份**: 操作前自动创建备份
- **操作回滚**: 失败时自动回滚更改
- **详细审计**: 完整的操作日志记录

## 📈 监控和日志

### 日志系统

```bash
# 实时查看日志
tail -f auto_action/logs/update_1panel_store.log

# 设置详细日志
python main.py --log-level DEBUG
```

### 日志级别

- **INFO**: 基本操作信息
- **DEBUG**: 详细调试信息
- **WARNING**: 警告信息
- **ERROR**: 错误信息

## 🧪 测试和验证

### 运行测试

```bash
# 运行功能测试
python tests/test_refactored.py

# 仅检查版本
python main.py --check-only

# 验证配置
python -c "from auto_action.core import get_config_manager; print(get_config_manager().get_all_apps())"
```

### 故障排除

常见问题解决：

1. **导入错误**: `pip install -r requirements.txt`
2. **配置错误**: 检查`config.json`格式
3. **权限问题**: 确保Git仓库和目录权限正确
4. **网络问题**: 检查网络连接和防火墙设置

## 📚 文档

- [📖 重构详细文档](docs/REFACTORING.md) - 完整的重构说明、架构和使用指南

## 🤝 贡献指南

### 开发环境

```bash
# 克隆仓库
git clone <repository_url>
cd 1PanelAppStore

# 安装依赖
pip install -r requirements.txt

# 运行测试
python tests/test_refactored.py
```

### 代码规范

- 使用Python 3.8+语法
- 遵循PEP 8编码规范
- 添加类型提示和文档字符串
- 编写相应的测试用例

## 📋 版本历史

### v2.0.0 (当前版本) - 重构版本
- 🏗️ 全新的模块化架构
- 🔧 统一配置管理和日志系统
- ⚡ 并行处理和性能优化
- 🛡️ 完善的错误处理和重试机制
- 🗑️ 移除1Panel面板同步功能，仅维护Git仓库（面板可通过应用商店的Git仓库地址自行同步）

### v1.x.x - 原始版本
- 基础的功能实现
- 简单的配置管理
- 基本的日志记录

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。

## 🙋‍♂️ 支持

如果您遇到问题或有建议，请：

1. 搜索现有的 [Issues](../../issues)
2. 创建新的 [Issue](../../issues/new)
3. 提交 [Pull Request](../../pulls)

---

⭐ 如果这个项目对您有帮助，请给我们一个星标！

**注意**: v2.0.0为当前的重构版本，旧版兼容层（auto_action/update_*.py 等）已移除，请直接使用 auto_action.core 的API。