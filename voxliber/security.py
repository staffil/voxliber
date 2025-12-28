"""
Security utilities for file validation, rate limiting, and authentication.
"""
import mimetypes
import magic
from django.core.exceptions import ValidationError
from django.conf import settings
from functools import wraps
from django.http import JsonResponse
from django.core.cache import cache
import hashlib
import time


# ==================== File Upload Validation ====================

# Allowed file types
ALLOWED_IMAGE_TYPES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'image/webp': ['.webp'],
}

ALLOWED_AUDIO_TYPES = {
    'audio/mpeg': ['.mp3'],
    'audio/wav': ['.wav'],
    'audio/x-wav': ['.wav'],
    'audio/ogg': ['.ogg'],
    'audio/mp4': ['.m4a'],
    'audio/x-m4a': ['.m4a'],
}

ALLOWED_VIDEO_TYPES = {
    'video/mp4': ['.mp4'],
    'video/webm': ['.webm'],
    'video/quicktime': ['.mov'],
}

# File size limits (in bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_AUDIO_SIZE = 100 * 1024 * 1024  # 100MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB


def validate_file_size(file, max_size):
    """
    Validate file size.

    Args:
        file: UploadedFile object
        max_size: Maximum allowed size in bytes

    Raises:
        ValidationError: If file exceeds max size
    """
    if file.size > max_size:
        size_mb = max_size / (1024 * 1024)
        raise ValidationError(f'파일 크기가 너무 큽니다. 최대 {size_mb}MB까지 업로드 가능합니다.')


def validate_file_type(file, allowed_types):
    """
    Validate file type using both extension and MIME type.

    Args:
        file: UploadedFile object
        allowed_types: Dict of allowed MIME types and extensions

    Raises:
        ValidationError: If file type is not allowed
    """
    # Get file extension
    file_ext = '.' + file.name.split('.')[-1].lower() if '.' in file.name else ''

    # Try to detect MIME type from content (magic bytes)
    try:
        mime = magic.Magic(mime=True)
        file.seek(0)
        detected_mime = mime.from_buffer(file.read(2048))
        file.seek(0)
    except:
        # Fallback to guessing from filename
        detected_mime = mimetypes.guess_type(file.name)[0]

    # Check if MIME type is allowed
    if detected_mime not in allowed_types:
        raise ValidationError(f'지원하지 않는 파일 형식입니다. 허용된 형식: {", ".join(allowed_types.keys())}')

    # Check if extension matches MIME type
    if file_ext not in allowed_types[detected_mime]:
        raise ValidationError(f'파일 확장자({file_ext})가 파일 형식({detected_mime})과 일치하지 않습니다.')


def validate_image_file(file):
    """
    Validate uploaded image file.

    Args:
        file: UploadedFile object

    Raises:
        ValidationError: If validation fails
    """
    validate_file_size(file, MAX_IMAGE_SIZE)
    validate_file_type(file, ALLOWED_IMAGE_TYPES)


def validate_audio_file(file):
    """
    Validate uploaded audio file.

    Args:
        file: UploadedFile object

    Raises:
        ValidationError: If validation fails
    """
    validate_file_size(file, MAX_AUDIO_SIZE)
    validate_file_type(file, ALLOWED_AUDIO_TYPES)


def validate_video_file(file):
    """
    Validate uploaded video file.

    Args:
        file: UploadedFile object

    Raises:
        ValidationError: If validation fails
    """
    validate_file_size(file, MAX_VIDEO_SIZE)
    validate_file_type(file, ALLOWED_VIDEO_TYPES)


# ==================== Rate Limiting ====================

