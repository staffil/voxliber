from django.contrib import admin
from .models import Genres, Tags, Books, BookTag, Content, BookReview, BookComment, ContentComment, ReadingProgress, VoiceList, SoundEffectLibrary, BackgroundMusicLibrary, BookSnap, AuthorAnnouncement, AudioBookGuide, APIKey


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
    list_display = ['title', 'book', 'number', 'created_at']
    list_filter = ['book', 'created_at']
    search_fields = ['title', 'book__name']


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


@admin.register(VoiceList)
class VoiceListAdmin(admin.ModelAdmin):
    list_display = ['voice_name', 'voice_id', 'language_code', 'created_at', 'get_types']
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
                'guide_image',
                'thumbnail',
                'preview_image',
            )
        }),

        ('컨텐츠 정보', {
            'fields': (
                'description',
                'video_url',
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
        if obj.guide_image:
            return format_html(
                '<img src="{}" style="width: 120px; height:auto; border-radius:8px;" />',
                obj.guide_image.url
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