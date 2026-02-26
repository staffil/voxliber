from firebase_admin import messaging
import logging

logger = logging.getLogger(__name__)


def send_push(token: str, title: str, body: str, data: dict = None):
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
    print(f'📤 send_push_multicast 호출됨: 토큰 {len(tokens)}개, title={title}')
    if not tokens:
        return

    data_str = {k: str(v) for k, v in (data or {}).items()}

    for i in range(0, len(tokens), 500):
        chunk = tokens[i:i + 500]
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
            print(f'✅ FCM 멀티캐스트: {response.success_count}개 성공, {response.failure_count}개 실패')
            for idx, result in enumerate(response.responses):
                if not result.success:
                    print(f'  ❌ 토큰[{idx}] 실패: {result.exception}')
                else:
                    print(f'  ✅ 토큰[{idx}] 성공: {result.message_id}')
            logger.info(f'FCM 멀티캐스트: 성공 {response.success_count}, 실패 {response.failure_count}')
        except Exception as e:
            print(f'❌ FCM 멀티캐스트 예외: {type(e).__name__}: {e}')
            logger.warning(f'FCM 멀티캐스트 실패: {e}')