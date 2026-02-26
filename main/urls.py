from django.urls import path
from main import views  
from django.conf import settings
from django.conf.urls.static import static

app_name = "main"

urlpatterns = [
    path("", views.main, name="main"),
    path("ai/novel/main/", views.ai_novel_main, name="ai_novel_main"),
    path('filter-books/', views.filter_books_by_genre, name='filter_books'),
    path('search/', views.search_books, name='search_books'),
    path('tts/health/', views.health_check, name='health_check'),
    path('test-colab/', views.test_colab, name='test_colab'),
    path('calculate/', views.calculate, name='calculate'),
    path('simple-tts/', views.generate_simple_tts, name='simple_tts'),
    path('new_books/', views.new_books, name='new_books'),
    path('snap/list/', views.snap_list, name='snap_list'),
    path('poem_winner/', views.poem_winner, name='poem_winner'),
    path('snippet_all/', views.snippet_all, name='snippet_all'),
    path('event/', views.event, name='event'),
    path('ai_recommended/', views.ai_recommended, name='ai_recommended'),
    path('genres_books/<int:genres_id>', views.genres_books, name='genres_books'),
    path('user/intro/<uuid:user_uuid>/', views.user_info, name='user_info'),
    path('shared/novel/<int:conv_id>/', views.shared_novel, name='shared_novel'),
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


    # api
    path('api/delete/listening/history/<uuid:book_uuid>/', views.api_delete_listening_history, name= "api_delete_listening_history"),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

