from django.urls import path
from main import views  
from django.conf import settings
from django.conf.urls.static import static

app_name = "main"

urlpatterns = [
    path("", views.main, name="main"),
    path('webnovel/', views.webnovel, name='webnovel'),
    path('filter-books/', views.filter_books_by_genre, name='filter_books'),
    path('search/', views.search_books, name='search_books'),
    path('tts/health/', views.health_check, name='health_check'),
    path('test-colab/', views.test_colab, name='test_colab'),
    path('calculate/', views.calculate, name='calculate'),
    path('simple-tts/', views.generate_simple_tts, name='simple_tts'),
    path('new_books/', views.new_books, name='new_books'),
    path('snap/list/', views.snap_list, name='snap_list'),
    path('snippet_all/', views.snippet_all, name='snippet_all'),
    path('event/', views.event, name='event'),
    path('genres_books/<int:genres_id>', views.genres_books, name='genres_books'),
    path('user/intro/<uuid:user_uuid>/', views.user_info, name='user_info'),
    path('delete/listening/history/<uuid:book_uuid>/', views.delete_listening_history ,name="delete_listening_history"),
    # others
    path('notice/', views.notice, name='notice'),
    path('contact/', views.contact_list, name='contact'),
    path('terms/of/service/', views.terms_of_service, name='terms_of_service'),
    path('privacy/policy/', views.privacy_policy, name='privacy_policy'),
    path('youth/protection/', views.youth_protection, name='youth_protection'),
    path('copyright/policy/', views.copyright_policy, name='copyright_policy'),
    path('contact/contact/write/', views.contact_write, name='contact_write'),
    path('contact/<int:contact_id>/', views.contact_detail, name='contact_detail'), 
    path('faq/', views.faq, name='faq'),

    path('playlist/<int:playlist_id>/', views.playlist_detail, name='playlist_detail'),
    path('playlists/', views.playlist_list, name='playlist_list'),
    path('ai-recommended/', views.ai_recommended_page, name='ai_recommended'),
    path('genres/', views.genres_all, name='genres_all'),
    path('voxliber-admin/', views.admin_dashboard, name='admin_dashboard'),
    path('voxliber-admin/subscription/change/<int:user_id>/', views.admin_subscription_change, name='admin_subscription_change'),
    path('voxliber-admin/inquiry/<int:inquiry_id>/reply/', views.admin_inquiry_reply, name='admin_inquiry_reply'),
    path('voxliber-admin/author-app/<int:app_id>/approve/', views.admin_approve_author, name='admin_approve_author'),
    path('voxliber-admin/author-app/<int:app_id>/reject/', views.admin_reject_author, name='admin_reject_author'),

    # api
    path('api/delete/listening/history/<uuid:book_uuid>/', views.api_delete_listening_history, name= "api_delete_listening_history"),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

