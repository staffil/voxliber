from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.conf import settings


# 보이스 테이블
class Voice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="voices")
    voice_name = models.CharField(max_length=190)
    voice_id = models.CharField(max_length=190)  # ElevenLabs voice_id
    sample_url = models.CharField(max_length=190)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "voice"
