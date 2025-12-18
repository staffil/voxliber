from django.urls import path
from main import views  
from django.conf import settings
from django.conf.urls.static import static
app_name = "main"

urlpatterns = [
    path("", views.main, name="main"),
    path('filter-books/', views.filter_books_by_genre, name='filter_books'),
    path('search/', views.search_books, name='search_books'),
    path('tts/health/', views.health_check, name='health_check'),
    path('test-colab/', views.test_colab, name='test_colab'),
    path('calculate/', views.calculate, name='calculate'),
    path('simple-tts/', views.generate_simple_tts, name='simple_tts'),
    path('new_books/', views.new_books, name='new_books'),
    path('poem_winner/', views.poem_winner, name='poem_winner'),
    path('snippet_all/', views.snippet_all, name='snippet_all'),
    path('event/', views.event, name='event'),
    path('ai_recommended/', views.ai_recommended, name='ai_recommended'),
    path('genres_books/<int:genres_id>', views.genres_books, name='genres_books'),

    # others
    path('notice/', views.notice, name='notice'),
    path('contact/', views.contact_list, name='contact'),
    path('terms_of_service/', views.terms_of_service, name='terms_of_service'),
    path('privacy_policy/', views.privacy_policy, name='privacy_policy'),
    path('youth_protection/', views.youth_protection, name='youth_protection'),
    path('copyright_policy/', views.copyright_policy, name='copyright_policy'),
    path('faq/', views.faq, name='faq'),


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

