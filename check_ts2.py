import os, sys, django
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'C:/AI2502/audioBook/voxliber')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxliber.settings')
django.setup()

import json
from book.models import Content, Books

# 최근 생성된 에피소드 확인
recent = Content.objects.filter(is_deleted=False, audio_timestamps__isnull=False).order_by('-created_at')[:5]

for ep in recent:
    ts = ep.audio_timestamps
    print(f"\n=== {ep.book.name} EP{ep.number}: {ep.title} ===")
    print(f"타입: {type(ts).__name__}")
    if isinstance(ts, list) and ts:
        first = ts[0]
        print(f"키: {list(first.keys())}")
        has_start = 'startTime' in first
        has_text = 'text' in first
        print(f"startTime: {has_start} | text: {has_text}")
        if has_text:
            print(f"text 샘플: {str(first.get('text',''))[:80]}")
    elif isinstance(ts, str):
        print(f"STRING! 앞부분: {ts[:100]}")
    else:
        print(f"값: {str(ts)[:100]}")
