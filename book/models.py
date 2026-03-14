from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid
from character.models import Story





# 장르 테이블
class Genres(models.Model):
    name = models.CharField(max_length=100, unique=True)
    genres_color = models.CharField(max_length=10, default="#FFF")
    genre_img = models.ImageField(upload_to="uploads/genres_img/", null=True, blank=True, max_length=1000)

    class Meta:
        db_table = "genres"
        verbose_name = '장르'

    def __str__(self):
        return self.name
    


# 태그 테이블
class Tags(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table ="tags"
        verbose_name = "책 태그"

    def __str__(self):
        return self.name

# 책 테이블
class Books(models.Model):

    STATUS_CHOICES = [
        ('ongoing', '연재 중'),
        ('paused', '휴재'),
        ('ended', '연재 종료'),
    ]
    public_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='books')
    name = models.CharField(max_length=190, unique=True)
    description = models.TextField(null=True, blank=True)
    cover_img = models.ImageField(upload_to="uploads/book_covers/", null=True, blank=True, max_length=1000)
    created_at = models.DateTimeField(default=timezone.now)
    book_score = models.DecimalField(max_digits=2, decimal_places=1, default=0.0)
    genres = models.ManyToManyField(Genres, related_name="books", blank=True)
    tags = models.ManyToManyField("Tags", through="BookTag", related_name="books")
    audio_file = models.FileField(upload_to="uploads/introduc/", null=True, blank=True, max_length=1000)
    episode_interval_weeks = models.IntegerField(default=1, help_text="에피소드 연재 주기 (주 단위)")
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='ongoing',
        help_text="작품 연재 상태"
    )
    adult_choice = models.BooleanField(default=False)
    author_name = models.CharField(max_length=100, null=True, blank=True, help_text="작가명 (미입력 시 유저 닉네임 사용)")
    voice_config = models.JSONField(default=dict, null=True, blank=True, help_text="캐릭터별 보이스 설정 {0: {name, voice_id}, ...}")
    draft_episode_title = models.CharField(max_length=200, null=True, blank=True, help_text="임시저장 에피소드 제목")
    draft_text = models.TextField(null=True, blank=True, help_text="임시저장 소설 텍스트")
    block_draft = models.JSONField(null=True, blank=True, help_text="블록 편집기 임시저장 (batch JSON)")
    is_deleted = models.BooleanField(default=False, db_index=True, help_text="소프트 삭제 여부 (데이터는 보존)")
    deleted_at = models.DateTimeField(null=True, blank=True)

    BOOK_TYPE_CHOICES = [
        ('audiobook', '오디오북'),
        ('webnovel', '웹소설'),
    ]
    book_type = models.CharField(
        max_length=20,
        choices=BOOK_TYPE_CHOICES,
        default='audiobook',
        db_index=True,
        help_text="콘텐츠 유형 (오디오북 / 웹소설)"
    )

    class Meta:
        db_table = 'book'
        verbose_name = '책 정보'

    def __str__(self):
        return self.name

    def get_total_duration_seconds(self):
        """이 책의 모든 에피소드의 총 오디오 길이(초)"""
        from django.db.models import Sum
        total = self.contents.aggregate(total=Sum('duration_seconds'))['total']
        return total or 0

    def get_total_duration_formatted(self):
        """이 책의 총 오디오 길이를 시:분:초 형식으로 반환"""
        total_seconds = self.get_total_duration_seconds()
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}시간 {minutes}분"
        elif minutes > 0:
            return f"{minutes}분 {seconds}초"
        else:
            return f"{seconds}초"
    

# 중간 테이블        
class BookTag(models.Model):
    book = models.ForeignKey(Books, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tags , on_delete=models.CASCADE)
    created_at   = models.DateTimeField(default=timezone.now)


    class Meta:
        db_table = "book_tag"
        verbose_name = "책 태그"

    def __str__(self):
        return f"{self.book.name} - {self.tag.name}"

