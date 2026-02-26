from django.db.models.signals import post_save
from django.dispatch import receiver
from book.models import Content, Follow, BookmarkBook
from .models import FCMToken, Notification
from .fcm import send_push_multicast


@receiver(post_save, sender=Content)
def notify_new_episode(sender, instance, created, **kwargs):
    """새 에피소드 업로드 시 해당 책을 서재에 담은 사용자에게 푸시 발송"""
    if not created:
        return

    book = instance.book

    # 해당 책을 서재에 담은 사용자 조회
    bookmarked_users = BookmarkBook.objects.filter(
        book=book
    ).values_list('user', flat=True)

    if not bookmarked_users:
        return

    # 이미지 URL 생성
    cover_url = ''
    if book.cover_img:
        cover_url = f'https://voxliber.ink{book.cover_img.url}'
    print(f"🖼️ cover_url: {cover_url}")

    # DB 알림 저장
    notifications = [
        Notification(
            user_id=uid,
            type='new_episode',
            title=f'새 에피소드 — {book.name}',
            message=instance.title,
            link=f'/book/{book.public_uuid}/',
        )
        for uid in bookmarked_users
    ]
    Notification.objects.bulk_create(notifications, ignore_conflicts=True)

    # FCM 푸시 발송
    tokens = list(
        FCMToken.objects.filter(user_id__in=bookmarked_users).values_list('token', flat=True)
    )
    if tokens:
        send_push_multicast(
            tokens=tokens,
            title=f'새 에피소드 — {book.name}',
            body=instance.title,
            data={
                'type': 'new_episode',
                'book_uuid': str(book.public_uuid),
                'content_uuid': str(instance.public_uuid),
                'cover_url': cover_url,
            },
        )


@receiver(post_save, sender=Follow)
def notify_new_follower(sender, instance, created, **kwargs):
    """팔로우 시 작가에게 푸시 발송"""
    if not created:
        return

    tokens = list(
        FCMToken.objects.filter(user=instance.following).values_list('token', flat=True)
    )

    if not tokens:
        return

    # DB 알림 저장
    Notification.objects.create(
        user=instance.following,
        type='new_follower',
        title='새 팔로워',
        message=f'{instance.follower.username}님이 팔로우했습니다.',
        link=f'/user/{instance.follower.id}/',
    )

    send_push_multicast(
        tokens=tokens,
        title='새 팔로워',
        body=f'{instance.follower.username}님이 팔로우했습니다.',
        data={'type': 'new_follower'},
    )