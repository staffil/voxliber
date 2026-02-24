from django.db.models.signals import post_save
from django.dispatch import receiver

from book.models import Content
from .models import FCMToken, Notification
from .fcm import send_push_multicast


@receiver(post_save, sender=Content)
def notify_new_episode(sender, instance, created, **kwargs):
    """새 에피소드 업로드 시 팔로워에게 푸시 발송"""
    if not created:
        return

    book = instance.book

    # 팔로워 조회 (mypage 앱의 Follow 모델 참조)
    try:
        from mypage.models import Follow
        follower_users = Follow.objects.filter(
            following=book.author
        ).select_related('follower').values_list('follower', flat=True)
    except Exception:
        return

    if not follower_users:
        return

    # DB 알림 저장
    notifications = [
        Notification(
            user_id=uid,
            type='new_episode',
            title=f'새 에피소드 — {book.title}',
            message=instance.title,
            link=f'/book/{book.public_uuid}/',
        )
        for uid in follower_users
    ]
    Notification.objects.bulk_create(notifications, ignore_conflicts=True)

    # FCM 푸시 발송
    tokens = list(
        FCMToken.objects.filter(user_id__in=follower_users).values_list('token', flat=True)
    )
    if tokens:
        send_push_multicast(
            tokens=tokens,
            title=f'새 에피소드 — {book.title}',
            body=instance.title,
            data={
                'type': 'new_episode',
                'book_uuid': str(book.public_uuid),
                'content_uuid': str(instance.public_uuid),
            },
        )
