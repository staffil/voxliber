"""
안드로이드 앱용 REST API 뷰
읽기 전용 API만 제공
"""
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Max, Q
from book.models import Books, Content, BookReview, ReadingProgress, ListeningHistory, Poem_list, BookSnippet, Tags, Follow, BookmarkBook
from book.api_utils import require_api_key, require_api_key_secure, paginate, api_response
from rest_framework.decorators import api_view
import json


# ==================== 📚 Books API ====================

@require_api_key
def api_books_list(request):
    """
    책 목록 API

    Query Parameters:
        - page: 페이지 번호 (기본: 1)
        - per_page: 페이지당 아이템 수 (기본: 20, 최대: 100)
        - genre: 장르 ID (선택)
        - status: ongoing/paused/ended (선택)
        - search: 검색어 (책 제목, 작가 닉네임)

    Example:
        GET /api/books/?page=1&per_page=20&search=판타지
    """
    # 쿼리 파라미터
    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 20)
    genre_id = request.GET.get('genre')
    status = request.GET.get('status')
    search = request.GET.get('search')

    # 기본 쿼리
    books = Books.objects.select_related('user').prefetch_related(
        'genres', 'tags'
    ).annotate(
        episodes_count=Count('contents'),
        avg_rating=Avg('reviews__rating')
    )

    # 필터링
    if genre_id:
        books = books.filter(genres__id=genre_id)
    if status:
        books = books.filter(status=status)
    if search:
        books = books.filter(name__icontains=search) | books.filter(user__nickname__icontains=search)

    # 정렬
    books = books.order_by('-created_at')

    # 페이지네이션
    result = paginate(books, page, per_page)

    # 데이터 직렬화
    books_data = []
    for book in result['items']:
        books_data.append({
            'id': book.id,
            'name': book.name,
            'description': book.description,
            'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
            'status': book.status,
            'status_display': book.get_status_display(),
            'book_score': float(book.book_score),
            'avg_rating': float(book.avg_rating) if book.avg_rating else 0,
            'episodes_count': book.episodes_count,
            'total_duration': book.get_total_duration_formatted(),
            'created_at': book.created_at.isoformat(),
            'author': {
                'id': book.user.user_id,
                'nickname': book.user.nickname,
            },
            'genres': [
                {'id': g.id, 'name': g.name, 'color': g.genres_color}
                for g in book.genres.all()
            ],
            'tags': [
                {'id': t.id, 'name': t.name}
                for t in book.tags.all()
            ]
        })

    return api_response({
        'books': books_data,
        'pagination': result['pagination']
    })


@require_api_key
def api_book_detail(request, book_id):
    """
    책 상세 정보 API (에피소드 포함)

    Example:
        GET /api/books/1/
    """
    book = get_object_or_404(
        Books.objects.select_related('user')
        .prefetch_related('genres', 'tags', 'contents')
        .annotate(
            episodes_count=Count('contents'),
            avg_rating=Avg('reviews__rating'),
            reviews_count=Count('reviews')
        ),
        id=book_id
    )

    # 최근 5개 리뷰
    recent_reviews = book.reviews.select_related('user').order_by('-created_at')[:5]

    data = {
        'id': book.id,
        'name': book.name,
        'description': book.description,
        'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
        'audio_file': request.build_absolute_uri(book.audio_file.url) if book.audio_file else None,
        'status': book.status,
        'status_display': book.get_status_display(),
        'book_score': float(book.book_score),
        'avg_rating': float(book.avg_rating) if book.avg_rating else 0,
        'episodes_count': book.episodes_count,
        'reviews_count': book.reviews_count,
        'total_duration': book.get_total_duration_formatted(),
        'total_duration_seconds': book.get_total_duration_seconds(),
        'episode_interval_weeks': book.episode_interval_weeks,
        'created_at': book.created_at.isoformat(),
        'author': {
            'id': book.user.user_id,
            'nickname': book.user.nickname,
            'email': book.user.email,
        },
        'genres': [
            {'id': g.id, 'name': g.name, 'color': g.genres_color}
            for g in book.genres.all()
        ],
        'tags': [
            {'id': t.id, 'name': t.name}
            for t in book.tags.all()
        ],
        'contents': [
            {
                'id': content.id,
                'title': content.title,
                'number': content.number,
                'text': content.text,
                'episode_image': request.build_absolute_uri(content.episode_image.url) if content.episode_image else None,
                'audio_file': request.build_absolute_uri(content.audio_file.url) if content.audio_file else None,
                'duration_seconds': content.duration_seconds,
                'duration_formatted': content.get_duration_formatted(),
                'audio_timestamps': content.audio_timestamps
            } for content in book.contents.all().order_by('number')
        ],
        'recent_reviews': [
            {
                'id': r.id,
                'rating': r.rating,
                'review_text': r.review_text,
                'created_at': r.created_at.isoformat(),
                'user': {
                    'nickname': r.user.nickname
                }
            }
            for r in recent_reviews
        ]
    }

    return api_response(data)


# ==================== 📖 Contents (Episodes) API ====================

@require_api_key
def api_contents_list(request, book_id):
    """
    에피소드 목록 API

    Query Parameters:
        - page: 페이지 번호 (기본: 1)
        - per_page: 페이지당 아이템 수 (기본: 20)

    Example:
        GET /api/books/1/contents/
    """
    book = get_object_or_404(Books, id=book_id)

    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 20)

    contents = Content.objects.filter(book=book).order_by('number')

    result = paginate(contents, page, per_page)

    contents_data = []
    for content in result['items']:
        contents_data.append({
            'id': content.id,
            'title': content.title,
            'number': content.number,
            'episode_image': request.build_absolute_uri(content.episode_image.url) if content.episode_image else None,
            'audio_url': request.build_absolute_uri(content.audio_file.url) if content.audio_file else None,
            'duration_seconds': content.duration_seconds,
            'duration_formatted': content.get_duration_formatted(),
            'created_at': content.created_at.isoformat(),
        })

    return api_response({
        'book': {
            'id': book.id,
            'name': book.name
        },
        'contents': contents_data,
        'pagination': result['pagination']
    })


@require_api_key
def api_content_detail(request, content_id):
    """
    에피소드 상세 정보 API

    Example:
        GET /api/contents/1/
    """
    content = get_object_or_404(
        Content.objects.select_related('book', 'book__user'),
        id=content_id
    )

    # 이전/다음 에피소드
    prev_content = Content.objects.filter(
        book=content.book,
        number__lt=content.number
    ).order_by('-number').first()

    next_content = Content.objects.filter(
        book=content.book,
        number__gt=content.number
    ).order_by('number').first()

    data = {
        'id': content.id,
        'title': content.title,
        'number': content.number,
        'text': content.text,
        'episode_image': request.build_absolute_uri(content.episode_image.url) if content.episode_image else None,
        'audio_url': request.build_absolute_uri(content.audio_file.url) if content.audio_file else None,
        'audio_timestamps': content.audio_timestamps,
        'duration_seconds': content.duration_seconds,
        'duration_formatted': content.get_duration_formatted(),
        'created_at': content.created_at.isoformat(),
        'book': {
            'id': content.book.id,
            'name': content.book.name,
            'cover_img': request.build_absolute_uri(content.book.cover_img.url) if content.book.cover_img else None,
            'author': {
                'id': content.book.user.user_id,
                'nickname': content.book.user.nickname
            }
        },
        'navigation': {
            'prev': {
                'id': prev_content.id,
                'title': prev_content.title,
                'number': prev_content.number
            } if prev_content else None,
            'next': {
                'id': next_content.id,
                'title': next_content.title,
                'number': next_content.number
            } if next_content else None
        }
    }

    return api_response(data)


