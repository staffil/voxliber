"""
웹소설 데이터 JSON 백업 커맨드

Usage:
    python manage.py export_webnovel
    python manage.py export_webnovel --output /home/ubuntu/backup
"""
import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from book.models import Books, Content


class Command(BaseCommand):
    help = "웹소설(book_type=webnovel) 데이터를 JSON 파일로 저장"

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default='.',
            help='저장할 폴더 경로 (기본값: 현재 폴더)',
        )
        parser.add_argument(
            '--type',
            default='webnovel',
            help='내보낼 book_type (기본값: webnovel)',
        )

    def handle(self, *args, **options):
        output_dir = options['output']
        book_type  = options['type']

        os.makedirs(output_dir, exist_ok=True)

        books = Books.objects.filter(book_type=book_type).prefetch_related(
            'contents', 'genres', 'tags'
        )

        if not books.exists():
            self.stdout.write(self.style.WARNING(f"book_type='{book_type}' 데이터가 없습니다."))
            return

        self.stdout.write(f"{books.count()}권 내보내는 중...")

        result = []
        for book in books:
            episodes = []
            for ep in book.contents.order_by('number'):
                episodes.append({
                    'id': ep.id,
                    'title': ep.title,
                    'number': ep.number,
                    'text': ep.text,
                    'created_at': ep.created_at.isoformat(),
                })

            result.append({
                'id': book.id,
                'public_uuid': str(book.public_uuid),
                'name': book.name,
                'description': book.description,
                'book_type': book.book_type,
                'status': book.status,
                'adult_choice': book.adult_choice,
                'author_name': book.author_name,
                'genres': [g.name for g in book.genres.all()],
                'tags': [t.name for t in book.tags.all()],
                'created_at': book.created_at.isoformat(),
                'episodes': episodes,
            })

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(output_dir, f'{book_type}_export_{timestamp}.json')

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(
            f"저장 완료: {filename} ({len(result)}권, "
            f"{sum(len(b['episodes']) for b in result)}개 에피소드)"
        ))
