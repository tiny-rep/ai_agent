import logging
import time
from uuid import UUID

from celery import shared_task
from flask import current_app


@shared_task
def demo_task(id: UUID) -> str:
    """异步任务测试"""
    logging.info("sleep five second")
    time.sleep(5)
    logging.info(f"id:{id}")
    logging.info(f"配置信息：{current_app.config}")
    return f"id {id} sam"