# ==================== ⭐ Reviews API ====================

@require_api_key
def api_reviews_list(request, book_id):
    """
    책 리뷰 목록 API

    Query Parameters:
        - page: 페이지 번호 (기본: 1)
        - per_page: 페이지당 아이템 수 (기본: 20)

    Example:
        GET /api/books/1/reviews/
    """
    book = get_object_or_404(Books, id=book_id)

    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 20)

    reviews = BookReview.objects.filter(book=book).select_related('user').order_by('-created_at')

    result = paginate(reviews, page, per_page)

    reviews_data = []
    for review in result['items']:
        reviews_data.append({
            'id': review.id,
            'rating': review.rating,
            'review_text': review.review_text,
            'created_at': review.created_at.isoformat(),
            'updated_at': review.updated_at.isoformat(),
            'user': {
                'nickname': review.user.nickname
            }
        })

    return api_response({
        'book': {
            'id': book.id,
            'name': book.name,
            'avg_rating': float(book.book_score)
        },
        'reviews': reviews_data,
        'pagination': result['pagination']
    })


# ==================== 📊 User Progress API ====================

@require_api_key
def api_my_progress(request):
    """
    내 독서 진행 상황 API

    Query Parameters:
        - status: reading/wishlist/completed (선택)

    Example:
        GET /api/my/progress/?status=reading
    """
    status_filter = request.GET.get('status')

    progress_list = ReadingProgress.objects.filter(
        user=request.api_user
    ).select_related('book', 'current_content')

    if status_filter:
        progress_list = progress_list.filter(status=status_filter)

    progress_list = progress_list.order_by('-last_read_at')

    progress_data = []
    for progress in progress_list:
        progress_data.append({
            'id': progress.id,
            'status': progress.status,
            'status_display': progress.get_status_display(),
            'last_read_content_number': progress.last_read_content_number,
            'last_read_at': progress.last_read_at.isoformat() if progress.last_read_at else None,
            'completed_at': progress.completed_at.isoformat() if progress.completed_at else None,
            'book': {
                'id': progress.book.id,
                'name': progress.book.name,
                'cover_img': request.build_absolute_uri(progress.book.cover_img.url) if progress.book.cover_img else None,
                'total_episodes': progress.book.contents.count()
            },
            'current_content': {
                'id': progress.current_content.id,
                'title': progress.current_content.title,
                'number': progress.current_content.number
            } if progress.current_content else None
        })

    return api_response({'progress': progress_data})


@require_api_key
def api_my_listening_history(request):
    """
    내 청취 기록 API

    Example:
        GET /api/my/listening-history/
    """
    qs = ListeningHistory.objects.filter(
        user=request.api_user,
        last_position__gt=0
    ).select_related('book', 'content').order_by('-last_listened_at')

    seen_books = set()
    history = []

    for lh in qs:
        if lh.book_id not in seen_books:  # 아직 추가되지 않은 책이면
            history.append(lh)
            seen_books.add(lh.book_id)
        if len(history) >= 5:  # 최대 5권까지만
            break

    history_data = []
    for h in history:
        history_data.append({
            'id': h.id,
            'listened_seconds': h.listened_seconds,
            'last_position': h.last_position,
            'last_listened_at': h.last_listened_at.isoformat(),
            'book': {
                'id': h.book.id,
                'name': h.book.name,
                'cover_img': h.book.cover_img.url if h.book.cover_img else None,
                'author': {
                    'id': h.book.user.user_id if h.book.user else None,
                    'nickname': h.book.user.nickname if h.book.user else None,
                } if h.book.user else None,
            },
            'content': {
                'id': h.content.id,
                'title': h.content.title,
                'number': h.content.number,
                'text':h.content.text,
                'audio_file': h.content.audio_file.url if h.content.audio_file else None,
                'episode_image': h.content.episode_image.url if h.content.episode_image else None,
            }
        })

    return api_response({'listening_history': history_data})


# ==================== 🔑 API Key 관리 ====================

@require_api_key
def api_key_info(request):
    """
    현재 API Key 정보 확인

    Example:
        GET /api/key/info/
    """
    api_key = request.api_key_obj

    return api_response({
        'key': api_key.key[:10] + '...',  # 일부만 표시
        'name': api_key.name,
        'user': {
            'id': api_key.user.user_id,
            'nickname': api_key.user.nickname,
            'email': api_key.user.email
        },
        'created_at': api_key.created_at.isoformat(),
        'last_used_at': api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        'is_active': api_key.is_active
    })


# ==================== 🔐 인증 API (로그인/로그아웃) ====================

def api_login(request):
    """
    사용자 로그인 API
    아이디/비밀번호로 로그인하여 API Key를 받습니다.

    POST Body (JSON):
        {
            "username": "user@example.com",  // email 또는 username
            "password": "mypassword"
        }

    Response:
        {
            "token": "PMU6Lvokw_jce...",
            "user": {
                "id": 1,
                "username": "user123",
                "email": "user@example.com",
                "nickname": "사용자"
            },
            "api_key": "PMU6Lvokw_jce..."
        }

    Example:
        POST /api/auth/login/
        Content-Type: application/json

        {"username": "test@example.com", "password": "password123"}
    """
    if request.method != 'POST':
        return JsonResponse({'message': 'POST 요청만 허용됩니다.'}, status=405)

    try:
        import json
        data = json.loads(request.body)
        username = data.get('username') or data.get('email')
        password = data.get('password')

        if not username or not password:
            return JsonResponse({'message': '아이디와 비밀번호가 필요합니다.'}, status=400)

        # Django 인증
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # 이메일 또는 username으로 사용자 찾기
        user = None
        try:
            # 먼저 이메일로 시도
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            try:
                # 이메일로 찾지 못하면 username으로 시도
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return JsonResponse({'message': '존재하지 않는 사용자입니다.'}, status=401)

        # 비밀번호 확인
        if not user.check_password(password):
            return JsonResponse({'message': '비밀번호가 일치하지 않습니다.'}, status=401)

        # API Key 생성 또는 기존 키 반환
        from book.models import APIKey
        import secrets

        # 기존 활성화된 API Key 찾기
        api_key_obj = APIKey.objects.filter(
            user=user,
            name='모바일 앱',
            is_active=True
        ).first()

        # 없으면 새로 생성
        if not api_key_obj:
            api_key_obj = APIKey.objects.create(
                user=user,
                name='모바일 앱',
                key=secrets.token_urlsafe(48)
            )

        # 마지막 사용 시간 업데이트
        from django.utils import timezone
        api_key_obj.last_used_at = timezone.now()
        api_key_obj.save(update_fields=['last_used_at'])

        # 프로필 이미지 안전하게 가져오기
        profile_image_url = None
        if hasattr(user, 'user_img') and user.user_img:
            try:
                profile_image_url = request.build_absolute_uri(user.user_img.url)
            except:
                profile_image_url = None

        # 앱이 기대하는 형식으로 반환 (api_response 래퍼 사용 안 함)
        return JsonResponse({
            'token': api_key_obj.key,  # token 필드 (필수)
            'user': {
                'id': user.user_id,
                'username': user.username,
                'email': user.email,
                'nickname': user.nickname,
                'first_name': user.first_name if hasattr(user, 'first_name') else None,
                'last_name': user.last_name if hasattr(user, 'last_name') else None,
                'profile_img': profile_image_url
            },
            'api_key': api_key_obj.key  # api_key 필드 (선택)
        })

    except json.JSONDecodeError:
        return JsonResponse({'message': '잘못된 JSON 형식입니다.'}, status=400)
    except Exception as e:
        return JsonResponse({'message': f'로그인 중 오류가 발생했습니다: {str(e)}'}, status=500)


