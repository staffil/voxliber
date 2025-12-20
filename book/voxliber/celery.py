import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voxliber.settings")

app = Celery("voxliber")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
