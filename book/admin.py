from django.contrib import admin
from .models import Genres, Tags, Books, BookTag, Content, BookReview, BookComment, ContentComment, ReadingProgress, VoiceList, SoundEffectLibrary, BackgroundMusicLibrary, BookSnap, AuthorAnnouncement, AudioBookGuide, APIKey, VoiceType, Follow, BookmarkBook, AbstractBaseUser
from character.models import HPImageMapping

@admin.register(Genres)
class GenresAdmin(admin.ModelAdmin):
    list_display = ['name', 'genres_color']
    search_fields = ['name']


@admin.register(Tags)
class TagsAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    search_fields = ['name', 'slug']


@admin.register(Books)
class BooksAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'book_score', 'created_at']
    list_filter = ['created_at', 'genres']
    search_fields = ['name', 'user__nickname']
    filter_horizontal = ['genres']


@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = ['title', 'book', 'number', 'is_deleted', 'created_at', 'deleted_at']
    list_filter = ['book', 'is_deleted', 'created_at']
    search_fields = ['title', 'book__name']
    readonly_fields = ['created_at', 'deleted_at']

    # 삭제 여부를 아이콘으로 표시
    def is_deleted(self, obj):
        return obj.is_deleted
    is_deleted.boolean = True  # ✓/× 아이콘으로 표시
    is_deleted.short_description = '삭제됨'


@admin.register(BookReview)
class BookReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__nickname', 'book__name']


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'last_read_content_number', 'status', 'get_progress_percentage', 'is_favorite', 'last_read_at']
    list_filter = ['status', 'is_favorite', 'started_at', 'completed_at']
    search_fields = ['user__nickname', 'book__name']
    readonly_fields = ['started_at', 'last_read_at', 'completed_at']

    def get_progress_percentage(self, obj):
        return f"{obj.get_progress_percentage()}%"
    get_progress_percentage.short_description = '진행률'

# 목소리 리스트
@admin.register(VoiceList)
class VoiceListAdmin(admin.ModelAdmin):
    list_display = ['voice_name', 'voice_id', 'language_code', 'created_at', 'get_types', 'voice_image']
    list_filter = ['language_code', 'created_at', 'types']
    search_fields = ['voice_name', 'voice_id']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('voice_name', 'voice_id', 'language_code', 'types')
        }),
        ('상세 정보', {
            'fields': ('voice_description', 'sample_audio', 'voice_image')
        }),
        ('생성일', {
            'fields': ('created_at',)
        }),
    )

    filter_horizontal = ['types']  # 여기 추가

    # ManyToManyField 문자열로 보여주기
    def get_types(self, obj):
        return ", ".join([t.name for t in obj.types.all()])
    get_types.short_description = "음성 유형"




@admin.register(VoiceType)
class VoiceTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("id",)

    readonly_fields = ("id",)

    fieldsets = (
        ("기본 정보", {
            "fields": ("id", "name"),
        }),
        ("상세 정보", {
            "description": (
                "음성 분류용 타입입니다.\n"
                "예: User Voice, Default Voice, AI Narration 등"
            ),
            "fields": (),
        }),
    )

    
    HPImageMapping