def api_register(request):
    """
    사용자 회원가입 API
    새로운 사용자를 생성하고 API Key를 발급합니다.

    POST Body (JSON):
        {
            "username": "user123",
            "email": "user@example.com",
            "password": "mypassword",
            "first_name": "홍",  // 선택
            "last_name": "길동"   // 선택
        }

    Response:
        {
            "token": "PMU6Lvokw_jce...",
            "user": {
                "id": 1,
                "username": "user123",
                "email": "user@example.com",
                "nickname": "user123"
            },
            "api_key": "PMU6Lvokw_jce..."
        }
    """
    if request.method != 'POST':
        return JsonResponse({'message': 'POST 요청만 허용됩니다.'}, status=405)

    try:
        import json
        data = json.loads(request.body)
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')

        # 필수 필드 검증
        if not username or not email or not password:
            return JsonResponse({'message': '아이디, 이메일, 비밀번호는 필수입니다.'}, status=400)

        # Django User 모델
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # 중복 체크
        if User.objects.filter(username=username).exists():
            return JsonResponse({'message': '이미 존재하는 아이디입니다.'}, status=400)

        if User.objects.filter(email=email).exists():
            return JsonResponse({'message': '이미 존재하는 이메일입니다.'}, status=400)

        # 사용자 생성
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # nickname 기본값 설정 (username 사용)
        if hasattr(user, 'nickname') and not user.nickname:
            user.nickname = username
            user.save(update_fields=['nickname'])

        # API Key 생성
        from book.models import APIKey
        import secrets

        api_key_obj = APIKey.objects.create(
            user=user,
            name='모바일 앱',
            key=secrets.token_urlsafe(48)
        )

        # 마지막 사용 시간 업데이트
        from django.utils import timezone
        api_key_obj.last_used_at = timezone.now()
        api_key_obj.save(update_fields=['last_used_at'])

        # 앱이 기대하는 형식으로 반환
        return JsonResponse({
            'token': api_key_obj.key,
            'user': {
                'id': user.user_id if hasattr(user, 'user_id') else user.id,
                'username': user.username,
                'email': user.email,
                'nickname': user.nickname if hasattr(user, 'nickname') else username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'profile_img': None
            },
            'api_key': api_key_obj.key
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'message': '잘못된 JSON 형식입니다.'}, status=400)
    except Exception as e:
        return JsonResponse({'message': f'회원가입 중 오류가 발생했습니다: {str(e)}'}, status=500)


@require_api_key_secure
def api_logout(request):
    """
    사용자 로그아웃 API
    현재 사용 중인 API Key를 비활성화합니다.

    Example:
        POST /api/auth/logout/
        X-API-Key: your-api-key
    """
    if request.method != 'POST':
        return api_response(error='POST 요청만 허용됩니다.', status=405)

    try:
        # 현재 API Key 비활성화
        api_key_obj = request.api_key_obj
        api_key_obj.is_active = False
        api_key_obj.save(update_fields=['is_active'])

        return api_response({
            'message': '로그아웃되었습니다.',
            'user': {
                'nickname': api_key_obj.user.nickname
            }
        })

    except Exception as e:
        return api_response(error=f'로그아웃 중 오류가 발생했습니다: {str(e)}', status=500)


@require_api_key_secure
def api_refresh_key(request):
    """
    API Key 재발급 API
    보안을 위해 새로운 API Key를 생성합니다.

    Example:
        POST /api/auth/refresh-key/
        X-API-Key: your-old-api-key
    """
    if request.method != 'POST':
        return api_response(error='POST 요청만 허용됩니다.', status=405)

    try:
        import secrets
        from django.utils import timezone
        from book.models import APIKey

        # 기존 키 비활성화
        old_key = request.api_key_obj
        old_key.is_active = False
        old_key.save(update_fields=['is_active'])

        # 새 키 생성
        new_key = APIKey.objects.create(
            user=old_key.user,
            name='모바일 앱',
            key=secrets.token_urlsafe(48),
            last_used_at=timezone.now()
        )

        return api_response({
            'message': 'API Key가 재발급되었습니다.',
            'api_key': new_key.key,
            'user': {
                'id': new_key.user.user_id,
                'nickname': new_key.user.nickname,
                'email': new_key.user.email
            }
        })

    except Exception as e:
        return api_response(error=f'API Key 재발급 중 오류가 발생했습니다: {str(e)}', status=500)


# ==================== 🏠 Home Page API ====================

def _serialize_book(book, request):
    """책 데이터를 직렬화"""
    # 작가 정보 안전하게 가져오기
    author_data = None
    if hasattr(book, 'user') and book.user:
        try:
            author_data = {
                'id': getattr(book.user, 'user_id', getattr(book.user, 'id', None)),
                'nickname': getattr(book.user, 'nickname', 'Unknown'),
                'email': getattr(book.user, 'email', '')
            }
        except:
            author_data = None

    return {
        'id': book.id,
        'name': book.name,
        'description': book.description or '',
        'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
        'book_score': float(book.book_score) if book.book_score else 0.0,
        'created_at': book.created_at.isoformat() if book.created_at else None,
        'author': author_data,
        'genres': [
            {'id': g.id, 'name': g.name, 'description': ''}
            for g in book.genres.all()
        ],
        'episode_count': book.contents.count()
    }


def _serialize_banner(banner, request):
    """배너 데이터를 직렬화"""
    return {
        'id': banner.id,
        'link': banner.link,
        'advertisment_img': request.build_absolute_uri(banner.advertisment_img.url) if banner.advertisment_img else None
    }


