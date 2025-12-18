"""
API 유틸리티 - 인증, 페이지네이션 등
"""
from functools import wraps
from django.http import JsonResponse
from django.utils import timezone
from book.models import APIKey


def require_api_key(view_func):
    """
    API Key 인증 데코레이터

    사용법:
    @require_api_key
    def my_api_view(request):
        # request.api_user 로 사용자 접근 가능
        return JsonResponse({'success': True})
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # HTTP 헤더에서 API Key 추출
        api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')

        if not api_key:
            return JsonResponse({
                'error': 'API Key가 필요합니다.',
                'message': 'HTTP 헤더에 X-API-Key를 포함하거나 URL 파라미터로 api_key를 전달하세요.'
            }, status=401)

        try:
            api_key_obj = APIKey.objects.select_related('user').get(
                key=api_key,
                is_active=True
            )
        except APIKey.DoesNotExist:
            return JsonResponse({
                'error': '유효하지 않은 API Key입니다.'
            }, status=401)

        # API Key 마지막 사용 시간 업데이트
        api_key_obj.last_used_at = timezone.now()
        api_key_obj.save(update_fields=['last_used_at'])

        # request에 사용자 정보 추가
        request.api_user = api_key_obj.user
        request.api_key_obj = api_key_obj

        return view_func(request, *args, **kwargs)

    return wrapper


def paginate(items, page=1, per_page=20):
    """
    간단한 페이지네이션

    Args:
        items: QuerySet 또는 리스트
        page: 페이지 번호 (1부터 시작)
        per_page: 페이지당 아이템 수

    Returns:
        dict: {
            'items': [...],
            'page': 1,
            'per_page': 20,
            'total': 100,
            'total_pages': 5,
            'has_next': True,
            'has_prev': False
        }
    """
    try:
        page = int(page)
        per_page = int(per_page)
    except (ValueError, TypeError):
        page = 1
        per_page = 20

    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    # Django QuerySet의 count()를 사용하거나 리스트의 len()을 사용
    total = items.count() if hasattr(items, 'count') else len(items)

    start = (page - 1) * per_page
    end = start + per_page

    # 슬라이싱
    paginated_items = items[start:end]

    total_pages = (total + per_page - 1) // per_page

    return {
        'items': list(paginated_items),
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
    }


def api_response(data=None, error=None, status=200):
    """
    표준화된 API 응답 형식

    성공:
        {
            'success': True,
            'data': {...}
        }

    실패:
        {
            'success': False,
            'error': '에러 메시지'
        }
    """
    if error:
        return JsonResponse({
            'success': False,
            'error': error
        }, status=status)

    return JsonResponse({
        'success': True,
        'data': data
    }, status=status)
