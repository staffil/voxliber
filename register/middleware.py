from django.utils import timezone
from .models import UserVisitLog

class VisitLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # API, static, admin 요청 제외
        excluded = ['/admin/', '/static/', '/media/', '/api/']
        if not any(request.path.startswith(p) for p in excluded):
            user = request.user if request.user.is_authenticated else None
            ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
                 or request.META.get('REMOTE_ADDR')
            
            UserVisitLog.objects.create(user=user, ip_address=ip)

        return self.get_response(request)