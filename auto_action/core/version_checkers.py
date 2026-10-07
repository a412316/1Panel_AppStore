#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本检查器实现
"""

import ipaddress
import re
import time
from abc import ABC
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urljoin, urlparse

import requests
from packaging import version

from .interfaces import VersionChecker, AppInfo
from .exceptions import VersionCheckError, NetworkError
from .logger import get_logger
from .retry import retry, circuit_breaker

logger = get_logger()


class BaseVersionChecker(VersionChecker, ABC):
    """版本检查器基类"""

    def __init__(self, timeout: int = 10, delay: float = 1.0):
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': '1Panel-AppStore/1.0 (Python Version Checker)'
        })

    def _parse_version_tags(self, tags: List[str], exclude_patterns: List[str] = None) -> Optional[str]:
        """
        从标签列表中解析稳定版本

        Args:
            tags: 版本标签列表
            exclude_patterns: 要排除的模式列表

        Returns:
            最新稳定版本号
        """
        if exclude_patterns is None:
            exclude_patterns = ['beta', 'alpha', 'rc', 'pre', 'dev', 'test']

        version_pattern = re.compile(
            r'^v?(\d+\.\d+(?:\.\d+)?[a-z]?(?:-[\w-]+)?(?:\+[\w-]+)?)$',
            re.IGNORECASE
        )

        stable_versions = []

        for tag in tags:
            if not tag or tag == 'latest':
                continue

            if not version_pattern.match(tag):
                continue

            # 检查是否包含排除模式
            tag_lower = tag.lower()
            if any(pattern in tag_lower for pattern in exclude_patterns):
                continue

            # 清理标签
            clean_tag = tag.lstrip('v')
            # 移除构建信息
            base_version = clean_tag.split('+')[0].split('-')[0]

            try:
                # 验证版本格式
                version.parse(base_version)
                stable_versions.append(base_version)
            except version.InvalidVersion:
                continue

        if not stable_versions:
            return None

        # 获取最新版本
        try:
            return max(stable_versions, key=version.parse)
        except version.InvalidVersion:
            return stable_versions[-1]  # 如果解析失败，返回最后一个

    # MinIO风格标签: RELEASE.<构建时间戳>[-变体后缀]
    # 如 RELEASE.2026-09-16T00-00-00Z-distroless、RELEASE.2026-09-03T13-18-01Z
    _MINIO_RELEASE_PATTERN = re.compile(
        r'^RELEASE\.(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)(?:-([\w.-]+))?$'
    )
    _MINIO_RELEASE_TIME_FORMAT = '%Y-%m-%dT%H-%M-%SZ'

    def _parse_minio_release_tags(self, tags: List[str], current_version: str) -> Optional[str]:
        """
        解析MinIO风格RELEASE时间戳标签（silo/MinIO镜像使用）

        只保留与当前版本变体后缀一致的标签（如当前用-distroless就继续
        用-distroless），同时天然排除-amd64/-arm64等架构标签和无后缀
        变体；按标签内的构建时间戳取最新，返回完整tag

        Args:
            tags: 版本标签列表
            current_version: 当前版本（完整tag），用于确定变体后缀

        Returns:
            最新稳定版本的完整tag；无匹配时返回None
        """
        current_match = self._MINIO_RELEASE_PATTERN.match(current_version or '')
        # 变体后缀跟随当前版本；当前版本不是该格式时退回匹配无后缀标签
        current_suffix = current_match.group(2) if current_match else ''

        candidates = []
        for tag in tags:
            m = self._MINIO_RELEASE_PATTERN.match(tag)
            if not m or m.group(2) != current_suffix:
                continue
            try:
                built_at = datetime.strptime(m.group(1), self._MINIO_RELEASE_TIME_FORMAT)
            except ValueError:
                continue
            candidates.append((built_at, tag))

        if not candidates:
            return None

        return max(candidates)[1]

    def _validate_url(self, url: str) -> None:
        """
        校验请求URL安全性

        仅允许 http/https，且拒绝 localhost、环回、私有和保留地址，
        防止配置被篡改后向内网发起请求

        Args:
            url: 待请求的URL

        Raises:
            NetworkError: URL不合法
        """
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise NetworkError(f"不允许的URL协议: {parsed.scheme} ({url})")

        host = (parsed.hostname or '').strip().lower()
        if not host:
            raise NetworkError(f"URL缺少主机名: {url}")
        if host == 'localhost' or host.endswith(('.local', '.internal', '.localhost')):
            raise NetworkError(f"不允许的主机名: {host}")

        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return  # 普通域名

        if any((ip.is_private, ip.is_loopback, ip.is_reserved,
                ip.is_link_local, ip.is_multicast, ip.is_unspecified)):
            raise NetworkError(f"不允许的内网/保留地址: {host}")

    def _make_request(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        发起HTTP请求

        Args:
            url: 请求URL
            params: 请求参数

        Returns:
            响应JSON数据

        Raises:
            NetworkError: 网络请求失败
        """
        self._validate_url(url)
        try:
            response = self.session.get(
                url,
                params=params or {},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise NetworkError(f"请求失败 {url}: {e}")

    def _extract_image_name(self, app_info: AppInfo) -> tuple[str, str]:
        """
        解析镜像名称

        Args:
            app_info: 应用信息

        Returns:
            (namespace, repository) 元组
        """
        image_name = app_info.image
        if '/' in image_name:
            return image_name.split('/', 1)
        return 'library', image_name


class DockerHubVersionChecker(BaseVersionChecker):
    """Docker Hub 版本检查器 - 多数据源fallback，任一源取到稳定版本即停止"""

    # 数据源列表: (源类型, 基础URL)，按优先级排列
    # hub_api:   Docker Hub官方API，支持page_size=100和next翻页
    # registry:  镜像加速站的registry v2接口，一次返回全量tags
    # hubproxy:  自建代理，仅返回第一页20个tags（page>1会404）
    DEFAULT_SOURCES: List[Tuple[str, str]] = [
        ('hub_api', 'https://hub.docker.com/v2/repositories'),
        ('registry', 'https://docker.1ms.run'),
        ('registry', 'https://dockerproxy.net'),
        ('hubproxy', 'https://hubproxy.xiao2026.com/api/tags'),
    ]

    def __init__(self,
                 timeout: int = 10,
                 delay: float = 1.0,
                 sources: Optional[List[Tuple[str, str]]] = None,
                 max_pages: int = 5):
        super().__init__(timeout, delay)
        self.sources = sources or list(self.DEFAULT_SOURCES)
        self.max_pages = max_pages

    @retry(max_attempts=3, delay=1.0)
    @circuit_breaker(failure_threshold=3, recovery_timeout=30.0)
    def check_version(self, app_info: AppInfo) -> Optional[str]:
        """
        检查Docker镜像最新版本

        依次尝试各数据源，某个源返回的tags中能解析出稳定版本即返回；
        某个源失败（网络/无标签/无稳定版本）时自动切换下一个源

        Args:
            app_info: 应用信息

        Returns:
            最新版本号；所有可达的源都没有稳定版本时返回None

        Raises:
            VersionCheckError: 所有数据源均不可达
        """
        if not app_info.image:
            raise VersionCheckError("应用镜像名称为空")

        namespace, repository = self._extract_image_name(app_info)
        logger.debug(f"检查Docker Hub版本: {namespace}/{repository}")

        reached_any = False

        for source_type, base_url in self.sources:
            source_name = f"{source_type}@{base_url}"
            try:
                tags = self._fetch_tags(source_type, base_url, namespace, repository)
            except (NetworkError, ValueError) as e:
                # 网络失败或响应不是合法JSON时切换下一个数据源
                logger.warning(f"数据源不可用({source_name}): {e}")
                continue

            reached_any = True

            if not tags:
                logger.warning(f"数据源未返回标签({source_name}): {namespace}/{repository}")
                continue

            if app_info.tag_scheme == 'minio_release':
                latest_version = self._parse_minio_release_tags(tags, app_info.current_version)
            else:
                latest_version = self._parse_version_tags(tags)
            if latest_version:
                logger.debug(f"Docker Hub最新版本: {namespace}/{repository} -> {latest_version} (源: {source_name})")
                return latest_version

            logger.warning(
                f"数据源未找到稳定版本({source_name}): {namespace}/{repository}，尝试下一个数据源"
            )

        if not reached_any:
            raise VersionCheckError(
                f"Docker Hub版本检查失败: 所有数据源均不可达 {namespace}/{repository}"
            )

        logger.warning(f"Docker Hub未找到有效版本: {namespace}/{repository}")
        return None

    def _fetch_tags(self, source_type: str, base_url: str,
                    namespace: str, repository: str) -> List[str]:
        """从指定数据源拉取tags列表"""
        fetchers = {
            'hub_api': self._fetch_tags_hub_api,
            'registry': self._fetch_tags_registry,
            'hubproxy': self._fetch_tags_hubproxy,
        }
        fetcher = fetchers.get(source_type)
        if fetcher is None:
            raise NetworkError(f"未知数据源类型: {source_type}")
        return fetcher(base_url, namespace, repository)

    def _fetch_tags_hub_api(self, base_url: str, namespace: str, repository: str) -> List[str]:
        """Docker Hub官方API，按页获取，直到没有下一页或达到页数上限"""
        tags = []
        for page in range(1, self.max_pages + 1):
            # 注意: 必须带/tags/后缀，不带时命中的是仓库详情接口(同样返回200但没有results字段)
            data = self._make_request(
                f"{base_url}/{namespace}/{repository}/tags/",
                {'page': page, 'page_size': 100}
            )
            results = [tag.get('name', '') for tag in data.get('results', [])]
            tags.extend(name for name in results if name and name != 'latest')

            # next为null表示已是最后一页
            if not results or not data.get('next'):
                break
        return tags

    def _fetch_tags_registry(self, base_url: str, namespace: str, repository: str) -> List[str]:
        """镜像加速站registry v2接口，一次返回全量tags"""
        url = f"{base_url}/v2/{namespace}/{repository}/tags/list"
        data = self._make_request(url)
        return [
            tag for tag in (data.get('tags') or [])
            if tag and tag != 'latest'
        ]

    def _fetch_tags_hubproxy(self, base_url: str, namespace: str, repository: str) -> List[str]:
        """自建代理接口，仅能获取第一页（page>1返回404，page_size参数不生效）"""
        data = self._make_request(
            f"{base_url}/{namespace}/{repository}",
            {'page': 1, 'page_size': 20}
        )
        return [
            tag.get('name', '') for tag in data.get('tags', [])
            if tag.get('name') and tag['name'] != 'latest'
        ]

    def get_checker_type(self) -> str:
        return "dockerhub"


class GitHubVersionChecker(BaseVersionChecker):
    """GitHub 版本检查器"""

    def __init__(self, api_url: str = "https://hubproxy.xiao2026.com/https://api.github.com", timeout: int = 10, delay: float = 1.0):
        super().__init__(timeout, delay)
        self.api_url = api_url

    @retry(max_attempts=3, delay=1.0)
    @circuit_breaker(failure_threshold=3, recovery_timeout=30.0)
    def check_version(self, app_info: AppInfo) -> Optional[str]:
        """
        检查GitHub仓库最新版本

        Args:
            app_info: 应用信息

        Returns:
            最新版本号
        """
        if not app_info.image:
            raise VersionCheckError("应用仓库名称为空")

        username, repository = self._extract_image_name(app_info)
        url = f"{self.api_url}/repos/{username}/{repository}/releases/latest"

        logger.debug(f"检查GitHub版本: {username}/{repository}")

        try:
            data = self._make_request(url)

            tag_name = data.get('tag_name', '')
            if not tag_name:
                logger.warning(f"GitHub发布无标签: {username}/{repository}")
                return None

            # 清理标签名
            clean_version = tag_name.lstrip('v')

            # 验证版本格式
            try:
                version.parse(clean_version)
                logger.debug(f"GitHub最新版本: {username}/{repository} -> {clean_version}")
                return clean_version
            except version.InvalidVersion:
                logger.warning(f"GitHub无效版本格式: {username}/{repository} -> {tag_name}")
                return None

        except Exception as e:
            logger.error(f"检查GitHub版本失败 {username}/{repository}: {e}")
            raise VersionCheckError(f"GitHub版本检查失败: {e}")

    def get_checker_type(self) -> str:
        return "github"


class VersionCheckerFactory:
    """版本检查器工厂"""

    _checkers = {
        'docker': DockerHubVersionChecker,
        'github': GitHubVersionChecker,
    }

    @classmethod
    def create_checker(cls, checker_type: str, **kwargs) -> VersionChecker:
        """
        创建版本检查器

        Args:
            checker_type: 检查器类型
            **kwargs: 检查器配置参数

        Returns:
            版本检查器实例
        """
        if checker_type not in cls._checkers:
            raise VersionCheckError(f"不支持的检查器类型: {checker_type}")

        checker_class = cls._checkers[checker_type]
        return checker_class(**kwargs)

    @classmethod
    def get_available_types(cls) -> List[str]:
        """获取可用的检查器类型"""
        return list(cls._checkers.keys())

    @classmethod
    def register_checker(cls, checker_type: str, checker_class: type):
        """
        注册自定义检查器

        Args:
            checker_type: 检查器类型名称
            checker_class: 检查器类
        """
        if not issubclass(checker_class, VersionChecker):
            raise VersionCheckError("检查器类必须继承自VersionChecker")

        cls._checkers[checker_type] = checker_class


class BatchVersionChecker:
    """批量版本检查器"""

    def __init__(self, delay: float = 5.0):
        self.delay = delay
        # 按类型缓存检查器实例，使retry/熔断状态在整个运行周期内累积
        self._checkers: Dict[str, VersionChecker] = {}

    def check_multiple(self, apps: List[AppInfo]) -> Dict[str, Optional[str]]:
        """
        批量检查多个应用的版本

        Args:
            apps: 应用列表

        Returns:
            应用名称到最新版本的映射
        """
        results = {}
        failed_apps = []

        logger.info(f"开始批量检查 {len(apps)} 个应用的版本")

        for i, app in enumerate(apps):
            try:
                if app.app_type not in self._checkers:
                    self._checkers[app.app_type] = VersionCheckerFactory.create_checker(app.app_type)
                checker = self._checkers[app.app_type]
                latest_version = checker.check_version(app)
                results[app.name] = latest_version

                status = "需要更新" if latest_version and latest_version != app.current_version else "已是最新"
                logger.info(f"{app.name}: {app.current_version} -> {latest_version or '无更新'} ({status})")

            except Exception as e:
                results[app.name] = None
                failed_apps.append(app.name)
                logger.error(f"检查 {app.name} 版本失败: {e}")

            # 添加延迟避免频率限制
            if i < len(apps) - 1:
                time.sleep(self.delay)

        # 总结
        success_count = len([v for v in results.values() if v is not None])
        logger.info(
            f"批量版本检查完成: 成功 {success_count}/{len(apps)}, "
            f"失败 {len(failed_apps)} 个"
        )

        if failed_apps:
            logger.warning(f"失败的应用: {', '.join(failed_apps)}")

        return results