from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.conf import settings



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
    

