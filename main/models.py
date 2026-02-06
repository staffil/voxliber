from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.conf import settings




# 책 기록 테이블
class UserBookLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="book_logs")
    book = models.ForeignKey("book.Books", on_delete=models.CASCADE, related_name="logs")
    last_played_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'user_book_log'
        verbose_name = '책 기록'

    def __str__(self):
        return f"{self.user.nickname} - {self.book.name}"



# 스냅버튼 테이블
class SnapBtn(models.Model):
    title = models.CharField(max_length=191)
    news_description = models.TextField(null=True)
    news_img = models.ImageField(upload_to="uploads/profile_img/", null=True, blank=True, max_length=1000)
    news_link = models.CharField(max_length=500)

    class Meta:
        db_table = 'snap_btn'
        verbose_name = '스냅화면'

    def __str__(self):
        return self.title
    
    
# 광고 테이블
class Advertisment(models.Model):
    title = models.CharField(max_length=300)
    link = models.CharField(max_length=200)
    advertisment_img = models.ImageField(upload_to="upload/advertisment/", null=True)

    class Meta:
        db_table= "advertisment"
        verbose_name = "광고 테이블"
    def __str__(self):
        return self.title

class Event(models.Model):
    event_name= models.CharField(max_length=300)
    event_img= models.ImageField(upload_to="upload/event/", null=True)
    link = models.CharField(max_length=200)

    class Meta:
        db_table= 'event'
        verbose_name = '이벤트'
    def __str__(self):
        return self.event_name
    

# others

# 1️⃣ 공지사항
class Notice(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "공지사항"
        verbose_name_plural = "공지사항"
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# 2️⃣ FAQ
class FAQ(models.Model):
    CATEGORY_CHOICES = [
        ('general', '일반'),
        ('payment', '결제'),
        ('account', '계정'),
        ('content', '콘텐츠'),
        ('other', '기타'),
    ]
    question = models.CharField(max_length=255)
    answer = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQ 목록"
        ordering = ['category', 'id']

    def __str__(self):
        return self.question
    


# 3️⃣ 문의(Contact)
class Contact(models.Model):
    STATUS_CHOICES = [
        ('pending', '대기'),
        ('answered', '답변 완료'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL , on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    answer = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "문의"
        verbose_name_plural = "문의 목록"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} ({self.email})"


# 4️⃣ 이용약관(Terms)
class Terms(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "이용약관"
        verbose_name_plural = "이용약관 목록"
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# 5️⃣ 정책 관련(Policy)
class Policy(models.Model):
    POLICY_TYPE_CHOICES = [
        ('copyright', '저작권 정책'),
        ('youth', '청소년 보호정책'),
        ('privacy', '개인정보처리방침'),
        ('terms', '이용약관'),
    ]
    title = models.CharField(max_length=200)
    content = models.TextField()
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "정책"
        verbose_name_plural = "정책 목록"
        ordering = ['policy_type', 'id']

    def __str__(self):
        return f"{self.get_policy_type_display()} - {self.title}"



# 광고 테이블
class ScreenAI(models.Model):
    title = models.CharField(max_length=300)
    link = models.CharField(max_length=200)
    advertisment_img = models.ImageField(upload_to="upload/advertisment/", null=True)

    class Meta:
        db_table= "screen_ai"
        verbose_name = "ai 광고 테이블"
    def __str__(self):
        return self.title

