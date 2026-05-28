import os
import time
import requests
from django.core.management.base import BaseCommand
from django.db.models import Sum, Count
from notion_client import Client
from book.models import Books, ListeningHistory

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_BOOKS = os.environ.get("NOTION_DB_BOOKS")


def get_notion_client():
    return Client(auth=NOTION_TOKEN)


def clear_notion_db(notion, database_id):
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
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
        if not resp.get("has_more"):
            break


def sync_books(notion, stdout=None):
    def log(msg):
        if stdout:
            stdout.write(msg)
        else:
            print(msg)

    log("기존 데이터 삭제 중...")
    clear_notion_db(notion, NOTION_DB_BOOKS)
    log("삭제 완료!")

    books = Books.objects.filter(is_deleted=False).prefetch_related("genres")

    listening_stats = (
        ListeningHistory.objects
        .values("book_id")
        .annotate(
            total_seconds=Sum("listened_seconds"),
            listener_count=Count("user", distinct=True),
        )
    )
    stats_map = {s["book_id"]: s for s in listening_stats}

    log(f"총 {books.count()}개 책 동기화 시작...")

    for book in books:
        genres = ", ".join(g.name for g in book.genres.all())
        author = book.author_name or ""
        stats = stats_map.get(book.pk, {})
        total_minutes = round((stats.get("total_seconds") or 0) / 60)
        listener_count = stats.get("listener_count") or 0

        properties = {
            "이름": {"title": [{"text": {"content": book.name[:100]}}]},
            "상태": {"rich_text": [{"text": {"content": dict(Books.STATUS_CHOICES).get(book.status, book.status)}}]},
            "작가": {"rich_text": [{"text": {"content": author[:100]}}]},
            "장르": {"rich_text": [{"text": {"content": genres[:200]}}]},
            "유형": {"select": {"name": "오디오북" if book.book_type == "audiobook" else "웹소설"}},
            "성인": {"checkbox": book.adult_choice},
            "생성일": {"date": {"start": book.created_at.strftime("%Y-%m-%d")}},
            "청취 시간": {"number": total_minutes},
            "청취 수": {"number": listener_count},
        }

        try:
            notion.pages.create(
                parent={"database_id": NOTION_DB_BOOKS},
                properties=properties,
            )
            log(f"  ✓ {book.name}")
        except Exception as e:
            log(f"  ✗ {book.name}: {e}")
        time.sleep(0.3)

    log("완료!")


class Command(BaseCommand):
    help = "Django Books DB → Notion 동기화"

    def handle(self, *args, **options):
        notion = get_notion_client()
        sync_books(notion, stdout=self.stdout)
