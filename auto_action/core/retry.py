#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重试机制装饰器
"""

import time
import random
from functools import wraps
from typing import Callable, Type, Tuple, Optional, Any, Union
from .exceptions import AppStoreException
from .logger import get_logger

logger = get_logger()


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    jitter: bool = True,
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟倍数
        exceptions: 需要重试的异常类型
        jitter: 是否添加随机抖动
        on_retry: 重试回调函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        # 最后一次尝试失败
                        logger.error(
                            f"函数 {func.__name__} 在 {max_attempts} 次尝试后失败: {e}"
                        )
                        raise e

                    # 计算延迟时间
                    if jitter:
                        actual_delay = current_delay * (0.5 + random.random() * 0.5)
                    else:
                        actual_delay = current_delay

                    logger.warning(
                        f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}, "
                        f"{actual_delay:.1f}秒后重试"
                    )

                    # 调用重试回调
                    if on_retry:
                        on_retry(e, attempt + 1)

                    time.sleep(actual_delay)
                    current_delay *= backoff

            # 这里不应该到达，但为了类型检查
            raise last_exception

        return wrapper
    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = AppStoreException
):
    """
    熔断器装饰器

    Args:
        failure_threshold: 失败阈值
        recovery_timeout: 恢复超时时间
        expected_exception: 预期的异常类型
    """
    def decorator(func: Callable) -> Callable:
        # 熔断器状态
        failure_count = 0
        last_failure_time = 0
        state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            nonlocal failure_count, last_failure_time, state

            current_time = time.time()

            # 检查熔断器状态
            if state == "OPEN":
                if current_time - last_failure_time >= recovery_timeout:
                    state = "HALF_OPEN"
                    logger.info(f"熔断器 {func.__name__} 进入半开状态")
                else:
                    raise AppStoreException(
                        f"熔断器 {func.__name__} 处于开启状态，拒绝调用"
                    )

            try:
                result = func(*args, **kwargs)

                # 成功调用，重置状态
                if state == "HALF_OPEN":
                    state = "CLOSED"
                    logger.info(f"熔断器 {func.__name__} 恢复到关闭状态")

                failure_count = 0
                return result

            except expected_exception as e:
                failure_count += 1
                last_failure_time = current_time

                logger.warning(
                    f"熔断器 {func.__name__} 记录失败 ({failure_count}/{failure_threshold}): {e}"
                )

                if failure_count >= failure_threshold:
                    state = "OPEN"
                    logger.error(f"熔断器 {func.__name__} 开启，{recovery_timeout}秒后尝试恢复")

                raise e

        return wrapper
    return decorator