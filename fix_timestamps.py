import os, sys, django
sys.path.insert(0, 'C:/AI2502/audioBook/voxliber')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxliber.settings')
django.setup()

import json
from book.models import Content

fixed = 0
skipped = 0
errors = 0

for content in Content.objects.filter(is_deleted=False).exclude(audio_timestamps=None):
    ts = content.audio_timestamps
    if isinstance(ts, str):
        try:
            parsed = json.loads(ts)
            content.audio_timestamps = parsed
            content.save(update_fields=['audio_timestamps'])
            print(f"✅ Fixed: {content.title} (ep{content.number})")
            fixed += 1
        except Exception as e:
            print(f"❌ Error: {content.title} - {e}")
            errors += 1
    else:
        skipped += 1

print(f"\n=== 완료 ===")
print(f"수정: {fixed}개 | 이미 정상: {skipped}개 | 오류: {errors}개")