# 에피소드 테이블
class Content(models.Model):
    public_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    book = models.ForeignKey("Books", on_delete=models.CASCADE, related_name='contents')
    title = models.CharField(max_length=190)
    number = models.IntegerField(default=1)
    text = models.TextField(blank=True, null=True)
    episode_image = models.ImageField(upload_to="uploads/episode_images/", null=True, blank=True)  # 에피소드 썸네일
    audio_file = models.FileField(upload_to="uploads/audio/", null=True, blank=True, max_length=1000)
    audio_timestamps = models.JSONField(null=True, blank=True)  # 각 대사의 시작/종료 시간 저장
    duration_seconds = models.IntegerField(default=0, help_text="오디오 길이(초)")
    mix_config = models.JSONField(null=True, blank=True, help_text="믹싱 설정 {bgm:[{id,name,desc,volume,start_page,end_page}], sfx:[{id,name,desc,volume,page_number}]}")  # 오디오 길이 (초 단위)
    llm_provider = models.CharField(max_length=20, blank=True, null=True, help_text="에피소드 작성 AI (gpt/grok/claude)")
    created_at  = models.DateTimeField(default=timezone.now)
    is_deleted = models.BooleanField(default=False, help_text="소프트 삭제 여부")  # Soft delete
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="삭제 시간")

    class Meta:
        db_table = 'content'
        verbose_name = '에피소드'

    def __str__(self):
        return self.title

    def get_duration_formatted(self):
        """오디오 길이를 시:분:초 형식으로 반환"""
        hours = self.duration_seconds // 3600
        minutes = (self.duration_seconds % 3600) // 60
        seconds = self.duration_seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"



# 페이지별 TTS 개별 저장 테이블
class PageAudio(models.Model):
    PAGE_TYPE_CHOICES = [
        ('tts', 'TTS'),
        ('silence', '무음'),
        ('duet', '듀엣'),
    ]
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name='page_audios')
    page_number = models.IntegerField()  # 1-based
    audio_file = models.FileField(upload_to='uploads/page_audio/', null=True, blank=True, max_length=1000)
    text = models.TextField(blank=True, default='')
    voice_id = models.CharField(max_length=100, blank=True, default='')
    language_code = models.CharField(max_length=10, default='ko')
    speed_value = models.FloatField(default=1.0)
    style_value = models.FloatField(default=0.85)
    similarity_value = models.FloatField(default=0.75)
    webaudio_effect = models.CharField(max_length=50, blank=True, default='normal')
    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, default='tts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'page_audio'
        unique_together = ('content', 'page_number')
        ordering = ['page_number']

    def __str__(self):
        return f"{self.content.title} - Page {self.page_number}"


# 책 평가 테이블
class BookReview(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='book_reviews')
    book = models.ForeignKey("Books", on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField(default=5)  # 1-5점
    review_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'book_review'
        verbose_name = '책 리뷰'
        unique_together = ('user', 'book')  # 한 사용자당 책 하나에 리뷰 하나만

    def __str__(self):
        return f"{self.user.nickname} - {self.book.name} ({self.rating}점)"


# 책 댓글 테이블
class BookComment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='book_comments')
    book = models.ForeignKey("Books", on_delete=models.CASCADE, related_name="book_comments")
    comment = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    # 대댓글
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies"
    )

    like_count = models.IntegerField(default=0)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'book_comment'
        verbose_name = '책 댓글'

    def __str__(self):
        return f"{self.user.nickname}: {self.comment[:20]}"


# 콘텐츠 댓글 테이블
class ContentComment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='content_comments')
    content = models.ForeignKey("Content", on_delete=models.CASCADE, related_name="comments")

    comment = models.TextField()
    created_at  = models.DateTimeField(default=timezone.now)

    # 대댓글
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies"
    )

    like_count = models.IntegerField(default=0)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'content_comment'
        verbose_name = '콘텐츠 댓글'

    def __str__(self):
        return f"{self.user.nickname}: {self.comment[:20]}"


