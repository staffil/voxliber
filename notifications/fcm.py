from firebase_admin import messaging
import logging

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
        messaging.send(message)
        return True
    except Exception as e:
        logger.warning(f'FCM 단일 발송 실패: {e}')
        return False


def send_push_multicast(tokens: list, title: str, body: str, data: dict = None):
    """여러 기기에 동시 발송 (최대 500개씩)"""
    if not tokens:
        return

    data_str = {k: str(v) for k, v in (data or {}).items()}

    # FCM은 한 번에 500개 제한
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
            logger.info(f'FCM 멀티캐스트: 성공 {response.success_count}, 실패 {response.failure_count}')
        except Exception as e:
            logger.warning(f'FCM 멀티캐스트 실패: {e}')
