"""
API 유틸리티 - 인증, 페이지네이션 등
"""
from functools import wraps
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from book.models import APIKey
import time


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


def get_client_ip(request):
    """요청의 클라이언트 IP 주소 추출"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def check_rate_limit(request, key_suffix='', limit=100, period=60):
    """
    API 요청 속도 제한 확인

    Args:
        request: Django request object
        key_suffix: 캐시 키 접미사 (뷰 이름 등)
        limit: 허용 요청 수 (기본: 100)
        period: 시간 주기(초) (기본: 60)

    Returns:
        tuple: (is_allowed, remaining, reset_time)
    """
    ip = get_client_ip(request)
    user_id = request.api_user.id if hasattr(request, 'api_user') else 'anonymous'
    cache_key = f'rate_limit:{ip}:{user_id}:{key_suffix}'

    # 현재 요청 수 확인
    current_count = cache.get(cache_key, 0)

    if current_count >= limit:
        # 제한 초과 - 리셋 시간 계산
        ttl = cache.ttl(cache_key)
        if ttl is None:
            ttl = period
        return False, 0, int(time.time()) + ttl

    # 카운터 증가
    if current_count == 0:
        cache.set(cache_key, 1, period)
    else:
        cache.incr(cache_key)

    remaining = limit - current_count - 1
    reset_time = int(time.time()) + period

    return True, remaining, reset_time


def rate_limited(limit=100, period=60):
    """
    API 속도 제한 데코레이터

    사용법:
        @rate_limited(limit=10, period=60)  # 60초당 10회
        @require_api_key
        def my_api_view(request):
            return JsonResponse({'success': True})
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            is_allowed, remaining, reset_time = check_rate_limit(
                request,
                key_suffix=view_func.__name__,
                limit=limit,
                period=period
            )

            if not is_allowed:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': f'요청 제한을 초과했습니다. {period}초당 최대 {limit}회 요청 가능합니다.',
                    'retry_after': reset_time
                }, status=429)

            response = view_func(request, *args, **kwargs)

            # 응답 헤더에 rate limit 정보 추가
            if isinstance(response, JsonResponse):
                response['X-RateLimit-Limit'] = str(limit)
                response['X-RateLimit-Remaining'] = str(remaining)
                response['X-RateLimit-Reset'] = str(reset_time)

            return response

        return wrapper
    return decorator


def log_decorator(msg):
    """데코레이터 로그를 파일에 작성"""
    import datetime
    try:
        with open('/home/ubuntu/voxliber/decorator_debug.log', 'a') as f:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] {msg}\n")
            f.flush()
    except Exception as e:
        pass  # 로그 실패해도 계속 진행

