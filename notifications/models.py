from django.db import models
from django.conf import settings


class FCMToken(models.Model):
    DEVICE_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fcm_tokens',
    )
    token = models.CharField(max_length=500, unique=True, verbose_name='FCM 토큰')
    device = models.CharField(max_length=10, choices=DEVICE_CHOICES, default='android')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fcm_token'
        verbose_name = 'FCM 토큰'

    def __str__(self):
        return f'{self.user} [{self.device}]'


class Notification(models.Model):
    TYPE_CHOICES = [
        ('new_episode', '새 에피소드'),
        ('follow', '팔로우'),
        ('comment', '댓글'),
        ('notice', '공지'),
        ('system', '시스템'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200, verbose_name='제목')
    message = models.TextField(verbose_name='내용')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=500, blank=True, verbose_name='이동 경로')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification'
        verbose_name = '알림'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_type_display()}] {self.user} - {self.title}'
