from django.urls import path
from register import views
from django.conf import settings
from register import api_views

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

    path("subscribe/plan/", views.subscribe_plan, name="subscribe_plan"),
    path("subscribe/checkout/<str:plan_type>/", views.subscribe_checkout, name="subscribe_checkout"),
    path("subscribe/process/<str:plan_type>/", views.subscribe_process, name="subscribe_process"),
    path("subscribe/success/<str:plan_type>/", views.subscribe_success, name="subscribe_success"),
    path("subscribe/change/", views.subscribe_change, name="subscribe_change"),
    path("subscribe/manage/", views.subscription_manage, name="subscription_manage"),
    path("subscribe/cancel/", views.subscription_cancel, name="subscription_cancel"),
    path("payment/history/", views.payment_history, name="payment_history"),
    path("author/apply/", views.author_apply, name="author_apply"),
    path("author/center/", views.author_center, name="author_center"),
    path("author/inquiry/list/", views.author_inquiry_list, name="author_inquiry_list"),
    path("author/inquiry/write/", views.author_inquiry_write, name="author_inquiry_write"),
    path("author/inquiry/<int:inquiry_id>/", views.author_inquiry_detail, name="author_inquiry_detail"),
    path("author/inquiry/<int:inquiry_id>/edit/", views.author_inquiry_edit, name="author_inquiry_edit"),
    path("author/inquiry/<int:inquiry_id>/delete/", views.author_inquiry_delete, name="author_inquiry_delete"),
]

