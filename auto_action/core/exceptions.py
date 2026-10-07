#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义异常类定义
"""


class AppStoreException(Exception):
    """应用商店基础异常类"""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(AppStoreException):
    """配置错误异常"""
    pass


class VersionCheckError(AppStoreException):
    """版本检查错误异常"""
    pass


class AppUpdateError(AppStoreException):
    """应用更新错误异常"""
    pass


class GitOperationError(AppStoreException):
    """Git操作错误异常"""
    pass


class SyncError(AppStoreException):
    """同步错误异常"""
    pass


class NetworkError(AppStoreException):
    """网络请求错误异常"""
    pass


class ValidationError(AppStoreException):
    """数据验证错误异常"""
    pass