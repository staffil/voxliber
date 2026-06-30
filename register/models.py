from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid


class PricePlan(models.Model):
    PLAN_CHOICES = [
        ('monthly', '월간 구독'),
        ('yearly', '연간 구독'),
    ]
    plan_type = models.CharField(max_length=10, choices=PLAN_CHOICES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='가격(원)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'price_plan'
        verbose_name = '가격 플랜'

    def __str__(self):
        return f"{self.get_plan_type_display()} - {self.price}원"


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


class PaymentHistory(models.Model):
    METHOD_CHOICES = [
        ('kakao', '카카오페이'),
        ('naver', '네이버페이'),
        ('card', '신용카드'),
        ('toss', '토스페이'),
        ('admin', '관리자 처리'),
    ]
    STATUS_CHOICES = [
        ('paid', '결제 완료'),
        ('failed', '결제 실패'),
        ('refunded', '환불'),
        ('cancelled', '취소'),
    ]
    PLAN_CHOICES = [
        ('monthly', '월간 구독'),
        ('yearly', '연간 구독'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_history'
    )
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES)
    amount = models.IntegerField(verbose_name='결제 금액(원)')
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='card')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='paid')
    receipt_email = models.EmailField(blank=True)
    paid_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'payment_history'
        ordering = ['-paid_at']
        verbose_name = '결제 내역'

    def __str__(self):
        return f"{self.user} - {self.get_plan_display()} {self.amount}원 ({self.paid_at:%Y-%m-%d})"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)

from datetime import date


# 유저 테이블
class Users(AbstractBaseUser, PermissionsMixin):

    GENDER_CHOICE = [
        ("M", "남성"),
        ("F", "여성"),
        ("O", "기타"),
    ]

    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True, null=True)
    nickname = models.CharField(max_length=100, unique=True, null=True)
    public_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICE, default='O')
    age = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    user_img = models.ImageField(upload_to="uploads/profile_img/", null=True, blank=True, max_length=1000)
    cover_img = models.ImageField(upload_to="uploads/cover_img/", null=True, blank=True, max_length=1000)

    oauth_provider = models.CharField(
        max_length=20,
        choices=[('google', 'Google'), ('microsoft', 'Microsoft'), ('github', 'GitHub')],
        null=True,
        blank=True
    )
    access_token = models.CharField(max_length=191, null=True, blank=True)
    oauth_uid = models.CharField(max_length=191, null=True, blank=True)

    refresh_token = models.TextField(null=True, blank=True)
    token_expiry = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=[('active', 'Active'), ('inactive', 'Inactive'), ('banned', 'Banned')],
        default='active'
    )

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    birthdate = models.DateField(null=True, blank=True)

    follow_count = models.IntegerField(default=0)

    is_profile_completed = models.BooleanField(default=False)
    is_author = models.BooleanField(default=False, verbose_name='작가 여부')

    objects = UserManager()

    USERNAME_FIELD = "email"

    class Meta:
        db_table = "users"
        verbose_name = "사용자"

    def __str__(self):
        return str(self.nickname or self.user_id or "")

    def get_total_audiobook_duration_seconds(self):
        """작가의 모든 책의 총 오디오 길이(초)"""
        from django.db.models import Sum
        total = 0
        for book in self.books.all():
            total += book.get_total_duration_seconds()
        return total

    def get_total_audiobook_duration_formatted(self):
        """작가의 모든 책의 총 오디오 길이를 포맷팅"""
        total_seconds = self.get_total_audiobook_duration_seconds()
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}시간 {minutes}분"
        elif minutes > 0:
            return f"{minutes}분"
        else:
            return f"{total_seconds}초"
        
    def is_adult(self):
        if not self.birthdate:
            return False

        today = date.today()
        age = today.year - self.birthdate.year - (
            (today.month, today.day) < (self.birthdate.month, self.birthdate.day)
        )
        return age >= 19
    
    




# 관리자 테이블
class Authority(models.Model):
    name = models.CharField(max_length=100)
    nickname = models.CharField(max_length=100, default="관리자")

    class Meta:
        db_table = "authority"
        verbose_name = "관리자"

    def __str__(self):
        return self.name



# user_auth 테이블
class UserAuth(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='authorities')
    authority = models.ForeignKey("Authority", on_delete=models.CASCADE, related_name='users')

    class Meta:
        db_table = 'user_auth'
        unique_together = (('user', 'authority'),)

    def __str__(self):
        return f"{self.user.nickname} - {self.authority.name}"
    



# 회원가입 이용약관 테이블
class SignupTOS(models.Model):
    title = models.CharField(max_length=200)
    version = models.CharField(max_length=20)
    TOS_description = models.TextField()
    is_required= models.BooleanField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    upload_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "signup_TOS"
        verbose_name = "회원가입 이용약관"
    def __str__(self):
        return f"{self.title}"
    



# 작가 신청 테이블
class AuthorApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', '검토 대기'),
        ('approved', '승인'),
        ('rejected', '거절'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='author_application')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    planned_work = models.TextField(verbose_name='쓰고 싶은 작품 소개', default='')
    portfolio = models.URLField(null=True, blank=True, verbose_name='포트폴리오 URL')
    policy_agreed = models.BooleanField(default=False, verbose_name='작가 정책 동의')
    reject_reason = models.TextField(null=True, blank=True, verbose_name='거절 사유')
    applied_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'author_application'
        verbose_name = '작가 신청'

    def __str__(self):
        return f"{self.user.nickname} - {self.get_status_display()}"


# 작가 전용 문의 테이블
class AuthorInquiry(models.Model):
    CATEGORY_CHOICES = [
        ('settlement', '정산'),
        ('content', '콘텐츠'),
        ('tts', 'TTS'),
        ('rights', '저작권'),
        ('other', '기타'),
    ]
    STATUS_CHOICES = [
        ('pending', '대기'),
        ('answered', '답변 완료'),
        ('closed', '종료'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='author_inquiries')
    book = models.ForeignKey('book.Books', on_delete=models.SET_NULL, null=True, blank=True, related_name='author_inquiries')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    title = models.CharField(max_length=200)
    message = models.TextField()
    attachment = models.FileField(upload_to='uploads/author_inquiry/', null=True, blank=True)
    answer = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'author_inquiry'
        verbose_name = '작가 문의'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.nickname} - {self.title}"


# 작가 정산 테이블 (정산 기준 미정 — 추후 도입)
class SettlementRecord(models.Model):
    STATUS_CHOICES = [
        ('pending', '정산 대기'),
        ('paid', '지급 완료'),
        ('cancelled', '취소'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='settlements')
    period = models.CharField(max_length=7, verbose_name='정산 월 (YYYY-MM)')
    total_listen_seconds = models.BigIntegerField(default=0, verbose_name='청취 시간(초)')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='정산 금액')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(null=True, blank=True, verbose_name='메모')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'settlement_record'
        verbose_name = '정산 기록'
        unique_together = ('user', 'period')
        ordering = ['-period']

    def __str__(self):
        return f"{self.user.nickname} - {self.period} ({self.get_status_display()})"


class UserVisitLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='visit_logs',
        null=True, blank=True  # 비로그인 방문자도 기록 가능
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    visited_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = "user_visit_log"
        verbose_name = "방문 로그"
    
    def __str__(self):
        return f"{self.user} - {self.visited_at.strftime('%Y-%m-%d %H:%M')}"