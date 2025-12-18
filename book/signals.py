"""
Django Signals - 로그인 시 자동으로 API Key 생성
"""
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from book.models import APIKey
import secrets


@receiver(user_logged_in)
def create_api_key_on_login(sender, request, user, **kwargs):
    """
    사용자가 로그인할 때 자동으로 API Key 생성
    (웹 로그인, 앱 로그인 모두 적용)

    - 이미 활성화된 API Key가 있으면 생성하지 않음
    - 없으면 새로 생성
    """
    # 이미 활성화된 API Key가 있는지 확인
    existing_key = APIKey.objects.filter(
        user=user,
        name='모바일 앱',
        is_active=True
    ).first()

    # 없으면 새로 생성
    if not existing_key:
        api_key = secrets.token_urlsafe(48)
        APIKey.objects.create(
            user=user,
            name='모바일 앱',
            key=api_key
        )
        print(f"✅ API Key 자동 생성 완료: {user.nickname} (ID: {user.pk})")
    else:
        print(f"ℹ️ 기존 API Key 사용: {user.nickname} (ID: {user.pk})")