@require_api_key
def api_home_sections(request):
    """
    홈 페이지 통합 데이터 API
    한 번의 요청으로 홈 페이지의 모든 섹션 데이터를 가져옵니다.

    Response:
        {
            "success": true,
            "data": {
                "banners": [...],
                "popular_books": [...],
                "trending_books": [...],
                "new_books": [...],
                "top_rated_books": [...],
                "genres_with_books": [...]
            }
        }

    Example:
        GET /book/api/home/sections/
    """
    from django.utils import timezone
    from datetime import timedelta
    from main.models import Advertisment
    from book.models import Genres

    thirty_days_ago = timezone.now() - timedelta(days=30)
    seven_days_ago = timezone.now() - timedelta(days=7)

    # 인기 작품 (평점과 에피소드 수를 고려한 종합 점수) - 랜덤 정렬
    popular_books = Books.objects.select_related('user').prefetch_related('genres').annotate(
        total_score=Count('contents') * 0.1 + Count('reviews') * 0.3
    ).order_by('-book_score', '-total_score')[:50]  # 상위 50개 가져온 후
    popular_books = sorted(list(popular_books), key=lambda x: __import__('random').random())[:12]  # 랜덤 12개

    # 트렌딩 작품 (최근 인기작 - 신작 제외) - 랜덤 정렬
    trending_books = Books.objects.filter(
        created_at__lte=seven_days_ago
    ).select_related('user').prefetch_related('genres').annotate(
        episode_count=Count('contents')
    ).order_by('-book_score', '-episode_count')[:30]  # 상위 30개 가져온 후
    trending_books = sorted(list(trending_books), key=lambda x: __import__('random').random())[:8]  # 랜덤 8개

    # 신작 (최근 30일) - 랜덤 정렬
    new_books = Books.objects.filter(
        created_at__gte=thirty_days_ago
    ).annotate(
        last_content_time=Max('contents__created_at')
    ).select_related('user').prefetch_related('genres').order_by('-last_content_time')[:50]  # 상위 50개 가져온 후
    new_books = sorted(list(new_books), key=lambda x: __import__('random').random())[:20]  # 랜덤 20개

    # 최고 평점 - 랜덤 정렬
    top_rated_books = Books.objects.filter(
        book_score__gt=0
    ).select_related('user').prefetch_related('genres').order_by('-book_score')[:30]  # 상위 30개 가져온 후
    top_rated_books = sorted(list(top_rated_books), key=lambda x: __import__('random').random())[:8]  # 랜덤 8개

    # 배너
    banners = Advertisment.objects.all()[:5]

    # 장르별 책
    all_genres = Genres.objects.all()[:6]
    genres_data = []
    for genre in all_genres:
        genre_books = Books.objects.filter(
            genres=genre
        ).select_related('user').prefetch_related('genres').order_by('-book_score')[:6]
        if genre_books.exists():
            genres_data.append({
                'genre': {
                    'id': genre.id,
                    'name': genre.name,
                    'description': ''
                },
                'books': [_serialize_book(book, request) for book in genre_books]
            })

    return api_response({
        'banners': [_serialize_banner(banner, request) for banner in banners],
        'popular_books': [_serialize_book(book, request) for book in popular_books],
        'trending_books': [_serialize_book(book, request) for book in trending_books],
        'new_books': [_serialize_book(book, request) for book in new_books],
        'top_rated_books': [_serialize_book(book, request) for book in top_rated_books],
        'genres_with_books': genres_data,
    })


@require_api_key
def api_popular_books(request):
    """
    인기 작품 목록 API

    Query Parameters:
        - limit: 결과 개수 (기본: 12)

    Example:
        GET /book/api/books/popular/?limit=12
    """
    limit = int(request.GET.get('limit', 12))
    books = Books.objects.select_related('user').prefetch_related('genres').annotate(
        total_score=Count('contents') * 0.1 + Count('reviews') * 0.3
    ).order_by('-book_score', '-total_score')[:limit]

    return api_response([_serialize_book(book, request) for book in books])


@require_api_key
def api_trending_books(request):
    """
    트렌딩 작품 목록 API

    Query Parameters:
        - limit: 결과 개수 (기본: 8)

    Example:
        GET /book/api/books/trending/?limit=8
    """
    from django.utils import timezone
    from datetime import timedelta

    limit = int(request.GET.get('limit', 8))
    seven_days_ago = timezone.now() - timedelta(days=7)

    books = Books.objects.filter(
        created_at__lte=seven_days_ago
    ).select_related('user').prefetch_related('genres').annotate(
        episode_count=Count('contents')
    ).order_by('-book_score', '-episode_count')[:limit]

    return api_response([_serialize_book(book, request) for book in books])


@require_api_key
def api_new_books(request):
    """
    신작 목록 API (최근 30일)

    Query Parameters:
        - limit: 결과 개수 (기본: 20)

    Example:
        GET /book/api/books/new/?limit=20
    """
    from django.utils import timezone
    from datetime import timedelta

    limit = int(request.GET.get('limit', 20))
    thirty_days_ago = timezone.now() - timedelta(days=30)

    books = Books.objects.filter(
        created_at__gte=thirty_days_ago
    ).annotate(
        last_content_time=Max('contents__created_at')
    ).select_related('user').prefetch_related('genres').order_by('-last_content_time')[:limit]

    return api_response([_serialize_book(book, request) for book in books])


@require_api_key
def api_top_rated_books(request):
    """
    최고 평점 작품 목록 API

    Query Parameters:
        - limit: 결과 개수 (기본: 8)

    Example:
        GET /book/api/books/top-rated/?limit=8
    """
    limit = int(request.GET.get('limit', 8))
    books = Books.objects.filter(
        book_score__gt=0
    ).select_related('user').prefetch_related('genres').order_by('-book_score')[:limit]

    return api_response([_serialize_book(book, request) for book in books])


@require_api_key
def api_banners(request):
    """
    배너(광고) 목록 API

    Example:
        GET /book/api/banners/
    """
    from main.models import Advertisment

    banners = Advertisment.objects.all()
    return api_response([_serialize_banner(banner, request) for banner in banners])


@require_api_key
def api_genres_list(request):
    """
    장르 목록 API

    Example:
        GET /book/api/genres/
    """
    from book.models import Genres

    genres = Genres.objects.all()
    genres_data = [
        {'id': g.id, 'name': g.name, 'description': ''}
        for g in genres
    ]
    return api_response(genres_data)


@require_api_key
def api_genre_books(request, genre_id):
    """
    특정 장르의 책 목록 API

    Query Parameters:
        - limit: 결과 개수 (기본: 6)

    Example:
        GET /book/api/genres/1/books/?limit=6
    """
    limit = int(request.GET.get('limit', 6))
    books = Books.objects.filter(
        genres__id=genre_id
    ).select_related('user').prefetch_related('genres').order_by('-book_score')[:limit]

    return api_response([_serialize_book(book, request) for book in books])


@require_api_key
def api_search_books(request):
    """
    책 검색 API

    Query Parameters:
        - q: 검색어 (필수)
        - type: 검색 타입 - 'book' 또는 'author' (기본: 'book')

    Example:
        GET /book/api/books/search/?q=판타지
        GET /book/api/books/search/?q=작가이름&type=author
    """
    from django.db.models import Q

    query = request.GET.get('q', '').strip()

    if not query:
        return api_response([])

    # 책 검색 (제목, 설명으로 검색)
    books = Books.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(user__nickname__icontains=query)
    ).select_related('user').prefetch_related('genres').distinct()[:50]

    return api_response([_serialize_book(book, request) for book in books])


# ==================== 📸 Book Snap API ====================

