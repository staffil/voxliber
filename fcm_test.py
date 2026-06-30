"""
FCM 직접 테스트 스크립트 (Django 없이 실행 가능)

사용법:
  python fcm_test.py <FCM_TOKEN>         # 특정 토큰에 발송
  python fcm_test.py --all               # DB의 모든 토큰에 발송 (Django 필요)

Flutter 앱 로그에서 FCM 토큰 확인:
  flutter run 후 로그에서 "FCM Token:" 또는 "토큰 등록" 검색
"""
import os
import sys

FIREBASE_KEY = os.path.join(os.path.dirname(__file__), 'voxliber-e6c96-firebase-adminsdk-fbsvc-673aff1037.json')

import firebase_admin
from firebase_admin import credentials, messaging

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_KEY)
    firebase_admin.initialize_app(cred)


def send_to_token(token: str):
    print(f'\n📤 발송 중... 토큰: {token[:30]}...')
    msg = messaging.Message(
        notification=messaging.Notification(
            title='🔔 VoxLiber 테스트',
            body='FCM 알림 테스트입니다!',
        ),
        data={
            'type': 'new_episode',
            'book_uuid': 'f17b3207-037b-11f1-9a87-0affd0efb551',
            'book_type': 'audiobook',
            'cover_url': '',
        },
        token=token,
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                channel_id='voxliber_push',
                sound='default',
            ),
        ),
    )
    try:
        resp = messaging.send(msg)
        print(f'✅ 성공! message_id: {resp}')
    except Exception as e:
        print(f'❌ 실패: {e}')


def send_to_all():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxliber.settings')
    import django
    django.setup()
    from notifications.models import FCMToken

    tokens_qs = FCMToken.objects.select_related('user').all()
    print(f'\n등록된 토큰: {tokens_qs.count()}개')
    for t in tokens_qs:
        print(f'  {t.user.email or t.user.username}')
        send_to_token(t.token)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == '--all':
        send_to_all()
    else:
        send_to_token(sys.argv[1])
