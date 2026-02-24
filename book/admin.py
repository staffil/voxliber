from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render as dj_render
from django.db.models import Avg, Count, Q, Sum

from .models import (
    Genres, Tags, Books, BookTag, Content, BookReview, BookComment,
    ContentComment, ReadingProgress, VoiceList, SoundEffectLibrary,
    BackgroundMusicLibrary, BookSnap, AuthorAnnouncement, AudioBookGuide,
    APIKey, VoiceType, Follow, BookmarkBook,
    GenrePlaylist, PlaylistItem,
    ListeningHistory, ContentBookmark, EpisodeSummary,
    BookSnippet, MyVoiceList, Merchandise, Poem_list,
)
from character.models import HPImageMapping


# =====================================================
# 장르
# =====================================================
@admin.register(Genres)
class GenresAdmin(admin.ModelAdmin):
    list_display = ['name', 'genres_color', 'color_preview']
    search_fields = ['name']

    def color_preview(self, obj):
        return format_html(
            '<span style="display:inline-block; width:24px; height:24px; '
            'border-radius:4px; background:{}; border:1px solid rgba(0,0,0,0.1);"></span>',
            obj.genres_color or '#ccc'
        )
    color_preview.short_description = '색상 미리보기'


# =====================================================
# 태그
# =====================================================
@admin.register(Tags)
class TagsAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    search_fields = ['name', 'slug']


# =====================================================
# 책
# =====================================================
@admin.register(Books)
class BooksAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'book_score', 'status', 'created_at']
    list_filter = ['created_at', 'genres', 'status']
    search_fields = ['name', 'user__nickname']
    filter_horizontal = ['genres']


# =====================================================
# 에피소드
# =====================================================
@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = ['title', 'book', 'number', 'get_is_deleted', 'created_at', 'deleted_at']
    list_filter = ['book', 'is_deleted', 'created_at']
    search_fields = ['title', 'book__name']
    readonly_fields = ['created_at', 'deleted_at']

    def get_is_deleted(self, obj):
        return obj.is_deleted
    get_is_deleted.boolean = True
    get_is_deleted.short_description = '삭제됨'


# =====================================================
# 리뷰
# =====================================================
@admin.register(BookReview)
class BookReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__nickname', 'book__name']


# =====================================================
# 독서 진행
# =====================================================
@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'last_read_content_number', 'status', 'get_progress_percentage', 'is_favorite', 'last_read_at']
    list_filter = ['status', 'is_favorite', 'started_at', 'completed_at']
    search_fields = ['user__nickname', 'book__name']
    readonly_fields = ['started_at', 'last_read_at', 'completed_at']

    def get_progress_percentage(self, obj):
        return f"{obj.get_progress_percentage()}%"
    get_progress_percentage.short_description = '진행률'


# =====================================================
# 보이스
# =====================================================
@admin.register(VoiceList)
class VoiceListAdmin(admin.ModelAdmin):
    list_display = ['voice_name', 'voice_id', 'language_code', 'get_types', 'created_at']
    list_filter = ['language_code', 'created_at', 'types']
    search_fields = ['voice_name', 'voice_id']
    readonly_fields = ['created_at']
    filter_horizontal = ['types']

    fieldsets = (
        ('기본 정보', {'fields': ('voice_name', 'voice_id', 'language_code', 'types')}),
        ('상세 정보', {'fields': ('voice_description', 'sample_audio', 'voice_image')}),
        ('생성일',   {'fields': ('created_at',)}),
    )

    def get_types(self, obj):
        return ", ".join([t.name for t in obj.types.all()])
    get_types.short_description = '음성 유형'


@admin.register(VoiceType)
class VoiceTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']
    ordering = ['id']
    readonly_fields = ['id']


# =====================================================
# HP 이미지 매핑
# =====================================================
@admin.register(HPImageMapping)
class HPImageMappingAdmin(admin.ModelAdmin):
    list_display = ['llm', 'min_hp', 'max_hp', 'sub_image', 'priority', 'note', 'created_at']
    list_filter = ['llm', 'created_at']
    search_fields = ['llm__name', 'note', 'extra_condition']
    ordering = ['-priority', 'min_hp', 'max_hp']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('기본 매핑 정보', {'fields': ('llm', ('min_hp', 'max_hp'), 'priority')}),
        ('이미지 설정',   {'fields': ('sub_image',)}),
        ('추가 조건',     {'fields': ('extra_condition', 'note')}),
        ('시스템 정보',   {'fields': ('created_at', 'updated_at')}),
    )


# =====================================================
# 사운드 이펙트 / 배경음
# =====================================================
@admin.register(SoundEffectLibrary)
class SoundEffectLibraryAdmin(admin.ModelAdmin):
    list_display = ['effect_name', 'effect_description', 'user', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['effect_name', 'effect_description']
    readonly_fields = ['created_at']

    fieldsets = (
        ('기본 정보', {'fields': ('effect_name', 'effect_description', 'user')}),
        ('오디오 파일', {'fields': ('audio_file',)}),
        ('생성일',      {'fields': ('created_at',)}),
    )


@admin.register(BackgroundMusicLibrary)
class BackgroundMusicLibraryAdmin(admin.ModelAdmin):
    list_display = ['music_name', 'music_description', 'duration_seconds', 'user', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['music_name', 'music_description']
    readonly_fields = ['created_at']

    fieldsets = (
        ('기본 정보', {'fields': ('music_name', 'music_description', 'duration_seconds', 'user')}),
        ('오디오 파일', {'fields': ('audio_file',)}),
        ('생성일',      {'fields': ('created_at',)}),
    )


# =====================================================
# 북 태그
# =====================================================
@admin.register(BookTag)
class BookTagAdmin(admin.ModelAdmin):
    list_display = ['book', 'tag']
    search_fields = ['book__name', 'tag__name']
    readonly_fields = ['book', 'tag']
    list_filter = ['tag']

    fieldsets = (
        ('도서', {'fields': ('book',)}),
        ('태그', {'fields': ('tag',)}),
    )


# =====================================================
# 북 스냅
# =====================================================
@admin.register(BookSnap)
class BookSnapAdmin(admin.ModelAdmin):
    list_display = ['id', 'snap_title', 'preview_thumb', 'has_video', 'created_at']
    list_filter = ['created_at']
    search_fields = ['snap_title']
    readonly_fields = ['created_at', 'preview_thumb']

    fieldsets = (
        ('스냅 미디어', {'fields': ('snap_title', 'snap_video', 'thumbnail', 'preview_thumb', 'book_link', 'book_comment')}),
        ('메타 정보',   {'fields': ('created_at',)}),
    )

    def preview_thumb(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="width:120px; border-radius:8px;" />', obj.thumbnail.url)
        if obj.snap_video:
            return format_html(
                '<video width="120" style="border-radius:8px;" muted>'
                '<source src="{}" type="video/mp4"></video>',
                obj.snap_video.url
            )
        return "(미디어 없음)"
    preview_thumb.short_description = '미리보기'

    def has_video(self, obj):
        return bool(obj.snap_video)
    has_video.boolean = True
    has_video.short_description = '영상 여부'


# =====================================================
# 작가 공지사항
# =====================================================
@admin.register(AuthorAnnouncement)
class AuthorAnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'book', 'author', 'is_pinned', 'created_at']
    list_filter = ['is_pinned', 'created_at', 'book']
    search_fields = ['title', 'content', 'book__name', 'author__nickname']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('공지사항 정보', {'fields': ('book', 'author', 'title', 'content', 'is_pinned')}),
        ('날짜 정보',     {'fields': ('created_at', 'updated_at')}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)


# =====================================================
# 오디오북 가이드
# =====================================================
@admin.register(AudioBookGuide)
class AudioBookGuideAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'guide_video', 'is_active', 'order_num', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['title', 'short_description', 'description', 'tags']
    readonly_fields = ['created_at', 'updated_at', 'preview_image']

    fieldsets = (
        ('기본 정보',     {'fields': ('title', 'short_description', 'thumbnail', 'preview_image')}),
        ('콘텐츠 정보',  {'fields': ('description', 'attachment', 'guide_video')}),
        ('분류 및 옵션', {'fields': ('category', 'tags', 'order_num', 'is_active')}),
        ('날짜 정보',    {'fields': ('created_at', 'updated_at')}),
    )

    class Media:
        js = ('admin/js/guide_category.js',)

    def preview_image(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="width:120px; border-radius:8px;" />', obj.thumbnail.url)
        return '이미지 없음'
    preview_image.short_description = '이미지 미리보기'


# =====================================================
# API Key
# =====================================================
@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['key_preview', 'name', 'user', 'is_active', 'created_at', 'last_used_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'user__nickname', 'key']
    readonly_fields = ['key', 'created_at', 'last_used_at']

    fieldsets = (
        ('API Key 정보', {'fields': ('user', 'name', 'key', 'is_active')}),
        ('사용 정보',    {'fields': ('created_at', 'last_used_at')}),
    )

    def key_preview(self, obj):
        return f"{obj.key[:20]}..."
    key_preview.short_description = 'API Key'

    def save_model(self, request, obj, form, change):
        if not change:
            import secrets
            obj.key = secrets.token_urlsafe(48)
        super().save_model(request, obj, form, change)


# =====================================================
# 팔로우
# =====================================================
@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ['follower', 'following', 'created_at']
    list_filter = ['created_at']
    search_fields = ['follower__nickname', 'following__nickname']
    readonly_fields = ['created_at']

    fieldsets = (
        ('팔로우 관계', {'fields': ('follower', 'following')}),
        ('생성일',      {'fields': ('created_at',)}),
    )


# =====================================================
# 북마크
# =====================================================
@admin.register(BookmarkBook)
class BookmarkBookAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'created_at', 'has_note']
    list_filter = ['created_at']
    search_fields = ['user__nickname', 'book__name']
    readonly_fields = ['created_at']

    fieldsets = (
        ('북마크 정보', {'fields': ('user', 'book', 'note')}),
        ('생성일',      {'fields': ('created_at',)}),
    )

    def has_note(self, obj):
        return bool(obj.note)
    has_note.boolean = True
    has_note.short_description = '메모 있음'


# =====================================================
# 청취 기록
# =====================================================
@admin.register(ListeningHistory)
class ListeningHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'content', 'listened_seconds_fmt', 'last_position_fmt', 'last_listened_at']
    list_filter  = ['last_listened_at', 'book']
    search_fields = ['user__nickname', 'book__name', 'content__title']
    readonly_fields = ['listened_at', 'last_listened_at']
    date_hierarchy = 'last_listened_at'

    def listened_seconds_fmt(self, obj):
        m, s = divmod(obj.listened_seconds, 60)
        return f"{m}분 {s}초"
    listened_seconds_fmt.short_description = '청취 시간'

    def last_position_fmt(self, obj):
        m, s = divmod(int(obj.last_position), 60)
        return f"{m}:{s:02d}"
    last_position_fmt.short_description = '마지막 위치'


# =====================================================
# 콘텐츠 북마크/메모
# =====================================================
@admin.register(ContentBookmark)
class ContentBookmarkAdmin(admin.ModelAdmin):
    list_display = ['user', 'content', 'position_fmt', 'has_memo', 'created_at']
    list_filter  = ['created_at']
    search_fields = ['user__nickname', 'content__title', 'memo']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('북마크 정보', {'fields': ('user', 'content', 'position', 'memo')}),
        ('날짜',        {'fields': ('created_at', 'updated_at')}),
    )

    def position_fmt(self, obj):
        return obj.get_position_formatted()
    position_fmt.short_description = '위치'

    def has_memo(self, obj):
        return bool(obj.memo)
    has_memo.boolean = True
    has_memo.short_description = '메모 있음'


# =====================================================
# 에피소드 요약
# =====================================================
@admin.register(EpisodeSummary)
class EpisodeSummaryAdmin(admin.ModelAdmin):
    list_display = ['content', 'has_summary', 'created_at', 'updated_at']
    list_filter  = ['created_at']
    search_fields = ['content__title', 'summary_text']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('요약 정보', {'fields': ('content', 'summary_text')}),
        ('날짜',      {'fields': ('created_at', 'updated_at')}),
    )

    def has_summary(self, obj):
        return bool(obj.summary_text)
    has_summary.boolean = True
    has_summary.short_description = '요약 있음'