@require_api_key
def api_snaps_list(request):
    """
    스냅 목록 API

    Query Parameters:
        - page: 페이지 번호 (기본: 1)
        - per_page: 페이지당 아이템 수 (기본: 20)

    Example:
        GET /book/api/snaps/?page=1&per_page=20
    """
    from book.models import BookSnap

    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    snaps = BookSnap.objects.select_related('user').prefetch_related(
        'booksnap_like', 'comments'
    ).order_by('?')

    # 페이지네이션
    start = (page - 1) * per_page
    end = start + per_page
    total = snaps.count()
    snaps_page = snaps[start:end]

    snaps_data = []
    for snap in snaps_page:
        snaps_data.append({
            'id': snap.id,
            'snap_title': snap.snap_title,
            'snap_video': request.build_absolute_uri(snap.snap_video.url) if snap.snap_video else None,
            'thumbnail': request.build_absolute_uri(snap.thumbnail.url) if snap.thumbnail else None,
            'likes_count': snap.booksnap_like.count(),
            'views': snap.views,
            'shares': snap.shares,
            'comments_count': snap.comments.count(),
            'allow_comments': snap.allow_comments,
            'book_id': snap.book.id if snap.book else None,
            'book_link': snap.book_link,
            'book_comment': snap.book_comment,
            'duration': snap.duration,
            'created_at': snap.created_at.isoformat(),
            'user': {
                'id': snap.user.user_id if snap.user else None,
                'nickname': snap.user.nickname if snap.user else 'Unknown',
                'profile_img': request.build_absolute_uri(snap.user.user_img.url) if snap.user and snap.user.user_img else None,
            } if snap.user else None,
        })

    return api_response({
        'snaps': snaps_data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page,
        }
    })


@require_api_key
def api_snap_detail(request, snap_id):
    """
    스냅 상세 정보 API

    Example:
        GET /book/api/snaps/1/
    """
    from book.models import BookSnap

    snap = get_object_or_404(
        BookSnap.objects.select_related('user').prefetch_related(
            'booksnap_like', 'comments__user'
        ),
        id=snap_id
    )

    # 댓글 데이터
    comments_data = []
    for comment in snap.comments.filter(parent__isnull=True).order_by('-created_at')[:50]:
        comments_data.append({
            'id': comment.id,
            'content': comment.content,
            'likes': comment.likes,
            'created_at': comment.created_at.isoformat(),
            'user': {
                'id': comment.user.user_id if comment.user else None,
                'nickname': comment.user.nickname if comment.user else 'Unknown',
                'profile_img': request.build_absolute_uri(comment.user.user_img.url) if comment.user and comment.user.user_img else None,
            },
            'replies_count': comment.replies.count(),
        })

    data = {
        'id': snap.id,
        'snap_title': snap.snap_title,
        'snap_video': request.build_absolute_uri(snap.snap_video.url) if snap.snap_video else None,
        'thumbnail': request.build_absolute_uri(snap.thumbnail.url) if snap.thumbnail else None,
        'likes_count': snap.booksnap_like.count(),
        'views': snap.views,
        'shares': snap.shares,
        'comments_count': snap.comments.count(),
        'allow_comments': snap.allow_comments,
        'book_id': snap.book.id if snap.book else None,
        'book_link': snap.book_link,
        'book_comment': snap.book_comment,
        'duration': snap.duration,
        'created_at': snap.created_at.isoformat(),
        'user': {
            'id': snap.user.user_id if snap.user else None,
            'nickname': snap.user.nickname if snap.user else 'Unknown',
            'profile_img': request.build_absolute_uri(snap.user.user_img.url) if snap.user and snap.user.user_img else None,
        } if snap.user else None,
        'comments': comments_data,
    }

    return api_response(data)


@api_view(['POST'])
@require_api_key_secure
def api_snap_like(request, snap_id):
    """
    스냅 좋아요 토글 API

    Example:
        POST /book/api/snaps/1/like/
    """
    from book.models import BookSnap, APIKey

    snap = get_object_or_404(BookSnap, id=snap_id)

    # API 키로 사용자 확인
    api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API key required'}, status=401)

    try:
        api_key_obj = APIKey.objects.get(key=api_key)
        user = api_key_obj.user
    except APIKey.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid API Key'}, status=401)

    if user in snap.booksnap_like.all():
        snap.booksnap_like.remove(user)
        liked = False
    else:
        snap.booksnap_like.add(user)
        liked = True

    return JsonResponse({
        'success': True,
        'data': {
            'liked': liked,
            'likes_count': snap.booksnap_like.count(),
        }
    })

