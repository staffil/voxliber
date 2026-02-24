"""
URL configuration for voxliber project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from book.sitemaps import BookSitemap, StaticViewSitemap
from django.http import FileResponse
from voxliber import api_views as voxliber_api
import os
from book.admin import EpisodeRankingView, ListeningStatsView,ListeningCalendarView,CharacterStatsView,CharacterCalendarView,SnapStatsView,AdStatsView,SnapCalendarView,AdCalendarView

# Sitemap 설정
sitemaps = {
    'books': BookSitemap,
    'static': StaticViewSitemap,
}

# Deep Link 검증 파일 제공 뷰
def serve_well_known(request, filename):
    file_path = os.path.join(settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.BASE_DIR / 'static', '.well-known', filename)
    return FileResponse(open(file_path, 'rb'), content_type='application/json')

urlpatterns = [
    path('admin/book/snap-calendar/',   SnapCalendarView.as_view()),
    path('admin/register/ad-calendar/', AdCalendarView.as_view()),
    path('admin/book/snap-stats/',      SnapStatsView.as_view(),  name='snap_stats'),

    # 📢 광고 통계
    path('admin/register/ad-stats/',    AdStatsView.as_view(),    name='ad_stats'),
    path('admin/character/calendar/', CharacterCalendarView.as_view(), name='character_calendar'),

    path('admin/character/stats/', CharacterStatsView.as_view(), name='character_stats'),

    path('admin/book/listening-calendar/', ListeningCalendarView.as_view(), name='listening_calendar'),

    path('admin/book/episode-ranking/', EpisodeRankingView.as_view(), name='episode_ranking'),
    path('admin/book/listening-stats/', ListeningStatsView.as_view(), name="listening-stats"),
    path("admin/", admin.site.urls),

    path("", include(("main.urls", "main"), namespace="main")),
    path("login/", include(("register.urls", "register"), namespace="register")),
    path("book/", include(("book.urls", "book"), namespace="book")),
    path("mypage/", include(("mypage.urls", "mypage"), namespace="mypage")),
    path("voice/", include(("voice.urls", "voice"), namespace="voice")),
    path("character/", include(("character.urls", "character"), namespace="character")),
    path("advertisment/", include(("advertisment.urls", "advertisment"), namespace="advertisment")),
    # 딥링크용 snap URL
    path("snap/detail/<uuid:snap_uuid>/", lambda request, snap_uuid: __import__('django.shortcuts', fromlist=['redirect']).redirect('book:book_snap_detail', snap_uuid=snap_uuid)),
    path("robots.txt", TemplateView.as_view(
        template_name="robots.txt",
        content_type="text/plain"
    )),
    path("sitemap.xml", sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('naver68afd1621fdbfa5d1c2dc3728aa152e8.html', TemplateView.as_view(template_name='naver68afd1621fdbfa5d1c2dc3728aa152e8.html')),

    # ==================== 자동 오디오북 생성 API ====================
    # 기본 CRUD
    path("api/v1/create-book/", voxliber_api.api_create_book, name="api_create_book"),
    path("api/v1/create-episode/", voxliber_api.api_create_episode, name="api_create_episode"),
    path("api/v1/delete-episode/", voxliber_api.api_delete_episode, name="api_delete_episode"),
    path("api/v1/regenerate-episode/", voxliber_api.api_regenerate_episode, name="api_regenerate_episode"),
    path("api/v1/my-books/", voxliber_api.api_my_books, name="api_my_books"),

    # 조회 API
    path("api/v1/voices/", voxliber_api.api_voice_list, name="api_voice_list"),
    path("api/v1/genres/", voxliber_api.api_genre_list, name="api_genre_list"),
    path("api/v1/voice-effects/", voxliber_api.api_voice_effect_presets, name="api_voice_effects"),
    path("api/v1/emotion-tags/", voxliber_api.api_emotion_tags, name="api_emotion_tags"),

    # 사운드 이펙트 & 배경음
    path("api/v1/sound-effect/create/", voxliber_api.api_create_sound_effect, name="api_create_sound_effect"),
    path("api/v1/sound-effects/", voxliber_api.api_sound_effect_library, name="api_sound_effect_library"),
    path("api/v1/background-music/create/", voxliber_api.api_create_background_music, name="api_create_background_music"),
    path("api/v1/background-music/", voxliber_api.api_background_music_library, name="api_background_music_library"),
    path("api/v1/mix-background/", voxliber_api.api_mix_background_music, name="api_mix_background"),

    # 이미지 업로드
    path("api/v1/upload-book-cover/", voxliber_api.api_upload_book_cover, name="api_upload_book_cover"),
    path("api/v1/upload-episode-image/", voxliber_api.api_upload_episode_image, name="api_upload_episode_image"),
    path("api/v1/upload-image-url/", voxliber_api.api_upload_image_from_url, name="api_upload_image_url"),

    # 태그 & 메타데이터
    path("api/v1/tags/", voxliber_api.api_tag_list, name="api_tag_list"),
    path("api/v1/update-book-metadata/", voxliber_api.api_update_book_metadata, name="api_update_book_metadata"),

    # 스냅
    path("api/v1/create-snap/", voxliber_api.api_create_snap, name="api_create_snap"),

    # AI 스토리 생성
    path("api/v1/create-ai-story/", voxliber_api.api_create_ai_story, name="api_create_ai_story"),
    path("api/v1/create-ai-llm/", voxliber_api.api_create_ai_llm, name="api_create_ai_llm"),

    # 로어북
    path("api/v1/lore-entry/", voxliber_api.api_lore_entry_list, name="api_lore_entry_list"),
    path("api/v1/lore-entry/create/", voxliber_api.api_lore_entry_create, name="api_lore_entry_create"),

    # 홈 차트/작가 (앱용)
    path("api/v1/popular-authors/", voxliber_api.api_popular_authors, name="api_popular_authors"),
    path("api/v1/realtime-chart/", voxliber_api.api_realtime_chart, name="api_realtime_chart"),
    path("api/v1/announcement/", voxliber_api.api_announcement, name="api_announcement"),

    # 알림 API (앱용)
    path("api/v1/notifications/", include("notifications.urls")),

    # 광고 API (앱용)
    path("api/v1/ads/check/", voxliber_api.api_ad_check, name="api_ad_check"),
    path("api/v1/ads/impression/", voxliber_api.api_ad_impression, name="api_ad_impression"),
    path("api/v1/ads/click/", voxliber_api.api_ad_click, name="api_ad_click"),
    path("api/v1/ads/skip/", voxliber_api.api_ad_skip, name="api_ad_skip"),

    # Deep Link Verification Files
    path('.well-known/apple-app-site-association',
         lambda request: serve_well_known(request, 'apple-app-site-association')),
    path('.well-known/assetlinks.json',
         lambda request: serve_well_known(request, 'assetlinks.json')),



]
# 개발 환경에서 미디어 파일 서빙
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


from main import views as  main


handler400 = 'main.views.bad_request'
handler403 = 'main.views.permission_denied'
handler404 = 'main.views.page_not_found'
handler500 = 'main.views.server_error'