"""
웹소설 book_type 수정 커맨드
book_type='audiobook'로 잘못 저장된 웹소설들을 'webnovel'로 수정

Usage:
    python manage.py fix_webnovel_types
    python manage.py fix_webnovel_types --dry-run   # 실제 변경 없이 확인만
"""
from django.core.management.base import BaseCommand
from book.models import Books

WEBNOVEL_UUIDS = [
    "bf046219-8547-418b-824d-912bb9426793",  # 빙의된 악녀의 역행
    "a7777d75-ff6f-47d9-ac8f-68062e06bd2a",  # 어둠의 황제에게 길들여지다
    "7161fcb6-5423-4780-99fd-9e0f3ee252b0",  # 나는 재벌의 숨겨진 딸이었다
    "7e6eda70-7a4e-4bde-af54-8e8bc9d30492",  # 던전 속에서 살아남는 방법
    "fd136c5d-8ee1-4ea9-99ca-7dfeb90078e5",  # 회귀한 황녀의 두 번째 선택
    "a1ff5c7c-fd69-4d8b-99bb-6054b8e450d2",  # AI 연인에게 사랑을 배우다
    "bc1988eb-78a3-4f9a-9a7a-f6f581578358",  # 마법학교의 낙제생이 세계를 구한다
    "e7515a91-2085-4ca0-a6f5-368be73a404c",  # 저주받은 용의 신부
    "a3a40766-0480-4a7c-a5cd-548912f870b7",  # 네온사인 아래의 도망자
    "5f8c3d82-52f6-44b7-81f4-40320b084e1c",  # 학교에 유령이 산다
]


class Command(BaseCommand):
    help = "웹소설 book_type을 'audiobook'에서 'webnovel'로 수정"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 변경 없이 대상 목록만 출력",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        wrong_books = Books.objects.filter(
            public_uuid__in=WEBNOVEL_UUIDS,
            book_type="audiobook",
        )

        if not wrong_books.exists():
            self.stdout.write(self.style.SUCCESS("수정할 책이 없습니다. (이미 모두 webnovel 타입)"))
            return

        self.stdout.write(f"수정 대상 {wrong_books.count()}권:")
        for book in wrong_books:
            self.stdout.write(f"  - {book.name} ({book.public_uuid})")

        if dry_run:
            self.stdout.write(self.style.WARNING("[dry-run] 실제 변경은 하지 않았습니다."))
            return

        updated = wrong_books.update(book_type="webnovel")
        self.stdout.write(self.style.SUCCESS(f"{updated}권 book_type → 'webnovel' 수정 완료"))
