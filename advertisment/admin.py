from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg
from django.utils import timezone
from advertisment.models import Advertisement, AdImpression, UserAdCounter, Subscription, AdRequest


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display  = [
        'title', 'placement_badge', 'ad_type_badge',
        'is_active', 'impression_count', 'click_count', 'ctr',
        'start_date', 'end_date', 'preview_media',
    ]
    list_filter   = ['placement', 'ad_type', 'is_active']
    search_fields = ['title']
    readonly_fields = ['created_at', 'preview_media', 'stat_summary']
    ordering      = ['-created_at']

    fieldsets = (
        ('기본 정보', {
            'fields': ('title', 'placement', 'ad_type', 'is_active')
        }),
        ('미디어', {
            'fields': ('image', 'audio', 'video', 'thumbnail', 'preview_media'),
        }),
        ('링크 & 기간', {
            'fields': ('link_url', 'duration_seconds', 'start_date', 'end_date')
        }),
        ('성과 요약', {
            'fields': ('stat_summary',)
        }),
        ('생성일', {
            'fields': ('created_at',)
        }),
    )

    def placement_badge(self, obj):
        colors = {'episode': '#4CAF50', 'chat': '#2196F3', 'tts': '#FF9800', 'snap': '#9C27B0'}
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            colors.get(obj.placement, '#999'), obj.get_placement_display()
        )
    placement_badge.short_description = '노출 위치'

    def ad_type_badge(self, obj):
        colors = {'audio': '#FF5722', 'image': '#009688', 'video': '#673AB7'}
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            colors.get(obj.ad_type, '#999'), obj.get_ad_type_display()
        )
    ad_type_badge.short_description = '광고 타입'

    def impression_count(self, obj):
        return obj.impressions.count()
    impression_count.short_description = '노출수'

    def click_count(self, obj):
        return obj.impressions.filter(is_clicked=True).count()
    click_count.short_description = '클릭수'

    def ctr(self, obj):
        total = obj.impressions.count()
        if total == 0:
            return '0%'
        clicks = obj.impressions.filter(is_clicked=True).count()
        return f'{round(clicks / total * 100, 2)}%'
    ctr.short_description = 'CTR'

    def preview_media(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height:80px;border-radius:4px"/>', obj.image.url)
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height:80px;border-radius:4px"/> (썸네일)', obj.thumbnail.url)
        if obj.audio:
            return format_html('<audio controls style="height:32px"><source src="{}"></audio>', obj.audio.url)
        return '-'
    preview_media.short_description = '미리보기'

    def stat_summary(self, obj):
        impressions = obj.impressions.count()
        clicks      = obj.impressions.filter(is_clicked=True).count()
        skips       = obj.impressions.filter(is_skipped=True).count()
        avg_watch   = obj.impressions.aggregate(avg=Avg('watched_seconds'))['avg'] or 0
        ctr         = round(clicks / impressions * 100, 2) if impressions else 0
        return format_html(
            '''
            <table style="border-collapse:collapse;min-width:300px">
                <tr style="background:#f5f5f5">
                    <th style="padding:8px;border:1px solid #ddd">항목</th>
                    <th style="padding:8px;border:1px solid #ddd">수치</th>
                </tr>
                <tr><td style="padding:8px;border:1px solid #ddd">총 노출수</td><td style="padding:8px;border:1px solid #ddd">{}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd">총 클릭수</td><td style="padding:8px;border:1px solid #ddd">{}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd">CTR</td><td style="padding:8px;border:1px solid #ddd">{}%</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd">스킵수</td><td style="padding:8px;border:1px solid #ddd">{}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd">평균 시청시간</td><td style="padding:8px;border:1px solid #ddd">{}초</td></tr>
            </table>
            ''',
            impressions, clicks, ctr, skips, round(avg_watch, 1)
        )
    stat_summary.short_description = '성과 요약'


@admin.register(AdImpression)
class AdImpressionAdmin(admin.ModelAdmin):
    list_display  = ['ad', 'user', 'placement', 'is_clicked', 'is_skipped', 'watched_seconds', 'created_at']
    list_filter   = ['placement', 'is_clicked', 'is_skipped', 'created_at']
    search_fields = ['ad__title', 'user__nickname']
    readonly_fields = [f.name for f in AdImpression._meta.fields]
    ordering      = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserAdCounter)
class UserAdCounterAdmin(admin.ModelAdmin):
    list_display  = ['user', 'chat_message_count', 'tts_count', 'episode_play_count', 'snap_view_count', 'updated_at']
    search_fields = ['user__nickname', 'user__email']
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'plan_badge', 'status_badge', 'started_at', 'expires_at', 'is_active_now', 'd_day']
    list_filter   = ['plan', 'status']
    search_fields = ['user__nickname', 'user__email']
    readonly_fields = ['created_at', 'is_active_now']
    ordering      = ['-created_at']

    def plan_badge(self, obj):
        color = '#2196F3' if obj.plan == 'monthly' else '#4CAF50'
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_plan_display()
        )
    plan_badge.short_description = '플랜'

    def status_badge(self, obj):
        colors = {'active': '#4CAF50', 'expired': '#999', 'cancelled': '#f44336'}
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            colors.get(obj.status, '#999'), obj.get_status_display()
        )
    status_badge.short_description = '상태'

    def is_active_now(self, obj):
        return format_html('<strong>{}</strong>', '✅ 구독 중' if obj.is_active else '❌ 만료/해지')
    is_active_now.short_description = '현재 구독 여부'

    def d_day(self, obj):
        if obj.status != 'active':
            return '-'
        diff = (obj.expires_at - timezone.now()).days
        if diff < 0:
            return format_html('<span style="color:red">만료됨</span>')
        elif diff <= 7:
            return format_html('<span style="color:orange">D-{}</span>', diff)
        return f'D-{diff}'
    d_day.short_description = '만료까지'