# =====================================================
# 북 스니펫
# =====================================================
@admin.register(BookSnippet)
class BookSnippetAdmin(admin.ModelAdmin):
    list_display = ['book', 'sentence_preview', 'has_audio', 'created_at']
    list_filter  = ['created_at', 'book']
    search_fields = ['book__name', 'sentence']
    readonly_fields = ['created_at']

    fieldsets = (
        ('스니펫 정보', {'fields': ('book', 'sentence', 'audio_file', 'link')}),
        ('날짜',        {'fields': ('created_at',)}),
    )

    def sentence_preview(self, obj):
        return obj.sentence[:50] + '...' if len(obj.sentence) > 50 else obj.sentence
    sentence_preview.short_description = '문장 미리보기'

    def has_audio(self, obj):
        return bool(obj.audio_file)
    has_audio.boolean = True
    has_audio.short_description = '오디오 있음'


# =====================================================
# 개인 목소리 목록
# =====================================================
@admin.register(MyVoiceList)
class MyVoiceListAdmin(admin.ModelAdmin):
    list_display = ['user', 'voice', 'book', 'alias_name', 'is_favorite', 'created_at']
    list_filter  = ['is_favorite', 'created_at']
    search_fields = ['user__nickname', 'alias_name', 'voice__voice_name']
    readonly_fields = ['created_at']

    fieldsets = (
        ('목소리 정보', {'fields': ('user', 'voice', 'book', 'alias_name', 'is_favorite')}),
        ('날짜',        {'fields': ('created_at',)}),
    )


