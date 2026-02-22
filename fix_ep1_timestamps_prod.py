"""
소개팅의 법칙 EP1 타임스탬프 소급 수정 (프로덕션 서버용)
- startTime 추가: page[0]=3000ms, page[i] = prev.endTime + 500ms
- String으로 저장된 timestamps를 Python 객체로 변환
실행: python fix_ep1_timestamps_prod.py
"""
import os, sys, django, json, re

def clean_tags(text):
    """TTS용 [] 태그 제거"""
    return re.sub(r'\[[^\]]*\]', '', text or '').strip()
sys.stdout.reconfigure(encoding='utf-8')

# 프로덕션 서버 Django 설정 경로에 맞게 조정
sys.path.insert(0, '/home/ubuntu/voxliber')  # 프로덕션 경로
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxliber.settings')
django.setup()

from book.models import Books, Content

BOOK_UUID = 'f97cb82b-cc57-4719-87e2-45dc77fefe26'
INTRO_SILENCE = 3000  # ms
INTER_SILENCE = 500   # ms

book = Books.objects.filter(public_uuid=BOOK_UUID).first()
if not book:
    print(f"책을 찾을 수 없음: {BOOK_UUID}")
    sys.exit(1)

print(f"책: {book.name}")

for ep in Content.objects.filter(book=book, is_deleted=False).order_by('number'):
    ts = ep.audio_timestamps
    print(f"\nEP{ep.number}: {ep.title}")
    print(f"  타입: {type(ts).__name__}")

    # String → list 변환
    if isinstance(ts, str):
        try:
            ts = json.loads(ts)
            print(f"  String → list 변환 완료")
        except Exception as e:
            print(f"  ❌ 파싱 실패: {e}")
            continue

    if not isinstance(ts, list) or not ts:
        print(f"  건너뜀: 비어있음")
        continue

    # startTime 없으면 추가
    if 'startTime' not in ts[0]:
        start = INTRO_SILENCE
        for i, entry in enumerate(ts):
            if i == 0:
                entry['startTime'] = start
            else:
                entry['startTime'] = ts[i-1]['endTime'] + INTER_SILENCE
            if 'endTime' not in entry:
                entry['endTime'] = entry['startTime'] + 3000
        print(f"  startTime 추가 완료")

    # [] 태그 제거
    for entry in ts:
        if 'text' in entry:
            entry['text'] = clean_tags(entry['text'])

    ep.audio_timestamps = ts  # Python 객체로 저장
    ep.save(update_fields=['audio_timestamps'])
    print(f"  ✅ 수정 완료 ({len(ts)}페이지)")

print("\n=== 완료 ===")