@api_view(['POST'])
@require_api_key_secure
def api_snap_comment(request, snap_id):
    from book.models import BookSnap, BookSnapComment, APIKey
    import json

    snap = get_object_or_404(BookSnap, id=snap_id)


    # API Key로 유저 가져오기
    api_key = request.GET.get('api_key')
    try:
        api_key_obj = APIKey.objects.select_related('user').get(key=api_key, is_active=True)
        user = api_key_obj.user
    except APIKey.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid API Key'}, status=401)

    # 댓글 허용 여부 확인
    if not snap.allow_comments:
        return JsonResponse({'success': False, 'error': 'Comments are disabled for this snap'}, status=403)

    # 요청 본문에서 댓글 내용 가져오기
    try:
        data = json.loads(request.body)
        content = data.get('content', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    if not content:
        return JsonResponse({'success': False, 'error': 'Comment content is required'}, status=400)

    # 댓글 생성
    comment = BookSnapComment.objects.create(
        snap=snap,
        user=user,
        content=content
    )

    return JsonResponse({
        'success': True,
        'data': {
            'id': comment.id,
            'content': comment.content,
            'likes': comment.likes,
            'created_at': comment.created_at.isoformat(),
            'user': {
                'id': user.user_id,
                'nickname': user.nickname,
                'profile_img': request.build_absolute_uri(user.user_img.url) if user.user_img else None,
            },
            'replies_count': 0,
        }
    })


from book.models import BookSnap
@require_api_key_secure
def snap_main_view(request):
    snap_qs = BookSnap.objects.all().order_by("?")
    snap_list = []
    for s in snap_qs:
        snap_list.append({
            'id': s.id,
            'snap_title': s.snap_title,
            'snap_video': request.build_absolute_uri(s.snap_video.url) if s.snap_video else None,
            'thumbnail': request.build_absolute_uri(s.thumbnail.url) if s.thumbnail else None,
        })
    return JsonResponse({'snaps': snap_list})



from main.models import SnapBtn, Advertisment

@require_api_key_secure
def api_main_new(reqeust):
    news_qs = SnapBtn.objects.all().order_by("-id")
    news_list= []
    for n in news_qs:
        news_list.append({
            'id': n.id,
            'title': n.title,
            'description': n.news_description,
            'img': reqeust.build_absolute_uri(n.news_img.url) if n.news_img else None,
            'link': n.news_link
        })
    return JsonResponse({'news': news_list})


from django.contrib.auth import get_user_model

User = get_user_model()
from book.service.recommendation import recommend_books
# AI 추천 책들
@require_api_key_secure
def api_ai_recommned(request, user_id):
    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    
    recommended = recommend_books(user)
    
    data = []
    for book in recommended:
        data.append({
            "id": book.id,
            "name": book.name,
            'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
            "genres": [g.name for g in book.genres.all()],
            "book_score": book.book_score,
            "author": {
                "id": book.user.user_id,
                "nickname": book.user.nickname,  
                "email": book.user.email,        
        }
        })
    return JsonResponse({"ai_recommended": data}, json_dumps_params={'ensure_ascii': False})
    


# 시 공모전 작품
@require_api_key_secure
def api_poem_main(request):
    poem_qs = Poem_list.objects.filter(status = 'winner').all().order_by("?")[:10]

    poem_list = []

    for p  in poem_qs:
        poem_list.append({
            "id": p.user_id,
            "title": p.title,
            "content": p.content,
            "poem_audio": p.poem_audio.url if p.poem_audio else None,
            "created_at": p.created_at,
            "image": p.image.url if p.image else None,
        })

    return JsonResponse({"poems": poem_list})

@require_api_key_secure
def api_book_snippet_main(request):
    snippet_qs = BookSnippet.objects.all().order_by("?")[:10]

    snippet_list = []
    for s in snippet_qs:
        snippet_list.append({
            "id": s.id,
            "sentence": s.sentence,
            "audio_file": s.audio_file.url if s.audio_file else None,
            "created_at": s.created_at,
            "link": s.link,
            "book": {
                "id": s.book.id if s.book else None,
                "title": s.book.name if s.book else None,
                "created_at": s.book.created_at if s.book else None,
                "author": s.book.user.nickname if s.book and s.book.user else None,
                "cover_img": s.book.cover_img.url if s.book and s.book.cover_img else None,

            }
        })
    return JsonResponse({"snippet":snippet_list })


# ==================== 🔍 통합 검색 API (웹용) ====================

def api_search(request):
    """
    통합 검색 API - 작품, 작가, 태그 검색

    Query Parameters:
        - q: 검색어 (필수)
        - filter: 필터 타입 - 'all', 'book', 'author', 'tag' (기본: 'all')

    Returns:
        {
            "results": [
                {
                    "type": "book",
                    "id": 1,
                    "title": "책 제목",
                    "author": "작가 닉네임",
                    "cover_image": "/media/...",
                    "genre": "장르명"
                },
                {
                    "type": "author",
                    "id": 1,
                    "name": "작가 닉네임",
                    "profile_image": "/media/...",
                    "book_count": 5
                },
                {
                    "type": "tag",
                    "id": 1,
                    "name": "태그명",
                    "book_count": 10
                }
            ]
        }

    Example:
        GET /book/api/search/?q=판타지
        GET /book/api/search/?q=작가&filter=author
    """
    from django.db.models import Q, Count
    from register.models import Users

    query = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')

    if not query:
        return JsonResponse({'results': []})

    results = []

    # 작품 검색
    if filter_type in ['all', 'book']:
        books = Books.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(user__nickname__icontains=query) |
            Q(tags__name__icontains=query)
        ).select_related('user').prefetch_related('genres', 'tags').distinct()[:30]

        for book in books:
            genre_names = ', '.join([g.name for g in book.genres.all()[:2]])
            results.append({
                'type': 'book',
                'id': book.id,
                'title': book.name,
                'author': book.user.nickname if book.user else '알 수 없음',
                'cover_image': book.cover_img.url if book.cover_img else None,
                'genre': genre_names if genre_names else '기타'
            })

    # 작가 검색
    if filter_type in ['all', 'author']:
        authors = Users.objects.filter(
            Q(nickname__icontains=query) |
            Q(username__icontains=query)
        ).annotate(
            book_count=Count('books')
        ).filter(book_count__gt=0)[:20]

        for author in authors:
            results.append({
                'type': 'author',
                'id': author.user_id,
                'name': author.nickname or author.username,
                'profile_image': author.profile_img.url if hasattr(author, 'profile_img') and author.profile_img else None,
                'book_count': author.book_count
            })

    # 태그 검색
    if filter_type in ['all', 'tag']:
        tags = Tags.objects.filter(
            name__icontains=query
        ).annotate(
            book_count=Count('books')
        ).filter(book_count__gt=0)[:20]

        for tag in tags:
            results.append({
                'type': 'tag',
                'id': tag.id,
                'name': tag.name,
                'book_count': tag.book_count
            })

    return JsonResponse({'results': results})


# ==================== 💬 Book Comments API ====================

@api_view(['GET', 'POST'])
@require_api_key_secure
def api_book_comments(request, book_id):
    """
    책 댓글 API

    GET: 댓글 목록 조회
    POST: 댓글 작성

    Query Parameters (GET):
        - page: 페이지 번호 (기본: 1)
        - per_page: 페이지당 아이템 수 (기본: 20)

    Body Parameters (POST):
        - comment: 댓글 내용 (필수)
        - parent: 대댓글일 경우 부모 댓글 ID (선택)
    """
    from book.models import BookComment, APIKey
    import json

    book = get_object_or_404(Books, id=book_id)

    # GET: 댓글 목록 조회
    if request.method == 'GET':
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))

        # 최상위 댓글만 가져오기 (대댓글 제외)
        comments = BookComment.objects.filter(
            book=book,
            parent__isnull=True,
            is_deleted=False
        ).select_related('user').prefetch_related('replies').order_by('-created_at')

        result = paginate(comments, page, per_page)

        comments_data = []
        for comment in result['items']:
            # 대댓글 가져오기
            replies_data = []
            for reply in comment.replies.filter(is_deleted=False).select_related('user').order_by('created_at')[:10]:
                replies_data.append({
                    'id': reply.id,
                    'comment': reply.comment,
                    'like_count': reply.like_count,
                    'created_at': reply.created_at.isoformat(),
                    'user': {
                        'id': reply.user.user_id,
                        'nickname': reply.user.nickname,
                        'profile_img': request.build_absolute_uri(reply.user.user_img.url) if reply.user.user_img else None,
                    }
                })

            comments_data.append({
                'id': comment.id,
                'comment': comment.comment,
                'like_count': comment.like_count,
                'created_at': comment.created_at.isoformat(),
                'user': {
                    'id': comment.user.user_id,
                    'nickname': comment.user.nickname,
                    'profile_img': request.build_absolute_uri(comment.user.user_img.url) if comment.user.user_img else None,
                },
                'replies_count': comment.replies.filter(is_deleted=False).count(),
                'replies': replies_data
            })

        return api_response({
            'book': {
                'id': book.id,
                'name': book.name
            },
            'comments': comments_data,
            'pagination': result['pagination']
        })

    # POST: 댓글 작성
    elif request.method == 'POST':
        # API 키로 사용자 확인
        api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
        if not api_key:
            return JsonResponse({'success': False, 'error': 'API key required'}, status=401)

        try:
            api_key_obj = APIKey.objects.get(key=api_key)
            user = api_key_obj.user
        except APIKey.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid API Key'}, status=401)

        # 요청 본문에서 댓글 내용 가져오기
        try:
            data = json.loads(request.body)
            comment_text = data.get('comment', '').strip()
            parent_id = data.get('parent')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

        if not comment_text:
            return JsonResponse({'success': False, 'error': 'Comment content is required'}, status=400)

        # 대댓글일 경우 부모 댓글 확인
        parent_comment = None
        if parent_id:
            try:
                parent_comment = BookComment.objects.get(id=parent_id, book=book)
            except BookComment.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Parent comment not found'}, status=404)

        # 댓글 생성
        comment = BookComment.objects.create(
            book=book,
            user=user,
            comment=comment_text,
            parent=parent_comment
        )

        return JsonResponse({
            'success': True,
            'data': {
                'id': comment.id,
                'comment': comment.comment,
                'like_count': comment.like_count,
                'created_at': comment.created_at.isoformat(),
                'user': {
                    'id': user.user_id,
                    'nickname': user.nickname,
                    'profile_img': request.build_absolute_uri(user.user_img.url) if user.user_img else None,
                },
                'replies_count': 0
            }
        })


