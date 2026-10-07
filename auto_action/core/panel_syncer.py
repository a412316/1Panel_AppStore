#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1Panel面板同步器实现
"""

import hashlib
import json
import time
import uuid
from typing import Dict, Any, Optional
from time import sleep

import requests

from .interfaces import PanelSyncer
from .config_manager import PanelConfig
from .exceptions import SyncError, NetworkError
from .logger import get_logger
from .retry import retry

logger = get_logger()


class Panel1PSyncer(PanelSyncer):
    """1Panel面板同步器实现"""

    def __init__(self, panel_config: PanelConfig,
                 sync_task_name: str = '同步本地应用',
                 post_run_delay: float = 10.0,
                 final_delay: float = 5.0):
        """
        Args:
            panel_config: 面板配置
            sync_task_name: 面板上用于触发同步的计划任务名称
            post_run_delay: 计划任务执行后的等待秒数
            final_delay: 触发本地同步后的等待秒数
        """
        self.panel_config = panel_config
        self.sync_task_name = sync_task_name
        self.post_run_delay = post_run_delay
        self.final_delay = final_delay
        self.base_url = self._build_base_url()
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': '1Panel-AppStore-Syncer/1.0'
        })

    def _build_base_url(self) -> str:
        """构建基础URL"""
        if self.panel_config.connection_type == 'https':
            return f"https://{self.panel_config.host}:{self.panel_config.port}/api/v2"
        else:
            return f"http://{self.panel_config.host}:{self.panel_config.port}/api/v2"

    def _generate_auth_headers(self) -> Dict[str, str]:
        """
        生成1Panel认证头部

        Returns:
            认证头部字典
        """
        if not self.panel_config.panel_token:
            raise SyncError("面板认证令牌为空")

        # 当前时间戳
        timestamp = str(int(time.time()))

        # 1Panel认证令牌格式: 1panel + token + timestamp
        token_data = f'1panel{self.panel_config.panel_token}{timestamp}'

        # 计算MD5
        md5_hash = hashlib.md5()
        md5_hash.update(token_data.encode('utf-8'))
        token = md5_hash.hexdigest()

        return {
            '1Panel-Token': token,
            '1Panel-Timestamp': timestamp
        }

    @retry(max_attempts=3, delay=2.0)
    def _make_request(self, endpoint: str, data: Dict[str, Any] = None, method: str = 'POST') -> Dict[str, Any]:
        """
        发起API请求

        Args:
            endpoint: API端点
            data: 请求数据
            method: HTTP方法

        Returns:
            响应数据

        Raises:
            NetworkError: 网络请求失败
            SyncError: 同步操作失败
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._generate_auth_headers()

        try:
            if method.upper() == 'GET':
                response = self.session.get(url, headers=headers, params=data)
            else:
                response = self.session.post(url, headers=headers, json=data)

            response.raise_for_status()

            result = response.json()
            if result.get('code') != 200:
                raise SyncError(f"API返回错误: {result.get('message', '未知错误')}")

            return result

        except requests.RequestException as e:
            raise NetworkError(f"请求失败 {url}: {e}")

    def sync_apps(self) -> bool:
        """
        同步应用到面板

        Returns:
            操作是否成功
        """
        logger.info(f"开始同步应用到1Panel面板: {self.panel_config.host}:{self.panel_config.port}")

        try:
            # 1. 查找同步本地应用计划任务
            cron_task_id = self._find_sync_cron_job()
            if not cron_task_id:
                logger.error(f"未找到'{self.sync_task_name}'计划任务")
                return False

            logger.info(f"找到同步计划任务: {cron_task_id}")

            # 2. 执行计划任务
            if not self._run_cron_job(cron_task_id):
                logger.error("执行同步计划任务失败")
                return False

            logger.info("计划任务执行成功")

            # 延迟，等待计划任务完成
            sleep(self.post_run_delay)

            # 3. 触发本地应用同步
            if not self._trigger_local_sync():
                logger.error("触发本地应用同步失败")
                return False

            logger.info("✅ 本地应用同步成功")

            # 延迟
            sleep(self.final_delay)
            return True

        except Exception as e:
            logger.error(f"同步应用失败: {e}")
            return False

    def _find_sync_cron_job(self) -> Optional[str]:
        """
        查找同步本地应用的计划任务

        Returns:
            任务ID，如果未找到返回None
        """
        try:
            data = {
                "order": "null",
                "orderBy": "createdAt",
                "page": 1,
                "pageSize": 20
            }

            result = self._make_request('/cronjobs/search', data)
            items = result.get('data', {}).get('items', [])

            for item in items:
                if item.get('name') == self.sync_task_name:
                    logger.debug(f"找到同步计划任务: {item}")
                    return item.get('id')

            logger.warning(f"未找到名为'{self.sync_task_name}'的计划任务")
            return None

        except Exception as e:
            logger.error(f"查找计划任务失败: {e}")
            return None

    def _run_cron_job(self, task_id: str) -> bool:
        """
        运行计划任务

        Args:
            task_id: 任务ID

        Returns:
            操作是否成功
        """
        try:
            data = {"id": task_id}
            result = self._make_request('/cronjobs/handle', data)

            if result.get('code') == 200:
                logger.debug(f"计划任务 {task_id} 执行成功")
                return True
            else:
                logger.error(f"计划任务执行失败: {result.get('message')}")
                return False

        except Exception as e:
            logger.error(f"执行计划任务失败: {e}")
            return False

    def _trigger_local_sync(self) -> bool:
        """
        触发本地应用同步

        Returns:
            操作是否成功
        """
        try:
            data = {
                "taskID": str(uuid.uuid1())
            }

            result = self._make_request('/apps/sync/local', data)

            if result.get('code') == 200:
                logger.debug("本地应用同步触发成功")
                return True
            else:
                logger.error(f"本地应用同步触发失败: {result.get('message')}")
                return False

        except Exception as e:
            logger.error(f"触发本地应用同步失败: {e}")
            return False

    def get_panel_status(self) -> Dict[str, Any]:
        """
        获取面板状态信息

        Returns:
            面板状态信息
        """
        try:
            # 尝试访问一个简单的端点来检查连接状态
            result = self._make_request('/system/info', method='GET')
            return {
                'connected': True,
                'version': result.get('data', {}).get('version', 'unknown'),
                'host': self.panel_config.host,
                'port': self.panel_config.port
            }

        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'host': self.panel_config.host,
                'port': self.panel_config.port
            }


