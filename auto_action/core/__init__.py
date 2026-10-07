#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1Panel应用商店核心模块

这个模块包含了重构后的核心组件：
- 配置管理 (config_manager)
- 日志系统 (logger)
- 异常处理 (exceptions)
- 重试机制 (retry)
- 版本检查器 (version_checkers)
- Git仓库操作 (git_repository)
- 应用管理器 (app_manager)
- 接口定义 (interfaces)
"""

from .config_manager import EnhancedConfigManager, get_config_manager
from .logger import EnhancedLogger, get_logger
from .exceptions import (
    AppStoreException,
    ConfigurationError,
    VersionCheckError,
    AppUpdateError,
    GitOperationError,
    NetworkError,
    ValidationError
)
from .interfaces import (
    AppInfo,
    UpdateResult,
    VersionChecker,
    AppUpdater,
    GitRepository,
    ConfigManager
)
from .version_checkers import (
    DockerHubVersionChecker,
    GitHubVersionChecker,
    VersionCheckerFactory,
    BatchVersionChecker
)
from .git_repository import EnhancedGitRepository
from .app_manager import AppManager, LocalAppUpdater
from .retry import retry, circuit_breaker

__all__ = [
    # 主要类
    'AppManager',
    'EnhancedConfigManager',
    'EnhancedGitRepository',
    'EnhancedLogger',

    # 工厂函数
    'get_config_manager',
    'get_logger',
    'VersionCheckerFactory',

    # 版本检查器
    'DockerHubVersionChecker',
    'GitHubVersionChecker',
    'BatchVersionChecker',

    # 应用更新器
    'LocalAppUpdater',

    # 数据类
    'AppInfo',
    'UpdateResult',

    # 异常类
    'AppStoreException',
    'ConfigurationError',
    'VersionCheckError',
    'AppUpdateError',
    'GitOperationError',
    'NetworkError',
    'ValidationError',

    # 接口
    'VersionChecker',
    'AppUpdater',
    'GitRepository',
    'ConfigManager',

    # 装饰器
    'retry',
    'circuit_breaker'
]

__version__ = "2.0.0"
__author__ = "1Panel AppStore Team"
__description__ = "1Panel应用商店自动更新工具核心模块"