@admin.register(HPImageMapping)
class HPImageMappingAdmin(admin.ModelAdmin):
    list_display = (
        'llm',
        'min_hp',
        'max_hp',
        'sub_image',
        'priority',
        'note',
        'created_at',
    )

    list_filter = (
        'llm',
        'created_at',
    )

    search_fields = (
        'llm__name',
        'note',
        'extra_condition',
    )

    ordering = (
        '-priority',
        'min_hp',
        'max_hp',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('기본 매핑 정보', {
            'fields': (
                'llm',
                ('min_hp', 'max_hp'),
                'priority',
            )
        }),
        ('이미지 설정', {
            'fields': (
                'sub_image',
            )
        }),
        ('추가 조건 (선택)', {
            'fields': (
                'extra_condition',
                'note',
            )
        }),
        ('시스템 정보', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )


@admin.register(SoundEffectLibrary)
class SoundEffectLibraryAdmin(admin.ModelAdmin):
    list_display = ['effect_name', 'effect_description', 'user', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['effect_name', 'effect_description']
    readonly_fields = ['created_at']

    fieldsets = (
        ('기본 정보', {
            'fields': ('effect_name', 'effect_description', 'user')
        }),
        ('오디오 파일', {
            'fields': ('audio_file',)
        }),
        ('생성일', {
            'fields': ('created_at',)
        }),
    )


@admin.register(BackgroundMusicLibrary)
class BackgroundMusicLibraryAdmin(admin.ModelAdmin):
    list_display = ['music_name', 'music_description', 'duration_seconds', 'user', 'created_at']
    list_filter = ['created_at', 'user', 'duration_seconds']
    search_fields = ['music_name', 'music_description']
    readonly_fields = ['created_at']

    fieldsets = (
        ('기본 정보', {
            'fields': ('music_name', 'music_description', 'duration_seconds', 'user')
        }),
        ('오디오 파일', {
            'fields': ('audio_file',)
        }),
        ('생성일', {
            'fields': ('created_at',)
        }),
    )


@admin.register(BookTag)
class BookTagAdmin(admin.ModelAdmin):
    list_display = ['book', 'tag']
    search_fields = ['book__name', 'tag__name']
    readonly_fields = ['book', 'tag']
    list_filter = ['tag']

    fieldsets = (
        ('도서', { 
            'fields': ('book',)
        }),
        ('태그', {
            'fields': ('tag',)
        }),
    )

from django.contrib import admin
from django.utils.html import format_html
from .models import BookSnap


@admin.register(BookSnap)
class BookSnapAdmin(admin.ModelAdmin):
    list_display = ('id', 'preview_thumb', 'has_video', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('snap_title',)
    readonly_fields = ('created_at', 'preview_thumb')

    fieldsets = (
        ('스냅 미디어', {
            'fields': ("snap_title", 'snap_image', 'snap_video', 'preview_thumb', 'book_link', "book_comment")
        }),
        ('메타 정보', {
            'fields': ('created_at',)
        }),
    )

    # --- 썸네일 미리보기 ---
    def preview_thumb(self, obj):
        """이미지 또는 비디오 썸네일 미리보기"""
        if obj.snap_image:
            return format_html(f'<img src="{obj.snap_image.url}" style="width:120px; height:auto; border-radius:8px;" />')
        if obj.snap_video:
            return format_html(f'''
                <video width="120" style="border-radius:8px;" muted>
                    <source src="{obj.snap_video.url}" type="video/mp4">
                </video>
            ''')
        return "(미디어 없음)"

    preview_thumb.short_description = "미리보기"

    # --- 비디오 여부 표시 ---
    def has_video(self, obj):
        return bool(obj.snap_video)
    has_video.boolean = True  # ✓/× 아이콘으로 표시
    has_video.short_description = "영상 여부"


@admin.register(AuthorAnnouncement)
class AuthorAnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'book', 'author', 'is_pinned', 'created_at']
    list_filter = ['is_pinned', 'created_at', 'book']
    search_fields = ['title', 'content', 'book__name', 'author__nickname']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('공지사항 정보', {
            'fields': ('book', 'author', 'title', 'content', 'is_pinned')
        }),
        ('날짜 정보', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(AudioBookGuide)
class AudioBookGuideAdmin(admin.ModelAdmin):

    list_display = ['title', 'category','guide_video', 'is_active', 'order_num', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['title', 'short_description', 'description', 'tags']

    readonly_fields = ['created_at', 'updated_at', 'preview_image']

    fieldsets = (
        ('기본 정보', {
            'fields': (
                'title',
                'short_description',
                'thumbnail',
                'preview_image',
            )
        }),

        ('컨텐츠 정보', {
            'fields': (
                'description',
                'attachment',
                "guide_video",
            ),
            'classes': ('category-content',)
        }),

        ('분류 및 옵션', {
            'fields': (
                'category',
                'tags',
                'order_num',
                'is_active',
            )
        }),

        ('날짜 정보', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

    class Media:
        js = ('admin/js/guide_category.js',)  # JS 주입

    def preview_image(self, obj):
        if obj.title:
            return format_html(
                '<img src="{}" style="width: 120px; height:auto; border-radius:8px;" />',
                obj.title.url
            )
        return "이미지 없음"

    preview_image.short_description = "이미지 미리보기"


# 🔑 API Key Admin
@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['key_preview', 'name', 'user', 'is_active', 'created_at', 'last_used_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'user__nickname', 'key']
    readonly_fields = ['key', 'created_at', 'last_used_at']

    fieldsets = (
        ('API Key 정보', {
            'fields': ('user', 'name', 'key', 'is_active')
        }),
        ('사용 정보', {
            'fields': ('created_at', 'last_used_at')
        }),
    )

    def key_preview(self, obj):
        """API Key 일부만 표시"""
        return f"{obj.key[:20]}..."
    key_preview.short_description = "API Key"

    def save_model(self, request, obj, form, change):
        """새로 생성할 때 자동으로 Key 생성"""
        if not change:  # 새로 생성하는 경우
            import secrets
            obj.key = secrets.token_urlsafe(48)
        super().save_model(request, obj, form, change)


# 팔로우 Admin
@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ['follower', 'following', 'created_at']
    list_filter = ['created_at']
    search_fields = ['follower__nickname', 'following__nickname']
    readonly_fields = ['created_at']

    fieldsets = (
        ('팔로우 관계', {
            'fields': ('follower', 'following')
        }),
        ('생성일', {
            'fields': ('created_at',)
        }),
    )


# 북마크 Admin
@admin.register(BookmarkBook)
class BookmarkBookAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'created_at', 'has_note']
    list_filter = ['created_at']
    search_fields = ['user__nickname', 'book__name']
    readonly_fields = ['created_at']

    fieldsets = (
        ('북마크 정보', {
            'fields': ('user', 'book', 'note')
        }),
        ('생성일', {
            'fields': ('created_at',)
        }),
    )

    def has_note(self, obj):
        return bool(obj.note)
    has_note.boolean = True
    has_note.short_description = "메모 있음"





from django.contrib import admin
from character.models import ArchivedConversation

@admin.register(ArchivedConversation)
class ArchivedConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "llm", "original_conversation_id", "archived_at")
    search_fields = ("user__username", "llm__name", "original_conversation_id")
    ordering = ("-archived_at",)
    readonly_fields = ("id", "user", "llm", "original_conversation_id", "user_text", "assistant_text", "messages", "state", "archived_at")

    fieldsets = (
        ("기본 정보", {
            "fields": ("id", "user", "llm", "original_conversation_id", "archived_at"),
        }),
        ("대화 내용", {
            "fields": ("user_text", "assistant_text", "messages", "state"),
            "description": (
                "사용자가 삭제한 Conversation과 관련된 메시지, 상태를 포함합니다.\n"
                "messages 필드는 JSON 형태로 모든 메시지 기록을 저장합니다.\n"
                "state 필드는 ConversationState 정보를 JSON으로 저장합니다.\n"
                "오디오 URL도 messages 내에 포함되어 있습니다."
            ),
        }),
    )
