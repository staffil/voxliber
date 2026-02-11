from django.urls import path
from character import views
from django.conf import settings
from django.conf.urls.static import static
from character import api_views

app_name = "character"

urlpatterns = [
    path('terms/ai/', views.character_terms, name='terms_ai'),
    path('make/ai/story/', views.make_ai_story, name='make_ai_story'),  # 새 스토리
    path('make/ai/story/<uuid:story_uuid>/', views.make_ai_story, name='edit_ai_story'),
    # 스토리 상세 + 캐릭터 목록
    path('story/<uuid:story_uuid>/', views.story_detail, name='story_detail'),

    # 캐릭터 생성 (story_uuid 옵션)
    path('make/ai/', views.make_ai, name='make_ai'),
    path('make/ai/<uuid:story_uuid>/', views.make_ai, name='make_ai_with_story'),
    path('ai/intro/<uuid:llm_uuid>/', views.ai_intro, name='ai_intro'),
    path('story/intro/<uuid:story_uuid>/', views.story_intro, name='story_intro'),
    path('delete/ai/conversation/<int:conv_id>/', views.delete_conversation, name="delete_conversation"),
 
    # AI 미리보기
    path('ai/preview/<uuid:llm_uuid>/', views.ai_preview, name='ai_preview'),

    # AI 업데이트
    path('make/ai/update/<uuid:llm_uuid>/', views.make_ai_update, name='make_ai_update'),

    # 채팅
    path('chat/<uuid:llm_uuid>/', views.chat_view, name='chat-view'),
    path('chat/api/<uuid:llm_uuid>/', views.chat_logic, name='chat-logic'),
    path("chat/tts/<uuid:llm_uuid>/", views.chat_tts, name='chat-tts'),

    # LLM 좋아요/댓글 API
    path("api/llm/<uuid:llm_uuid>/like/", views.toggle_llm_like, name='toggle_llm_like'),
    path("api/llm/<uuid:llm_uuid>/comment/", views.add_llm_comment, name='add_llm_comment'),
    path("api/llm/comment/<int:comment_id>/delete/", views.delete_llm_comment, name='delete_llm_comment'),

    # Story 좋아요/댓글/북마크 API
    path("api/story/<uuid:story_uuid>/like/", views.toggle_story_like, name='toggle_story_like'),
    path("api/story/<uuid:story_uuid>/comment/", views.add_story_comment, name='add_story_comment'),
    path("api/story/comment/<int:comment_id>/delete/", views.delete_story_comment, name='delete_story_comment'),
    path("story/delete/<uuid:story_uuid>/", views.delete_story, name='delete_story'),
    path("llm/delete/<uuid:llm_uuid>/", views.delete_llm, name='delete_llm'),
    path("story/<uuid:story_uuid>/bookmark/toggle/", views.toggle_story_bookmark, name='toggle_story_bookmark'),



    # api 
    path("api/ai/story/list/", api_views.public_story_list, name ="public_story_list"),
    path('api/public/shared/conversations/', api_views.public_shared_llm_conversations, name='public_shared_stories'),
    path("api/ai/llm/", api_views.public_llm_list, name ="public_llm_list"),
    path("api/ai/story/detail/<uuid:story_uuid>/", api_views.public_story_detail, name='public_story_detail'),
    path("api/ai/llm/detail/<uuid:llm_uuid>/", api_views.public_llm_detail, name='public_llm_detail'),
    path("api/ai/shared/novel/<int:conv_id>/", api_views.api_shared_novel, name= "api_shared_novel"),
    path("api/ai/novel/result/<int:conv_id>/", api_views.api_novel_result, name= "api_novel_result"),
    path('api/chat/<uuid:llm_uuid>/', api_views.api_chat_view, name='api_chat_view'),
    path('api/chat/<uuid:llm_uuid>/send/', api_views.api_chat_send, name='api_chat_send'),
    path('api/chat/<uuid:llm_uuid>/reset/', api_views.api_chat_reset, name='api_chat_reset'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
