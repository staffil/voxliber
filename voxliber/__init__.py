# Celery app을 Django와 함께 시작
from .celery import app as celery_app

__all__ = ("celery_app",)