def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def rate_limit(limit=60, period=60, key_prefix='rate_limit'):
    """
    Rate limiting decorator.

    Args:
        limit: Number of requests allowed
        period: Time period in seconds
        key_prefix: Cache key prefix

    Usage:
        @rate_limit(limit=10, period=60)  # 10 requests per minute
        def my_view(request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Get client identifier (IP + user_id if authenticated)
            ip = get_client_ip(request)
            user_id = request.user.id if request.user.is_authenticated else 'anonymous'
            cache_key = f'{key_prefix}:{ip}:{user_id}:{func.__name__}'

            # Get current request count
            current = cache.get(cache_key, 0)

            if current >= limit:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'detail': f'최대 {limit}회/{period}초 요청 제한을 초과했습니다. 잠시 후 다시 시도해주세요.'
                }, status=429)

            # Increment counter
            cache.set(cache_key, current + 1, period)

            return func(request, *args, **kwargs)

        return wrapper
    return decorator


def api_rate_limit(limit=100, period=60):
    """
    Rate limiting decorator for API endpoints.
    More permissive than general rate limiting.

    Args:
        limit: Number of requests allowed (default: 100)
        period: Time period in seconds (default: 60)
    """
    return rate_limit(limit=limit, period=period, key_prefix='api_rate_limit')


def strict_rate_limit(limit=5, period=60):
    """
    Strict rate limiting decorator for sensitive operations.

    Args:
        limit: Number of requests allowed (default: 5)
        period: Time period in seconds (default: 60)
    """
    return rate_limit(limit=limit, period=period, key_prefix='strict_rate_limit')


# ==================== API Key Validation Enhancement ====================

def validate_request_signature(request, api_key):
    """
    Validate request signature to prevent replay attacks.

    Args:
        request: Django request object
        api_key: API key string

    Returns:
        bool: True if signature is valid
    """
    timestamp = request.META.get('HTTP_X_TIMESTAMP')
    signature = request.META.get('HTTP_X_SIGNATURE')

    if not timestamp or not signature:
        return False

    # Check if timestamp is recent (within 5 minutes)
    try:
        request_time = int(timestamp)
        current_time = int(time.time())
        if abs(current_time - request_time) > 300:  # 5 minutes
            return False
    except (ValueError, TypeError):
        return False

    # Verify signature
    expected_signature = hashlib.sha256(
        f"{api_key}{timestamp}{request.body.decode('utf-8', errors='ignore')}".encode()
    ).hexdigest()

    return signature == expected_signature


def require_api_key_with_origin_check(func):
    """
    Enhanced API key decorator that also checks request origin.
    This replaces @csrf_exempt with proper security.
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        from book.models import APIKey

        # Get API key from header
        api_key = request.META.get('HTTP_X_API_KEY')

        if not api_key:
            return JsonResponse({
                'error': 'API key required',
                'detail': 'X-API-Key header is missing'
            }, status=401)

        # Validate API key
        try:
            key_obj = APIKey.objects.get(key=api_key, is_active=True)
        except APIKey.DoesNotExist:
            return JsonResponse({
                'error': 'Invalid API key',
                'detail': 'The provided API key is invalid or inactive'
            }, status=401)

        # Check allowed origins for production
        if not settings.DEBUG:
            origin = request.META.get('HTTP_ORIGIN', '')
            referer = request.META.get('HTTP_REFERER', '')

            allowed_origins = [
                'https://voxliber.ink',
                'https://www.voxliber.ink',
                'app://voxliber',  # Mobile app
            ]

            is_valid_origin = any(
                origin.startswith(allowed) or referer.startswith(allowed)
                for allowed in allowed_origins
            )

            if not is_valid_origin and origin and referer:
                return JsonResponse({
                    'error': 'Invalid origin',
                    'detail': 'Request origin is not allowed'
                }, status=403)

        # Attach API key to request for use in view
        request.api_key = key_obj

        return func(request, *args, **kwargs)

    return wrapper


# ==================== CORS Headers for API ====================

def add_cors_headers(response, allowed_origins=None):
    """
    Add CORS headers to response.

    Args:
        response: Django response object
        allowed_origins: List of allowed origins (default: production domains)
    """
    if allowed_origins is None:
        allowed_origins = [
            'https://voxliber.ink',
            'https://www.voxliber.ink',
        ]
        if settings.DEBUG:
            allowed_origins.append('http://localhost:*')

    response['Access-Control-Allow-Origin'] = ', '.join(allowed_origins)
    response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key, X-Timestamp, X-Signature'
    response['Access-Control-Max-Age'] = '86400'  # 24 hours

    return response


# ==================== Input Sanitization ====================

def sanitize_text_input(text, max_length=10000):
    """
    Sanitize text input to prevent XSS and injection attacks.

    Args:
        text: Input text
        max_length: Maximum allowed length

    Returns:
        str: Sanitized text
    """
    if not text:
        return ''

    # Trim to max length
    text = text[:max_length]

    # Remove null bytes
    text = text.replace('\x00', '')

    # Django templates auto-escape HTML, but we sanitize SQL-injection patterns
    dangerous_patterns = [
        '--',  # SQL comment
        ';--',
        '/*',
        '*/',
        'xp_',  # SQL Server extended procedures
        'EXEC',
        'EXECUTE',
    ]

    text_upper = text.upper()
    for pattern in dangerous_patterns:
        if pattern in text_upper:
            raise ValidationError('입력에 허용되지 않는 문자가 포함되어 있습니다.')

    return text.strip()


def validate_json_input(data, required_fields=None, max_nesting=5):
    """
    Validate JSON input.

    Args:
        data: Parsed JSON data (dict or list)
        required_fields: List of required field names
        max_nesting: Maximum allowed nesting depth

    Raises:
        ValidationError: If validation fails
    """
    def check_depth(obj, current_depth=0):
        if current_depth > max_nesting:
            raise ValidationError('JSON 데이터가 너무 깊게 중첩되어 있습니다.')

        if isinstance(obj, dict):
            for value in obj.values():
                check_depth(value, current_depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                check_depth(item, current_depth + 1)

    # Check nesting depth
    check_depth(data)

    # Check required fields
    if required_fields and isinstance(data, dict):
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValidationError(f'필수 필드가 누락되었습니다: {", ".join(missing_fields)}')
