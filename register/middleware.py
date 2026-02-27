from django.utils import timezone
from .models import UserVisitLog

BOT_AGENTS = ['googlebot', 'bingbot', 'yandex', 'baidu', 'slurp', 'duckduck',
              'facebot', 'ia_archiver', 'python-requests', 'curl', 'wget',
              'scrapy', 'crawler', 'spider', 'bot', 'preview']

class VisitLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        excluded = ['/admin/', '/static/', '/media/', '/api/', '/favicon']
        path = request.path

        if not any(path.startswith(p) for p in excluded):
            ua = request.META.get('HTTP_USER_AGENT', '').lower()
            is_bot = any(bot in ua for bot in BOT_AGENTS)

            if not is_bot:
                user = request.user if request.user.is_authenticated else None
                ip = (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                      or request.META.get('REMOTE_ADDR'))

                # 같은 IP/유저가 10분 내 재방문이면 기록 생략 (새로고침 중복 방지)
                from datetime import timedelta
                ten_min_ago = timezone.now() - timedelta(minutes=10)
                already = UserVisitLog.objects.filter(
                    ip_address=ip,
                    visited_at__gte=ten_min_ago
                ).exists()

                if not already:
                    UserVisitLog.objects.create(user=user, ip_address=ip)

        return self.get_response(request)