# 독서 진행 상황 테이블
class ReadingProgress(models.Model):
    STATUS_CHOICES = [
        ('reading', '읽는 중'),
        ('completed', '완독'),
        ('paused', '일시중지'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reading_progress')
    book = models.ForeignKey("Books", on_delete=models.CASCADE, related_name="reading_progress")
    current_content = models.ForeignKey("Content", on_delete=models.SET_NULL, null=True, blank=True, related_name="readers")

    last_read_content_number = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='reading')

    started_at = models.DateTimeField(default=timezone.now)
    last_read_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    is_favorite = models.BooleanField(default=False)

    class Meta:
        db_table = 'reading_progress'
        verbose_name = '독서 진행 상황'
        unique_together = ('user', 'book')

    def __str__(self):
        return f"{self.user.nickname} - {self.book.name} ({self.get_progress_percentage()}%)"

    def get_progress_percentage(self):
        total_contents = self.book.contents.count()
        if total_contents == 0:
            return 0
        return round((self.last_read_content_number / total_contents) * 100, 1)

    def get_reading_status(self):
        """
        이어듣기(current_content) 기준으로 동적 상태 계산:
        - current_content가 마지막 에피소드면: 완독
        - current_content가 중간 에피소드면: 읽는 중
        - 작가가 새 에피소드 추가 시 자동으로 '읽는 중'으로 변경됨

        예시: 총 12화, 7화로 돌아갔으면 → 읽는 중
              총 12화, 12화까지 들었으면 → 완독
              총 12화였다가 13화 추가되고 12화에 있으면 → 읽는 중
        """
        total_contents = self.book.contents.count()
        if total_contents == 0:
            return 'reading'

        # current_content가 없으면 읽는 중
        if not self.current_content:
            return 'reading'

        # current_content의 화수가 마지막 화 이상이면 완독
        if self.current_content.number >= total_contents:
            return 'completed'
        else:
            return 'reading'


# 음성 유형 테이블
class VoiceType(models.Model):
    name = models.CharField(max_length=50, unique=True) 

    class Meta:
        db_table = 'voice_type'
        verbose_name = '음성 타입'
    def __str__(self):
        return self.name

# 보이스 테이블
class VoiceList(models.Model):
    voice_name = models.CharField(max_length=100)
    voice_id = models.CharField(max_length=100)
    sample_audio = models.FileField(upload_to='audio_samples/', null=True, blank=True)
    voice_image= models.ImageField(upload_to='uploads/voice_images/HOME v.png/', null=True, blank=True, default="uploads/voice_images/HOMEv.png/")
    created_at = models.DateTimeField(default=timezone.now)
    voice_description = models.TextField(null=True, blank=True)
    language_code = models.CharField(max_length=20, default="ko")
    types = models.ManyToManyField(VoiceType, blank=True)


    class Meta:
        db_table = 'voice_list'
        verbose_name = '음성 목록'

    def __str__(self):
        return self.voice_name


# 사운드 이팩트 라이브러리 테이블
class SoundEffectLibrary(models.Model):
    effect_name = models.CharField(max_length=100)
    effect_description = models.TextField()
    audio_file = models.FileField(upload_to='sound_effects/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey('register.Users', on_delete=models.CASCADE, related_name='sound_effects', null=True, blank=True)

    class Meta:
        db_table = 'sound_effect_library'
        verbose_name = '사운드 이팩트 라이브러리'
        ordering = ['-created_at']

    def __str__(self):
        return self.effect_name


# 배경음 라이브러리 테이블
class BackgroundMusicLibrary(models.Model):
    music_name = models.CharField(max_length=100)
    music_description = models.TextField()
    audio_file = models.FileField(upload_to='background_music/', null=True, blank=True)
    duration_seconds = models.IntegerField(default=30)
    created_at = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey('register.Users', on_delete=models.CASCADE, related_name='background_music', null=True, blank=True)

    class Meta:
        db_table = 'background_music_library'
        verbose_name = '배경음 라이브러리'
        ordering = ['-created_at']

    def __str__(self):
        return self.music_name


# 🔑 API Key 모델 - 안드로이드 앱 연동용
class APIKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    key = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=100, help_text="API Key 이름 (예: 안드로이드 앱)")
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'api_key'
        verbose_name = 'API Key'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.nickname} - {self.name}"

    def save(self, *args, **kwargs):
        # API Key가 없으면 자동 생성
        if not self.key:
            import secrets
            self.key = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)


