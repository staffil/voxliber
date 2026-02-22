import os, sys, django
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'C:/AI2502/audioBook/voxliber')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxliber.settings')
django.setup()

from book.models import Books, Content

# UUID로 직접 찾기
uuid1 = 'f97cb82b-cc57-4719-87e2-45dc77fefe26'
uuid2 = 'a55de868-7506-49f8-ad8d-0555497360c1'

for u in [uuid1, uuid2]:
    b = Books.objects.filter(public_uuid=u).first()
    c = Content.objects.filter(public_uuid=u).first()
    if b:
        print(f"책 발견: {b.name} | {u}")
    elif c:
        print(f"에피소드 발견: {c.title} | book={c.book.name} | {u}")
    else:
        print(f"없음: {u}")

# 최근 생성된 에피소드 5개
print("\n=== 최근 에피소드 ===")
for ep in Content.objects.filter(is_deleted=False).order_by('-created_at')[:5]:
    ts = ep.audio_timestamps
    has_start = isinstance(ts, list) and ts and 'startTime' in ts[0]
    has_text = isinstance(ts, list) and ts and 'text' in ts[0]
    print(f"{ep.book.name} EP{ep.number} | startTime={has_start} | text={has_text}")