# =====================================================
# 굿즈
# =====================================================
@admin.register(Merchandise)
class MerchandiseAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_fmt', 'is_new', 'preview_img', 'created_at']
    list_filter  = ['is_new', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'preview_img']

    fieldsets = (
        ('상품 정보', {'fields': ('name', 'description', 'price', 'link', 'is_new')}),
        ('이미지',    {'fields': ('image', 'preview_img')}),
        ('날짜',      {'fields': ('created_at',)}),
    )

    def price_fmt(self, obj):
        return f"₩{obj.price:,}"
    price_fmt.short_description = '가격'

    def preview_img(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width:80px; border-radius:6px;" />', obj.image.url)
        return '이미지 없음'
    preview_img.short_description = '미리보기'


# =====================================================
# 시 공모전 출품작
# =====================================================
@admin.register(Poem_list)
class PoemListAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'is_public', 'has_audio', 'created_at']
    list_filter  = ['status', 'is_public', 'created_at']
    search_fields = ['title', 'content', 'user__nickname']
    readonly_fields = ['created_at', 'updated_at', 'preview_img']
    actions = ['mark_as_winner']

    fieldsets = (
        ('출품 정보',  {'fields': ('user', 'title', 'content')}),
        ('미디어',     {'fields': ('image', 'preview_img', 'poem_audio')}),
        ('상태',       {'fields': ('status', 'is_public')}),
        ('날짜',       {'fields': ('created_at', 'updated_at')}),
    )

    def has_audio(self, obj):
        return bool(obj.poem_audio)
    has_audio.boolean = True
    has_audio.short_description = '오디오 있음'

    def preview_img(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width:100px; border-radius:6px;" />', obj.image.url)
        return '이미지 없음'
    preview_img.short_description = '이미지 미리보기'

    @admin.action(description='🏆 수상작으로 선정')
    def mark_as_winner(self, request, queryset):
        n = queryset.update(status='winner')
        self.message_user(request, f'🏆 {n}개 작품을 수상작으로 선정했습니다.')


# =====================================================
# 🎵 장르 플레이리스트 - 유틸 함수
# =====================================================
def calc_episode_score(content_id, duration_seconds=1):
    import math
    stats = ListeningHistory.objects.filter(content_id=content_id).aggregate(
        listeners=Count('user', distinct=True),
        avg_pos=Avg('last_position'),
    )
    comments    = ContentComment.objects.filter(content_id=content_id, is_deleted=False).count()
    listeners   = stats['listeners'] or 0
    avg_pos     = stats['avg_pos'] or 0
    duration    = duration_seconds or 1
    completion  = min(avg_pos / duration, 1.0) * 100
    listener_sc = min(math.log1p(listeners) / math.log1p(500) * 100, 100)
    comment_sc  = min(math.log1p(comments)  / math.log1p(100) * 100, 100)
    return round(listener_sc * 0.4 + completion * 0.4 + comment_sc * 0.2, 1)


# ─────────────────────────────────────────────────────
# 인라인 폼
# ─────────────────────────────────────────────────────
class PlaylistItemForm(forms.ModelForm):
    class Meta:
        model = PlaylistItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Content.objects.filter(
            is_deleted=False, duration_seconds__gt=0,
        ).select_related('book').order_by('book__name', 'number')
        self.fields['content'].queryset = qs
        self.fields['content'].label = '에피소드'
        self.fields['content'].label_from_instance = self._label

    @staticmethod
    def _label(obj):
        m, s = obj.duration_seconds // 60, obj.duration_seconds % 60
        return f"[{obj.book.name}]  {obj.number}화 · {obj.title}  ({m}:{s:02d})"


class PlaylistItemInline(admin.TabularInline):
    model = PlaylistItem
    form = PlaylistItemForm
    extra = 1
    fields = ['order', 'content', 'book_cover_cell', 'book_info_cell', 'stats_cell', 'added_at']
    readonly_fields = ['book_cover_cell', 'book_info_cell', 'stats_cell', 'added_at']
    ordering = ['order']

    def book_cover_cell(self, obj):
        if not obj.pk or not obj.content_id:
            return '-'
        book = obj.content.book
        if book.cover_img:
            return format_html(
                '<img src="{}" style="width:44px;height:60px;object-fit:cover;'
                'border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,0.2);" />',
                book.cover_img.url
            )
        return format_html(
            '<div style="width:44px;height:60px;border-radius:4px;background:#e0e0f0;'
            'display:flex;align-items:center;justify-content:center;font-size:1.2rem;">📖</div>'
        )
    book_cover_cell.short_description = '표지'

    def book_info_cell(self, obj):
        if not obj.pk or not obj.content_id:
            return '-'
        c = obj.content
        m, s = c.duration_seconds // 60, c.duration_seconds % 60
        return format_html(
            '<div style="line-height:1.7;">'
            '<div style="font-weight:700;font-size:0.85rem;">{}</div>'
            '<div style="font-size:0.78rem;color:#6366f1;font-weight:600;">📖 {}</div>'
            '<div style="font-size:0.75rem;color:#888;">{}화 · {}:{:02d}</div>'
            '<a href="/admin/book/content/{}/change/" target="_blank"'
            '   style="font-size:0.72rem;color:#aaa;">↗ 상세</a>'
            '</div>',
            c.title, c.book.name, c.number, m, s, c.pk,
        )
    book_info_cell.short_description = '책 · 에피소드'

    def stats_cell(self, obj):
        if not obj.pk or not obj.content_id:
            return '-'
        c = obj.content
        stats = ListeningHistory.objects.filter(content_id=c.pk).aggregate(
            listeners=Count('user', distinct=True),
            avg_pos=Avg('last_position'),
        )
        comments   = ContentComment.objects.filter(content_id=c.pk, is_deleted=False).count()
        listeners  = stats['listeners'] or 0
        avg_pos    = stats['avg_pos'] or 0
        completion = min(int(avg_pos / (c.duration_seconds or 1) * 100), 100)
        score      = calc_episode_score(c.pk, c.duration_seconds)
        bar_color   = '#22c55e' if completion >= 70 else '#f59e0b' if completion >= 40 else '#ef4444'
        score_color = '#6366f1' if score >= 60 else '#f59e0b' if score >= 30 else '#94a3b8'

        return format_html(
            '<div style="font-size:0.75rem;line-height:2.1;min-width:140px;">'
            '<div style="margin-bottom:5px;">'
            '<span style="background:{sc};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-weight:700;font-size:0.8rem;">★ {}점</span>'
            '</div>'
            '<div>👥 청취자 <b style="color:#1d4ed8;">{}명</b></div>'
            '<div style="display:flex;align-items:center;gap:5px;">'
            '⏱ 완료율 <b>{}%</b>'
            '<div style="width:55px;height:5px;background:#e5e7eb;border-radius:3px;overflow:hidden;">'
            '<div style="width:{}%;height:100%;background:{bar};border-radius:3px;"></div>'
            '</div></div>'
            '<div>💬 댓글 <b style="color:#059669;">{}개</b></div>'
            '</div>',
            score, listeners, completion, completion,
            sc=score_color, bar=bar_color,
        )
    stats_cell.short_description = '유저 반응 지표'


# =====================================================
# 📊 에피소드 인기 랭킹 뷰
# =====================================================
class EpisodeRankingView(View):
    template_name = 'admin/book/episode_ranking.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        import math
        genre_id = request.GET.get('genre')
        genres   = Genres.objects.all()
        rows     = []

        if genre_id:
            contents = (
                Content.objects
                .filter(book__genres__id=genre_id, is_deleted=False, duration_seconds__gt=0)
                .select_related('book')
                .annotate(
                    listener_count=Count('listening_stats__user', distinct=True),
                    avg_position=Avg('listening_stats__last_position'),
                    comment_count=Count('comments', filter=Q(comments__is_deleted=False)),
                )
            )
            for c in contents:
                duration   = c.duration_seconds or 1
                avg_pos    = c.avg_position or 0
                listeners  = c.listener_count or 0
                comments   = c.comment_count or 0
                completion = min(int(avg_pos / duration * 100), 100)
                listener_sc = min(math.log1p(listeners) / math.log1p(500) * 100, 100)
                comment_sc  = min(math.log1p(comments)  / math.log1p(100) * 100, 100)
                score = round(listener_sc * 0.4 + completion * 0.4 + comment_sc * 0.2, 1)
                rows.append({
                    'content': c, 'book': c.book,
                    'listeners': listeners, 'completion': completion,
                    'comments': comments, 'score': score,
                })
            rows.sort(key=lambda x: x['score'], reverse=True)

        context = {
            **admin.site.each_context(request),
            'title':    '에피소드 인기 랭킹',
            'genres':   genres,
            'genre_id': int(genre_id) if genre_id else None,
            'rows':     rows,
            'opts':     Content._meta,
        }
        return dj_render(request, self.template_name, context)


# =====================================================
# 🎧 청취 기록 통계 뷰
# =====================================================
class ListeningStatsView(View):
    template_name = 'admin/book/listening_stats.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta

        period_choices = [('7', '7일'), ('30', '30일'), ('90', '90일'), ('365', '1년')]
        period = request.GET.get('period', '7')
        days   = int(period)
        since  = timezone.now() - timedelta(days=days)

        total = ListeningHistory.objects.filter(last_listened_at__gte=since).aggregate(
            total_users=Count('user', distinct=True),
            total_seconds=Sum('listened_seconds'),
            total_sessions=Count('id'),
        )
        top_books = (
            ListeningHistory.objects.filter(last_listened_at__gte=since)
            .values('book__name', 'book__id')
            .annotate(listeners=Count('user', distinct=True), total_sec=Sum('listened_seconds'))
            .order_by('-listeners')[:10]
        )
        top_episodes = (
            ListeningHistory.objects.filter(last_listened_at__gte=since, content__isnull=False)
            .values('content__title', 'content__id', 'content__book__name')
            .annotate(listeners=Count('user', distinct=True), avg_pos=Avg('last_position'))
            .order_by('-listeners')[:10]
        )
        daily = []
        for i in range(days - 1, -1, -1):
            day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
            day_end   = day_start + timedelta(days=1)
            cnt = ListeningHistory.objects.filter(
                last_listened_at__gte=day_start, last_listened_at__lt=day_end,
            ).values('user').distinct().count()
            daily.append({'date': day_start.strftime('%m/%d'), 'count': cnt})

        total_sec = total['total_seconds'] or 0
        context = {
            **admin.site.each_context(request),
            'title':          '청취 기록 통계',
            'period':         period,
            'period_choices': period_choices,
            'total_users':    total['total_users'] or 0,
            'total_hours':    total_sec // 3600,
            'total_minutes':  (total_sec % 3600) // 60,
            'total_sessions': total['total_sessions'] or 0,
            'top_books':      top_books,
            'top_episodes':   top_episodes,
            'daily':          daily,
            'opts':           ListeningHistory._meta,
        }
        return dj_render(request, self.template_name, context)


# =====================================================
# 🎵 장르 플레이리스트
# =====================================================
@admin.register(GenrePlaylist)
class GenrePlaylistAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'genre', 'playlist_type_badge',
        'item_count', 'is_active', 'is_auto_generated',
        'updated_at', 'ranking_link',
    ]
    list_filter   = ['genre', 'playlist_type', 'is_active', 'is_auto_generated']
    search_fields = ['title', 'genre__name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'item_count', 'playlist_preview']
    list_editable = ['is_active', 'is_auto_generated']
    ordering = ['genre__name', 'playlist_type']
    inlines = [PlaylistItemInline]

    fieldsets = (
        ('기본 정보', {
            'fields': ('genre', 'playlist_type', 'title', 'description', 'cover_img'),
        }),
        ('설정', {
            'fields': ('is_active', 'is_auto_generated'),
            'description': (
                '✅ <b>is_auto_generated = ON</b> → 매일 새벽 자동 갱신 (수동 수정 덮어써짐)<br>'
                '🔒 <b>is_auto_generated = OFF</b> → 자동 갱신 스킵, 관리자가 직접 관리<br>'
                '💡 에피소드 선정 참고: <a href="/admin/book/episode-ranking/" target="_blank">'
                '장르별 에피소드 인기 랭킹 보기 →</a> &nbsp;|&nbsp; '
                '<a href="/admin/book/listening-stats/" target="_blank">🎧 청취 통계 →</a>'
            ),
        }),
        ('현재 구성', {
            'fields': ('item_count', 'playlist_preview'),
            'classes': ('collapse',),
        }),
        ('날짜', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def playlist_type_badge(self, obj):
        MAP = {
            'popular': ('🔥', '#ef4444'), 'new': ('🆕', '#3b82f6'),
            'short':   ('⚡', '#f59e0b'), 'rated': ('⭐', '#8b5cf6'),
            'night':   ('🌙', '#6366f1'), 'custom': ('✨', '#10b981'),
        }
        emoji, color = MAP.get(obj.playlist_type, ('🎵', '#6b7280'))
        return format_html(
            '<span style="padding:3px 10px;border-radius:12px;font-size:0.78rem;'
            'font-weight:600;background:{}22;color:{};">{} {}</span>',
            color, color, emoji, obj.get_playlist_type_display()
        )
    playlist_type_badge.short_description = '유형'

    def item_count(self, obj):
        count = obj.items.count()
        return format_html('<b style="color:#6366f1;">{}화</b>', count)
    item_count.short_description = '에피소드 수'

    def ranking_link(self, obj):
        return format_html(
            '<a href="/admin/book/episode-ranking/?genre={}" target="_blank" '
            'style="padding:3px 8px;border-radius:5px;font-size:0.75rem;'
            'background:#f0f0ff;color:#6366f1;text-decoration:none;border:1px solid #c7d2fe;">'
            '📊 랭킹 보기</a>',
            obj.genre_id
        )
    ranking_link.short_description = '랭킹'

    def playlist_preview(self, obj):
        items = obj.items.select_related('content__book').order_by('order')[:10]
        if not items:
            return format_html('<p style="color:#999;font-size:0.85rem;">에피소드가 없습니다.</p>')
        rows_html = []
        for item in items:
            c = item.content
            m, s = c.duration_seconds // 60, c.duration_seconds % 60
            score = calc_episode_score(c.pk, c.duration_seconds)
            cover = ''
            if c.book.cover_img:
                cover = format_html(
                    '<img src="{}" style="width:32px;height:44px;object-fit:cover;'
                    'border-radius:3px;flex-shrink:0;" />', c.book.cover_img.url
                )
            rows_html.append(format_html(
                '<div style="display:flex;align-items:center;gap:10px;'
                'padding:7px;border-radius:6px;background:#f8f8ff;margin-bottom:3px;">'
                '<span style="width:18px;text-align:center;font-size:0.72rem;color:#aaa;">{}</span>'
                '{}'
                '<div style="flex:1;min-width:0;">'
                '<div style="font-size:0.82rem;font-weight:700;white-space:nowrap;'
                'overflow:hidden;text-overflow:ellipsis;">{}</div>'
                '<div style="font-size:0.72rem;color:#6366f1;">📖 {} &nbsp;·&nbsp; {}화 &nbsp;·&nbsp; {}:{:02d}</div>'
                '</div>'
                '<span style="background:#6366f166;color:#fff;padding:1px 6px;'
                'border-radius:8px;font-size:0.72rem;font-weight:700;white-space:nowrap;">'
                '★ {}</span></div>',
                item.order + 1, cover, c.title, c.book.name, c.number, m, s, score,
            ))
        total = obj.items.count()
        more = format_html(
            '<p style="font-size:0.75rem;color:#6366f1;margin-top:4px;">+ {}개 더 있음</p>',
            total - 10
        ) if total > 10 else ''
        return format_html(
            '<div style="max-width:520px;">{}{}</div>',
            format_html(''.join(str(r) for r in rows_html)), more
        )
    playlist_preview.short_description = '현재 구성'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not obj.is_auto_generated:
            self.message_user(
                request,
                f'🔒 [{obj.title}] 수동 관리 모드 — 자동 갱신이 스킵됩니다.',
                level='WARNING'
            )

    actions = ['enable_auto', 'disable_auto', 'refresh_now']

    @admin.action(description='✅ 자동 갱신 ON')
    def enable_auto(self, request, queryset):
        n = queryset.update(is_auto_generated=True)
        self.message_user(request, f'{n}개 플레이리스트 자동 갱신 ON으로 변경했습니다.')

    @admin.action(description='🔒 자동 갱신 OFF (수동 관리)')
    def disable_auto(self, request, queryset):
        n = queryset.update(is_auto_generated=False)
        self.message_user(request, f'{n}개 플레이리스트 수동 관리로 변경했습니다.', level='WARNING')

    @admin.action(description='🔄 즉시 갱신 (점수 기반 자동생성 항목만)')
    def refresh_now(self, request, queryset):
        import math
        from django.utils import timezone
        from datetime import timedelta

        refreshed = 0
        for playlist in queryset.filter(is_auto_generated=True):
            genre = playlist.genre
            ptype = playlist.playlist_type
            base_qs = Content.objects.filter(
                book__genres=genre, is_deleted=False, duration_seconds__gt=0,
            ).select_related('book').annotate(
                listener_count=Count('listening_stats__user', distinct=True),
                avg_position=Avg('listening_stats__last_position'),
                comment_count=Count('comments', filter=Q(comments__is_deleted=False)),
            )
            if ptype == 'new':
                base_qs = base_qs.filter(created_at__gte=timezone.now() - timedelta(days=30))
            elif ptype == 'short':
                base_qs = base_qs.filter(duration_seconds__lte=600)
            elif ptype == 'rated':
                base_qs = base_qs.filter(book__book_score__gte=4.0)

            scored = []
            for c in base_qs:
                dur = c.duration_seconds or 1
                avg_pos = c.avg_position or 0
                listeners = c.listener_count or 0
                comments = c.comment_count or 0
                completion = min(avg_pos / dur, 1.0) * 100
                ls = min(math.log1p(listeners) / math.log1p(500) * 100, 100)
                cs = min(math.log1p(comments)  / math.log1p(100) * 100, 100)
                score = ls * 0.4 + completion * 0.4 + cs * 0.2
                scored.append((score, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            top_contents = [c for _, c in scored[:30]]

            playlist.items.all().delete()
            PlaylistItem.objects.bulk_create([
                PlaylistItem(playlist=playlist, content=c, order=i)
                for i, c in enumerate(top_contents)
            ])
            refreshed += 1
        self.message_user(request, f'🎵 {refreshed}개 플레이리스트를 점수 기반으로 갱신했습니다.')


# =====================================================
# 플레이리스트 항목
# =====================================================
@admin.register(PlaylistItem)
class PlaylistItemAdmin(admin.ModelAdmin):
    form = PlaylistItemForm
    list_display = [
        'order', 'book_cover_list', 'book_and_episode',
        'score_badge', 'listeners_col', 'completion_col', 'comments_col',
        'playlist_link', 'added_at',
    ]
    list_filter   = ['playlist__genre', 'playlist__playlist_type', 'playlist']
    search_fields = ['content__title', 'content__book__name', 'playlist__title']
    ordering = ['playlist', 'order']
    readonly_fields = ['added_at']

    fieldsets = (
        ('에피소드 선택', {
            'description': '드롭다운: [책이름] 화수 · 제목 (길이) 형식으로 검색하세요.',
            'fields': ('playlist', 'order', 'content'),
        }),
        ('날짜', {'fields': ('added_at',), 'classes': ('collapse',)}),
    )

    def _get_stats(self, obj):
        c = obj.content
        st = ListeningHistory.objects.filter(content_id=c.pk).aggregate(
            listeners=Count('user', distinct=True),
            avg_pos=Avg('last_position'),
        )
        comments   = ContentComment.objects.filter(content_id=c.pk, is_deleted=False).count()
        listeners  = st['listeners'] or 0
        avg_pos    = st['avg_pos'] or 0
        completion = min(int(avg_pos / (c.duration_seconds or 1) * 100), 100)
        score      = calc_episode_score(c.pk, c.duration_seconds)
        return listeners, completion, comments, score

    def book_cover_list(self, obj):
        if obj.content.book.cover_img:
            return format_html(
                '<img src="{}" style="width:30px;height:42px;object-fit:cover;'
                'border-radius:3px;box-shadow:0 1px 3px rgba(0,0,0,0.2);" />',
                obj.content.book.cover_img.url
            )
        return '📖'
    book_cover_list.short_description = ''

    def book_and_episode(self, obj):
        c = obj.content
        return format_html(
            '<div><div style="font-weight:700;font-size:0.85rem;">{}</div>'
            '<div style="font-size:0.75rem;color:#6366f1;">📖 {} · {}화</div></div>',
            c.title, c.book.name, c.number,
        )
    book_and_episode.short_description = '에피소드 / 책'

    def score_badge(self, obj):
        _, _, _, score = self._get_stats(obj)
        color = '#6366f1' if score >= 60 else '#f59e0b' if score >= 30 else '#94a3b8'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-weight:700;font-size:0.8rem;">★ {}</span>',
            color, score
        )
    score_badge.short_description = '종합점수'

    def listeners_col(self, obj):
        listeners, _, _, _ = self._get_stats(obj)
        return format_html('<b style="color:#1d4ed8;">{}명</b>', listeners)
    listeners_col.short_description = '청취자'

    def completion_col(self, obj):
        _, completion, _, _ = self._get_stats(obj)
        color = '#22c55e' if completion >= 70 else '#f59e0b' if completion >= 40 else '#ef4444'
        return format_html('<span style="color:{}; font-weight:600;">{}%</span>', color, completion)
    completion_col.short_description = '완료율'

    def comments_col(self, obj):
        _, _, comments, _ = self._get_stats(obj)
        return format_html('<b style="color:#059669;">{}개</b>', comments)
    comments_col.short_description = '댓글'

    def playlist_link(self, obj):
        return format_html(
            '<a href="/admin/book/genreplaylist/{}/change/" target="_blank">{}</a>',
            obj.playlist_id, obj.playlist.title
        )
    playlist_link.short_description = '플레이리스트'



import calendar
import json
from datetime import date, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render as dj_render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View



# =====================================================
# 📅 청취 캘린더 뷰  (admin/book/listening-calendar/)
# =====================================================
class ListeningCalendarView(View):
    template_name = 'admin/book/listening_calendar.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        today = timezone.localdate()

        # ── 연/월 파라미터 ──────────────────────────────
        try:
            year = int(request.GET.get('year', today.year))
        except (ValueError, TypeError):
            year = today.year
        try:
            month = int(request.GET.get('month', today.month))
        except (ValueError, TypeError):
            month = today.month

        # 범위 보정
        month = max(1, min(12, month))
        year  = max(2020, min(today.year + 1, year))

        # ── 이전/다음 월 ────────────────────────────────
        first_of_month = date(year, month, 1)
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1

        # ── 이달 전체 집계 ──────────────────────────────
        month_qs = ListeningHistory.objects.filter(
            last_listened_at__year=year,
            last_listened_at__month=month,
        )
        month_agg = month_qs.aggregate(
            total_users=Count('user', distinct=True),
            total_seconds=Sum('listened_seconds'),
            total_sessions=Count('id'),
        )
        total_sec = month_agg['total_seconds'] or 0

        # ── 일별 데이터 ─────────────────────────────────
        # {day: {'count': int, 'sessions': int, 'total_seconds': int, 'books': [...]}}
        _, days_in_month = calendar.monthrange(year, month)
        daily_data = {}

        daily_qs = (
            month_qs
            .values('last_listened_at__day')
            .annotate(
                day_users=Count('user', distinct=True),
                day_sessions=Count('id'),
                day_seconds=Sum('listened_seconds'),
            )
        )
        for row in daily_qs:
            d = row['last_listened_at__day']
            daily_data[d] = {
                'count': row['day_users'],
                'sessions': row['day_sessions'],
                'total_seconds': row['day_seconds'] or 0,
                'books': [],
            }

        # 일별 인기 도서 (상위 5)
        book_daily_qs = (
            month_qs
            .filter(book__isnull=False)
            .values('last_listened_at__day', 'book__name')
            .annotate(cnt=Count('id'))
            .order_by('last_listened_at__day', '-cnt')
        )
        books_by_day = {}
        for row in book_daily_qs:
            d = row['last_listened_at__day']
            books_by_day.setdefault(d, [])
            if len(books_by_day[d]) < 5:
                books_by_day[d].append({'name': row['book__name'], 'cnt': row['cnt']})

        for d, books in books_by_day.items():
            if d in daily_data:
                daily_data[d]['books'] = books

        # ── 최대값 (히트맵 레벨 계산용) ────────────────
        max_count = max((v['count'] for v in daily_data.values()), default=1) or 1

        def level(cnt):
            if cnt == 0: return 0
            ratio = cnt / max_count
            if ratio <= 0.25: return 1
            if ratio <= 0.50: return 2
            if ratio <= 0.75: return 3
            return 4

        # ── 캘린더 셀 구성 ──────────────────────────────
        # calendar.monthrange: (첫날 요일 0=월, ..., 6=일, 일수)
        first_weekday, _ = calendar.monthrange(year, month)  # 0=월

        calendar_cells = []
        for day in range(1, days_in_month + 1):
            cell_date = date(year, month, day)
            # day of week: 0=월 … 6=일
            dow = cell_date.weekday()
            data = daily_data.get(day, {'count': 0, 'sessions': 0, 'total_seconds': 0, 'books': []})
            calendar_cells.append({
                'day': day,
                'date_str': f"{year}년 {month}월 {day}일",
                'dow': dow,
                'is_today': cell_date == today,
                'count': data['count'],
                'sessions': data['sessions'],
                'total_seconds': data['total_seconds'],
                'books': json.dumps(data['books'], ensure_ascii=False),
                'level': level(data['count']),
            })

        # 앞뒤 빈칸 (월요일 시작)
        leading_blanks  = range(first_weekday)           # 0=월이면 빈칸 0개
        trailing_total  = (7 - (first_weekday + days_in_month) % 7) % 7
        trailing_blanks = range(trailing_total)

        # ── 연도 탭 (서비스 시작 연도 ~ 올해) ──────────
        start_year = 2023   # 서비스 오픈 연도로 조정하세요
        year_range = range(start_year, today.year + 1)

        context = {
            **self.admin_site_context(request),
            'title': '청취 캘린더',
            'year': year,
            'month': month,
            'prev_year': prev_year,
            'prev_month': prev_month,
            'next_year': next_year,
            'next_month': next_month,
            'year_range': list(year_range),
            'calendar_cells': calendar_cells,
            'leading_blanks': leading_blanks,
            'trailing_blanks': trailing_blanks,
            # 이달 요약
            'month_total_users': month_agg['total_users'] or 0,
            'month_total_hours': total_sec // 3600,
            'month_total_minutes': (total_sec % 3600) // 60,
            'month_total_sessions': month_agg['total_sessions'] or 0,
            'active_days': len(daily_data),
            'opts': ListeningHistory._meta,
        }
        return dj_render(request, self.template_name, context)

    # admin 공통 context (site 객체 주입)
    def admin_site_context(self, request):
        from django.contrib import admin as django_admin
        return django_admin.site.each_context(request)
    







import json
from datetime import timedelta

from django.contrib import admin as django_admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, F, Q, Sum
from django.shortcuts import render as dj_render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from character.models import (
    Conversation,
    ConversationMessage,
    LLM,
    LLMLike,
    Story,
    StoryLike,
    StoryComment,
    Report,
)


# =====================================================
# 🤖 캐릭터 & TTS 통계 대시보드
# =====================================================
class CharacterStatsView(View):
    template_name = 'admin/character/character_stats.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        today     = timezone.localdate()
        now       = timezone.now()

        # ── 기간 선택 ────────────────────────────────
        period_choices = [('1', '오늘'), ('7', '7일'), ('30', '30일'), ('90', '90일')]
        period = request.GET.get('period', '7')
        days   = int(period)
        since  = now - timedelta(days=days)

        # ══════════════════════════════════════════════
        # 1. TTS 생성 통계
        # ══════════════════════════════════════════════
        tts_qs = ConversationMessage.objects.filter(
            role='assistant',
            audio__isnull=False,
            created_at__gte=since,
            is_deleted=False,
        )

        tts_total_count   = tts_qs.count()
        tts_total_seconds = tts_qs.aggregate(s=Sum('audio_duration'))['s'] or 0
        tts_avg_duration  = tts_qs.aggregate(a=Avg('audio_duration'))['a'] or 0

        # 일별 TTS 생성 수 + 총 초
        daily_tts = []
        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)
            day_qs  = tts_qs.filter(created_at__gte=day_start, created_at__lt=day_end)
            daily_tts.append({
                'date':    day_start.strftime('%m/%d'),
                'count':   day_qs.count(),
                'seconds': round(day_qs.aggregate(s=Sum('audio_duration'))['s'] or 0, 1),
            })

        # ══════════════════════════════════════════════
        # 2. 캐릭터(LLM) 별 좋아요 TOP 20
        # ══════════════════════════════════════════════
        top_llm_likes = (
            LLM.objects
            .annotate(like_cnt=Count('llmlike'))
            .order_by('-like_cnt')
            .values('id', 'name', 'llm_image', 'like_cnt', 'is_public')[:20]
        )

        # 기간 내 새 좋아요 (인기 급상승)
        rising_llms = (
            LLMLike.objects.filter(created_at__gte=since)
            .values('llm__id', 'llm__name', 'llm__llm_image')
            .annotate(new_likes=Count('id'))
            .order_by('-new_likes')[:10]
        )

        # ══════════════════════════════════════════════
        # 3. 캐릭터별 TTS 음성 생성 초 (기간 내)
        # ══════════════════════════════════════════════
        llm_tts_stats = (
            ConversationMessage.objects.filter(
                role='assistant',
                audio__isnull=False,
                created_at__gte=since,
                is_deleted=False,
            )
            .values('conversation__llm__id', 'conversation__llm__name', 'conversation__llm__llm_image')
            .annotate(
                tts_count=Count('id'),
                tts_seconds=Sum('audio_duration'),
            )
            .order_by('-tts_seconds')[:15]
        )

        # ══════════════════════════════════════════════
        # 4. 인기 스토리 TOP 10
        # ══════════════════════════════════════════════
        top_stories = (
            Story.objects
            .annotate(
                like_cnt=Count('likes', distinct=True),
                comment_cnt=Count('comments', distinct=True),
                char_cnt=Count('characters', distinct=True),
            )
            .order_by('-like_cnt')
            .values('id', 'title', 'cover_image', 'is_public',
                    'like_cnt', 'comment_cnt', 'char_cnt', 'created_at')[:10]
        )

        # ══════════════════════════════════════════════
        # 5. 전체 요약 카드
        # ══════════════════════════════════════════════
        total_llms      = LLM.objects.count()
        total_public    = LLM.objects.filter(is_public=True).count()
        total_conv      = Conversation.objects.filter(created_at__gte=since).count()
        total_stories   = Story.objects.count()
        pending_reports = Report.objects.filter(status='pending').count()

        # ══════════════════════════════════════════════
        # 6. 신고 현황 (유형별)
        # ══════════════════════════════════════════════
        report_by_type = (
            Report.objects.filter(status='pending')
            .values('content_type')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )

        # ══════════════════════════════════════════════
        # 7. 일별 대화 세션 수
        # ══════════════════════════════════════════════
        daily_conv = []
        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)
            daily_conv.append({
                'date':  day_start.strftime('%m/%d'),
                'count': Conversation.objects.filter(
                    created_at__gte=day_start, created_at__lt=day_end
                ).count(),
            })

        # 일별 TTS 초 최대값 (차트 바 높이 계산용)
        max_tts_sec  = max((d['seconds'] for d in daily_tts), default=1) or 1
        max_conv_cnt = max((d['count']   for d in daily_conv), default=1) or 1

        context = {
            **django_admin.site.each_context(request),
            'title':           '🤖 캐릭터 & TTS 통계',
            'period':          period,
            'period_choices':  period_choices,
            # TTS
            'tts_total_count':   tts_total_count,
            'tts_total_seconds': int(tts_total_seconds),
            'tts_total_minutes': int(tts_total_seconds // 60),
            'tts_avg_duration':  round(tts_avg_duration, 1),
            'daily_tts':         json.dumps(daily_tts, ensure_ascii=False),
            'daily_tts_list':    daily_tts,
            'max_tts_sec':       max_tts_sec,
            # 캐릭터 좋아요
            'top_llm_likes':  list(top_llm_likes),
            'rising_llms':    list(rising_llms),
            # 캐릭터별 TTS
            'llm_tts_stats':  list(llm_tts_stats),
            # 스토리
            'top_stories':    list(top_stories),
            # 요약
            'total_llms':      total_llms,
            'total_public':    total_public,
            'total_conv':      total_conv,
            'total_stories':   total_stories,
            'pending_reports': pending_reports,
            # 신고
            'report_by_type':  list(report_by_type),
            # 대화 추이
            'daily_conv':      json.dumps(daily_conv, ensure_ascii=False),
            'daily_conv_list': daily_conv,
            'max_conv_cnt':    max_conv_cnt,
        }
        return dj_render(request, self.template_name, context)
    



# =====================================================
# 📅 캐릭터 & TTS 캘린더 뷰  (admin/character/calendar/)
# =====================================================
class CharacterCalendarView(View):
    template_name = 'admin/character/character_calendar.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        today = timezone.localdate()
        now   = timezone.now()

        # ── 연/월 파라미터 ──────────────────────────
        try:
            year = int(request.GET.get('year', today.year))
        except (ValueError, TypeError):
            year = today.year
        try:
            month = int(request.GET.get('month', today.month))
        except (ValueError, TypeError):
            month = today.month

        month = max(1, min(12, month))
        year  = max(2023, min(today.year + 1, year))

        # ── 이전/다음 월 ────────────────────────────
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1

        # ── 이달 전체 집계 ──────────────────────────
        # TTS 메시지 (assistant + audio 있는 것)
        month_tts_qs = ConversationMessage.objects.filter(
            role='assistant',
            audio__isnull=False,
            is_deleted=False,
            created_at__year=year,
            created_at__month=month,
        )
        # 대화 세션
        month_conv_qs = Conversation.objects.filter(
            created_at__year=year,
            created_at__month=month,
        )
        # 좋아요
        month_like_qs = LLMLike.objects.filter(
            created_at__year=year,
            created_at__month=month,
        )

        month_tts_agg = month_tts_qs.aggregate(
            total_count=Count('id'),
            total_seconds=Sum('audio_duration'),
        )
        month_total_tts     = month_tts_agg['total_count'] or 0
        month_total_seconds = int(month_tts_agg['total_seconds'] or 0)
        month_total_conv    = month_conv_qs.count()
        month_total_likes   = month_like_qs.count()

        # ── 일별 데이터 수집 ────────────────────────
        _, days_in_month = calendar.monthrange(year, month)

        # 일별 TTS 집계
        tts_by_day_qs = (
            month_tts_qs
            .values('created_at__day')
            .annotate(tts_count=Count('id'), tts_seconds=Sum('audio_duration'))
        )
        tts_by_day = {
            r['created_at__day']: {
                'tts_count':   r['tts_count'],
                'tts_seconds': round(r['tts_seconds'] or 0, 1),
            }
            for r in tts_by_day_qs
        }

        # 일별 대화 집계
        conv_by_day_qs = (
            month_conv_qs
            .values('created_at__day')
            .annotate(conv_count=Count('id'))
        )
        conv_by_day = {r['created_at__day']: r['conv_count'] for r in conv_by_day_qs}

        # 일별 좋아요
        like_by_day_qs = (
            month_like_qs
            .values('created_at__day')
            .annotate(like_count=Count('id'))
        )
        like_by_day = {r['created_at__day']: r['like_count'] for r in like_by_day_qs}

        # 일별 인기 캐릭터 (TTS 초 기준 상위 3)
        char_by_day_qs = (
            month_tts_qs
            .values('created_at__day', 'conversation__llm__name', 'conversation__llm__id')
            .annotate(char_seconds=Sum('audio_duration'))
            .order_by('created_at__day', '-char_seconds')
        )
        chars_by_day = {}
        for r in char_by_day_qs:
            d = r['created_at__day']
            chars_by_day.setdefault(d, [])
            if len(chars_by_day[d]) < 3:
                chars_by_day[d].append({
                    'name':    r['conversation__llm__name'] or '?',
                    'seconds': round(r['char_seconds'] or 0, 1),
                })

        # ── 히트맵 레벨 계산 ────────────────────────
        max_tts_sec = max(
            (v['tts_seconds'] for v in tts_by_day.values()), default=1
        ) or 1

        def level(sec):
            if sec == 0: return 0
            r = sec / max_tts_sec
            if r <= 0.25: return 1
            if r <= 0.50: return 2
            if r <= 0.75: return 3
            return 4

        # ── 캘린더 셀 구성 ──────────────────────────
        first_weekday, _ = calendar.monthrange(year, month)  # 0=월

        calendar_cells = []
        for day in range(1, days_in_month + 1):
            cell_date = date(year, month, day)
            dow  = cell_date.weekday()
            tts  = tts_by_day.get(day, {'tts_count': 0, 'tts_seconds': 0})
            chars_json = json.dumps(chars_by_day.get(day, []), ensure_ascii=False)
            calendar_cells.append({
                'day':          day,
                'date_str':     f"{year}년 {month}월 {day}일",
                'dow':          dow,
                'is_today':     cell_date == today,
                'tts_count':    tts['tts_count'],
                'tts_seconds':  tts['tts_seconds'],
                'conv_count':   conv_by_day.get(day, 0),
                'like_count':   like_by_day.get(day, 0),
                'chars_json':   chars_json,
                'level':        level(tts['tts_seconds']),
                'has_data':     tts['tts_count'] > 0 or conv_by_day.get(day, 0) > 0,
            })

        leading_blanks  = range(first_weekday)
        trailing_total  = (7 - (first_weekday + days_in_month) % 7) % 7
        trailing_blanks = range(trailing_total)

        # ── 연도 탭 ──────────────────────────────────
        start_year = 2023
        year_range = range(start_year, today.year + 1)

        # ── 이달 일별 추이 (바 차트용 JSON) ─────────
        daily_chart = []
        for day in range(1, days_in_month + 1):
            daily_chart.append({
                'day':     str(day),
                'tts_sec': tts_by_day.get(day, {}).get('tts_seconds', 0),
                'conv':    conv_by_day.get(day, 0),
                'likes':   like_by_day.get(day, 0),
            })

        active_days = sum(1 for d in calendar_cells if d['has_data'])

        context = {
            **django_admin.site.each_context(request),
            'title':        '📅 캐릭터 & TTS 캘린더',
            'year':         year,
            'month':        month,
            'prev_year':    prev_year,
            'prev_month':   prev_month,
            'next_year':    next_year,
            'next_month':   next_month,
            'year_range':   list(year_range),
            'calendar_cells':   calendar_cells,
            'leading_blanks':   leading_blanks,
            'trailing_blanks':  trailing_blanks,
            # 월 요약
            'month_total_tts':     month_total_tts,
            'month_total_seconds': month_total_seconds,
            'month_total_minutes': month_total_seconds // 60,
            'month_total_conv':    month_total_conv,
            'month_total_likes':   month_total_likes,
            'active_days':         active_days,
            # 차트
            'daily_chart_json': json.dumps(daily_chart, ensure_ascii=False),
            'max_tts_sec':      max_tts_sec,
        }
        return dj_render(request, self.template_name, context)



"""
=================================================================
book/admin.py 또는 register/admin.py 하단에 추가하세요.

URL 등록 (urls.py):
    path('admin/book/snap-stats/',   SnapStatsView.as_view(),  name='snap_stats'),
    path('admin/register/ad-stats/', AdStatsView.as_view(),    name='ad_stats'),
=================================================================
"""

import json
from datetime import timedelta

from django.contrib import admin as django_admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render as dj_render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from advertisment.models import Advertisement, AdImpression, UserAdCounter, AdRequest
from book.models import BookSnap, BookSnapComment


# =====================================================
# 📸 BookSnap 통계 대시보드
# URL: /admin/book/snap-stats/
# =====================================================
class SnapStatsView(View):
    template_name = 'admin/book/snap_stats.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        now = timezone.now()

        period_choices = [('1', '오늘'), ('7', '7일'), ('30', '30일'), ('90', '90일')]
        period = request.GET.get('period', '7')
        days   = int(period)
        since  = now - timedelta(days=days)

        # ── 기간 내 요약 ─────────────────────────────
        snap_qs = BookSnap.objects.filter(created_at__gte=since)
        total_snaps    = snap_qs.count()
        total_views    = snap_qs.aggregate(s=Sum('views'))['s'] or 0
        total_shares   = snap_qs.aggregate(s=Sum('shares'))['s'] or 0   # shares = 링크 클릭수
        total_comments = BookSnapComment.objects.filter(
            snap__created_at__gte=since
        ).count()
        # 좋아요 (M2M — 기간 내 업로드된 스냅의 현재 좋아요 수 합산)
        total_likes = sum(
            s.booksnap_like.count()
            for s in snap_qs.prefetch_related('booksnap_like')
        )

        # ── 전체 누적 요약 ───────────────────────────
        all_agg = BookSnap.objects.aggregate(
            all_views=Sum('views'), all_shares=Sum('shares')
        )
        all_total_views  = all_agg['all_views']  or 0
        all_total_shares = all_agg['all_shares'] or 0
        all_total_snaps  = BookSnap.objects.count()

        # ── 일별 업로드 / 조회수 / 링크클릭 추이 ────
        daily_data = []
        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)
            day_qs  = BookSnap.objects.filter(created_at__gte=day_start, created_at__lt=day_end)
            day_agg = day_qs.aggregate(v=Sum('views'), sh=Sum('shares'))
            daily_data.append({
                'date':   day_start.strftime('%m/%d'),
                'count':  day_qs.count(),
                'views':  day_agg['v']  or 0,
                'shares': day_agg['sh'] or 0,
            })

        max_views  = max((d['views']  for d in daily_data), default=1) or 1
        max_shares = max((d['shares'] for d in daily_data), default=1) or 1

        # ── TOP 스냅 (조회수) ────────────────────────
        top_by_views = list(
            BookSnap.objects
            .annotate(
                like_cnt=Count('booksnap_like', distinct=True),
                comment_cnt=Count('comments', distinct=True),
            )
            .order_by('-views')
            .select_related('book', 'story', 'user')[:15]
        )

        # ── TOP 스냅 (링크 클릭 = shares) ───────────
        top_by_shares = list(
            BookSnap.objects
            .annotate(
                like_cnt=Count('booksnap_like', distinct=True),
                comment_cnt=Count('comments', distinct=True),
            )
            .order_by('-shares')
            .select_related('book', 'story', 'user')[:15]
        )

        # ── TOP 스냅 (좋아요) ────────────────────────
        top_by_likes = list(
            BookSnap.objects
            .annotate(like_cnt=Count('booksnap_like', distinct=True))
            .order_by('-like_cnt')
            .select_related('book', 'user')[:10]
        )

        # ── 댓글 많은 스냅 TOP 10 ────────────────────
        top_commented = list(
            BookSnap.objects
            .annotate(comment_cnt=Count('comments', distinct=True))
            .filter(comment_cnt__gt=0)
            .order_by('-comment_cnt')
            .select_related('book', 'user')[:10]
        )

        # ── 링크 타입별 현황 ─────────────────────────
        has_book_link   = BookSnap.objects.filter(
            book_link__isnull=False).exclude(book_link='').count()
        has_story_link  = BookSnap.objects.filter(
            story_link__isnull=False).exclude(story_link='').count()
        has_no_link     = all_total_snaps - has_book_link - has_story_link

        context = {
            **django_admin.site.each_context(request),
            'title':          '📸 BookSnap 통계',
            'period':         period,
            'period_choices': period_choices,
            'total_snaps':    total_snaps,
            'total_views':    total_views,
            'total_shares':   total_shares,
            'total_likes':    total_likes,
            'total_comments': total_comments,
            'all_total_snaps':  all_total_snaps,
            'all_total_views':  all_total_views,
            'all_total_shares': all_total_shares,
            'top_by_views':   top_by_views,
            'top_by_shares':  top_by_shares,
            'top_by_likes':   top_by_likes,
            'top_commented':  top_commented,
            'has_book_link':  has_book_link,
            'has_story_link': has_story_link,
            'has_no_link':    has_no_link,
            'daily_data':     json.dumps(daily_data, ensure_ascii=False),
            'daily_data_list': daily_data,
            'max_views':      max_views,
            'max_shares':     max_shares,
            'opts':           BookSnap._meta,
        }
        return dj_render(request, self.template_name, context)


# =====================================================
# 📢 광고(Advertisement) 통계 대시보드
# URL: /admin/register/ad-stats/
# =====================================================
class AdStatsView(View):
    template_name = 'admin/register/ad_stats.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):

        now = timezone.now()

        period_choices = [('1', '오늘'), ('7', '7일'), ('30', '30일'), ('90', '90일')]
        period = request.GET.get('period', '7')
        days   = int(period)
        since  = now - timedelta(days=days)

        imp_qs = AdImpression.objects.filter(created_at__gte=since)

        # ── 핵심 지표 ────────────────────────────────
        total_impressions = imp_qs.count()
        total_clicks      = imp_qs.filter(is_clicked=True).count()
        total_skips       = imp_qs.filter(is_skipped=True).count()
        ctr               = round(total_clicks / total_impressions * 100, 2) if total_impressions else 0
        avg_watched_sec   = round(imp_qs.aggregate(a=Avg('watched_seconds'))['a'] or 0, 1)

        # 총 시청(노출) 시간
        total_watched_sec = imp_qs.aggregate(s=Sum('watched_seconds'))['s'] or 0
        tw_hours   = total_watched_sec // 3600
        tw_minutes = (total_watched_sec % 3600) // 60
        tw_seconds = total_watched_sec % 60

        # ── 광고 위치별 성과 ─────────────────────────
        PLACEMENT_LABELS = {
            'episode': '🎧 에피소드',
            'chat':    '💬 AI 채팅',
            'tts':     '🎙 TTS',
            'snap':    '📸 북스냅',
        }
        placement_stats = []
        for row in (
            imp_qs
            .values('placement')
            .annotate(
                impr=Count('id'),
                clicks=Count('id', filter=Q(is_clicked=True)),
                skips=Count('id', filter=Q(is_skipped=True)),
                avg_watch=Avg('watched_seconds'),
                total_watch=Sum('watched_seconds'),
            )
            .order_by('-impr')
        ):
            tw = row['total_watch'] or 0
            row['label']    = PLACEMENT_LABELS.get(row['placement'], row['placement'])
            row['ctr']      = round(row['clicks'] / row['impr'] * 100, 1) if row['impr'] else 0
            row['avg_watch'] = round(row['avg_watch'] or 0, 1)
            row['tw_hours']  = tw // 3600
            row['tw_min']    = (tw % 3600) // 60
            row['tw_sec']    = tw % 60
            placement_stats.append(row)

        # ── 광고 타입별 성과 ─────────────────────────
        TYPE_LABELS = {'audio': '🔊 오디오', 'image': '🖼 이미지', 'video': '🎬 영상'}
        type_stats = []
        for row in (
            imp_qs
            .values('ad__ad_type')
            .annotate(
                impr=Count('id'),
                clicks=Count('id', filter=Q(is_clicked=True)),
                avg_watch=Avg('watched_seconds'),
            )
            .order_by('-impr')
        ):
            row['label'] = TYPE_LABELS.get(row['ad__ad_type'], row['ad__ad_type'] or '-')
            row['ctr']   = round(row['clicks'] / row['impr'] * 100, 1) if row['impr'] else 0
            type_stats.append(row)

        # ── 광고별 성과 TOP 20 ───────────────────────
        top_ads = list(
            Advertisement.objects
            .filter(impressions__created_at__gte=since)
            .annotate(
                impr_cnt=Count('impressions', distinct=True),
                click_cnt=Count('impressions',
                                filter=Q(impressions__is_clicked=True), distinct=True),
                skip_cnt=Count('impressions',
                                filter=Q(impressions__is_skipped=True), distinct=True),
                avg_watch=Avg('impressions__watched_seconds'),
                total_watch=Sum('impressions__watched_seconds'),
            )
            .order_by('-click_cnt')[:20]
        )
        # 시청 시간 포맷 추가
        for ad in top_ads:
            tw = ad.total_watch or 0
            ad.ctr = round(ad.click_cnt / ad.impr_cnt * 100, 1) if ad.impr_cnt else 0
            ad.tw_hours   = tw // 3600
            ad.tw_minutes = (tw % 3600) // 60
            ad.tw_fmt     = (f"{ad.tw_hours}시간 {ad.tw_minutes}분"
                             if ad.tw_hours else f"{ad.tw_minutes}분 {tw % 60}초")

        # ── 비용 청구 집계 ───────────────────────────
        # "비용 청구당 시간" = watched_seconds 합 / 3600 (시간 단위)
        # AdRequest.budget 승인분 합계
        approved_reqs = AdRequest.objects.filter(status='approved')
        total_budget  = approved_reqs.aggregate(s=Sum('budget'))['s'] or 0

        # 광고별 총 시청 시간 (비용 청구 기준, 초 → 시간)
        billing_stats = []
        for row in (
            AdImpression.objects
            .filter(created_at__gte=since)
            .values('ad__id', 'ad__title', 'ad__ad_type', 'ad__placement')
            .annotate(
                total_watch_sec=Sum('watched_seconds'),
                impr=Count('id'),
                clicks=Count('id', filter=Q(is_clicked=True)),
            )
            .order_by('-total_watch_sec')[:20]
        ):
            tw = row['total_watch_sec'] or 0
            billing_stats.append({
                **row,
                'tw_hours':   tw // 3600,
                'tw_minutes': (tw % 3600) // 60,
                'tw_seconds': tw % 60,
                'tw_fmt':     (f"{tw // 3600}시간 {(tw % 3600) // 60}분"
                               if tw >= 3600 else f"{(tw % 3600) // 60}분 {tw % 60}초"),
                'type_label': TYPE_LABELS.get(row['ad__ad_type'], '-'),
                'place_label': PLACEMENT_LABELS.get(row['ad__placement'], '-'),
                'ctr': round(row['clicks'] / row['impr'] * 100, 1) if row['impr'] else 0,
            })

        # ── 일별 노출/클릭/시청시간 추이 ────────────
        daily_data = []
        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)
            day_qs  = AdImpression.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end
            )
            day_impr   = day_qs.count()
            day_clicks = day_qs.filter(is_clicked=True).count()
            day_watch  = day_qs.aggregate(s=Sum('watched_seconds'))['s'] or 0
            daily_data.append({
                'date':        day_start.strftime('%m/%d'),
                'impressions': day_impr,
                'clicks':      day_clicks,
                'ctr':         round(day_clicks / day_impr * 100, 1) if day_impr else 0,
                'watch_min':   round(day_watch / 60, 1),
            })

        max_impr  = max((d['impressions'] for d in daily_data), default=1) or 1
        max_watch = max((d['watch_min']   for d in daily_data), default=0.1) or 0.1

        # ── 광고 요청 현황 ───────────────────────────
        STATUS_LABELS = {
            'pending': '⏳ 검토중', 'approved': '✅ 승인',
            'rejected': '❌ 거절',  'completed': '🏁 종료',
        }
        request_stats = [
            {**r, 'label': STATUS_LABELS.get(r['status'], r['status'])}
            for r in AdRequest.objects.values('status').annotate(cnt=Count('id'))
        ]

        # ── 현재 활성 광고 목록 ──────────────────────
        active_ads = Advertisement.objects.filter(is_active=True).order_by('-created_at')[:20]

        context = {
            **django_admin.site.each_context(request),
            'title':           '📢 광고 통계 대시보드',
            'period':          period,
            'period_choices':  period_choices,
            # 핵심 지표
            'total_impressions':   total_impressions,
            'total_clicks':        total_clicks,
            'total_skips':         total_skips,
            'ctr':                 ctr,
            'avg_watched_sec':     avg_watched_sec,
            # 시청 시간 합계
            'tw_hours':   tw_hours,
            'tw_minutes': tw_minutes,
            'tw_seconds': tw_seconds,
            'total_watched_sec': total_watched_sec,
            # 비용/예산
            'total_budget':   total_budget,
            'billing_stats':  billing_stats,
            # 위치별/타입별
            'placement_stats': placement_stats,
            'type_stats':      type_stats,
            # 광고별 성과
            'top_ads':         top_ads,
            # 요청 현황
            'request_stats':   request_stats,
            'approved_count':  approved_reqs.count(),
            'pending_count':   AdRequest.objects.filter(status='pending').count(),
            # 활성 광고
            'active_ads':      active_ads,
            # 일별 추이
            'daily_data':      json.dumps(daily_data, ensure_ascii=False),
            'daily_data_list': daily_data,
            'max_impr':        max_impr,
            'max_watch':       max_watch,
        }
        return dj_render(request, self.template_name, context)
    