# 북 스냅 테이블
class BookSnap(models.Model):
    public_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    book = models.ForeignKey('Books', on_delete=models.CASCADE, null=True, blank=True, related_name='snaps')
    story = models.ForeignKey(Story, null=True, blank=True, on_delete=models.SET_NULL)

    snap_title = models.CharField(max_length=200, null=True, blank=True)

    # Media
    snap_video = models.FileField(upload_to="uploads/book_snaps/videos/", null=True, blank=True)
    thumbnail = models.ImageField(upload_to="uploads/book_snaps/thumbnails/", null=True, blank=True)

    # Basic stats
    booksnap_like = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_snaps', blank=True)
    views = models.IntegerField(default=0)
    viewed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="viewed_snaps", blank=True
    )
    shares = models.IntegerField(default=0)

    # Settings
    allow_comments = models.BooleanField(default=True)
    book_link = models.URLField(max_length=1000, null=True, blank=True)
    story_link = models.URLField(max_length=1000, null=True, blank=True)
    book_comment = models.CharField(max_length=200, null=True, blank=True)
    duration = models.FloatField(null=True, blank=True)
    adult_choice = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'book_snap'
        verbose_name = '북 스냅'

    def __str__(self):
        return f"{self.snap_title} - Snap {self.id}"


# 북 스냅 댓글 테이블
class BookSnapComment(models.Model):
    snap = models.ForeignKey("BookSnap", on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    likes = models.IntegerField(default=0)

    # parent → 대댓글
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies'
    )

    class Meta:
        db_table = 'book_snap_comment'
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user} on Snap {self.snap.id}"
    


# 개인 목소리 저장 테이블
class MyVoiceList(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    voice = models.ForeignKey("VoiceList", on_delete=models.CASCADE, null=True, blank=True)
    book = models.ForeignKey("Books", on_delete=models.CASCADE, null=True, blank=True)

    alias_name = models.CharField(max_length=100, null=True, blank=True)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        db_table = 'my_voice_list'
        verbose_name = '개인 목소리 목록'
    def __str__(self):
        return f"{self.user.nickname} - {self.alias_name or self.voice.voice_name}"


# 청취 기록 테이블 (작가 센터 통계용)
class ListeningHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='listening_history')
    book = models.ForeignKey("Books", on_delete=models.CASCADE, related_name="listening_stats")
    content = models.ForeignKey("Content", on_delete=models.CASCADE, related_name="listening_stats", null=True, blank=True)

    listened_seconds = models.IntegerField(default=0, help_text="청취한 시간(초)")
    listened_at = models.DateTimeField(default=timezone.now)
    last_listened_at = models.DateTimeField(default=timezone.now, help_text="마지막 청취 시각")
    last_position = models.FloatField(default=0, help_text="마지막 재생 위치(초)")

    class Meta:
        db_table = 'listening_history'
        verbose_name = '청취 기록'
        ordering = ['-last_listened_at']

    def __str__(self):
        return f"{self.user.nickname} - {self.book.name} ({self.listened_seconds}초)"


# 작가 공지사항 테이블
class AuthorAnnouncement(models.Model):
    book = models.ForeignKey("Books", on_delete=models.CASCADE, related_name="announcements")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=200, default="공지사항")
    content = models.TextField(help_text="작가의 공지사항 내용")
    is_pinned = models.BooleanField(default=False, help_text="상단 고정 여부")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'author_announcement'
        verbose_name = '작가 공지사항'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"{self.book.name} - {self.title}"


