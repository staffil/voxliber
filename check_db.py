import os, sys, django
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'C:/AI2502/audioBook/voxliber')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxliber.settings')
django.setup()

from django.db import connection
from book.models import Books, Content

print("DB 호스트:", connection.settings_dict.get('HOST'))
print("DB 이름:", connection.settings_dict.get('NAME'))
print("DB 포트:", connection.settings_dict.get('PORT'))
print("---")
print("전체 책 수:", Books.objects.count())
print("전체 에피소드 수:", Content.objects.filter(is_deleted=False).count())

# 소개팅의 법칙 찾기
for b in Books.objects.filter(name__icontains='소개팅'):
    print(f"소개팅 책: {b.name} | {b.public_uuid}")
