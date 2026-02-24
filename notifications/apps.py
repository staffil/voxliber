from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = '알림'

    def ready(self):
        import firebase_admin
        from firebase_admin import credentials
        from django.conf import settings
        import os

        if not firebase_admin._apps:
            key_path = settings.FIREBASE_KEY_PATH
            if os.path.exists(key_path):
                cred = credentials.Certificate(str(key_path))
                firebase_admin.initialize_app(cred)
            else:
                import logging
                logging.getLogger(__name__).warning(
                    f'Firebase 키 파일 없음: {key_path} — 푸시 알림 비활성화'
                )

        import notifications.signals  # noqa: F401
