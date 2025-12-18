from django.db import models
from django.conf import settings

# Create your models here.

# 사용자 음성 테이블
class VoiceProfile(models.Model):
    STATUS_CHOICE = [
        ('uploaded', '업로드 완료'),
        ('processing', '전처리 중'),
        ('training', '학습 중'),
        ('completed', '완료'),
        ('failed', '실패'),
    ]


    voice_id = models.CharField(max_length=100, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='voice_profiles')
    name = models.CharField(max_length=100)

    audio_files = models.JSONField(default=list)
    total_duration = models.IntegerField(default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICE, default='uploaded')

    progress = models.IntegerField(default=0)
    model_path = models.CharField(max_length=500, blank=True)  
    config_path = models.CharField(max_length=500, blank=True)

    created_at= models.DateTimeField(auto_now_add=True)
    upload_at = models.DateTimeField(auto_now_add=True )

    is_activate = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.voice_id})"
    


# 보이스 생성 비용 테이블
class VoiceGenerationLog(models.Model):
    
    voice_profile = models.ForeignKey(VoiceProfile, on_delete=models.CASCADE)
    text = models.TextField()
    audio_file = models.FileField(upload_to='generated_audio/')
    duration = models.FloatField()  # 초
    created_at = models.DateTimeField(auto_now_add=True)
    
    # 비용 추적
    compute_cost = models.DecimalField(max_digits=10, decimal_places=4, default=0)