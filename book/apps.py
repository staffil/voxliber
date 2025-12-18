from django.apps import AppConfig


class BookConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "book"

    def ready(self):
        """
        앱이 준비될 때 실행
        - 신호(signals) 등록
        """
        import book.signals  # 신호 등록