# ==================== ⭐ Book Reviews Create/Update API ====================

@api_view(['POST', 'PATCH', 'DELETE'])
@require_api_key_secure
def api_book_review_create(request, book_id):
    """
    책 리뷰/평가 작성/수정/삭제 API

    POST: 리뷰 작성
    PATCH: 리뷰 수정
    DELETE: 리뷰 삭제

    Body Parameters (POST, PATCH):
        - rating: 평점 (1-5, 필수)
        - review_text: 리뷰 내용 (선택)
    """
    from book.models import BookReview, APIKey
    import json

    book = get_object_or_404(Books, id=book_id)

    # API 키로 사용자 확인
    api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API key required'}, status=401)

    try:
        api_key_obj = APIKey.objects.get(key=api_key)
        user = api_key_obj.user
    except APIKey.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid API Key'}, status=401)

    # POST: 리뷰 작성
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print(f"[REVIEW DEBUG] Received data: {data}")
            rating = data.get('rating')
            review_text = data.get('review_text', '').strip()
        except json.JSONDecodeError as e:
            print(f"[REVIEW DEBUG] JSON decode error: {e}")
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

        print(f"[REVIEW DEBUG] Rating: {rating}, Review text: {review_text}")

        if not rating:
            print(f"[REVIEW DEBUG] Rating is missing")
            return JsonResponse({'success': False, 'error': 'Rating is required'}, status=400)

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except (ValueError, TypeError) as e:
            print(f"[REVIEW DEBUG] Rating validation error: {e}, rating={rating}")
            return JsonResponse({'success': False, 'error': 'Rating must be between 1 and 5'}, status=400)

        # 이미 리뷰가 있는지 확인
        existing_review = BookReview.objects.filter(user=user, book=book).first()
        if existing_review:
            print(f"[REVIEW DEBUG] Existing review found for user {user.user_id}, book {book_id}")
            return JsonResponse({'success': False, 'error': 'You have already reviewed this book. Use PATCH to update.'}, status=400)

        # 리뷰 생성
        review = BookReview.objects.create(
            user=user,
            book=book,
            rating=rating,
            review_text=review_text
        )

        # 책 평점 업데이트
        _update_book_score(book)

        return JsonResponse({
            'success': True,
            'data': {
                'id': review.id,
                'rating': review.rating,
                'review_text': review.review_text,
                'created_at': review.created_at.isoformat(),
                'updated_at': review.updated_at.isoformat(),
                'user': {
                    'id': user.user_id,
                    'nickname': user.nickname,
                    'profile_img': request.build_absolute_uri(user.user_img.url) if user.user_img else None,
                }
            }
        })

    # PATCH: 리뷰 수정
    elif request.method == 'PATCH':
        try:
            review = BookReview.objects.get(user=user, book=book)
        except BookReview.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Review not found'}, status=404)

        try:
            data = json.loads(request.body)
            rating = data.get('rating')
            review_text = data.get('review_text')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

        # 평점 업데이트
        if rating is not None:
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    raise ValueError
                review.rating = rating
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Rating must be between 1 and 5'}, status=400)

        # 리뷰 텍스트 업데이트
        if review_text is not None:
            review.review_text = review_text.strip()

        review.save()

        # 책 평점 업데이트
        _update_book_score(book)

        return JsonResponse({
            'success': True,
            'data': {
                'id': review.id,
                'rating': review.rating,
                'review_text': review.review_text,
                'created_at': review.created_at.isoformat(),
                'updated_at': review.updated_at.isoformat(),
                'user': {
                    'id': user.user_id,
                    'nickname': user.nickname,
                    'profile_img': request.build_absolute_uri(user.user_img.url) if user.user_img else None,
                }
            }
        })

    # DELETE: 리뷰 삭제
    elif request.method == 'DELETE':
        try:
            review = BookReview.objects.get(user=user, book=book)
            review.delete()

            # 책 평점 업데이트
            _update_book_score(book)

            return JsonResponse({
                'success': True,
                'message': 'Review deleted successfully'
            })
        except BookReview.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Review not found'}, status=404)


def _update_book_score(book):
    """책의 평균 평점 업데이트"""
    from django.db.models import Avg

    avg_rating = BookReview.objects.filter(book=book).aggregate(Avg('rating'))['rating__avg']
    if avg_rating:
        book.book_score = round(avg_rating, 1)
    else:
        book.book_score = 0.0
    book.save()


# ==================== 👥 Follow API ====================