@admin.register(AdRequest)
class AdRequestAdmin(admin.ModelAdmin):
    list_display  = [
        'preview_thumb', 'title', 'company_name', 'contact_name',
        'ad_type_badge', 'placement_badge', 'status_badge',
        'budget', 'created_at',
    ]
    list_display_links = ['title']
    list_filter   = ['status', 'ad_type', 'placement', 'created_at']
    search_fields = ['title', 'company_name', 'contact_name', 'email']
    readonly_fields = ['created_at', 'reviewed_at', 'preview_media']
    ordering      = ['-created_at']
    actions       = ['approve_selected', 'reject_selected']

    fieldsets = (
        ('신청자 정보', {
            'fields': ('user', 'company_name', 'contact_name', 'email', 'phone')
        }),
        ('광고 내용', {
            'fields': ('title', 'description', 'ad_type', 'placement', 'link_url', 'budget', 'start_date', 'end_date')
        }),
        ('미디어', {
            'fields': ('image', 'audio', 'video', 'preview_media')
        }),
        ('심사', {
            'fields': ('status', 'advertisement', 'reviewed_at', 'created_at')
        }),
    )

    def preview_thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:48px;height:48px;object-fit:cover;border-radius:6px;">',
                obj.image.url
            )
        icons = {'video': '🎬', 'audio': '🎵', 'image': '🖼️'}
        return format_html('<span style="font-size:22px;">{}</span>', icons.get(obj.ad_type, '📄'))
    preview_thumb.short_description = ''

    def preview_media(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width:420px;border-radius:8px;">', obj.image.url)
        if obj.video:
            return format_html('<video src="{}" controls style="max-width:420px;border-radius:8px;"></video>', obj.video.url)
        if obj.audio:
            return format_html('<audio src="{}" controls style="width:420px;"></audio>', obj.audio.url)
        return '-'
    preview_media.short_description = '미디어 미리보기'

    def ad_type_badge(self, obj):
        colors = {'image': '#009688', 'video': '#673AB7', 'audio': '#FF5722'}
        labels = {'image': '이미지', 'video': '영상', 'audio': '오디오'}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            colors.get(obj.ad_type, '#888'), labels.get(obj.ad_type, obj.ad_type)
        )
    ad_type_badge.short_description = '유형'

    def placement_badge(self, obj):
        colors = {'chat': '#2196F3', 'tts': '#FF9800', 'snap': '#9C27B0', 'episode': '#4CAF50'}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;font-size:11px;">{}</span>',
            colors.get(obj.placement, '#888'), obj.get_placement_display()
        )
    placement_badge.short_description = '노출 위치'

    def status_badge(self, obj):
        styles = {
            'pending':   ('rgba(255,193,7,0.15)',   '#ffc107', '⏳ 검토중'),
            'approved':  ('rgba(76,175,80,0.15)',   '#4CAF50', '✔ 승인'),
            'rejected':  ('rgba(231,76,60,0.15)',   '#e74c3c', '✘ 거절'),
            'completed': ('rgba(150,150,150,0.15)', '#999',    '■ 종료'),
        }
        bg, color, label = styles.get(obj.status, ('#888', '#fff', obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:4px 12px;border-radius:20px;font-size:11px;font-weight:700;">{}</span>',
            bg, color, label
        )
    status_badge.short_description = '상태'

    def _create_advertisement(self, ad_req: AdRequest) -> Advertisement:
        """AdRequest → Advertisement 생성 공통 함수"""
        ad = Advertisement(
            title      = ad_req.title,
            ad_type    = ad_req.ad_type,
            placement  = ad_req.placement,
            link_url   = ad_req.link_url,
            start_date = ad_req.start_date,
            end_date   = ad_req.end_date,
            is_active  = True,
        )
        if ad_req.image: ad.image = ad_req.image
        if ad_req.audio: ad.audio = ad_req.audio
        if ad_req.video: ad.video = ad_req.video
        ad.save()
        return ad

    def save_model(self, request, obj, form, change):
        """상세 페이지에서 status를 직접 approved로 바꿀 때 처리"""
        if change and 'status' in form.changed_data:
            obj.reviewed_at = timezone.now()
            if obj.status == 'approved' and obj.advertisement is None:
                obj.advertisement = self._create_advertisement(obj)
        super().save_model(request, obj, form, change)

    @admin.action(description='선택 항목 승인 → Advertisement 자동 생성')
    def approve_selected(self, request, queryset):
        count = 0
        for ad_req in queryset.filter(status='pending'):
            ad_req.advertisement = self._create_advertisement(ad_req)
            ad_req.status        = 'approved'
            ad_req.reviewed_at   = timezone.now()
            ad_req.save(update_fields=['status', 'reviewed_at', 'advertisement'])
            count += 1
        self.message_user(request, f'{count}건 승인 및 광고 생성이 완료됐습니다.')

    @admin.action(description='선택 항목 거절')
    def reject_selected(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='rejected',
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f'{updated}건 거절됐습니다.')