"""
URL 등록:
    path('admin/book/snap-calendar/',   SnapCalendarView.as_view(),  name='snap_calendar'),
    path('admin/register/ad-calendar/', AdCalendarView.as_view(),    name='ad_calendar'),
"""

import calendar
import json
from datetime import date, timedelta

from django.contrib import admin as django_admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render as dj_render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from book.models import BookSnap, BookSnapComment


# =====================================================
# 📸 BookSnap 캘린더  (admin/book/snap-calendar/)
# =====================================================
class SnapCalendarView(View):
    template_name = 'admin/book/snap_calendar.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        today = timezone.localdate()

        try:    year  = int(request.GET.get('year',  today.year))
        except: year  = today.year
        try:    month = int(request.GET.get('month', today.month))
        except: month = today.month

        month = max(1, min(12, month))
        year  = max(2023, min(today.year + 1, year))

        prev_year,  prev_month  = (year - 1, 12)  if month == 1  else (year, month - 1)
        next_year,  next_month  = (year + 1, 1)   if month == 12 else (year, month + 1)

        # ── 이달 전체 집계 ──────────────────────────
        month_snap_qs = BookSnap.objects.filter(
            created_at__year=year, created_at__month=month,
        )
        month_comment_qs = BookSnapComment.objects.filter(
            created_at__year=year, created_at__month=month,
        )
        month_agg = month_snap_qs.aggregate(
            total_views=Sum('views'), total_shares=Sum('shares'),
        )
        month_total_snaps    = month_snap_qs.count()
        month_total_views    = month_agg['total_views']  or 0
        month_total_shares   = month_agg['total_shares'] or 0
        month_total_comments = month_comment_qs.count()
        month_total_likes    = sum(
            s.booksnap_like.count()
            for s in month_snap_qs.prefetch_related('booksnap_like')
        )

        # ── 일별 데이터 ─────────────────────────────
        _, days_in_month = calendar.monthrange(year, month)

        snap_by_day = {
            r['created_at__day']: {
                'snap_count': r['snap_count'],
                'views':      r['day_views']  or 0,
                'shares':     r['day_shares'] or 0,
            }
            for r in month_snap_qs
            .values('created_at__day')
            .annotate(snap_count=Count('id'), day_views=Sum('views'), day_shares=Sum('shares'))
        }

        comment_by_day = {
            r['created_at__day']: r['cnt']
            for r in month_comment_qs.values('created_at__day').annotate(cnt=Count('id'))
        }

        # 일별 인기 스냅 TOP 3 (조회수 기준)
        tops_by_day = {}
        for r in (
            month_snap_qs
            .values('created_at__day', 'snap_title', 'id', 'views', 'shares')
            .order_by('created_at__day', '-views')
        ):
            d = r['created_at__day']
            tops_by_day.setdefault(d, [])
            if len(tops_by_day[d]) < 3:
                tops_by_day[d].append({
                    'title':  r['snap_title'] or '제목 없음',
                    'views':  r['views'],
                    'shares': r['shares'],
                })

        # ── 히트맵 레벨 (조회수 기준) ────────────────
        max_views = max((v['views'] for v in snap_by_day.values()), default=1) or 1

        def level(v):
            if v == 0: return 0
            r = v / max_views
            return 1 if r <= .25 else 2 if r <= .50 else 3 if r <= .75 else 4

        # ── 캘린더 셀 ───────────────────────────────
        first_weekday, _ = calendar.monthrange(year, month)
        calendar_cells = []
        for day in range(1, days_in_month + 1):
            cell_date = date(year, month, day)
            sn = snap_by_day.get(day, {'snap_count': 0, 'views': 0, 'shares': 0})
            calendar_cells.append({
                'day':        day,
                'date_str':   f"{year}년 {month}월 {day}일",
                'dow':        cell_date.weekday(),
                'is_today':   cell_date == today,
                'snap_count': sn['snap_count'],
                'views':      sn['views'],
                'shares':     sn['shares'],
                'comments':   comment_by_day.get(day, 0),
                'tops_json':  json.dumps(tops_by_day.get(day, []), ensure_ascii=False),
                'level':      level(sn['views']),
                'has_data':   sn['snap_count'] > 0,
            })

        leading_blanks  = range(first_weekday)
        trailing_blanks = range((7 - (first_weekday + days_in_month) % 7) % 7)
        year_range      = range(2023, today.year + 1)

        daily_chart = [
            {
                'day':    str(d),
                'snaps':  snap_by_day.get(d, {}).get('snap_count', 0),
                'views':  snap_by_day.get(d, {}).get('views', 0),
                'shares': snap_by_day.get(d, {}).get('shares', 0),
                'cmts':   comment_by_day.get(d, 0),
            }
            for d in range(1, days_in_month + 1)
        ]

        context = {
            **django_admin.site.each_context(request),
            'title': '📸 BookSnap 캘린더',
            'year': year, 'month': month,
            'prev_year': prev_year, 'prev_month': prev_month,
            'next_year': next_year, 'next_month': next_month,
            'year_range': list(year_range),
            'calendar_cells': calendar_cells,
            'leading_blanks': leading_blanks,
            'trailing_blanks': trailing_blanks,
            'month_total_snaps': month_total_snaps,
            'month_total_views': month_total_views,
            'month_total_shares': month_total_shares,
            'month_total_likes': month_total_likes,
            'month_total_comments': month_total_comments,
            'active_days': sum(1 for c in calendar_cells if c['has_data']),
            'daily_chart_json': json.dumps(daily_chart, ensure_ascii=False),
            'max_views': max_views,
        }
        return dj_render(request, self.template_name, context)


