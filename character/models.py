from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class Story(models.Model):
    public_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stories')
    title = models.CharField(max_length=200, verbose_name="소설/채팅 제목")
    description = models.TextField(blank=True, verbose_name="스토리 간단 설명")
    created_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=False)
    cover_image = models.ImageField(upload_to='uploads/story_covers/', null=True, blank=True)
    genres = models.ManyToManyField('book.Genres', related_name='llms', blank=True)
    tags = models.ManyToManyField('book.Tags', related_name='llms', blank=True) 
    adult_choice = models.BooleanField(default=False)
    story_desc_video = models.FileField(upload_to='uploads/story_covers/desc', null=True, blank=True)
    story_desc_img = models.ImageField(upload_to='uploads/story_covers/desc/img', null=True, blank=True)



    class Meta:
        db_table = 'story'
        verbose_name = '소설/스토리'
        verbose_name_plural = '소설/스토리들'

    def __str__(self):
        return self.title

class LLM(models.Model):
    MODEL_CHOICES = [
        ('gpt:gpt-4o-mini', 'GPT-4o Mini'),
        ('grok:grok-3-mini', 'Grok-3-mini '),
    ]
    public_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='llm_set')
    voice = models.ForeignKey('book.VoiceList', on_delete=models.CASCADE, null=True, blank=True, related_name='llms')

    narrator_voice = models.ForeignKey(
        'book.VoiceList', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='narrator_llms',
        verbose_name="나레이션 목소리 (선택)"
    )
    story = models.ForeignKey(
        'character.Story',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='characters',
        verbose_name="소속 스토리 (선택)"
    )

    name = models.CharField(max_length=100, verbose_name='user 가 지정한 LLM 이름')
    prompt = models.TextField(verbose_name='user 가 지정한 프롬프트')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='user 가 LLM 을 만든 시기')
    update_at = models.DateTimeField(null=True, blank=True, auto_now=True, verbose_name='user 가 프롬프트, 목소리 변형을 했을 경우 나중에 문제가 생겼을때 원인을 찾을 수 있음')
    llm_image = models.ImageField(upload_to='uploads/llm_images/', null=True, blank=True, max_length=500)
    response_mp3 = models.CharField(max_length=255, null=True, blank=True, verbose_name='해당 보이스를 저장할 수 있는 mp3 파일 -> 목소리는 ai가 대답할 떄마다 기록이 덮어씌워짐')
    model = models.CharField(max_length=20, choices=MODEL_CHOICES, default='gpt:gpt-4o-mini', verbose_name='gpt 모델 중 하나를 선택해서 사용할 수 있음')
    language = models.CharField(max_length=10, default='en')
    temperature = models.FloatField(default=1.0)
    stability = models.FloatField(default=0.5)
    speed = models.FloatField(default=1.0)
    style = models.FloatField(default=0.5)
    is_public = models.BooleanField(default=False, verbose_name='해당 LLM 을 공유 할 것인가?')
    title = models.CharField(max_length=1000, null=True)
    description = models.TextField(null=True, blank=True, verbose_name='해당 LLM 이 공유될떄 실행')
    llm_like_count = models.IntegerField(default=0, verbose_name='llm이 받은 좋아요 갯수')
    llm_background_image = models.ImageField(upload_to='uploads/llm_background_images/', null=True, blank=True)
    invest_count = models.IntegerField(default=0)
    first_sentence = models.TextField(verbose_name="첫 마디", null=True)

    class Meta:
        db_table = 'LLM'
        verbose_name = 'ai 정보'


# 기존 LLMSubImage는 그대로 유지 (단순 이미지 저장소 역할)
class LLMSubImage(models.Model):
    llm = models.ForeignKey('character.LLM', on_delete=models.CASCADE, related_name='sub_images', null=True)
    image = models.ImageField(upload_to='uploads/llm_sub_images/', max_length=500, null=True)
    title = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True )
    is_public = models.BooleanField(default=False)

    class Meta:
        db_table = 'llm_sub_image'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.llm.name} - {self.title or '이미지'} {self.id}"


# 새 테이블: 사용자가 직접 설정하는 HP 조건 → 이미지 매핑
class HPImageMapping(models.Model):
    llm = models.ForeignKey('character.LLM', on_delete=models.CASCADE, related_name='hp_image_mappings', null=True)
    
    # HP 범위 조건
    min_hp = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name="최소 HP (이 값 이상일 때 적용)"
    )
    max_hp = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name="최대 HP (이 값 이하일 때 적용)"
    )
    
    # 추가 조건 (선택적 확장용, 지금은 비워둬도 됨)
    extra_condition = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="추가 조건 (예: corruption > 50, level >= 5)"
    )
    
    # 연결할 서브 이미지
    sub_image = models.ForeignKey(
        'character.LLMSubImage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="이 HP 범위에서 사용할 서브 이미지"
    )
    
    # 우선순위 (같은 HP 범위에 여러 매핑이 있을 때)
    priority = models.PositiveIntegerField(default=0, verbose_name="우선순위 (숫자 높을수록 우선)")
    
    # 비고 (사용자 메모용)
    note = models.CharField(max_length=200, blank=True, verbose_name="설명 (예: 'HP 30 이하 - 중상 상태')")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hp_image_mapping'
        verbose_name = 'HP별 이미지 매핑'
        verbose_name_plural = 'HP별 이미지 매핑들'
        ordering = ['-priority', 'min_hp', 'max_hp']
        unique_together = ('llm', 'min_hp', 'max_hp')  # 같은 범위 중복 방지 (필요 시 제거)

    def __str__(self):
        range_str = f"HP {self.min_hp or '?'} ~ {self.max_hp or '?'}"
        return f"{self.llm.name} - {range_str} → {self.sub_image}"



