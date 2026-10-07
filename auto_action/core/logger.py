#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志系统
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'

    def format(self, record):
        # 只有在支持颜色的终端才使用颜色
        if sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, '')
            record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class EnhancedLogger:
    """增强的日志管理器"""

    def __init__(self, name: str = "appstore", log_dir: Optional[Path] = None):
        self.name = name
        self.logger = logging.getLogger(name)

        # 防止重复添加handler
        if self.logger.handlers:
            return

        # 设置日志级别
        self.logger.setLevel(logging.INFO)

        # 确定日志目录
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs"

        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{name}.log"

        # 创建格式化器
        detailed_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = ColoredFormatter(
            '%(asctime)s [%(levelname)s]: %(message)s',
            datefmt='%H:%M:%S'
        )

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)

        # 文件处理器（带轮转）
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(detailed_formatter)
        file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)

    def debug(self, message: str, **kwargs):
        """调试日志"""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """信息日志"""
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """警告日志"""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """错误日志"""
        self._log_with_context(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """严重错误日志"""
        self._log_with_context(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        """异常日志（包含堆栈跟踪）"""
        self._log_with_context(logging.ERROR, message, exc_info=True, **kwargs)

    def _log_with_context(self, level: int, message: str, **kwargs):
        """带上下文的日志记录"""
        # 添加额外的上下文信息
        extra_info = []

        if 'app_name' in kwargs:
            extra_info.append(f"App:{kwargs['app_name']}")

        if 'operation' in kwargs:
            extra_info.append(f"Op:{kwargs['operation']}")

        if 'duration' in kwargs:
            extra_info.append(f"Duration:{kwargs['duration']:.2f}s")

        # 构建完整的消息
        if extra_info:
            full_message = f"[{' '.join(extra_info)}] {message}"
        else:
            full_message = message

        # 记录日志
        exc_info = kwargs.get('exc_info', False)
        self.logger.log(level, full_message, exc_info=exc_info)

    def log_operation_start(self, operation: str, details: str = ""):
        """记录操作开始"""
        message = f"开始{operation}"
        if details:
            message += f": {details}"
        self.info(message, operation=operation)

    def log_operation_success(self, operation: str, details: str = "", duration: float = None):
        """记录操作成功"""
        message = f"成功{operation}"
        if details:
            message += f": {details}"

        log_kwargs = {'operation': operation}
        if duration is not None:
            log_kwargs['duration'] = duration

        self.info(message, **log_kwargs)

    def log_operation_failure(self, operation: str, error: str, duration: float = None):
        """记录操作失败"""
        message = f"失败{operation}: {error}"

        log_kwargs = {'operation': operation}
        if duration is not None:
            log_kwargs['duration'] = duration

        self.error(message, **log_kwargs)

    def log_app_update(self, app_name: str, old_version: str, new_version: str, success: bool):
        """记录应用更新"""
        status = "✅" if success else "❌"
        message = f"{status} {app_name}: {old_version} → {new_version}"

        if success:
            self.info(message, app_name=app_name, operation="update")
        else:
            self.error(message, app_name=app_name, operation="update")

    def create_progress_logger(self, total: int, operation: str = "处理"):
        """创建进度日志器"""
        return ProgressLogger(self.logger, total, operation)


class ProgressLogger:
    """进度日志器"""

    def __init__(self, logger: logging.Logger, total: int, operation: str = "处理"):
        self.logger = logger
        self.total = total
        self.operation = operation
        self.current = 0
        self.start_time = datetime.now()

    def update(self, increment: int = 1, item_name: str = ""):
        """更新进度"""
        self.current += increment
        percentage = (self.current / self.total) * 100

        elapsed = datetime.now() - self.start_time
        if self.current > 0:
            eta = elapsed * (self.total - self.current) / self.current
            eta_str = f", ETA: {eta.total_seconds():.1f}s"
        else:
            eta_str = ""

        message = f"{self.operation}进度: {self.current}/{self.total} ({percentage:.1f}%){eta_str}"
        if item_name:
            message += f" - {item_name}"

        self.logger.info(message)

    def finish(self):
        """完成进度"""
        elapsed = datetime.now() - self.start_time
        self.logger.info(
            f"{self.operation}完成! 总计: {self.total}, 耗时: {elapsed.total_seconds():.2f}s"
        )


# 全局日志器实例
_global_logger: Optional[EnhancedLogger] = None


def get_logger(name: str = "appstore") -> EnhancedLogger:
    """获取全局日志器实例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = EnhancedLogger(name)
    return _global_logger


# 为了向后兼容，保留原来的logger变量
logger = get_logger().logger