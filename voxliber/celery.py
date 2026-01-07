import os
from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voxliber.settings")

# Redis를 broker로 명시적으로 지정
app = Celery(
    "voxliber",
    broker="redis://127.0.0.1:6379/0"
)

# settings.py에서 CELERY 설정 불러오기 (backend 포함)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Django 앱에서 task를 자동으로 찾기
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# book.task 모듈을 명시적으로 import (파일 이름이 task.py라서)
app.autodiscover_tasks(['book'], related_name='task')