# 북마크/메모 테이블
class ContentBookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_bookmarks")
    content = models.ForeignKey("Content", on_delete=models.CASCADE, related_name="bookmarks")
    position = models.FloatField(help_text="북마크 위치(초)")
    memo = models.TextField(blank=True, null=True, help_text="사용자 메모")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'content_bookmark'
        verbose_name = '북마크/메모'
        ordering = ['position']
        unique_together = ['user', 'content', 'position']

    def __str__(self):
        return f"{self.user.nickname} - {self.content.title} ({self.position}초)"

    def get_position_formatted(self):
        """위치를 분:초 형식으로 반환"""
        minutes = int(self.position // 60)
        seconds = int(self.position % 60)
        return f"{minutes}:{seconds:02d}"


# 오디오북 가이드
class AudioBookGuide(models.Model):
    title = models.CharField(max_length=200)
    short_description = models.CharField(max_length=200, null=True, blank=True)

    thumbnail = models.ImageField(upload_to="uploads/guide/thumbs/", null=True, blank=True)

    description = models.TextField(null=True)
    video_url = models.URLField(null=True, blank=True)
    guide_video = models.FileField(upload_to="uploads/guide/video", null=True, blank=True)


    attachment = models.FileField(upload_to="uploads/guide/files/", null=True, blank=True)

    category = models.CharField(
        max_length=50,
        choices=[
            ('soundEffect', '사운드 이펙트'),
            ('musicSound', '배경음'),
            ('page', '대사'),
        
            ('voiceChoice', '보이스 선택하기'),
            ('save', '임시저장'),
            ('emotionList', '감정리스트'),
            ('pageAudio', '페이지 오디오'),
            ('voiceSetting', '음성 설정'),
            ('preview', '미리듣기'),
            ('etc', '기타'),
            ('fast', "초보자 가이드")
        ],
        default='etc'
    )

    tags = models.CharField(max_length=200, null=True, blank=True)
    order_num = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title
    
    class Meta:
        db_table = 'audio_book_guide'
        verbose_name = '오디오북 가이드'



# 에피소드 요약본
class EpisodeSummary(models.Model):
    content = models.OneToOneField("Content", on_delete=models.CASCADE, related_name="summary")
    summary_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "episode_summary"
        verbose_name = "에피소드 요약"

    def __str__(self):
        return f"{self.content.title} 요약"



class Poem_list(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    poem_audio = models.FileField(upload_to="uploads/poem/", null=True, blank=True, max_length=1000)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to="uploads/poem_img", blank=True, null=True, verbose_name="이미지", max_length=300)

    is_public = models.BooleanField(default=True)  # 공개 여부
    status = models.CharField(
        max_length=20, 
        choices=[('submitted', '제출됨'), ('winner', '수상작')], 
        default='submitted'
    )

    class Meta:
        db_table = "poem_list"
        verbose_name = "시 공모전 출품작"


#북 스니펫
class BookSnippet(models.Model):
    book = models.ForeignKey(Books, on_delete=models.CASCADE, related_name="snippets")
    sentence = models.CharField(max_length=500)
    audio_file = models.FileField(upload_to="uploads/snippets/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=300, null=True)
    
    class Meta:
        db_table = "book_snippet"
        verbose_name= '북 스니펫'


# 굿즈 테이블
class Merchandise(models.Model):
    name = models.CharField(max_length=100, verbose_name="상품명")
    description = models.TextField(blank=True, null=True, verbose_name="상품 설명")
    price = models.PositiveIntegerField(verbose_name="가격")  # 원 단위
    image = models.ImageField(upload_to="merch/", blank=True, null=True, verbose_name="이미지")
    link = models.URLField(blank=True, null=True, verbose_name="구매 링크")
    is_new = models.BooleanField(default=False, verbose_name="신상품 여부")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록일")

    class Meta:
        db_table = "merchandise"
        verbose_name = "굿즈"
        verbose_name_plural = "굿즈 목록"

    def __str__(self):
        return self.name


# 팔로우 테이블
class Follow(models.Model):
    """
    사용자가 작가를 팔로우하는 관계
    """
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='following',
        verbose_name="팔로워"
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='followers',
        verbose_name="팔로잉"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="팔로우 시작일")

    class Meta:
        db_table = "follow"
        verbose_name = "팔로우"
        verbose_name_plural = "팔로우 목록"
        unique_together = ('follower', 'following')  # 중복 팔로우 방지
        indexes = [
            models.Index(fields=['follower']),
            models.Index(fields=['following']),
        ]

    def __str__(self):
        return f"{self.follower.nickname} → {self.following.nickname}"


# 북마크/나중에 보기 테이블
class BookmarkBook(models.Model):
    """
    사용자가 나중에 보기 위해 저장한 책
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookmarked_books',
        verbose_name="사용자"
    )
    book = models.ForeignKey(
        'Books',
        on_delete=models.CASCADE,
        related_name='bookmarked_by',
        verbose_name="책"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="저장일")
    note = models.TextField(blank=True, null=True, verbose_name="메모")  # 선택: 왜 저장했는지 메모

    class Meta:
        db_table = "bookmark_book"
        verbose_name = "북마크한 책"
        verbose_name_plural = "북마크 목록"
        unique_together = ('user', 'book')  # 중복 북마크 방지
        ordering = ['-created_at']  # 최근 저장한 순서
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.nickname} → {self.book.name}"
    





class GenrePlaylist(models.Model):
    PLAYLIST_TYPE_CHOICES = [
        ('popular', '🔥 인기'),
        ('new', '🆕 신작'),
        ('short', '⚡ 짧게 듣기'),
        ('rated', '⭐ 고평점'),
        ('night', '🌙 자기 전 듣기'),
        ('custom', '✨ 큐레이션'),
    ]

    genre = models.ForeignKey(
        'Genres',
        on_delete=models.CASCADE,
        related_name='playlists',
        verbose_name='장르'
    )
    playlist_type = models.CharField(
        max_length=20,
        choices=PLAYLIST_TYPE_CHOICES,
        default='popular',
        verbose_name='플레이리스트 유형'
    )
    title = models.CharField(max_length=200, verbose_name='플레이리스트 제목')
    description = models.TextField(blank=True, null=True, verbose_name='설명')
    cover_img = models.ImageField(
        upload_to='uploads/playlists/',
        null=True, blank=True,
        verbose_name='커버 이미지'
    )
    is_active = models.BooleanField(default=True, verbose_name='활성화')
    is_auto_generated = models.BooleanField(
        default=True,
        verbose_name='자동생성 여부',
        help_text='True면 주기적으로 자동 갱신, False면 관리자 수동 관리'
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'genre_playlist'
        verbose_name = '장르 플레이리스트'
        unique_together = ('genre', 'playlist_type')  # 장르당 유형별 1개

    def __str__(self):
        return f"[{self.genre.name}] {self.title}"

    def get_total_duration_seconds(self):
        return sum(
            item.content.duration_seconds
            for item in self.items.select_related('content').all()
        )

    def get_total_duration_formatted(self):
        total = self.get_total_duration_seconds()
        hours = total // 3600
        minutes = (total % 3600) // 60
        if hours > 0:
            return f"{hours}시간 {minutes}분"
        return f"{minutes}분"

    def get_listener_count(self):
        from django.db.models import Count
        return ListeningHistory.objects.filter(
            content__in=self.items.values('content')
        ).values('user').distinct().count()


class PlaylistItem(models.Model):
    playlist = models.ForeignKey(
        GenrePlaylist,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='플레이리스트'
    )
    content = models.ForeignKey(
        'Content',
        on_delete=models.CASCADE,
        related_name='playlist_items',
        verbose_name='에피소드'
    )
    order = models.PositiveIntegerField(default=0, verbose_name='재생 순서')
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'playlist_item'
        verbose_name = '플레이리스트 항목'
        ordering = ['order']
        unique_together = ('playlist', 'content')  # 중복 에피소드 방지

    def __str__(self):
        return f"{self.playlist.title} - {self.order}. {self.content.title}"


# TTS 사용량 쿼터 테이블 (한도 적용 준비용 — 현재는 제한 없음)
class UserTTSQuota(models.Model):
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tts_quota')
    used_chars       = models.IntegerField(default=0, verbose_name='이번 달 사용 글자 수')
    total_chars      = models.IntegerField(default=0, verbose_name='누적 총 사용 글자 수')
    monthly_limit    = models.IntegerField(default=0, verbose_name='월 한도 (0=무제한)')
    is_premium       = models.BooleanField(default=False, verbose_name='프리미엄 여부')
    reset_date       = models.DateField(null=True, blank=True, verbose_name='다음 리셋 날짜')
    last_used_at     = models.DateTimeField(null=True, blank=True, verbose_name='마지막 TTS 생성 시각')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_tts_quota'
        verbose_name = 'TTS 사용량 쿼터'

    def __str__(self):
        return f"{self.user.username} | {self.used_chars}자 사용 / 한도 {'무제한' if self.monthly_limit == 0 else self.monthly_limit}"