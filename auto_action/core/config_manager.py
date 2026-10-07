#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一配置管理器
"""

import json
import os
import configparser
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .interfaces import ConfigManager, AppInfo
from .exceptions import ConfigurationError, ValidationError


@dataclass
class PanelConfig:
    """面板配置数据类"""
    host: str
    port: str
    panel_token: str
    connection_type: str = "http"

    def validate(self) -> None:
        """验证面板配置"""
        if not all([self.host, self.port, self.panel_token]):
            raise ValidationError(f"面板配置不完整: {self}")


class EnhancedConfigManager(ConfigManager):
    """增强的配置管理器实现"""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.dirname(__file__)

        # 配置目录由调用方传入，拒绝路径穿越
        if any(part == '..' for part in Path(config_dir).parts):
            raise ConfigurationError(f"配置目录不允许包含路径穿越: {config_dir}")

        self.config_dir = Path(config_dir)
        self.apps_config_file = self.config_dir / "config.json"
        self.ini_config_file = self.config_dir / "config.ini"

        self._apps_config: Optional[Dict[str, Any]] = None
        self._ini_config: Optional[configparser.ConfigParser] = None

        self._load_configs()

    def _load_configs(self) -> None:
        """加载配置文件"""
        if not self.apps_config_file.exists():
            raise ConfigurationError(f"应用配置文件不存在: {self.apps_config_file}")

        if not self.ini_config_file.exists():
            raise ConfigurationError(f"INI配置文件不存在: {self.ini_config_file}")

        try:
            self._apps_config = json.loads(self.apps_config_file.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"应用配置文件格式错误: {e}")

        self._ini_config = configparser.ConfigParser()
        try:
            self._ini_config.read(self.ini_config_file, encoding='utf-8')
        except configparser.Error as e:
            raise ConfigurationError(f"INI配置文件读取错误: {e}")

    def get_apps_config(self) -> Dict[str, Any]:
        """获取应用配置"""
        if self._apps_config is None:
            raise ConfigurationError("应用配置未加载")
        return self._apps_config.copy()

    def get_app_info(self, app_name: str) -> Optional[AppInfo]:
        """
        获取单个应用信息

        Args:
            app_name: 应用名称

        Returns:
            应用信息对象，如果不存在返回None
        """
        apps_config = self.get_apps_config()
        if app_name not in apps_config:
            return None

        app_config = apps_config[app_name]
        return AppInfo(
            name=app_name,
            image=app_config.get('image', ''),
            current_version=app_config.get('version', ''),
            app_type=app_config.get('type', 'docker'),
            prefix=app_config.get('prefix', True),
            tag_scheme=app_config.get('tag_scheme')
        )

    def get_all_apps(self) -> List[AppInfo]:
        """获取所有应用信息"""
        apps_config = self.get_apps_config()
        apps = []

        for app_name, app_config in apps_config.items():
            # 跳过特殊处理的应用
            # if app_config.get('image') == "xiaoyaliu/alist" or app_config.get('image') == "sky22333/hubproxy" or app_config.get('image') == "p3terx/aria2-pro":
            #     continue
            if app_config.get('version') == "latest" :
                continue

            apps.append(AppInfo(
                name=app_name,
                image=app_config.get('image', ''),
                current_version=app_config.get('version', ''),
                app_type=app_config.get('type', 'docker'),
                prefix=app_config.get('prefix', True),
                tag_scheme=app_config.get('tag_scheme')
            ))

        return apps

    def update_app_version(self, app_name: str, version: str) -> None:
        """更新应用版本"""
        if self._apps_config is None:
            raise ConfigurationError("应用配置未加载")

        if app_name not in self._apps_config:
            raise ConfigurationError(f"应用 {app_name} 不存在于配置中")

        # 验证版本格式
        if not version or not isinstance(version, str):
            raise ValidationError(f"无效的版本号: {version}")

        self._apps_config[app_name]['version'] = version

    def save_config(self) -> None:
        """保存配置到文件"""
        if self._apps_config is None:
            raise ConfigurationError("应用配置未加载")

        # 防御路径穿越：写目标必须仍是配置目录下的固定文件
        if self.apps_config_file.resolve().parent != self.config_dir.resolve():
            raise ConfigurationError(f"配置文件路径越界，已拒绝: {self.apps_config_file}")

        # 创建备份
        backup_file = self.apps_config_file.with_suffix('.json.backup')
        if self.apps_config_file.exists():
            backup_file.write_text(
                self.apps_config_file.read_text(encoding='utf-8'),
                encoding='utf-8'
            )

        try:
            self.apps_config_file.write_text(
                json.dumps(self._apps_config, ensure_ascii=False, indent=4),
                encoding='utf-8'
            )
        except Exception as e:
            # 如果保存失败，恢复备份
            if backup_file.exists():
                backup_file.replace(self.apps_config_file)
            raise ConfigurationError(f"保存配置文件失败: {e}")
        finally:
            # 清理备份文件
            if backup_file.exists():
                backup_file.unlink()

    def get_panel_config(self, panel_name: str) -> PanelConfig:
        """获取面板配置"""
        if self._ini_config is None:
            raise ConfigurationError("INI配置未加载")

        if not self._ini_config.has_section(panel_name):
            raise ConfigurationError(f"面板配置段 {panel_name} 不存在")

        try:
            config = PanelConfig(
                host=self._get_ini_value(panel_name, 'host'),
                port=self._get_ini_value(panel_name, 'port'),
                panel_token=self._get_ini_value(panel_name, 'panel_token'),
                connection_type=self._get_ini_value(panel_name, 'type', 'http')
            )
            config.validate()
            return config
        except Exception as e:
            raise ConfigurationError(f"解析面板配置 {panel_name} 失败: {e}")

    def _get_ini_value(self, section: str, key: str, default: str = '') -> str:
        """获取INI配置值"""
        if self._ini_config is None:
            raise ConfigurationError("INI配置未加载")

        try:
            value = self._ini_config.get(section, key)
            return value.strip().strip('"').strip("'")
        except (configparser.NoSectionError, configparser.NoOptionError):
            if default:
                return default
            raise ConfigurationError(f"配置项 {section}.{key} 不存在")

    def get_git_config(self) -> Dict[str, str]:
        """获取Git配置"""
        if self._ini_config is None:
            raise ConfigurationError("INI配置未加载")

        if not self._ini_config.has_section('gitea'):
            raise ConfigurationError("Git配置段 [gitea] 不存在")

        return {
            'username': self._get_ini_value('gitea', 'username'),
            'password': self._get_ini_value('gitea', 'password'),
            'email': self._get_ini_value('gitea', 'email', '')
        }

    def validate_configs(self) -> None:
        """验证所有配置"""
        # 验证应用配置
        apps_config = self.get_apps_config()
        if not apps_config:
            raise ConfigurationError("应用配置为空")

        for app_name, app_config in apps_config.items():
            required_fields = ['image', 'version', 'type']
            for field in required_fields:
                if field not in app_config:
                    raise ConfigurationError(f"应用 {app_name} 缺少必需字段: {field}")

            if app_config['type'] not in ['docker', 'github']:
                raise ConfigurationError(f"应用 {app_name} 类型无效: {app_config['type']}")

    def reload_configs(self) -> None:
        """重新加载配置文件"""
        self._load_configs()


# 全局配置管理器实例
_config_manager: Optional[EnhancedConfigManager] = None


def get_config_manager(config_dir: Optional[str] = None) -> EnhancedConfigManager:
    """获取全局配置管理器实例（config_dir 仅在首次创建时生效）"""
    global _config_manager
    if _config_manager is None:
        _config_manager = EnhancedConfigManager(config_dir)
    return _config_manager