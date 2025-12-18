from django.urls import path
from register import views  
from django.conf import settings
from register import api_views
app_name = "register"

urlpatterns =[
    path("", views.login_view, name="login_view"),

    path('oauth/kakao/', views.kakao_login, name='kakao_login'),
    path('oauth/kakao/callback/', views.kakao_callback, name='kakao_callback'),

    path('oauth/naver/', views.naver_login, name='naver_login'),
    path('oauth/naver/callback/', views.naver_callback, name='naver_callback'),

    path('oauth/google/', views.google_login, name='google_login'),
    path('oauth/google/callback/', views.google_callback, name='google_callback'),

    # 네이티브 앱 OAuth
    path('oauth/<str:provider>/native/', views.native_oauth_callback, name='native_oauth_callback'),

    # 모바일 앱 로그인 성공
    path('mobile-login-success/<str:api_key>/', views.mobile_login_success, name='mobile_login_success'),

    path('logout/', views.logout_view, name='logout'),

    path("signup/", views.signup_view, name="signup_view"),

# api 회원가입
    path("api/signup/", api_views.api_signup, name="api_signup"),
]