def require_api_key_secure(view_func):
    """
    보안이 강화된 API Key 인증 데코레이터
    - API key 검증
    - Rate limiting (100 req/min)
    - Origin 검증 (production only)
    - CSRF 보호를 대체하는 보안 강화

    이 데코레이터는 @csrf_exempt를 대체합니다.

    사용법:
        @require_api_key_secure
        def my_api_view(request):
            # request.api_user로 사용자 접근 가능
            return JsonResponse({'success': True})
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        log_decorator(f"🔐 [require_api_key_secure] 데코레이터 시작 - {view_func.__name__}")
        print(f"🔐 [require_api_key_secure] 데코레이터 시작 - {view_func.__name__}")

        # 1. API Key 검증
        # DRF Request와 Django HttpRequest 모두 지원
        try:
            log_decorator("  Step 1: API Key 추출 시작")
            if hasattr(request, 'query_params'):  # DRF Request
                api_key = request.headers.get('X-API-Key') or request.query_params.get('api_key')
            else:  # Django HttpRequest
                api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')

            log_decorator(f"🔑 [require_api_key_secure] API Key: {api_key[:10] if api_key else 'None'}...")
            print(f"🔑 [require_api_key_secure] API Key: {api_key[:10] if api_key else 'None'}...")

            if not api_key:
                log_decorator("❌ [require_api_key_secure] API Key 없음")
                print("❌ [require_api_key_secure] API Key 없음")
                return JsonResponse({
                    'error': 'API Key가 필요합니다.',
                    'message': 'HTTP 헤더에 X-API-Key를 포함하거나 URL 파라미터로 api_key를 전달하세요.'
                }, status=401)

            log_decorator("  Step 2: DB에서 API Key 조회 시작")
            api_key_obj = APIKey.objects.select_related('user').get(
                key=api_key,
                is_active=True
            )
            log_decorator(f"✅ [require_api_key_secure] API Key 검증 성공 - user: {api_key_obj.user.email}")
            print(f"✅ [require_api_key_secure] API Key 검증 성공 - user: {api_key_obj.user.email}")
        except APIKey.DoesNotExist:
            log_decorator("❌ [require_api_key_secure] 유효하지 않은 API Key")
            print("❌ [require_api_key_secure] 유효하지 않은 API Key")
            return JsonResponse({
                'error': '유효하지 않은 API Key입니다.'
            }, status=401)
        except Exception as e:
            log_decorator(f"❌ [require_api_key_secure] API Key 검증 중 예외: {e}")
            print(f"❌ [require_api_key_secure] API Key 검증 중 예외: {e}")
            import traceback
            log_decorator(traceback.format_exc())
            return JsonResponse({
                'error': f'API Key 검증 중 오류: {str(e)}'
            }, status=500)

        # 2. Origin 검증 (프로덕션에서만)
        log_decorator("  Step 2.1: Origin 검증 시작")
        if not settings.DEBUG:
            log_decorator("  Step 2.2: Production 모드, Origin 확인")
            origin = request.META.get('HTTP_ORIGIN', '')
            referer = request.META.get('HTTP_REFERER', '')
            print(f"🌐 [require_api_key_secure] Origin: '{origin}', Referer: '{referer}'")

            allowed_origins = [
                # 'https://voxliber.ink',
                # 'https://www.voxliber.ink',
                "*"
            ]

            # 모바일 앱은 origin이 없을 수 있음
            if origin or referer:
                is_valid_origin = any(
                    origin.startswith(allowed) or referer.startswith(allowed)
                    for allowed in allowed_origins
                )

                if not is_valid_origin:
                    print(f"❌ [require_api_key_secure] Invalid origin blocked")
                    return JsonResponse({
                        'error': 'Invalid origin',
                        'message': '허용되지 않는 출처에서의 요청입니다.'
                    }, status=403)
                print(f"✅ [require_api_key_secure] Origin 검증 통과")
            else:
                print(f"✅ [require_api_key_secure] Origin/Referer 없음 (모바일 앱), 검증 스킵")
        else:
            print(f"✅ [require_api_key_secure] DEBUG 모드, Origin 검증 스킵")

        # 3. Rate Limiting (100 requests per minute)
        log_decorator("  Step 2.3: Rate limiting 시작")
        try:
            ip = get_client_ip(request)
            cache_key = f'rate_limit:{ip}:{api_key_obj.user.user_id}:{view_func.__name__}'
            current_count = cache.get(cache_key, 0)
            log_decorator(f"  Rate limit - IP: {ip}, Count: {current_count}/100")

            if current_count >= 100:
                log_decorator("  Rate limit 초과")
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': '요청 제한을 초과했습니다. 1분당 최대 100회 요청 가능합니다.'
                }, status=429)

            # 카운터 증가
            if current_count == 0:
                cache.set(cache_key, 1, 60)
            else:
                cache.incr(cache_key)
            log_decorator("  Step 2.4: Rate limiting 통과")
        except Exception as e:
            log_decorator(f"❌ Rate limiting 오류: {e}")
            import traceback
            log_decorator(traceback.format_exc())

        # 4. API Key 마지막 사용 시간 업데이트
        log_decorator("  Step 2.5: API Key last_used_at 업데이트 시작")
        try:
            api_key_obj.last_used_at = timezone.now()
            api_key_obj.save(update_fields=['last_used_at'])
            log_decorator("  Step 2.6: API Key 업데이트 완료")
        except Exception as e:
            log_decorator(f"❌ API Key 업데이트 오류: {e}")
            import traceback
            log_decorator(traceback.format_exc())

        # 5. request에 사용자 정보 추가
        log_decorator("  Step 3: request 객체에 사용자 정보 추가")
        request.api_user = api_key_obj.user
        request.api_key_obj = api_key_obj

        log_decorator(f"✅ [require_api_key_secure] 모든 검증 통과, view 함수 호출: {view_func.__name__}")
        print(f"✅ [require_api_key_secure] 모든 검증 통과, view 함수 호출: {view_func.__name__}")

        try:
            result = view_func(request, *args, **kwargs)
            log_decorator(f"✅ [require_api_key_secure] View 함수 실행 완료: {view_func.__name__}")
            return result
        except Exception as e:
            log_decorator(f"❌ [require_api_key_secure] View 함수 실행 중 예외: {e}")
            import traceback
            log_decorator(traceback.format_exc())
            raise

    # CSRF exempt 적용 - Django의 csrf_exempt 데코레이터로 감싸기
    return csrf_exempt(wrapper)


def oauth_callback_secure(view_func):
    """
    OAuth 콜백 전용 보안 데코레이터
    - CSRF 검증 없음 (OAuth providers가 CSRF 토큰을 보낼 수 없음)
    - Rate limiting 적용
    - State parameter 검증 (선택적)

    사용법:
        @oauth_callback_secure
        def native_oauth_callback(request, provider):
            return JsonResponse({'success': True})
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Rate Limiting - OAuth callbacks에 대한 엄격한 제한
        ip = get_client_ip(request)
        cache_key = f'oauth_rate_limit:{ip}:{view_func.__name__}'
        current_count = cache.get(cache_key, 0)

        # OAuth callback은 1분에 5회로 제한 (더 엄격)
        if current_count >= 5:
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': 'OAuth 요청 제한을 초과했습니다. 잠시 후 다시 시도해주세요.'
            }, status=429)

        # 카운터 증가
        if current_count == 0:
            cache.set(cache_key, 1, 60)
        else:
            cache.incr(cache_key)

        # Origin 검증 (프로덕션에서만, 느슨하게)
        if not settings.DEBUG:
            origin = request.META.get('HTTP_ORIGIN', '')

            # 모바일 앱이나 허용된 도메인만 허용
            allowed_patterns = [
                'voxliber.ink',
                'localhost',
                'app://',  # Flutter 앱
            ]

            if origin:
                is_valid = any(pattern in origin for pattern in allowed_patterns)
                if not is_valid:
                    return JsonResponse({
                        'error': 'Invalid origin',
                        'message': '허용되지 않는 출처에서의 요청입니다.'
                    }, status=403)

        return view_func(request, *args, **kwargs)

    # OAuth 콜백은 CSRF 토큰을 보낼 수 없으므로 exempt 적용
    return csrf_exempt(wrapper)


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
