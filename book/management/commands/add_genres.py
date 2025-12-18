from django.core.management.base import BaseCommand
from book.models import Genres


class Command(BaseCommand):
    help = '장르 데이터 추가'

    def handle(self, *args, **options):
        genres_data = [
            {"name": "판타지", "genres_color": "#9b59b6"},
            {"name": "로맨스", "genres_color": "#e91e63"},
            {"name": "무협", "genres_color": "#f39c12"},
            {"name": "현대판타지", "genres_color": "#3498db"},
            {"name": "SF", "genres_color": "#34495e"},
            {"name": "미스터리", "genres_color": "#2c3e50"},
            {"name": "스릴러", "genres_color": "#c0392b"},
            {"name": "역사", "genres_color": "#8b4513"},
            {"name": "드라마", "genres_color": "#16a085"},
            {"name": "액션", "genres_color": "#e74c3c"},
            {"name": "모험", "genres_color": "#27ae60"},
            {"name": "코미디", "genres_color": "#f1c40f"},
            {"name": "공포", "genres_color": "#000000"},
            {"name": "하렘", "genres_color": "#ff69b4"},
            {"name": "학원", "genres_color": "#1abc9c"},
            {"name": "게임", "genres_color": "#9b59b6"},
            {"name": "스포츠", "genres_color": "#e67e22"},
            {"name": "BL", "genres_color": "#3498db"},
            {"name": "GL", "genres_color": "#e91e63"},
            {"name": "19금", "genres_color": "#c0392b"},
        ]

        created_count = 0
        updated_count = 0

        for genre_data in genres_data:
            genre, created = Genres.objects.get_or_create(
                name=genre_data["name"],
                defaults={"genres_color": genre_data["genres_color"]}
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 새 장르 추가: {genre.name} ({genre.genres_color})')
                )
            else:
                # 이미 존재하는 경우 색상만 업데이트
                if genre.genres_color != genre_data["genres_color"]:
                    genre.genres_color = genre_data["genres_color"]
                    genre.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'! 장르 업데이트: {genre.name} ({genre.genres_color})')
                    )
                else:
                    self.stdout.write(f'- 이미 존재: {genre.name}')

        self.stdout.write(
            self.style.SUCCESS(f'\n완료: {created_count}개 생성, {updated_count}개 업데이트')
        )
