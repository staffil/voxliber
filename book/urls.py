from django.urls import path
from book import api_views  # 🔥 API 뷰 추가
from django.conf import settings
from book import views
from django.conf.urls.static import static
app_name = "book"

urlpatterns=[
    # 검색 페이지
    path("search/", views.search_page, name="search_page"),

    path("book/tos/", views.book_tos, name="book_tos"),
    path("book/profile/", views.book_profile, name="book_profile"),
    path("book/serialization/", views.book_serialization, name="book_serialization"),
    path("detail/<uuid:book_uuid>/", views.book_detail, name="book_detail"),
    path("content/<uuid:content_uuid>/", views.content_detail, name="content_detail"),
    path("content/<uuid:content_uuid>/save-listening/", views.save_listening_history, name="save_listening_history"),

    path("review/<uuid:book_uuid>/", views.submit_review, name="submit_review"),
    path("comment/<uuid:book_uuid>/", views.submit_book_comment, name="submit_book_comment"),
    path("my/books/", views.my_books, name="my_books"),
    path("delete/<uuid:book_uuid>/", views.delete_book, name="delete_book"),
    path("tags/search/", views.search_tags, name="search_tags"),
    path("tags/add/", views.add_tags, name="add_tags"),

    # tts 생성
    path("tts/generate/", views.generate_tts_api, name="generate_tts_api"),

    # 사운드 이팩트 생성 및 조회
    path("sound-effect/generate/", views.generate_sound_effect_api, name="generate_sound_effect_api"),
    path("sound-effect/library/", views.get_sound_effects_library, name="get_sound_effects_library"),

    # 배경음 생성 및 조회
    path("background-music/generate/", views.generate_background_music_api, name="generate_background_music_api"),
    path("background-music/library/", views.get_background_music_library, name="get_background_music_library"),

    # 미리듣기
    path("preview/", views.preview_page, name="preview_page"),
    path("preview/generate/", views.generate_preview_audio, name="generate_preview_audio"),
    path("preview/generate-async/", views.generate_preview_audio_async, name="generate_preview_audio_async"),
    path("preview/task-status/<str:task_id>/", views.preview_task_status, name="preview_task_status"),

    # 북 스냅 페이지
    path("book/snap/", views.book_snap_list, name="book_snap_list"),
    path("book/snap/<uuid:snap_uuid>/", views.book_snap_detail, name="book_snap_detail"),

    # API (AJAX)
    path("book/snap/<uuid:snap_uuid>/like/", views.book_snap_like, name="book_snap_like"),
    path("book/snap/<uuid:snap_uuid>/view/", views.book_snap_view_count, name="book_snap_view_count"),
    path("book/snap/<uuid:snap_uuid>/comment/", views.book_snap_comment, name="book_snap_comment"),

    # 스냅 리스트
    path("my/snap/list/", views.my_book_snap_list, name="my_book_snap_list"),
    path("create/snap/", views.create_book_snap, name="create_book_snap"),
    path("snap/<uuid:snap_uuid>/edit/", views.edit_snap, name="edit_snap"),
    path("snap/<uuid:snap_uuid>/delete/", views.delete_snap, name="delete_snap"),

    # test
    path("test/", views.test, name="test"),
    path('chat-api/', views.chat_api, name='chat_api'),


    path('ads/audio/<uuid:uuid>/', views.audio_view, name='ad_audio'),
    path('ads/click/<uuid:uuid>/', views.ad_click, name='ad_click'),
    path('ads/skip/<uuid:uuid>/', views.ad_skip, name='ad_skip'),
    path('ads/video/<uuid:uuid>/', views.video_view, name='ad_video'),

    # 작가 센터
    path("author/dashboard/", views.author_dashboard, name="author_dashboard"),
    path('<uuid:book_uuid>/toggle_status/', views.toggle_status, name='toggle_status'),


    # 공지사항
    path("announcement/create/<uuid:book_uuid>/", views.create_announcement, name="create_announcement"),
    path("announcement/update/<int:announcement_id>/", views.update_announcement, name="update_announcement"),
    path("announcement/delete/<int:announcement_id>/", views.delete_announcement, name="delete_announcement"),

    # 에피소드 삭제
    path("content/delete/<uuid:content_uuid>/", views.delete_content, name="delete_content"),

    # 에피소드 순서 변경
    path("detail/<uuid:book_uuid>/reorder/", views.reorder_content, name="reorder_content"),

    # 북마크/메모 (콘텐츠 북마크)
    path("content/<uuid:content_uuid>/bookmark/save/", views.save_bookmark, name="save_bookmark"),
    path("content/<uuid:content_uuid>/bookmark/list/", views.get_bookmarks, name="get_bookmarks"),
    path("bookmark/delete/<int:bookmark_id>/", views.delete_bookmark, name="delete_bookmark"),

    # 북마크 (책 북마크 - 나중에 보기)
    path("bookmark/<uuid:book_uuid>/toggle/", views.toggle_bookmark, name="toggle_bookmark"),
    path("my-bookmarks/", views.my_bookmarks, name="my_bookmarks"),


    # book_serilazation_fast
    path("serialization/fast/<uuid:book_uuid>/", views.book_serilazation_fast_view, name="book_serilazation_fast_view"),
    path("serialization/fast/<uuid:book_uuid>/voice-config/save/", views.save_voice_config, name="save_voice_config"),
    path("json/generate/", views.process_json_audiobook, name="process_json_audiobook"),
    path("json/ai-generate/", views.ai_analyze_audiobook, name="ai_analyze_audiobook"),
    path("json/ai-speakers/", views.ai_assign_speakers, name="ai_assign_speakers"),
    path("json/task-status/<str:task_id>/", views.audiobook_task_status, name="audiobook_task_status"),


    # ==================== 📱 API 엔드포인트 (안드로이드 앱용) ====================
    # 🔍 통합 검색 (웹용)
    path("api/search/", api_views.api_search, name="api_search"),

    # 📚 Books
    path("api/books/", api_views.api_books_list, name="api_books_list"),
    path("api/books/search/", api_views.api_search_books, name="api_search_books"),
    path("api/books/<uuid:book_uuid>/", api_views.api_book_detail, name="api_book_detail"),

    # 📖 Contents (Episodes)
    path("api/books/<uuid:book_uuid>/contents/", api_views.api_contents_list, name="api_contents_list"),
    path("api/contents/<uuid:content_uuid>/", api_views.api_content_detail, name="api_content_detail"),

    # ⭐ Reviews
    path("api/books/<uuid:book_uuid>/reviews/", api_views.api_reviews_list, name="api_reviews_list"),
    path("api/books/<uuid:book_uuid>/review/", api_views.api_book_review_create, name="api_book_review_create"),

    # 💬 Comments
    path("api/books/<uuid:book_uuid>/comments/", api_views.api_book_comments, name="api_book_comments"),

    # 📊 User Progress
    path("api/my/progress/", api_views.api_my_progress, name="api_my_progress"),
    path("api/my/listening-history/", api_views.api_my_listening_history, name="api_my_listening_history"),
    path("api/listening-history/update/", views.update_listening_position_api, name="update_listening_position_api"),

    # 🔑 API Key Info
    path("api/key/info/", api_views.api_key_info, name="api_key_info"),

    # 🔐 Authentication
    path("api/auth/login/", api_views.api_login, name="api_login"),
    path("api/auth/register/", api_views.api_register, name="api_register"),
    path("api/auth/logout/", api_views.api_logout, name="api_logout"),
    path("api/auth/refresh-key/", api_views.api_refresh_key, name="api_refresh_key"),

    # 🏠 Home Page APIs
    path("api/home/sections/", api_views.api_home_sections, name="api_home_sections"),
    path("api/books/popular/", api_views.api_popular_books, name="api_popular_books"),
    path("api/books/trending/", api_views.api_trending_books, name="api_trending_books"),
    path("api/books/new/", api_views.api_new_books, name="api_new_books"),
    path("api/books/top-rated/", api_views.api_top_rated_books, name="api_top_rated_books"),
    path("api/banners/", api_views.api_banners, name="api_banners"),
    path("api/genres/", api_views.api_genres_list, name="api_genres_list"),
    path("api/book_detail/<uuid:book_uuid>/", api_views.api_book_detail, name="api_book_detail"),
    path("api/genres/<int:genre_id>/books/", api_views.api_genre_books, name="api_genre_books"),
    path("api/news/", api_views.api_main_new, name="api_main_new"),
    path("api/main_view/", api_views.snap_main_view, name="snap_main_view"),
    path("api/ai_recommned/<int:user_id>/", api_views.api_ai_recommend, name="api_ai_recommend"),

    # 📸 Snaps
    path("api/snaps/", api_views.api_snaps_list, name="api_snaps_list"),
    path("api/snaps/<uuid:snap_uuid>/", api_views.api_snap_detail, name="api_snap_detail"),
    path("api/snaps/<uuid:snap_uuid>/like/", api_views.api_snap_like, name="api_snap_like"),
    path("api/snaps/<uuid:snap_uuid>/comment/", api_views.api_snap_comment, name="api_snap_comment"),

    # 시 공모전(main)
    path("api/poem_list/", api_views.api_poem_main, name="api_poem_main"),
    path("api/snippet/", api_views.api_book_snippet_main, name="api_book_snippet_main"),

    # 👥 Follow System
    path("api/authors/<int:author_id>/follow/", api_views.api_follow_toggle, name="api_follow_toggle"),
    path("api/users/<int:user_id>/followers/", api_views.api_user_followers, name="api_user_followers"),
    path("api/users/<int:user_id>/following/", api_views.api_user_following, name="api_user_following"),
    path("api/following/feed/", api_views.api_following_feed, name="api_following_feed"),
    path("follow/<int:user_id>/toggle/", views.toggle_follow, name="toggle_follow"),  # 웹용 팔로우

    # 🔖 Bookmark System
    path("api/books/<uuid:book_uuid>/bookmark/", api_views.api_bookmark_toggle, name="api_bookmark_toggle"),
    path("api/books/<uuid:book_uuid>/bookmark/note/", api_views.api_bookmark_update_note, name="api_bookmark_update_note"),
    path("api/bookmarks/", api_views.api_user_bookmarks, name="api_user_bookmarks"),

]
