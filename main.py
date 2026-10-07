#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1Panel应用商店更新工具 - 主入口文件

这个工具用于自动检查和更新1Panel应用商店中的应用版本，
包括从Docker Hub和GitHub获取最新版本，更新本地配置文件，
并提交到Git仓库。
"""

import sys
import os
import argparse
import signal
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from auto_action.core.config_manager import get_config_manager
from auto_action.core.git_repository import EnhancedGitRepository
from auto_action.core.app_manager import AppManager
from auto_action.core.exceptions import AppStoreException
from auto_action.core.logger import get_logger

logger = get_logger("main")


class ApplicationStoreUpdater:
    """应用商店更新器主类"""

    def __init__(self, config_dir: Optional[str] = None, parallel: bool = False):
        """
        初始化更新器

        Args:
            config_dir: 配置目录路径
            parallel: 是否启用并行更新
        """
        self.config_dir = config_dir
        self.parallel_update = parallel
        self._setup_components()

    def _setup_components(self):
        """设置各个组件"""
        try:
            # 配置管理器
            logger.info("初始化配置管理器...")
            self.config_manager = get_config_manager(self.config_dir)

            # 验证配置
            logger.info("验证配置文件...")
            self.config_manager.validate_configs()

            # Git仓库管理器（推送认证依赖运行环境的Git凭据，如SSH密钥）
            logger.info("初始化Git仓库管理器...")
            project_root = Path(__file__).parent
            self.git_repository = EnhancedGitRepository(str(project_root))

            # 应用管理器
            logger.info("初始化应用管理器...")
            self.app_manager = AppManager(
                config_manager=self.config_manager,
                git_repo=self.git_repository,
                parallel_update=self.parallel_update,
                max_workers=4
            )

            logger.info("✅ 所有组件初始化完成")

        except Exception as e:
            logger.error(f"❌ 组件初始化失败: {e}")
            raise AppStoreException(f"组件初始化失败: {e}")

    def run_update(self) -> Dict[str, Any]:
        """
        运行更新流程

        Returns:
            更新结果
        """
        logger.info("🚀 开始执行应用商店更新流程")
        logger.info("=" * 60)

        try:
            # 执行完整的更新流程
            result = self.app_manager.run_full_update_cycle()

            if result.get('success', False):
                logger.info("🎉 应用商店更新流程执行成功!")
            else:
                logger.error("💥 应用商店更新流程执行失败")

            return result

        except KeyboardInterrupt:
            logger.warning("⚠️  用户中断了更新流程")
            return {'success': False, 'error': '用户中断', 'interrupted': True}

        except Exception as e:
            logger.error(f"💥 更新流程中发生未知错误: {e}")
            return {'success': False, 'error': str(e)}

        finally:
            logger.info("=" * 60)
            logger.info("应用商店更新流程结束")

    def check_versions_only(self) -> Dict[str, Any]:
        """
        仅检查版本，不执行更新

        Returns:
            版本检查结果
        """
        logger.info("🔍 仅检查应用版本（不执行更新）")
        logger.info("=" * 40)

        try:
            # 检查所有应用的版本（get_apps_needing_update 复用该结果，避免重复请求）
            version_results = self.app_manager.check_all_versions()

            # 获取需要更新的应用
            apps_to_update = self.app_manager.get_apps_needing_update(version_results)

            result = {
                'success': True,
                'total_apps': len(version_results),
                'apps_need_update': len(apps_to_update),
                'version_results': version_results,
                'apps_to_update': [app.name for app in apps_to_update]
            }

            logger.info(f"版本检查完成: 总计 {result['total_apps']} 个应用，"
                       f"其中 {result['apps_need_update']} 个需要更新")

            if apps_to_update:
                logger.info("需要更新的应用:")
                for app in apps_to_update:
                    logger.info(f"  - {app.name}: {app.current_version} → {app.latest_version}")

            return result

        except Exception as e:
            logger.error(f"版本检查失败: {e}")
            return {'success': False, 'error': str(e)}

        finally:
            logger.info("=" * 40)


def setup_signal_handlers():
    """设置信号处理器"""
    def signal_handler(signum, frame):
        logger.info(f"接收到信号 {signum}，正在安全退出...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="1Panel应用商店自动更新工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py                    # 执行完整更新流程
  python main.py --check-only       # 仅检查版本，不执行更新
  python main.py --parallel         # 启用并行更新
  python main.py --config-dir /path/to/config  # 指定配置目录

配置文件:
  - auto_action/config.json: 应用配置文件
        """
    )

    parser.add_argument(
        '--check-only',
        action='store_true',
        help='仅检查版本，不执行实际更新'
    )

    parser.add_argument(
        '--parallel',
        action='store_true',
        help='启用并行更新（提高多应用更新速度）'
    )

    parser.add_argument(
        '--config-dir',
        type=str,
        help='配置文件目录路径（默认为auto_action目录）'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别（默认INFO）'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='1Panel AppStore Updater v2.0.0'
    )

    return parser.parse_args()


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    # 设置信号处理器
    setup_signal_handlers()

    # 设置日志级别
    logger.logger.setLevel(getattr(logging, args.log_level))

    try:
        # 创建更新器实例
        updater = ApplicationStoreUpdater(
            config_dir=args.config_dir,
            parallel=args.parallel
        )

        # 根据参数执行相应操作
        if args.check_only:
            result = updater.check_versions_only()
        else:
            result = updater.run_update()

        # 根据结果设置退出码
        if result.get('success', False):
            logger.info("🎉 程序执行成功!")
            return 0
        else:
            logger.error("💥 程序执行失败!")
            return 1

    except AppStoreException as e:
        logger.error(f"应用商店更新错误: {e}")
        return 1

    except KeyboardInterrupt:
        logger.info("👋 用户中断程序执行")
        return 130  # 标准的Ctrl+C退出码

    except Exception as e:
        logger.error(f"程序执行过程中发生未知错误: {e}")
        logger.debug("错误详情:", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())