class MultiPanelSyncer:
    """多面板同步器"""

    def __init__(self, panel_configs: Dict[str, PanelConfig]):
        """
        初始化多面板同步器

        Args:
            panel_configs: 面板名称到配置的映射
        """
        self.syncers = {
            name: Panel1PSyncer(config)
            for name, config in panel_configs.items()
        }

    def sync_all_panels(self) -> Dict[str, bool]:
        """
        同步所有面板

        Returns:
            面板名称到同步结果的映射
        """
        logger.info(f"开始同步 {len(self.syncers)} 个面板")

        results = {}

        for name, syncer in self.syncers.items():
            logger.info(f"同步面板: {name}")

            try:
                success = syncer.sync_apps()
                results[name] = success

                if success:
                    logger.info(f"✅ 面板 {name} 同步成功")
                else:
                    logger.error(f"❌ 面板 {name} 同步失败")

            except Exception as e:
                logger.error(f"❌ 面板 {name} 同步异常: {e}")
                results[name] = False

        successful_count = sum(1 for success in results.values() if success)
        logger.info(f"多面板同步完成: 成功 {successful_count}/{len(results)}")

        return results

    def get_all_panel_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有面板状态

        Returns:
            面板状态信息
        """
        status = {}

        for name, syncer in self.syncers.items():
            try:
                status[name] = syncer.get_panel_status()
            except Exception as e:
                status[name] = {
                    'connected': False,
                    'error': str(e)
                }

        return status