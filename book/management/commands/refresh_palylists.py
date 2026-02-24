from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from book.models import Genres, Content, GenrePlaylist, PlaylistItem


class Command(BaseCommand):
    help = '장르별 플레이리스트 자동 갱신'

    def handle(self, *args, **kwargs):
        genres = Genres.objects.filter(books__isnull=False).distinct()

        for genre in genres:
            self._refresh_popular(genre)
            self._refresh_new(genre)
            self._refresh_short(genre)
            self._refresh_rated(genre)

        self.stdout.write(self.style.SUCCESS('✅ 플레이리스트 갱신 완료'))

    def _build_playlist(self, genre, playlist_type, title, contents):
        """플레이리스트 생성 또는 갱신 (자동생성 플레이리스트만)"""
        playlist, created = GenrePlaylist.objects.get_or_create(
            genre=genre,
            playlist_type=playlist_type,
            defaults={
                'title': title,
                'is_auto_generated': True,
            }
        )

        # 수동 관리 중인 건 자동 갱신 스킵
        if not playlist.is_auto_generated:
            return

        # 기존 항목 삭제 후 재생성
        playlist.items.all().delete()
        items = [
            PlaylistItem(playlist=playlist, content=content, order=i)
            for i, content in enumerate(contents)
        ]
        PlaylistItem.objects.bulk_create(items)

    def _refresh_popular(self, genre):
        contents = Content.objects.filter(
            book__genres=genre,
            is_deleted=False,
            duration_seconds__gt=0
        ).annotate(
            play_count=Count('listening_stats')
        ).order_by('-play_count').select_related('book')[:30]

        self._build_playlist(
            genre, 'popular',
            f'{genre.name} 인기 TOP',
            contents
        )

    def _refresh_new(self, genre):
        thirty_days_ago = timezone.now() - timedelta(days=30)
        contents = Content.objects.filter(
            book__genres=genre,
            is_deleted=False,
            created_at__gte=thirty_days_ago,
            duration_seconds__gt=0
        ).order_by('-created_at').select_related('book')[:30]

        self._build_playlist(
            genre, 'new',
            f'{genre.name} 신작 모아듣기',
            contents
        )

    def _refresh_short(self, genre):
        contents = Content.objects.filter(
            book__genres=genre,
            is_deleted=False,
            duration_seconds__gt=0,
            duration_seconds__lte=600  # 10분 이하
        ).annotate(
            play_count=Count('listening_stats')
        ).order_by('-play_count').select_related('book')[:30]

        self._build_playlist(
            genre, 'short',
            f'{genre.name} 짧게 듣기',
            contents
        )

    def _refresh_rated(self, genre):
        contents = Content.objects.filter(
            book__genres=genre,
            book__book_score__gte=4.0,
            is_deleted=False,
            duration_seconds__gt=0
        ).order_by('-book__book_score', '-created_at').select_related('book')[:30]

        self._build_playlist(
            genre, 'rated',
            f'{genre.name} 고평점 모음',
            contents
        )