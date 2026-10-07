#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抽象接口定义
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class AppInfo:
    """应用信息数据类"""
    name: str
    image: str
    current_version: str
    latest_version: Optional[str] = None
    app_type: str = "docker"  # docker, github
    prefix: bool = True
    # 特殊标签匹配方案，None走默认语义版本匹配；如 minio_release 用于
    # RELEASE.<时间戳>[-变体] 这种非语义版本标签(见version_checkers)
    tag_scheme: Optional[str] = None

    @property
    def needs_update(self) -> bool:
        """检查是否需要更新"""
        if not self.latest_version:
            return False
        return self.current_version != self.latest_version


@dataclass
class UpdateResult:
    """更新结果数据类"""
    success: bool
    app_name: str
    old_version: str
    new_version: str
    message: str
    details: Dict[str, Any] = None


class VersionChecker(ABC):
    """版本检查器抽象接口"""

    @abstractmethod
    def check_version(self, app_info: AppInfo) -> Optional[str]:
        """
        检查应用最新版本

        Args:
            app_info: 应用信息

        Returns:
            最新版本号，如果没有更新返回None
        """
        pass

    @abstractmethod
    def get_checker_type(self) -> str:
        """获取检查器类型"""
        pass


class AppUpdater(ABC):
    """应用更新器抽象接口"""

    @abstractmethod
    def update_app(self, app_info: AppInfo) -> UpdateResult:
        """
        更新应用

        Args:
            app_info: 应用信息

        Returns:
            更新结果
        """
        pass


class GitRepository(ABC):
    """Git仓库操作抽象接口"""

    @abstractmethod
    def commit_and_push(self, message: str) -> bool:
        """
        提交并推送更改

        Args:
            message: 提交消息

        Returns:
            操作是否成功
        """
        pass

    @abstractmethod
    def pull_and_reset(self) -> bool:
        """
        拉取并重置到远程最新状态

        Returns:
            操作是否成功
        """
        pass

    @abstractmethod
    def has_changes(self) -> bool:
        """检查是否有未提交的更改"""
        pass


class ConfigManager(ABC):
    """配置管理器抽象接口"""

    @abstractmethod
    def get_apps_config(self) -> Dict[str, Any]:
        """获取应用配置"""
        pass

    @abstractmethod
    def update_app_version(self, app_name: str, version: str) -> None:
        """更新应用版本"""
        pass

    @abstractmethod
    def save_config(self) -> None:
        """保存配置到文件"""
        pass