"""
Django DB → Notion DB 동기화 스크립트
실행: python notion_sync.py
"""
import os
import sys
import time
import django
import requests

# Django 설정 초기화
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voxliber.settings")

from dotenv import load_dotenv
load_dotenv()
django.setup()

from django.db.models import Sum, Count
from notion_client import Client
from book.models import Books, ListeningHistory

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_BOOKS = os.environ.get("NOTION_DB_BOOKS")

notion = Client(auth=NOTION_TOKEN)


def clear_notion_db(database_id):
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    print("기존 데이터 삭제 중...")
    while True:
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{database_id}/query",
            headers=headers,
            json={"page_size": 100},
        ).json()
        results = resp.get("results", [])
        if not results:
            break
        for page in results:
            notion.pages.update(page_id=page["id"], archived=True)
        print(f"  {len(results)}개 삭제됨")
        if not resp.get("has_more"):
            break
    print("삭제 완료!")


def sync_books():
    books = Books.objects.filter(is_deleted=False).prefetch_related("genres")

    clear_notion_db(NOTION_DB_BOOKS)

    # 책별 청취 통계 한 번에 조회 (N+1 방지)
    listening_stats = (
        ListeningHistory.objects
        .values("book_id")
        .annotate(
            total_seconds=Sum("listened_seconds"),
            listener_count=Count("user", distinct=True),
        )
    )
    stats_map = {s["book_id"]: s for s in listening_stats}

    print(f"총 {books.count()}개 책 동기화 시작...")

    for book in books:
        genres = ", ".join(g.name for g in book.genres.all())
        author = book.author_name or ""
        stats = stats_map.get(book.pk, {})
        total_minutes = round((stats.get("total_seconds") or 0) / 60)
        listener_count = stats.get("listener_count") or 0

        properties = {
            "이름": {
                "title": [{"text": {"content": book.name[:100]}}]
            },
            "상태": {
                "rich_text": [{"text": {"content": dict(Books.STATUS_CHOICES).get(book.status, book.status)}}]
            },
            "작가": {
                "rich_text": [{"text": {"content": author[:100] if author else ""}}]
            },
            "장르": {
                "rich_text": [{"text": {"content": genres[:200]}}]
            },
            "유형": {
                "select": {"name": "오디오북" if book.book_type == "audiobook" else "웹소설"}
            },
            "성인": {
                "checkbox": book.adult_choice
            },
            "생성일": {
                "date": {"start": book.created_at.strftime("%Y-%m-%d")}
            },
            "청취 시간": {
                "number": total_minutes
            },
            "청취 수": {
                "number": listener_count
            },
        }

        try:
            notion.pages.create(
                parent={"database_id": NOTION_DB_BOOKS},
                properties=properties,
            )
            print(f"  ✓ {book.name}")
        except Exception as e:
            print(f"  ✗ {book.name}: {e}")
        time.sleep(0.3)

    print("완료!")


if __name__ == "__main__":
    sync_books()