# =====================================================
# 📢 광고 캘린더  (admin/register/ad-calendar/)
# =====================================================
class AdCalendarView(View):
    template_name = 'admin/register/ad_calendar.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):

        today = timezone.localdate()

        try:    year  = int(request.GET.get('year',  today.year))
        except: year  = today.year
        try:    month = int(request.GET.get('month', today.month))
        except: month = today.month

        month = max(1, min(12, month))
        year  = max(2023, min(today.year + 1, year))

        prev_year,  prev_month  = (year - 1, 12)  if month == 1  else (year, month - 1)
        next_year,  next_month  = (year + 1, 1)   if month == 12 else (year, month + 1)

        # ── 이달 전체 집계 ──────────────────────────
        month_imp_qs = AdImpression.objects.filter(
            created_at__year=year, created_at__month=month,
        )
        month_agg = month_imp_qs.aggregate(
            total_impr=Count('id'),
            total_clicks=Count('id', filter=Q(is_clicked=True)),
            total_skips=Count('id', filter=Q(is_skipped=True)),
            total_watched=Sum('watched_seconds'),
        )
        month_total_impr    = month_agg['total_impr']    or 0
        month_total_clicks  = month_agg['total_clicks']  or 0
        month_total_skips   = month_agg['total_skips']   or 0
        month_total_watched = month_agg['total_watched'] or 0
        month_ctr = round(month_total_clicks / month_total_impr * 100, 1) if month_total_impr else 0

        tw = month_total_watched
        tw_fmt = f"{tw//3600}시간 {(tw%3600)//60}분" if tw >= 3600 else f"{tw//60}분 {tw%60}초"

        # ── 일별 데이터 ─────────────────────────────
        _, days_in_month = calendar.monthrange(year, month)

        imp_by_day = {
            r['created_at__day']: {
                'impr':    r['impr'],
                'clicks':  r['clicks'],
                'skips':   r['skips'],
                'watched': r['watched'] or 0,
            }
            for r in month_imp_qs
            .values('created_at__day')
            .annotate(
                impr=Count('id'),
                clicks=Count('id', filter=Q(is_clicked=True)),
                skips=Count('id', filter=Q(is_skipped=True)),
                watched=Sum('watched_seconds'),
            )
        }

        # 일별 TOP 광고 3 (클릭 기준)
        PLACEMENT_ICON = {'episode': '🎧', 'chat': '💬', 'tts': '🎙', 'snap': '📸'}
        tops_by_day = {}
        for r in (
            month_imp_qs.filter(is_clicked=True)
            .values('created_at__day', 'ad__id', 'ad__title', 'ad__placement')
            .annotate(click_cnt=Count('id'))
            .order_by('created_at__day', '-click_cnt')
        ):
            d = r['created_at__day']
            tops_by_day.setdefault(d, [])
            if len(tops_by_day[d]) < 3:
                tops_by_day[d].append({
                    'title':  r['ad__title'] or '광고',
                    'clicks': r['click_cnt'],
                    'icon':   PLACEMENT_ICON.get(r['ad__placement'], '📢'),
                })

        # ── 히트맵 레벨 (노출 수 기준) ───────────────
        max_impr = max((v['impr'] for v in imp_by_day.values()), default=1) or 1

        def level(v):
            if v == 0: return 0
            r = v / max_impr
            return 1 if r <= .25 else 2 if r <= .50 else 3 if r <= .75 else 4

        # ── 캘린더 셀 ───────────────────────────────
        first_weekday, _ = calendar.monthrange(year, month)
        calendar_cells = []
        for day in range(1, days_in_month + 1):
            cell_date = date(year, month, day)
            imp = imp_by_day.get(day, {'impr': 0, 'clicks': 0, 'skips': 0, 'watched': 0})
            w   = imp['watched']
            ctr = round(imp['clicks'] / imp['impr'] * 100, 1) if imp['impr'] else 0
            calendar_cells.append({
                'day':         day,
                'date_str':    f"{year}년 {month}월 {day}일",
                'dow':         cell_date.weekday(),
                'is_today':    cell_date == today,
                'impr':        imp['impr'],
                'clicks':      imp['clicks'],
                'skips':       imp['skips'],
                'watched':     w,
                'watched_fmt': (f"{w//3600}h {(w%3600)//60}m" if w >= 3600 else f"{w//60}m {w%60}s"),
                'ctr':         ctr,
                'tops_json':   json.dumps(tops_by_day.get(day, []), ensure_ascii=False),
                'level':       level(imp['impr']),
                'has_data':    imp['impr'] > 0,
            })

        leading_blanks  = range(first_weekday)
        trailing_blanks = range((7 - (first_weekday + days_in_month) % 7) % 7)
        year_range      = range(2023, today.year + 1)

        daily_chart = [
            {
                'day':     str(d),
                'impr':    imp_by_day.get(d, {}).get('impr', 0),
                'clicks':  imp_by_day.get(d, {}).get('clicks', 0),
                'watched': round((imp_by_day.get(d, {}).get('watched', 0)) / 60, 1),
            }
            for d in range(1, days_in_month + 1)
        ]

        context = {
            **django_admin.site.each_context(request),
            'title': '📢 광고 캘린더',
            'year': year, 'month': month,
            'prev_year': prev_year, 'prev_month': prev_month,
            'next_year': next_year, 'next_month': next_month,
            'year_range': list(year_range),
            'calendar_cells': calendar_cells,
            'leading_blanks': leading_blanks,
            'trailing_blanks': trailing_blanks,
            'month_total_impr': month_total_impr,
            'month_total_clicks': month_total_clicks,
            'month_total_skips': month_total_skips,
            'month_ctr': month_ctr,
            'tw_fmt': tw_fmt,
            'active_days': sum(1 for c in calendar_cells if c['has_data']),
            'daily_chart_json': json.dumps(daily_chart, ensure_ascii=False),
            'max_impr': max_impr,
        }
        return dj_render(request, self.template_name, context)