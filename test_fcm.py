"""
FCM 푸시 알림 테스트 스크립트
사용법:
  python test_fcm.py              → 등록된 모든 토큰에 테스트 알림 발송
  python test_fcm.py --list       → 등록된 FCM 토큰 목록 출력
  python test_fcm.py --user EMAIL → 특정 사용자에게 발송
"""
import os
import sys
import django

# Django 설정 초기화
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxliber.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import firebase_admin
from firebase_admin import credentials, messaging
from notifications.models import FCMToken

# Firebase 초기화
if not firebase_admin._apps:
    key_path = os.path.join(os.path.dirname(__file__), 'voxliber-e6c96-firebase-adminsdk-fbsvc-673aff1037.json')
    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)


def list_tokens():
    tokens = FCMToken.objects.select_related('user').all()
    print(f'\n등록된 FCM 토큰: {tokens.count()}개')
    print('-' * 60)
    for t in tokens:
        print(f'  [{t.device}] {t.user.email or t.user.username} → {t.token[:40]}...')
    print()


def send_test(email=None):
    if email:
        tokens = list(FCMToken.objects.filter(user__email=email).values_list('token', flat=True))
        label = email
    else:
        tokens = list(FCMToken.objects.values_list('token', flat=True))
        label = '전체'

    if not tokens:
        print(f'❌ 토큰 없음 (대상: {label})')
        return

    print(f'\n📤 발송 대상: {label} ({len(tokens)}개 토큰)')

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title='🔔 VoxLiber 테스트 알림',
            body='FCM 알림이 정상 작동합니다!',
        ),
        data={
            'type': 'new_episode',
            'book_uuid': 'test-uuid',
            'book_type': 'audiobook',
            'cover_url': '',
        },
        tokens=tokens,
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                channel_id='voxliber_push',
                sound='default',
            ),
        ),
    )

    response = messaging.send_each_for_multicast(message)
    print(f'✅ 성공: {response.success_count}개')
    print(f'❌ 실패: {response.failure_count}개')

    for i, result in enumerate(response.responses):
        if not result.success:
            print(f'   토큰[{i}] 실패: {result.exception}')


if __name__ == '__main__':
    if '--list' in sys.argv:
        list_tokens()
    elif '--user' in sys.argv:
        idx = sys.argv.index('--user')
        email = sys.argv[idx + 1]
        send_test(email=email)
    else:
        list_tokens()
        send_test()