# 프롬프트 테이블
class Prompt(models.Model):
    PROMPT_TYPE_CHOICES = [
        ('text', '일반 프롬프트'),
        ('voice', '목소리 프롬프트'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    prompt_title = models.CharField(max_length=100, verbose_name="프롬프트 제목 적는칸")
    prompt = models.TextField(verbose_name="프롬프트 적는 칸")
    prompt_type = models.CharField(max_length=10, choices=PROMPT_TYPE_CHOICES, default='text')
    created_at = models.DateTimeField(auto_now_add=True)    

    class Meta:
        db_table = "prompt"
        verbose_name = 'prompt 정보'


class Conversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations',
        null=True
    )
    llm = models.ForeignKey('character.LLM', on_delete=models.CASCADE)
    user_message = models.TextField()
    llm_response = models.TextField()
    response_audio = models.FileField(upload_to='audio/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_public = models.BooleanField(default=False, verbose_name="공개 여부")
    shared_at = models.DateTimeField(null=True, blank=True, verbose_name="공유 시간")

    class Meta:
        db_table = 'conversation'
        verbose_name = '대화목록'

    def __str__(self):
        return f"Conversation {self.id} by {self.user}"


class ConversationMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField()
    audio = models.FileField(upload_to='uploads/tts_audio/', null=True, blank=True, verbose_name='TTS 오디오 파일')
    created_at = models.DateTimeField(default=timezone.now)
    hp_after_message = models.IntegerField(null=True, blank=True)  # 이 메시지 후의 HP
    hp_range_min = models.IntegerField(null=True, blank=True)      # 적용된 구간 시작
    hp_range_max = models.IntegerField(null=True, blank=True)
    audio_duration = models.FloatField(null=True, blank=True, verbose_name="오디오 길이(초)")

    class Meta:
        db_table= 'conversation_message'
        ordering = ['created_at']


        
class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    llm = models.ForeignKey('character.LLM', on_delete=models.CASCADE)
    content = models.TextField(verbose_name='댓글')
    created_at = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='replies',
        verbose_name='답글 대상 댓글',
    )

    class Meta:
        db_table = 'comment'
        verbose_name = 'AI 대한 댓글창'
        ordering = ['-created_at']


# LLM 장기기억 모델
class CharacterMemory(models.Model):
    llm = models.ForeignKey('character.LLM', on_delete=models.CASCADE, related_name='memories')
    conversation = models.ForeignKey('character.Conversation', on_delete=models.SET_NULL, null=True, blank=True)
    summary = models.TextField(verbose_name="AI가 추출한 요약 (3~5문장)")
    key_facts = models.JSONField(default=dict, verbose_name="중요 사실 JSON {fact: '값', ...}")
    type = models.CharField(max_length=20, choices=[('summary', '대화 요약'), ('fact', '영구 사실'), ('event', '주요 사건')])
    relevance_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'character_memory'
        verbose_name = '캐릭터 장기 기억'


# 세계관 설정
class LoreEntry(models.Model):
    llm = models.ForeignKey('character.LLM', on_delete=models.CASCADE, related_name='lore_entries')
    keys = models.TextField(verbose_name="활성화 키워드 (쉼표 또는 줄바꿈 구분)")
    content = models.TextField(verbose_name="주입될 내용 (설명, 사실, 설정 등)")
    priority = models.IntegerField(default=0, verbose_name="우선순위 (높을수록 먼저 주입)")
    always_active = models.BooleanField(default=False, verbose_name="항상 포함?")
    category = models.CharField(max_length=50, blank=True, choices=[('personality', '성격'), ('world', '세계관'), ('relationship', '관계')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lore_entry'
        verbose_name = '로어북 항목'


# 채팅 상태
class ConversationState(models.Model):
    conversation = models.OneToOneField('character.Conversation', on_delete=models.CASCADE, related_name='state')
    current_location = models.CharField(max_length=200, blank=True)
    character_stats = models.JSONField(default=dict)
    relationships = models.JSONField(default=dict)
    inventory = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversation_state'
        unique_together = ('conversation',)


class LLMLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    llm = models.ForeignKey('character.LLM', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'llm_like'
        unique_together = ('user', 'llm')


class LLMPrompt(models.Model):
    llm = models.ForeignKey('character.LLM', on_delete=models.CASCADE, related_name='additional_prompts')
    prompt = models.ForeignKey('character.Prompt', on_delete=models.SET_NULL, null=True)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'llm_prompt'
        unique_together = ('llm', 'prompt')


# 스토리 좋아요
class StoryLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    story = models.ForeignKey('character.Story', on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'story_like'
        unique_together = ('user', 'story')


# 스토리 댓글
class StoryComment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    story = models.ForeignKey('character.Story', on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(verbose_name='댓글')
    created_at = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name='답글 대상 댓글',
    )

    class Meta:
        db_table = 'story_comment'
        verbose_name = '스토리 댓글'
        ordering = ['-created_at']


# 스토리 북마크
class StoryBookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='story_bookmarks')
    story = models.ForeignKey('character.Story', on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'story_bookmark'
        unique_together = ('user', 'story')
        verbose_name = '스토리 북마크'





