import os, sys, django
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'C:/AI2502/audioBook/voxliber')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxliber.settings')
django.setup()
import json
from book.models import Content, Books

# UUID로 직접 찾기
book = Books.objects.filter(public_uuid='f97cb82b-cc57-4719-87e2-45dc77fefe26').first()
if not book:
    print("UUID로 못 찾음. 전체 책 목록:")
    for b in Books.objects.all():
        print(f"  {b.name} | {b.public_uuid}")
else:
    print(f"Found: {book.name}")
    for ep in Content.objects.filter(book=book, is_deleted=False).order_by('number'):
        ts = ep.audio_timestamps
        if isinstance(ts, list) and ts:
            keys = list(ts[0].keys())
            has_start = 'startTime' in keys
            has_text = 'text' in keys
            print(f"  EP{ep.number}: keys={keys} | startTime={has_start} | text={has_text}")
        else:
            print(f"  EP{ep.number}: type={type(ts).__name__} val={str(ts)[:80]}")