@require_api_key_secure
def api_follow_toggle(request, author_id):
    """
    작가 팔로우/언팔로우 토글 API

    POST /api/authors/<author_id>/follow/

    Returns:
        {
            "success": true,
            "is_following": true,
            "follower_count": 150
        }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST 요청만 허용됩니다'}, status=405)

    user = request.api_user

    # 작가 확인
    from register.models import CustomUser
    try:
        author = CustomUser.objects.get(user_id=author_id)
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': '작가를 찾을 수 없습니다'}, status=404)

    # 자기 자신을 팔로우할 수 없음
    if user.user_id == author.user_id:
        return JsonResponse({'success': False, 'error': '자기 자신을 팔로우할 수 없습니다'}, status=400)

    # 팔로우 토글
    follow, created = Follow.objects.get_or_create(
        follower=user,
        following=author
    )

    if not created:
        # 이미 팔로우 중이면 언팔로우
        follow.delete()
        is_following = False
    else:
        is_following = True

    # 팔로워 수 계산
    follower_count = Follow.objects.filter(following=author).count()

    return JsonResponse({
        'success': True,
        'is_following': is_following,
        'follower_count': follower_count
    })


@require_api_key
def api_user_followers(request, user_id):
    """
    특정 사용자의 팔로워 목록 API

    GET /api/users/<user_id>/followers/?page=1&per_page=20
    """
    from register.models import CustomUser

    try:
        target_user = CustomUser.objects.get(user_id=user_id)
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': '사용자를 찾을 수 없습니다'}, status=404)

    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 20)

    # 팔로워 목록
    followers = Follow.objects.filter(following=target_user).select_related('follower')
    result = paginate(followers, page, per_page)

    followers_data = []
    for follow in result['items']:
        follower = follow.follower
        followers_data.append({
            'user_id': follower.user_id,
            'nickname': follower.nickname,
            'profile_img': request.build_absolute_uri(follower.user_img.url) if follower.user_img else None,
            'followed_at': follow.created_at.isoformat()
        })

    return api_response({
        'followers': followers_data,
        'pagination': result['pagination']
    })


@require_api_key
def api_user_following(request, user_id):
    """
    특정 사용자가 팔로우하는 작가 목록 API

    GET /api/users/<user_id>/following/?page=1&per_page=20
    """
    from register.models import CustomUser

    try:
        target_user = CustomUser.objects.get(user_id=user_id)
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': '사용자를 찾을 수 없습니다'}, status=404)

    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 20)

    # 팔로잉 목록
    following = Follow.objects.filter(follower=target_user).select_related('following')
    result = paginate(following, page, per_page)

    following_data = []
    for follow in result['items']:
        author = follow.following
        # 작가의 책 수와 총 팔로워 수
        books_count = Books.objects.filter(user=author).count()
        followers_count = Follow.objects.filter(following=author).count()

        following_data.append({
            'user_id': author.user_id,
            'nickname': author.nickname,
            'profile_img': request.build_absolute_uri(author.user_img.url) if author.user_img else None,
            'books_count': books_count,
            'followers_count': followers_count,
            'followed_at': follow.created_at.isoformat()
        })

    return api_response({
        'following': following_data,
        'pagination': result['pagination']
    })


@require_api_key
def api_following_feed(request):
    """
    팔로우한 작가들의 최신 책 피드 API

    GET /api/following/feed/?page=1&per_page=20

    팔로우한 작가들이 작성한 책을 최신순으로 반환
    """
    user = request.api_user
    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 20)

    # 팔로우한 작가들의 ID 목록
    following_ids = Follow.objects.filter(follower=user).values_list('following_id', flat=True)

    if not following_ids:
        return api_response({
            'books': [],
            'pagination': {
                'page': 1,
                'per_page': 20,
                'total': 0,
                'total_pages': 0,
                'has_next': False,
                'has_prev': False
            }
        })

    # 팔로우한 작가들의 책 목록
    books = Books.objects.filter(
        user_id__in=following_ids
    ).select_related('user').prefetch_related('genres', 'tags').annotate(
        episodes_count=Count('contents'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-created_at')

    result = paginate(books, page, per_page)

    books_data = []
    for book in result['items']:
        books_data.append({
            'id': book.id,
            'name': book.name,
            'description': book.description,
            'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
            'status': book.status,
            'status_display': book.get_status_display(),
            'book_score': float(book.book_score),
            'avg_rating': float(book.avg_rating) if book.avg_rating else 0,
            'episodes_count': book.episodes_count,
            'total_duration': book.get_total_duration_formatted(),
            'created_at': book.created_at.isoformat(),
            'author': {
                'id': book.user.user_id,
                'nickname': book.user.nickname,
                'profile_img': request.build_absolute_uri(book.user.user_img.url) if book.user.user_img else None,
            },
            'genres': [
                {'id': g.id, 'name': g.name, 'color': g.genres_color}
                for g in book.genres.all()
            ],
            'tags': [
                {'id': t.id, 'name': t.name}
                for t in book.tags.all()
            ]
        })

    return api_response({
        'books': books_data,
        'pagination': result['pagination']
    })


# ==================== 🔖 Bookmark API ====================

@require_api_key_secure
def api_bookmark_toggle(request, book_id):
    """
    책 북마크(나중에 보기) 토글 API

    POST /api/books/<book_id>/bookmark/

    Body (optional):
        {
            "note": "나중에 읽고 싶은 책"
        }

    Returns:
        {
            "success": true,
            "is_bookmarked": true
        }
    """
    try:
        print(f"📍 [DEBUG] api_bookmark_toggle 시작 - book_id: {book_id}")
        print(f"📍 [DEBUG] request.api_user: {request.api_user}")

        if request.method != 'POST':
            return JsonResponse({'error': 'POST 요청만 허용됩니다'}, status=405)

        user = request.api_user
        print(f"📍 [DEBUG] user: {user}")

        # 책 확인
        try:
            book = Books.objects.get(id=book_id)
            print(f"📍 [DEBUG] book found: {book.title}")
        except Books.DoesNotExist:
            return JsonResponse({'success': False, 'error': '책을 찾을 수 없습니다'}, status=404)

        # 요청 바디에서 메모 추출 (선택사항)
        note = None
        if request.body:
            try:
                data = json.loads(request.body)
                note = data.get('note', '')
            except json.JSONDecodeError:
                pass

        print(f"📍 [DEBUG] About to toggle bookmark for user={user.id}, book={book.id}")
        # 북마크 토글
        bookmark, created = BookmarkBook.objects.get_or_create(
            user=user,
            book=book,
            defaults={'note': note or ''}
        )
        print(f"📍 [DEBUG] Bookmark toggled: created={created}")

        if not created:
            # 이미 북마크되어 있으면 제거
            bookmark.delete()
            is_bookmarked = False
        else:
            is_bookmarked = True

        print(f"📍 [DEBUG] Returning success: is_bookmarked={is_bookmarked}")
        return JsonResponse({
            'success': True,
            'is_bookmarked': is_bookmarked
        })
    except Exception as e:
        print(f"❌ [ERROR] Exception in api_bookmark_toggle: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@require_api_key_secure
def api_bookmark_update_note(request, book_id):
    """
    북마크 메모 업데이트 API

    PATCH /api/books/<book_id>/bookmark/note/

    Body:
        {
            "note": "새로운 메모 내용"
        }
    """
    if request.method != 'PATCH':
        return JsonResponse({'error': 'PATCH 요청만 허용됩니다'}, status=405)

    user = request.api_user

    try:
        bookmark = BookmarkBook.objects.get(user=user, book_id=book_id)
    except BookmarkBook.DoesNotExist:
        return JsonResponse({'success': False, 'error': '북마크를 찾을 수 없습니다'}, status=404)

    try:
        data = json.loads(request.body)
        note = data.get('note', '')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    bookmark.note = note
    bookmark.save()

    return JsonResponse({
        'success': True,
        'data': {
            'book_id': book_id,
            'note': bookmark.note,
            'updated_at': bookmark.created_at.isoformat()
        }
    })


@require_api_key
def api_user_bookmarks(request):
    """
    사용자의 북마크 목록 API

    GET /api/bookmarks/?page=1&per_page=20

    Returns bookmarked books with notes
    """
    user = request.api_user
    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 20)

    # 북마크 목록
    bookmarks = BookmarkBook.objects.filter(
        user=user
    ).select_related('book', 'book__user').prefetch_related(
        'book__genres', 'book__tags'
    )

    result = paginate(bookmarks, page, per_page)

    bookmarks_data = []
    for bookmark in result['items']:
        book = bookmark.book
        # 책 정보
        episodes_count = Content.objects.filter(book=book).count()
        avg_rating = BookReview.objects.filter(book=book).aggregate(Avg('rating'))['rating__avg']

        bookmarks_data.append({
            'bookmark_id': bookmark.id,
            'bookmarked_at': bookmark.created_at.isoformat(),
            'note': bookmark.note,
            'book': {
                'id': book.id,
                'name': book.name,
                'description': book.description,
                'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
                'status': book.status,
                'status_display': book.get_status_display(),
                'book_score': float(book.book_score),
                'avg_rating': float(avg_rating) if avg_rating else 0,
                'episodes_count': episodes_count,
                'total_duration': book.get_total_duration_formatted(),
                'created_at': book.created_at.isoformat(),
                'author': {
                    'id': book.user.user_id,
                    'nickname': book.user.nickname,
                    'profile_img': request.build_absolute_uri(book.user.user_img.url) if book.user.user_img else None,
                },
                'genres': [
                    {'id': g.id, 'name': g.name, 'color': g.genres_color}
                    for g in book.genres.all()
                ],
                'tags': [
                    {'id': t.id, 'name': t.name}
                    for t in book.tags.all()
                ]
            }
        })

    return api_response({
        'bookmarks': bookmarks_data,
        'pagination': result['pagination']
    })
