from firebase_admin import messaging
import logging
from book.models import Content, Follow

logger = logging.getLogger(__name__)


def send_push(token: str, title: str, body: str, data: dict = None):
    """단일 기기에 푸시 발송"""
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        token=token,
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                channel_id='voxliber_push',
                sound='default',
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound='default')
            )
        ),
    )
    try:
        response = messaging.send(message)
        print(f'✅ FCM 단일 발송 성공: {response}')
        return True
    except Exception as e:
        print(f'❌ FCM 단일 발송 실패: {type(e).__name__}: {e}')
        logger.warning(f'FCM 단일 발송 실패: {e}')
        return False


def send_push_multicast(tokens: list, title: str, body: str, data: dict = None):
    """여러 기기에 동시 발송 (최대 500개씩)"""
    print(f'📤 send_push_multicast 호출됨: 토큰 {len(tokens)}개, title={title}')
    
    if not tokens:
        print('⚠️ 토큰 없음 - 종료')
        return

    data_str = {k: str(v) for k, v in (data or {}).items()}
    print(f'📦 data_str: {data_str}')

    for i in range(0, len(tokens), 500):
        chunk = tokens[i:i + 500]
        print(f'📨 청크 {i}~{i+len(chunk)}: {[t[:20] for t in chunk]}')
        
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data_str,
            tokens=chunk,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='voxliber_push',
                    sound='default',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default')
                )
            ),
        )
        try:
            response = messaging.send_each_for_multicast(message)
            print(f'✅ FCM 멀티캐스트 성공: {response.success_count}개 성공, {response.failure_count}개 실패')
            
            # 실패한 토큰 상세 출력
            for idx, result in enumerate(response.responses):
                if not result.success:
                    print(f'  ❌ 토큰[{idx}] 실패: {result.exception}')
                else:
                    print(f'  ✅ 토큰[{idx}] 성공: {result.message_id}')
                    
            logger.info(f'FCM 멀티캐스트: 성공 {response.success_count}, 실패 {response.failure_count}')
        except Exception as e:
            print(f'❌ FCM 멀티캐스트 예외: {type(e).__name__}: {e}')
            logger.warning(f'FCM 멀티캐스트 실패: {e}')

@receiver(post_save, sender=Follow)
def notify_new_follower(sender, instance, created, **kwargs):
    """팔로우 시 작가에게 푸시 발송"""
    if not created:
        return

    tokens = list(
        FCMToken.objects.filter(user=instance.following).values_list('token', flat=True)
    )
    print(f"👤 팔로우 알림: {instance.follower} → {instance.following}, 토큰 {len(tokens)}개")

    if tokens:
        send_push_multicast(
            tokens=tokens,
            title='새 팔로워',
            body=f'{instance.follower.username}님이 팔로우했습니다.',
            data={'type': 'new_follower'},
        )