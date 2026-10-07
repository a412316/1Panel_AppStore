#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用管理器实现
"""

import os
import re
import shutil
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .interfaces import AppUpdater, AppInfo, UpdateResult, ConfigManager, GitRepository
from .exceptions import AppUpdateError, ValidationError
from .logger import get_logger
from .version_checkers import VersionCheckerFactory, BatchVersionChecker
from .config_manager import get_config_manager

logger = get_logger()

# 应用名/版本号的白名单：有限字符集，禁止路径分隔符和穿越序列
_SAFE_SEGMENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')


def _is_safe_segment(value: str) -> bool:
    """校验单个路径段（应用名/版本号）不含路径穿越序列"""
    return bool(_SAFE_SEGMENT.match(value)) and '..' not in value


class LocalAppUpdater(AppUpdater):
    """本地应用文件更新器"""

    def __init__(self, apps_root_dir: str):
        self.apps_root_dir = Path(apps_root_dir)

        if not self.apps_root_dir.exists():
            raise AppUpdateError(f"应用根目录不存在: {self.apps_root_dir}")

    def update_app(self, app_info: AppInfo) -> UpdateResult:
        """
        更新应用文件

        Args:
            app_info: 应用信息

        Returns:
            更新结果
        """
        app_name = app_info.name
        old_version = app_info.current_version
        new_version = app_info.latest_version

        if not new_version:
            return UpdateResult(
                success=False,
                app_name=app_name,
                old_version=old_version,
                new_version=old_version,
                message="没有新版本"
            )

        # 应用名与版本号来自配置文件，先做路径段白名单校验，防止路径穿越
        if not all(_is_safe_segment(v) for v in (app_name, old_version, new_version)):
            error_msg = f"应用名或版本号含非法字符: {app_name}, {old_version}, {new_version}"
            logger.error(f"❌ {app_name} 更新失败: {error_msg}")
            return UpdateResult(
                success=False,
                app_name=app_name,
                old_version=old_version,
                new_version=new_version,
                message=error_msg
            )

        if old_version == new_version:
            return UpdateResult(
                success=True,
                app_name=app_name,
                old_version=old_version,
                new_version=old_version,
                message="版本已是最新"
            )

        app_path = self.apps_root_dir / app_name
        old_version_path = app_path / old_version
        new_version_path = app_path / new_version

        # 应用名与版本号来自配置文件，防御路径穿越：目标路径必须仍在应用根目录内
        root = self.apps_root_dir.resolve()
        for p in (old_version_path, new_version_path):
            resolved = p.resolve()
            if resolved != root and root not in resolved.parents:
                error_msg = f"路径越界，已拒绝: {p}"
                logger.error(f"❌ {app_name} 更新失败: {error_msg}")
                return UpdateResult(
                    success=False,
                    app_name=app_name,
                    old_version=old_version,
                    new_version=new_version,
                    message=error_msg
                )

        # print(f'新: {new_version_path}')
        # print(f'旧: {old_version_path}')
        # print(f'名称: {app_info.name}')
        # print(f'镜像: {app_info.image}')
        # print(f'新版本号: {new_version}')
        # print(f'类型: {app_info.app_type}')
        # print(f'其他: {app_info.prefix}')

        # 验证路径
        if not old_version_path.exists():
            error_msg = f"源版本目录不存在: {old_version_path}"
            logger.error(f"❌ {app_name} 更新失败: {error_msg}")
            return UpdateResult(
                success=False,
                app_name=app_name,
                old_version=old_version,
                new_version=new_version,
                message=error_msg
            )

        if new_version_path.exists():
            warning_msg = f"目标版本目录已存在: {new_version_path}"
            logger.warning(f"⚠️  {app_name} 跳过更新: {warning_msg}")
            return UpdateResult(
                success=False,
                app_name=app_name,
                old_version=old_version,
                new_version=new_version,
                message=warning_msg
            )

        try:
            logger.info(f"🔄 开始更新 {app_name}: {old_version} → {new_version}")

            # 复制版本目录
            shutil.copytree(old_version_path, new_version_path)
            logger.debug(f"✅ 已复制目录: {old_version_path} → {new_version_path}")

            # 更新Docker Compose文件中的镜像版本
            if app_info.prefix:
                t_version = 'v' + new_version
            else:
                t_version = new_version
            # print(t_version)
            if app_info.app_type == 'github':
                t_image = 'ghcr.io/' + app_info.image
                self._update_compose_file(new_version_path, t_image, t_version)
            else:
                self._update_compose_file(new_version_path, app_info.image, t_version)

            # 删除旧版本目录
            shutil.rmtree(old_version_path)
            logger.debug(f"✅ 已删除旧版本目录: {old_version_path}")

            success_msg = f"成功更新到版本 {new_version}"
            logger.info(f"✅ {app_name} {success_msg}")

            return UpdateResult(
                success=True,
                app_name=app_name,
                old_version=old_version,
                new_version=new_version,
                message=success_msg
            )

        except Exception as e:
            # 清理失败的更新
            if new_version_path.exists():
                shutil.rmtree(new_version_path, ignore_errors=True)

            error_msg = f"更新失败: {str(e)}"
            logger.error(f"❌ {app_name} {error_msg}")
            return UpdateResult(
                success=False,
                app_name=app_name,
                old_version=old_version,
                new_version=new_version,
                message=error_msg
            )

    def _update_compose_file(self, version_path: Path, image_name: str, new_version: str) -> None:
        """
        更新Docker Compose文件中的镜像版本

        Args:
            version_path: 版本目录路径
            image_name: 镜像名称
            new_version: 新版本号
        """
        compose_file = version_path / 'docker-compose.yml'
        logger.debug(f"docker-compose文件路径: {compose_file}")

        if not compose_file.exists():
            logger.warning(f"Docker Compose文件不存在: {compose_file}")
            return

        # 写入前净化：目标必须仍在应用根目录内，防止路径穿越
        if not compose_file.resolve().is_relative_to(self.apps_root_dir.resolve()):
            raise AppUpdateError(f"Docker Compose路径越界，已拒绝: {compose_file}")

        try:
            content = compose_file.read_text(encoding='utf-8')

            # 查找当前的镜像版本（兼容镜像名被引号包裹的写法，如 image: "foo/bar:1.0"）
            current_image_pattern = rf'(image:\s*["\']?{re.escape(image_name)}:)[\w\.-]+'
            current_match = re.search(current_image_pattern, content)

            if not current_match:
                logger.warning(f"未找到镜像配置: {image_name}")
                return

            current_image = current_match.group(0)
            logger.debug(f"当前镜像配置: {current_image}")

            # 更新版本号
            new_image = f"{current_match.group(1)}{new_version}"
            # print(f'{current_match.group(1)}')
            # print(f'{new_version}')
            updated_content = re.sub(current_image_pattern, new_image, content)

            if content == updated_content:
                logger.warning("镜像版本没有变化")
                return

            # 写入更新后的内容
            compose_file.write_text(updated_content, encoding='utf-8')

            logger.debug(f"✅ 已更新Docker Compose文件: {new_image}")

        except Exception as e:
            raise AppUpdateError(f"更新Docker Compose文件失败: {e}")

    def validate_app_structure(self, app_path: Path) -> List[str]:
        """
        验证应用目录结构

        Args:
            app_path: 应用目录路径

        Returns:
            验证错误列表
        """
        errors = []

        required_files = ['data.yml', 'docker-compose.yml', 'README.md']
        for file_name in required_files:
            if not (app_path / file_name).exists():
                errors.append(f"缺少必需文件: {file_name}")

        # 检查版本目录
        version_dirs = [d for d in app_path.iterdir() if d.is_dir() and d.name != 'latest']
        if not version_dirs:
            errors.append("没有版本目录")

        # 检查latest链接
        latest_link = app_path / 'latest'
        if latest_link.exists() and not latest_link.is_symlink():
            errors.append("'latest' 不是符号链接")

        return errors


class AppManager:
    """应用管理器 - 统一管理应用的生命周期"""

    def __init__(self,
                 config_manager: Optional[ConfigManager] = None,
                 git_repo: Optional[GitRepository] = None,
                 parallel_update: bool = False,
                 max_workers: int = 4):
        """
        初始化应用管理器

        Args:
            config_manager: 配置管理器
            git_repo: Git仓库操作器
            parallel_update: 是否并行更新应用
            max_workers: 最大并行工作数
        """
        self.config_manager = config_manager or get_config_manager()
        self.git_repo = git_repo
        self.parallel_update = parallel_update
        self.max_workers = max_workers

        # 初始化更新器
        project_root = Path(__file__).parent.parent.parent
        apps_dir = project_root / "apps"
        self.app_updater = LocalAppUpdater(str(apps_dir))

        # 版本检查器
        self.version_checker = BatchVersionChecker(delay=2.0)

    def check_all_versions(self) -> Dict[str, Optional[str]]:
        """
        检查所有应用的最新版本

        Returns:
            应用名称到最新版本的映射
        """
        apps = self.config_manager.get_all_apps()

        if not apps:
            logger.warning("没有找到需要检查的应用")
            return {}

        return self.version_checker.check_multiple(apps)

    def get_apps_needing_update(self, version_results: Optional[Dict[str, Optional[str]]] = None) -> List[AppInfo]:
        """
        获取需要更新的应用列表

        Args:
            version_results: 已有的版本检查结果，传入时直接复用，避免重复网络请求

        Returns:
            需要更新的应用信息列表
        """
        logger.info("检查需要更新的应用...")

        apps = self.config_manager.get_all_apps()

        if version_results is None:
            version_results = self.check_all_versions()

        apps_needing_update = []

        for app in apps:
            latest_version = version_results.get(app.name)

            if latest_version and latest_version != app.current_version:
                app.latest_version = latest_version
                apps_needing_update.append(app)

        if apps_needing_update:
            logger.info(f"找到 {len(apps_needing_update)} 个需要更新的应用:")
            for app in apps_needing_update:
                logger.info(f"  - {app.name}: {app.current_version} → {app.latest_version}")
        else:
            logger.info("所有应用都已是最新版本")

        return apps_needing_update

    def update_apps(self, apps: List[AppInfo]) -> List[UpdateResult]:
        """
        更新应用列表

        Args:
            apps: 需要更新的应用列表

        Returns:
            更新结果列表
        """
        if not apps:
            logger.info("没有需要更新的应用")
            return []

        logger.info(f"开始更新 {len(apps)} 个应用")

        if self.parallel_update and len(apps) > 1:
            return self._update_apps_parallel(apps)
        else:
            return self._update_apps_sequential(apps)

    def _update_apps_sequential(self, apps: List[AppInfo]) -> List[UpdateResult]:
        """顺序更新应用"""
        results = []

        progress_logger = logger.create_progress_logger(len(apps), "更新应用")

        for i, app in enumerate(apps):
            progress_logger.update(item_name=app.name)

            result = self.app_updater.update_app(app)
            results.append(result)

            if result.success:
                # 更新配置中的版本号
                try:
                    self.config_manager.update_app_version(app.name, result.new_version)
                except Exception as e:
                    logger.error(f"更新配置失败 {app.name}: {e}")

        progress_logger.finish()

        return results

    def _update_apps_parallel(self, apps: List[AppInfo]) -> List[UpdateResult]:
        """并行更新应用"""
        results = []

        progress_logger = logger.create_progress_logger(len(apps), "更新应用")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_app = {
                executor.submit(self.app_updater.update_app, app): app
                for app in apps
            }

            # 收集结果
            for future in as_completed(future_to_app):
                app = future_to_app[future]
                try:
                    result = future.result()
                    results.append(result)

                    if result.success:
                        # 更新配置中的版本号（这里需要同步访问配置）
                        try:
                            self.config_manager.update_app_version(app.name, result.new_version)
                        except Exception as e:
                            logger.error(f"更新配置失败 {app.name}: {e}")

                except Exception as e:
                    error_result = UpdateResult(
                        success=False,
                        app_name=app.name,
                        old_version=app.current_version,
                        new_version=app.latest_version or app.current_version,
                        message=f"更新过程中发生异常: {e}"
                    )
                    results.append(error_result)

                progress_logger.update(item_name=app.name)

        progress_logger.finish()

        return results

    def commit_and_push(self, commit_message: Optional[str] = None) -> bool:
        """
        提交更改并推送到远程仓库

        Args:
            commit_message: 提交消息

        Returns:
            操作是否成功
        """
        if not commit_message:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            commit_message = f"更新应用版本 - {timestamp}"

        success = True

        # 保存配置文件
        try:
            self.config_manager.save_config()
            logger.info("✅ 配置文件保存成功")
        except Exception as e:
            logger.error(f"❌ 保存配置文件失败: {e}")
            success = False

        # Git提交和推送
        if self.git_repo and success:
            try:
                if self.git_repo.commit_and_push(commit_message):
                    logger.info("✅ Git提交推送成功")
                else:
                    logger.error("❌ Git提交推送失败")
                    success = False
            except Exception as e:
                logger.error(f"❌ Git操作异常: {e}")
                success = False

        return success

    def run_full_update_cycle(self) -> Dict[str, Any]:
        """
        执行完整的更新流程

        Returns:
            更新流程结果统计
        """
        logger.info("=" * 50)
        logger.info("开始应用商店更新流程")
        logger.info("=" * 50)

        start_time = datetime.now()

        try:
            # 1. 检查需要更新的应用
            apps_to_update = self.get_apps_needing_update()

            if not apps_to_update:
                logger.info("没有应用需要更新，流程结束")
                return {
                    'success': True,
                    'total_apps': 0,
                    'updated_apps': 0,
                    'failed_apps': 0,
                    'duration': (datetime.now() - start_time).total_seconds()
                }

            # 2. 更新应用
            update_results = self.update_apps(apps_to_update)

            # 3. 统计更新结果
            successful_updates = [r for r in update_results if r.success]
            failed_updates = [r for r in update_results if not r.success]

            logger.info(f"更新结果统计: 成功 {len(successful_updates)}, 失败 {len(failed_updates)}")

            # 4. 提交和推送（如果有成功更新的应用）
            if successful_updates:
                app_names = [r.app_name for r in successful_updates]
                commit_message = f"更新应用版本: {', '.join(app_names)}"
                self.commit_and_push(commit_message)

            # 5. 返回结果统计
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result = {
                'success': len(failed_updates) == 0,
                'total_apps': len(apps_to_update),
                'updated_apps': len(successful_updates),
                'failed_apps': len(failed_updates),
                'duration': duration,
                'results': update_results
            }

            logger.info("=" * 50)
            logger.info(f"更新流程完成: 耗时 {duration:.2f}秒")
            logger.info(f"总计: {result['total_apps']}, 成功: {result['updated_apps']}, 失败: {result['failed_apps']}")
            logger.info("=" * 50)

            return result

        except Exception as e:
            logger.error(f"更新流程中发生错误: {e}")
            return {
                'success': False,
                'error': str(e),
                'duration': (datetime.now() - start_time).total_seconds()
            }