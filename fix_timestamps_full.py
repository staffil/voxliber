"""
기존 에피소드의 audio_timestamps에 startTime + text 소급 추가
- startTime 계산: 첫 페이지=3000ms, 이후 = 전 페이지 endTime + 500ms
- text 추출: content.text를 '---'로 분리
"""
import os, sys, django, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'C:/AI2502/audioBook/voxliber')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxliber.settings')
django.setup()

from book.models import Content

fixed = 0
skipped = 0
already_ok = 0
errors = 0

contents = Content.objects.filter(
    is_deleted=False,
    audio_timestamps__isnull=False
).select_related('book')

for content in contents:
    ts = content.audio_timestamps
    if not isinstance(ts, list) or not ts:
        skipped += 1
        continue

    # 이미 startTime + text 있으면 패스
    if 'startTime' in ts[0] and 'text' in ts[0]:
        already_ok += 1
        continue

    try:
        # 1. startTime 계산
        INTRO_SILENCE = 3000  # ms
        INTER_SILENCE = 500   # ms

        start = INTRO_SILENCE
        for i, entry in enumerate(ts):
            if i == 0:
                entry['startTime'] = start
            else:
                entry['startTime'] = ts[i-1]['endTime'] + INTER_SILENCE
            # endTime이 없으면 startTime + 3000 임시
            if 'endTime' not in entry:
                entry['endTime'] = entry['startTime'] + 3000

        # 2. text 추출 (content.text를 --- 기준 분리)
        page_texts = []
        if content.text:
            parts = re.split(r'\n*---\n*', content.text)
            page_texts = [p.strip() for p in parts if p.strip()]

        # 3. text 매핑
        for i, entry in enumerate(ts):
            if i < len(page_texts):
                entry['text'] = page_texts[i]
            else:
                # fallback: 텍스트 없으면 pageIndex 표시
                entry['text'] = f"[페이지 {i+1}]"

        content.audio_timestamps = ts
        content.save(update_fields=['audio_timestamps'])
        print(f"✅ {content.book.name} EP{content.number}: {len(ts)}페이지 수정")
        fixed += 1

    except Exception as e:
        print(f"❌ 오류 {content.book.name} EP{content.number}: {e}")
        errors += 1

print(f"\n=== 완료 ===")
print(f"수정: {fixed}개 | 이미 정상: {already_ok}개 | 건너뜀: {skipped}개 | 오류: {errors}개")
