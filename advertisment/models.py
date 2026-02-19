from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.conf import settings
import uuid
from character.models import Story


# Create your models here.
# 광고 테이블 수정
class Advertisement(models.Model):
    PLACEMENT_CHOICES = [
        ('episode', '에피소드 중간'),
        ('chat', 'AI 채팅'),
        ('tts', 'TTS'),
        ('snap', '북스냅'),
    ]
    AD_TYPE_CHOICES = [
        ('audio', '오디오 광고'),    # 에피소드용
        ('image', '이미지 광고'),    # AI 채팅 / TTS용
        ('video', '영상 광고'),      # 스냅용
    ]

    # 광고 위치 + 타입 조합 규칙
    # episode  → audio  only
    # chat/tts → image  only
    # snap     → video  only
    public_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    title = models.CharField(max_length=200, verbose_name="광고 제목")
    ad_type = models.CharField(max_length=10, choices=AD_TYPE_CHOICES)
    placement = models.CharField(max_length=20, choices=PLACEMENT_CHOICES)

    # 미디어 (ad_type에 따라 하나만 채워짐)
    image = models.ImageField(upload_to='uploads/ads/images/', null=True, blank=True)
    audio = models.FileField(upload_to='uploads/ads/audio/', null=True, blank=True)
    video = models.FileField(upload_to='uploads/ads/videos/', null=True, blank=True)
    thumbnail = models.ImageField(upload_to='uploads/ads/thumbnails/', null=True, blank=True)  # 영상 썸네일

    link_url = models.URLField(null=True, blank=True, verbose_name="클릭 시 이동 URL")
    duration_seconds = models.IntegerField(default=0, verbose_name="광고 길이(초) - 오디오/영상용")

    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'advertisement'
        verbose_name = '광고'

    def __str__(self):
        return f"[{self.get_placement_display()}] [{self.get_ad_type_display()}] {self.title}"

    def clean(self):
        """위치-타입 조합 유효성 검사"""
        from django.core.exceptions import ValidationError
        rules = {
            'episode': 'audio',
            'chat': 'image',
            'tts': 'image',
            'snap': 'video',
        }
        expected = rules.get(self.placement)
        if expected and self.ad_type != expected:
            raise ValidationError(
                f"{self.get_placement_display()} 위치에는 {expected} 타입만 허용됩니다."
            )


# 광고 노출 / 클릭 기록
class AdImpression(models.Model):
    ad = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='impressions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    placement = models.CharField(max_length=20)
    is_clicked = models.BooleanField(default=False)
    is_skipped = models.BooleanField(default=False, verbose_name="스킵 여부 - 영상광고용")
    watched_seconds = models.IntegerField(default=0, verbose_name="시청 시간(초) - 영상/오디오용")
    clicked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'ad_impression'
        verbose_name = '광고 노출 기록'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ad.title} - {self.user} ({'클릭' if self.is_clicked else '노출'})"


# 유저별 광고 카운터
class UserAdCounter(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ad_counter'
    )
    chat_message_count = models.IntegerField(default=0)   # % 5  → 이미지 광고
    tts_count = models.IntegerField(default=0)            # % 2  → 이미지 광고
    episode_play_count = models.IntegerField(default=0)   # % 3  → 오디오 광고
    snap_view_count = models.IntegerField(default=0)      # 랜덤 → 영상 광고
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_ad_counter'
        verbose_name = '유저 광고 카운터'

    def should_show_ad(self, placement: str) -> bool:
        import random
        if placement == 'snap':
            return random.random() < 0.2  # 20% 확률
        rules = {
            'chat': (self.chat_message_count, 5),
            'tts': (self.tts_count, 2),
            'episode': (self.episode_play_count, 3),
        }
        count, threshold = rules.get(placement, (0, 999))
        return count > 0 and count % threshold == 0


# 구독제 (미리 만들어두기)
class Subscription(models.Model):
    PLAN_CHOICES = [
        ('monthly', '월간 구독'),
        ('yearly', '연간 구독'),
    ]
    STATUS_CHOICES = [
        ('active', '구독 중'),
        ('expired', '만료'),
        ('cancelled', '해지'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default='monthly')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subscription'
        verbose_name = '구독 정보'

    def __str__(self):
        return f"{self.user} - {self.get_plan_display()} ({self.get_status_display()})"

    @property
    def is_active(self) -> bool:
        return self.status == 'active' and self.expires_at > timezone.now()
    





class AdRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', '검토중'),
        ('approved', '승인'),
        ('rejected', '거절'),
        ('completed', '종료'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ad_requests',
        verbose_name="신청자"
    )
    # 광고주 정보
    company_name = models.CharField(max_length=200, verbose_name="회사명")
    contact_name = models.CharField(max_length=100, verbose_name="담당자명")
    email = models.EmailField(verbose_name="이메일")
    phone = models.CharField(max_length=50, blank=True, null=True, verbose_name="연락처")

    # 광고 정보
    title = models.CharField(max_length=200, verbose_name="광고 제목")
    description = models.TextField(blank=True, null=True, verbose_name="광고 설명")

    placement = models.CharField(
        max_length=20,
        choices=Advertisement.PLACEMENT_CHOICES,
        verbose_name="희망 광고 위치"
    )
    link_url = models.URLField(null=True, blank=True, verbose_name="랜딩 URL")
    ad_type = models.CharField(
        max_length=10,
        choices=Advertisement.AD_TYPE_CHOICES,
        verbose_name="광고 타입"
    )

    # 집행 조건
    budget = models.IntegerField(verbose_name="예산(원)", default=0)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    # 업로드 파일 (요청 단계에서 받기)
    image = models.ImageField(upload_to='uploads/ad_requests/images/', null=True, blank=True)
    audio = models.FileField(upload_to='uploads/ad_requests/audio/', null=True, blank=True)
    video = models.FileField(upload_to='uploads/ad_requests/videos/', null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # 승인 후 실제 광고 연결
    advertisement = models.OneToOneField(
        Advertisement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request'
    )

    class Meta:
        db_table = 'ad_request'
        verbose_name = '광고 요청'

    def __str__(self):
        return f"{self.company_name} - {self.title} ({self.get_status_display()})"
