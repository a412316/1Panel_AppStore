#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1Panel应用商店更新工具测试脚本

验证核心模块（配置管理、版本检查、应用更新等）是否正常工作。
运行: python tests/test_refactored.py
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """测试核心模块导入"""
    print("🔍 测试模块导入...")

    try:
        from auto_action.core import (
            get_config_manager,
            get_logger,
            AppManager,
            EnhancedConfigManager,
            EnhancedGitRepository,
            AppInfo,
            VersionCheckerFactory,
            DockerHubVersionChecker,
            GitHubVersionChecker
        )
        print("✅ 核心模块导入成功")
        return True

    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def test_config_manager():
    """测试配置管理器"""
    print("\n🔍 测试配置管理器...")

    try:
        from auto_action.core import get_config_manager

        config_manager = get_config_manager()

        # 测试应用配置
        apps_config = config_manager.get_apps_config()
        print(f"✅ 获取应用配置成功，共 {len(apps_config)} 个应用")

        # 测试单个应用信息
        first_app_name = list(apps_config.keys())[0] if apps_config else None
        if first_app_name:
            app_info = config_manager.get_app_info(first_app_name)
            if app_info:
                print(f"✅ 获取应用信息成功: {app_info.name} - {app_info.image}")
            else:
                print(f"⚠️  应用信息为空: {first_app_name}")

        # 测试所有应用列表
        all_apps = config_manager.get_all_apps()
        print(f"✅ 获取所有应用列表成功，共 {len(all_apps)} 个应用")

        return True

    except Exception as e:
        print(f"❌ 配置管理器测试失败: {e}")
        return False


def test_version_checker():
    """测试版本检查器"""
    print("\n🔍 测试版本检查器...")

    try:
        from auto_action.core import VersionCheckerFactory, AppInfo

        # 测试Docker Hub检查器
        docker_checker = VersionCheckerFactory.create_checker('docker')
        print("✅ Docker Hub版本检查器创建成功")

        # 测试GitHub检查器
        github_checker = VersionCheckerFactory.create_checker('github')
        print("✅ GitHub版本检查器创建成功")

        # 测试批量检查器复用实例（熔断状态在整个运行周期累积）
        from auto_action.core import BatchVersionChecker
        batch = BatchVersionChecker()
        batch._checkers['docker'] = docker_checker
        assert 'docker' in batch._checkers, "批量检查器应缓存实例"
        print("✅ 批量检查器实例复用正常")

        return True

    except Exception as e:
        print(f"❌ 版本检查器测试失败: {e}")
        return False


def test_minio_release_tag_parsing():
    """测试MinIO风格RELEASE时间戳标签解析（silo）"""
    print("\n🔍 测试MinIO风格标签解析...")

    try:
        from auto_action.core import DockerHubVersionChecker, EnhancedConfigManager

        checker = DockerHubVersionChecker()

        # pgsty/silo 在 Docker Hub 上的真实标签（2026-10抽样）
        tags = [
            'latest', 'distroless', 'distroless-arm64', 'distroless-amd64',
            'latest-arm64', 'latest-amd64',
            'RELEASE.2026-09-16T00-00-00Z-distroless', 'RELEASE.2026-09-16T00-00-00Z',
            'RELEASE.2026-09-16T00-00-00Z-distroless-arm64', 'RELEASE.2026-09-16T00-00-00Z-distroless-amd64',
            'RELEASE.2026-09-16T00-00-00Z-arm64', 'RELEASE.2026-09-16T00-00-00Z-amd64',
            'RELEASE.2026-09-03T13-18-01Z-distroless', 'RELEASE.2026-09-03T13-18-01Z',
            'RELEASE.2026-09-03T13-18-01Z-distroless-arm64', 'RELEASE.2026-09-03T13-18-01Z-distroless-amd64',
            'RELEASE.2026-09-03T13-18-01Z-arm64', 'RELEASE.2026-09-03T13-18-01Z-amd64',
            'RELEASE.2026-08-06T00-00-00Z-distroless', 'RELEASE.2026-08-06T00-00-00Z',
        ]

        # distroless变体：选中最新的distroless标签，排除架构标签/无后缀变体/旧版本
        result = checker._parse_minio_release_tags(tags, 'RELEASE.2026-09-03T13-18-01Z-distroless')
        assert result == 'RELEASE.2026-09-16T00-00-00Z-distroless', f"distroless变体解析错误: {result}"

        # 无后缀变体
        result = checker._parse_minio_release_tags(tags, 'RELEASE.2026-09-03T13-18-01Z')
        assert result == 'RELEASE.2026-09-16T00-00-00Z', f"无后缀变体解析错误: {result}"

        # 当前版本已是最新
        result = checker._parse_minio_release_tags(tags, 'RELEASE.2026-09-16T00-00-00Z-distroless')
        assert result == 'RELEASE.2026-09-16T00-00-00Z-distroless', f"已是最新时解析错误: {result}"

        # 无匹配标签时返回None
        assert checker._parse_minio_release_tags(['latest', 'v1.0.0'], 'RELEASE.2026-09-03T13-18-01Z-distroless') is None

        # 配置中silo已启用该方案且字段能透传到AppInfo
        core_dir = Path(__file__).parent.parent / "auto_action" / "core"
        app_info = EnhancedConfigManager(core_dir).get_app_info('silo')
        assert app_info is not None and app_info.tag_scheme == 'minio_release', "silo的tag_scheme配置未生效"

        print("✅ MinIO风格标签解析测试通过")
        return True

    except Exception as e:
        print(f"❌ MinIO风格标签解析测试失败: {e}")
        return False


def test_logger():
    """测试日志系统"""
    print("\n🔍 测试日志系统...")

    try:
        from auto_action.core import get_logger

        logger = get_logger("test")

        # 测试不同级别的日志
        logger.info("测试信息日志")
        logger.warning("测试警告日志")
        logger.error("测试错误日志")

        print("✅ 日志系统测试成功")
        return True

    except Exception as e:
        print(f"❌ 日志系统测试失败: {e}")
        return False


def test_app_manager():
    """测试应用管理器"""
    print("\n🔍 测试应用管理器...")

    try:
        from auto_action.core import AppManager

        # 创建应用管理器实例
        app_manager = AppManager()
        print("✅ 应用管理器创建成功")

        # 测试获取应用列表
        apps = app_manager.config_manager.get_all_apps()
        print(f"✅ 获取应用列表成功，共 {len(apps)} 个应用")

        return True

    except Exception as e:
        print(f"❌ 应用管理器测试失败: {e}")
        return False


def test_main_entry():
    """测试main.py主入口"""
    print("\n🔍 测试main.py主入口...")

    try:
        from main import ApplicationStoreUpdater

        print("✅ ApplicationStoreUpdater导入成功")
        return True

    except Exception as e:
        print(f"❌ main.py主入口测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 1Panel应用商店功能测试")
    print("=" * 60)

    tests = [
        ("模块导入", test_imports),
        ("配置管理器", test_config_manager),
        ("版本检查器", test_version_checker),
        ("MinIO风格标签解析", test_minio_release_tag_parsing),
        ("日志系统", test_logger),
        ("应用管理器", test_app_manager),
        ("main.py主入口", test_main_entry),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n--- 执行测试: {test_name} ---")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")

    print("\n" + "=" * 60)
    print(f"🧪 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！")
        return 0
    else:
        print("💥 部分测试失败，需要检查代码")
        return 1


if __name__ == "__main__":
    sys.exit(main())
