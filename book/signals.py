"""
Django Signals
- 로그인 시 자동으로 API Key 생성
- 이미지 업로드 시 자동 최적화
"""
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import pre_save
from django.dispatch import receiver
from book.models import APIKey, Books
from book.image_utils import optimize_image
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


@receiver(pre_save, sender=Books)
def optimize_book_cover_image(sender, instance, **kwargs):
    """
    책 커버 이미지 자동 최적화
    - 이미지가 변경되었을 때만 최적화 실행
    - 최대 1200x1200으로 리사이징
    - JPEG 품질 85%로 압축
    """
    if not instance.cover_img:
        return

    # 기존 인스턴스 확인 (이미지가 변경되었는지)
    try:
        old_instance = Books.objects.get(pk=instance.pk)
        # 이미지가 변경되지 않았으면 최적화 안 함
        if old_instance.cover_img == instance.cover_img:
            return
    except Books.DoesNotExist:
        # 새로운 책 생성 시
        pass

    # 이미지 최적화
    try:
        optimized = optimize_image(instance.cover_img, max_width=1200, max_height=1200, quality=85)
        if optimized:
            instance.cover_img = optimized
            print(f"✅ 이미지 최적화 완료: {instance.name}")
    except Exception as e:
        print(f"⚠️ 이미지 최적화 실패: {str(e)}")
