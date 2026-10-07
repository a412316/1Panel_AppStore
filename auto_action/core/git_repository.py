#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git仓库操作实现
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from git import Repo, InvalidGitRepositoryError, GitCommandError
from git.exc import GitError

from .interfaces import GitRepository
from .exceptions import GitOperationError
from .logger import get_logger
from .retry import retry

logger = get_logger()


class EnhancedGitRepository(GitRepository):
    """增强的Git仓库操作实现"""

    def __init__(self, repo_path: str, git_config: Optional[Dict[str, str]] = None):
        """
        初始化Git仓库

        Args:
            repo_path: 仓库路径
            git_config: Git配置（用户名、邮箱等）
        """
        self.repo_path = Path(repo_path).absolute()
        self.git_config = git_config or {}
        self._repo: Optional[Repo] = None

        self._validate_repo()

    def _validate_repo(self) -> None:
        """验证仓库有效性"""
        if not self.repo_path.exists():
            raise GitOperationError(f"仓库路径不存在: {self.repo_path}")

        try:
            self._repo = Repo(self.repo_path)
        except InvalidGitRepositoryError:
            raise GitOperationError(f"路径不是Git仓库: {self.repo_path}")

    def _ensure_git_config(self) -> None:
        """确保Git配置已设置"""
        if not self._repo:
            raise GitOperationError("仓库未初始化")

        # 设置用户名
        if 'username' in self.git_config:
            try:
                self._repo.config_writer().set_value("user", "name", self.git_config['username'])
            except GitError as e:
                logger.warning(f"设置Git用户名失败: {e}")

        # 设置邮箱
        if 'email' in self.git_config:
            try:
                self._repo.config_writer().set_value("user", "email", self.git_config['email'])
            except GitError as e:
                logger.warning(f"设置Git邮箱失败: {e}")

    def _configure_credentials(self) -> None:
        """配置Git认证信息"""
        if not self._repo:
            return

        # 设置密码（用于HTTPS认证）
        if 'password' in self.git_config:
            try:
                self._repo.config_writer().set_value("user", "password", self.git_config['password'])
            except GitError as e:
                logger.warning(f"设置Git密码失败: {e}")

    @retry(max_attempts=3, delay=1.0)
    def commit_and_push(self, message: str) -> bool:
        """
        提交并推送更改

        Args:
            message: 提交消息

        Returns:
            操作是否成功
        """
        if not self._repo:
            raise GitOperationError("仓库未初始化")

        if not message:
            message = f"自动提交 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        logger.info(f"开始提交并推送更改: {message}")

        try:
            # 配置Git用户信息
            # self._ensure_git_config()
            # self._configure_credentials()

            # 检查是否有更改
            if not self.has_changes():
                logger.info("没有需要提交的更改")
                return True

            # 添加所有更改
            self._repo.git.add('--all')
            logger.debug("已添加所有更改到暂存区")

            # 提交更改
            commit_result = self._repo.index.commit(message)
            logger.debug(f"提交成功: {commit_result.hexsha[:8]}")

            # 推送到远程仓库
            if 'origin' in [remote.name for remote in self._repo.remotes]:
                origin = self._repo.remote('origin')

                # # 配置认证URL（如果提供了密码）
                # if 'username' in self.git_config and 'password' in self.git_config:
                #     username = self.git_config['username']
                #     password = self.git_config['password']
                #     for url in origin.urls:
                #         if 'https://' in url:
                #             auth_url = url.replace(
                #                 'https://',
                #                 f"https://{username}:{password}@"
                #             )
                #             print(auth_url)
                #             origin.set_url(auth_url)
                #             break

                push_result = origin.push()
                for push_info in push_result:
                    if push_info.flags & push_info.ERROR:
                        raise GitOperationError(f"推送失败: {push_info.summary}")

                logger.info(f"推送成功: {push_result[0].summary}")
            else:
                logger.warning("没有找到origin远程仓库，跳过推送")

            return True

        except GitCommandError as e:
            logger.error(f"Git操作失败: {e}")
            return False
        except Exception as e:
            logger.error(f"提交推送过程中发生错误: {e}")
            raise GitOperationError(f"提交推送失败: {e}")

    @retry(max_attempts=3, delay=1.0)
    def pull_and_reset(self) -> bool:
        """
        拉取并重置到远程最新状态

        Returns:
            操作是否成功
        """
        if not self._repo:
            raise GitOperationError("仓库未初始化")

        logger.info("开始拉取并重置到远程最新状态")

        try:
            # 配置认证信息
            self._configure_credentials()

            # 获取远程更新
            origin = self._repo.remote('origin')
            origin.fetch()
            logger.debug("已获取远程更新")

            # 检查是否有未提交的更改
            if self._repo.is_dirty(untracked_files=True):
                logger.info("检测到本地更改，正在丢弃...")

                # 丢弃所有未提交的更改
                self._repo.git.reset('--hard', 'HEAD')

                # 清除所有未跟踪的文件
                self._repo.git.clean('-fd')

                logger.info("已成功丢弃所有本地更改")

            # 重置到远程分支最新状态
            remote_head = origin.refs[0].name  # 通常是origin/HEAD或origin/main
            self._repo.git.reset('--hard', remote_head)

            logger.info("已成功重置到远程最新状态")
            return True

        except GitCommandError as e:
            logger.error(f"Git拉取操作失败: {e}")
            return False
        except Exception as e:
            logger.error(f"拉取重置过程中发生错误: {e}")
            raise GitOperationError(f"拉取重置失败: {e}")

    def has_changes(self) -> bool:
        """检查是否有未提交的更改"""
        if not self._repo:
            raise GitOperationError("仓库未初始化")

        try:
            # 检查是否有修改的文件
            if self._repo.is_dirty():
                return True

            # 检查是否有未跟踪的文件
            if self._repo.untracked_files:
                return True

            # 检查暂存区是否有内容
            if self._repo.index.diff("HEAD"):
                return True

            return False

        except Exception as e:
            logger.error(f"检查更改状态失败: {e}")
            return False

    def get_changed_files(self) -> List[str]:
        """获取已更改的文件列表"""
        if not self._repo:
            raise GitOperationError("仓库未初始化")

        try:
            changed_files = []

            # 获取修改的文件
            for item in self._repo.index.diff(None):
                changed_files.append(item.a_path)

            # 获取未跟踪的文件
            changed_files.extend(self._repo.untracked_files)

            return changed_files

        except Exception as e:
            logger.error(f"获取更改文件列表失败: {e}")
            return []

    def create_backup(self, backup_dir: Optional[str] = None) -> str:
        """
        创建当前状态的备份

        Args:
            backup_dir: 备份目录，如果为None则使用临时目录

        Returns:
            备份路径
        """
        if not backup_dir:
            backup_dir = tempfile.mkdtemp(prefix="git_backup_")

        backup_path = Path(backup_dir) / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            logger.info(f"创建备份到: {backup_path}")

            # 使用git archive创建备份（仅包括已跟踪的文件）
            backup_path.mkdir(parents=True, exist_ok=True)

            # 获取当前HEAD的提交哈希
            head_commit = self._repo.head.commit.hexsha[:8]

            # 使用git worktree创建工作树备份
            self._repo.git.worktree('add', str(backup_path), head_commit)

            logger.info(f"备份创建成功: {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            # 清理失败的备份目录
            if backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            raise GitOperationError(f"创建备份失败: {e}")

    def restore_backup(self, backup_path: str) -> bool:
        """
        从备份恢复

        Args:
            backup_path: 备份路径

        Returns:
            恢复是否成功
        """
        try:
            logger.info(f"从备份恢复: {backup_path}")

            backup_path = Path(backup_path)
            if not backup_path.exists():
                raise GitOperationError(f"备份路径不存在: {backup_path}")

            # 删除当前worktree
            self._repo.git.worktree('remove', str(backup_path))

            logger.info("备份恢复成功")
            return True

        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False

    def get_repo_status(self) -> Dict[str, Any]:
        """获取仓库状态信息"""
        if not self._repo:
            raise GitOperationError("仓库未初始化")

        try:
            status = {
                'is_dirty': self._repo.is_dirty(),
                'untracked_files': self._repo.untracked_files,
                'branch': self._repo.active_branch.name,
                'head_commit': self._repo.head.commit.hexsha[:8] if self._repo.head.is_valid() else None,
                'remotes': [remote.name for remote in self._repo.remotes],
                'changed_files': self.get_changed_files()
            }

            return status

        except Exception as e:
            logger.error(f"获取仓库状态失败: {e}")
            return {}