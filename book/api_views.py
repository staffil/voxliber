"""
안드로이드 앱용 REST API 뷰
읽기 전용 API만 제공
"""
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Max, Q
from django.views.decorators.csrf import csrf_exempt
from book.models import Books, Content, BookReview, ReadingProgress, ListeningHistory, Poem_list, BookSnippet, Tags, Follow, BookmarkBook
from book.api_utils import require_api_key, paginate, api_response
from rest_framework.decorators import api_view
import json
from django.utils import timezone


# ==================== 📚 Books API ====================

@require_api_key
def api_books_list(request):
    """
    책 목록 API (UUID 기반)

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
    book_type = request.GET.get('book_type', '')  # 'audiobook' or 'webnovel'

    # 기본 쿼리
    books = Books.objects.select_related('user').prefetch_related('genres', 'tags').annotate(
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
    if book_type in ('audiobook', 'webnovel'):
        books = books.filter(book_type=book_type)

    # 정렬
    books = books.order_by('-created_at')

    # 페이지네이션
    result = paginate(books, page, per_page)

    # 데이터 직렬화
    books_data = []
    for book in result['items']:
        books_data.append({
            'id': str(book.public_uuid),  # UUID
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
                'id': str(book.user.public_uuid),  # UUID
                'nickname': book.author_name or book.user.nickname,
            },
            'genres': [
                {'id': str(g.id), 'name': g.name, 'color': getattr(g, 'genres_color', None)}
                for g in book.genres.all()
            ],
            'tags': [
                {'id': str(t.id), 'name': t.name}
                for t in book.tags.all()
            ],
            'adult_choice': book.adult_choice,
            'book_type': getattr(book, 'book_type', 'audiobook'),
        })

    return api_response({
        'books': books_data,
        'pagination': result['pagination']
    })



@require_api_key
def api_book_detail(request, book_uuid):
    """
    책 상세 정보 API (에피소드 포함)

    Example:
        GET /api/books/<uuid>/
    """
    book = get_object_or_404(
        Books.objects.select_related('user')
        .prefetch_related('genres', 'tags', 'contents')
        .annotate(
            episodes_count=Count('contents'),
            avg_rating=Avg('reviews__rating'),
            reviews_count=Count('reviews')
        ),
        public_uuid=book_uuid
    )

    # 최근 5개 리뷰
    recent_reviews = book.reviews.select_related('user').order_by('-created_at')[:5]

    data = {
        'id': str(book.public_uuid),  # UUID
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
        'adult_choice': book.adult_choice,
        'created_at': book.created_at.isoformat(),
        'author': {
            'id': str(book.user.public_uuid),  # UUID
            'nickname': book.author_name or book.user.nickname,
            'email': book.user.email,
        },
        'genres': [
            {'id': str(g.id), 'name': g.name, 'color': getattr(g, 'genres_color', None)}
            for g in book.genres.all()
        ],
        'tags': [
            {'id': str(t.id), 'name': t.name}
            for t in book.tags.all()
        ],
        'contents': [
            {
                'id': str(content.public_uuid),  # UUID
                'title': content.title,
                'number': content.number,
                'text': content.text,
                'episode_image': request.build_absolute_uri(content.episode_image.url) if content.episode_image else None,
                'audio_file': request.build_absolute_uri(content.audio_file.url) if content.audio_file else None,
                'duration_seconds': content.duration_seconds,
                'duration_formatted': content.get_duration_formatted(),
                'audio_timestamps': content.audio_timestamps
            }  for content in book.contents.filter(is_deleted=False).order_by('number')

        ],
        'recent_reviews': [
            {
                'id': str(r.id),  # 여기도 리뷰 UUID 필요하면 수정 가능
                'rating': r.rating,
                'review_text': r.review_text,
                'created_at': r.created_at.isoformat(),
                'user': {
                    'id': str(r.user.public_uuid),  # 리뷰 작성자 UUID
                    'nickname': r.user.nickname
                }
            }
            for r in recent_reviews
        ]
    }

    return api_response(data)


# ==================== 📖 Contents (Episodes) API ====================

@require_api_key
def api_contents_list(request, book_uuid):
    """
    에피소드 목록 API (UUID 기반)

    Query Parameters:
        - page: 페이지 번호 (기본: 1)
        - per_page: 페이지당 아이템 수 (기본: 20)

    Example:
        GET /api/books/<uuid>/contents/
    """
    # 책 조회
    book = get_object_or_404(Books, public_uuid=book_uuid)

    # 페이지네이션 파라미터
    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 20)

    # 에피소드 조회
    contents = Content.objects.filter(book=book, is_deleted=False).order_by('number')

    # 페이지네이션 적용
    result = paginate(contents, page, per_page)

    # 데이터 직렬화
    contents_data = []
    for content in result['items']:
        contents_data.append({
            'id': str(content.public_uuid),  # UUID
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
            'id': str(book.public_uuid),  # UUID
            'name': book.name
        },
        'contents': contents_data,
        'pagination': result['pagination']
    })



@require_api_key
def api_content_detail(request, content_uuid):
    """
    에피소드 상세 정보 API (UUID 기반)

    Example:
        GET /api/contents/<uuid>/
    """
    content = get_object_or_404(
        Content.objects.select_related('book', 'book__user'),
        public_uuid=content_uuid
    )

    # 이전/다음 에피소드
    prev_content = Content.objects.filter(
        book=content.book,
        number__lt=content.number,is_deleted=False
    ).order_by('-number').first()

    next_content = Content.objects.filter(
        book=content.book,
        number__gt=content.number,is_deleted=False
    ).order_by('number').first()

    data = {
        'id': str(content.public_uuid),  # UUID
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
            'id': str(content.book.public_uuid),  # UUID
            'name': content.book.name,
            'cover_img': request.build_absolute_uri(content.book.cover_img.url) if content.book.cover_img else None,
            'author': {
                'id': str(content.book.user.public_uuid),  # UUID
                'nickname': content.book.author_name or content.book.user.nickname
            }
        },
        'navigation': {
            'prev': {
                'id': str(prev_content.public_uuid),
                'title': prev_content.title,
                'number': prev_content.number
            } if prev_content else None,
            'next': {
                'id': str(next_content.public_uuid),
                'title': next_content.title,
                'number': next_content.number
            } if next_content else None
        }
    }

    return api_response(data)


# ==================== ⭐ Reviews API ====================

@require_api_key
def api_reviews_list(request, book_uuid):
    """
    책 리뷰 목록 API (UUID 기반)

    Query Parameters:
        - page: 페이지 번호 (기본: 1)
        - per_page: 페이지당 아이템 수 (기본: 20)

    Example:
        GET /api/books/<uuid>/reviews/
    """
    book = get_object_or_404(Books, public_uuid=book_uuid)

    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 20)

    reviews = BookReview.objects.filter(book=book).select_related('user').order_by('-created_at')

    result = paginate(reviews, page, per_page)

    reviews_data = []
    for review in result['items']:
        reviews_data.append({
            'id': str(review.public_uuid) if hasattr(review, 'public_uuid') else review.id,
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
            'id': str(book.public_uuid),
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
    내 독서 진행 상황 API (UUID 기반)

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
            'id': str(progress.public_uuid) if hasattr(progress, 'public_uuid') else progress.id,
            'status': progress.status,
            'status_display': progress.get_status_display(),
            'last_read_content_number': progress.last_read_content_number,
            'last_read_at': progress.last_read_at.isoformat() if progress.last_read_at else None,
            'completed_at': progress.completed_at.isoformat() if progress.completed_at else None,
            'book': {
                'id': str(progress.book.public_uuid),
                'name': progress.book.name,
                'cover_img': request.build_absolute_uri(progress.book.cover_img.url) if progress.book.cover_img else None,
                'total_episodes': progress.book.contents.count()
            },
            'current_content': {
                'id': str(progress.current_content.public_uuid),
                'title': progress.current_content.title,
                'number': progress.current_content.number
            } if progress.current_content else None
        })

    return api_response({'progress': progress_data})



@require_api_key
def api_my_listening_history(request):
    """
    내 청취 기록 API (UUID 기반)

    Example:
        GET /api/my/listening-history/
    """
    qs = ListeningHistory.objects.filter(
        user=request.api_user,
        last_position__gt=0
    ).select_related('book', 'content', 'book__user').order_by('-last_listened_at')

    seen_books = set()
    history = []

    for lh in qs:
        if lh.book.public_uuid not in seen_books:  # 아직 추가되지 않은 책이면
            history.append(lh)
            seen_books.add(lh.book.public_uuid)
        if len(history) >= 5:  # 최대 5권까지만
            break

    history_data = []
    for h in history:
        history_data.append({
            'id': str(h.public_uuid) if hasattr(h, 'public_uuid') else h.id,
            'listened_seconds': h.listened_seconds,
            'last_position': h.last_position,
            'last_listened_at': h.last_listened_at.isoformat(),
            'book': {
                'id': str(h.book.public_uuid),
                'name': h.book.name,
                'cover_img': request.build_absolute_uri(h.book.cover_img.url) if h.book.cover_img else None,
                'author': {
                    'id': str(h.book.user.public_uuid) if h.book.user else None,
                    'nickname': (h.book.author_name or h.book.user.nickname) if h.book.user else None,
                } if h.book.user else None,
            },
            'content': {
                'id': str(h.content.public_uuid) if h.content else None,
                'title': h.content.title if h.content else None,
                'number': h.content.number if h.content else None,
                'text': h.content.text if h.content else None,
                'audio_file': request.build_absolute_uri(h.content.audio_file.url) if h.content and h.content.audio_file else None,
                'episode_image': request.build_absolute_uri(h.content.episode_image.url) if h.content and h.content.episode_image else None,
            } if h.content else None
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
                'id': str(user.public_uuid),
                'username': user.username,
                'email': user.email,
                'nickname': user.nickname,
                'first_name': user.first_name if hasattr(user, 'first_name') else None,
                'last_name': user.last_name if hasattr(user, 'last_name') else None,
                'profile_img': profile_image_url,
                'birthdate': str(user.birthdate) if user.birthdate else None,
                'is_adult': user.is_adult(),
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
                'id':  str(user.public_uuid),
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


@csrf_exempt
def api_logout(request):
    """
    사용자 로그아웃 API
    현재 사용 중인 API Key를 비활성화합니다.

    Example:
        POST /api/auth/logout/
        X-API-Key: your-api-key
    """
    from book.models import APIKey

    if request.method != 'POST':
        return api_response(error='POST 요청만 허용됩니다.', status=405)

    try:
        # API 키로 사용자 확인
        api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
        if not api_key:
            return api_response(error='API key required', status=401)

        try:
            api_key_obj = APIKey.objects.get(key=api_key, is_active=True)
        except APIKey.DoesNotExist:
            return api_response(error='Invalid API Key', status=401)

        # 현재 API Key 비활성화
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


@csrf_exempt
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

        # API 키로 사용자 확인
        api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
        if not api_key:
            return api_response(error='API key required', status=401)

        try:
            old_key = APIKey.objects.get(key=api_key, is_active=True)
        except APIKey.DoesNotExist:
            return api_response(error='Invalid API Key', status=401)

        # 기존 키 비활성화
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
    print(f"Serializing book: name={book.name}, public_uuid={book.public_uuid}")
    author_data = None
    if hasattr(book, 'user') and book.user:
        try:
            author_data = {
                'id': getattr(book.user, 'user_id', getattr(book.user, 'id', None)),
                'nickname': getattr(book, 'author_name', None) or getattr(book.user, 'nickname', 'Unknown'),
                'email': getattr(book.user, 'email', '')
            }
        except:
            author_data = None

    return {
        'id': str(book.public_uuid),
        'name': book.name,
        'description': book.description or '',
        'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
        'book_score': float(book.book_score) if book.book_score else 0.0,
        'created_at': book.created_at.isoformat() if book.created_at else None,
        'author': author_data,
        'genres': [
            {'id': g.id, 'name': g.name, 'description': '', 'color': getattr(g, 'genres_color', None)}
            for g in book.genres.all()
        ],
        'tags': [
            {'id': t.id, 'name': t.name}
            for t in book.tags.all()
        ],
        'episode_count': book.contents.count(),
        'book_type': getattr(book, 'book_type', 'audiobook'),
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

    # 오디오북만 필터링 (webnovel 제외)
    audiobook_qs = Books.objects.filter(book_type='audiobook', is_deleted=False)

    # 인기 작품 (평점과 에피소드 수를 고려한 종합 점수) - 랜덤 정렬
    popular_books = audiobook_qs.select_related('user').prefetch_related('genres').annotate(
        total_score=Count('contents') * 0.1 + Count('reviews') * 0.3
    ).order_by('-book_score', '-total_score')[:50]
    popular_books = sorted(list(popular_books), key=lambda x: __import__('random').random())[:12]

    # 트렌딩 작품 (최근 인기작 - 신작 제외) - 랜덤 정렬
    trending_books = audiobook_qs.filter(
        created_at__lte=seven_days_ago
    ).select_related('user').prefetch_related('genres').annotate(
        episode_count=Count('contents')
    ).order_by('-book_score', '-episode_count')[:30]
    trending_books = sorted(list(trending_books), key=lambda x: __import__('random').random())[:8]

    # 신작 (최근 30일) - 랜덤 정렬
    new_books = audiobook_qs.filter(
        created_at__gte=thirty_days_ago
    ).annotate(
        last_content_time=Max('contents__created_at')
    ).select_related('user').prefetch_related('genres').order_by('-last_content_time')[:50]
    new_books = sorted(list(new_books), key=lambda x: __import__('random').random())[:20]

    # 최고 평점 - 랜덤 정렬
    top_rated_books = audiobook_qs.filter(
        book_score__gt=0
    ).select_related('user').prefetch_related('genres').order_by('-book_score')[:30]
    top_rated_books = sorted(list(top_rated_books), key=lambda x: __import__('random').random())[:8]

    # 배너
    banners = Advertisment.objects.all()[:5]

    # 장르별 책
    all_genres = Genres.objects.all()[:6]
    genres_data = []
    for genre in all_genres:
        genre_books = audiobook_qs.filter(
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

    # 웹소설 섹션 (랜덤 정렬)
    import random as _random
    _webnovel_pool = list(Books.objects.filter(
        book_type='webnovel', is_deleted=False
    ).select_related('user').prefetch_related('genres', 'tags').order_by('-book_score', '-created_at')[:40])
    _random.shuffle(_webnovel_pool)
    popular_webnovels = _webnovel_pool[:20]

    _new_webnovel_pool = list(Books.objects.filter(
        book_type='webnovel', is_deleted=False,
        created_at__gte=thirty_days_ago
    ).select_related('user').prefetch_related('genres', 'tags').order_by('-created_at')[:40])
    _random.shuffle(_new_webnovel_pool)
    new_webnovels = _new_webnovel_pool[:20]

    # 장르별 웹소설
    genre_webnovels = []
    wn_genres = Genres.objects.filter(
        books__book_type='webnovel', books__is_deleted=False
    ).distinct()[:8]
    for g in wn_genres:
        g_novels = list(Books.objects.filter(
            book_type='webnovel', is_deleted=False, genres=g
        ).select_related('user').prefetch_related('genres', 'tags').order_by('-created_at')[:20])
        _random.shuffle(g_novels)
        if g_novels:
            genre_webnovels.append({
                'genre': {'id': g.id, 'name': g.name, 'color': g.genres_color or '#7C3AED'},
                'books': [_serialize_book(b, request) for b in g_novels[:10]],
            })

    return api_response({
        'banners': [_serialize_banner(banner, request) for banner in banners],
        'popular_books': [_serialize_book(book, request) for book in popular_books],
        'trending_books': [_serialize_book(book, request) for book in trending_books],
        'new_books': [_serialize_book(book, request) for book in new_books],
        'top_rated_books': [_serialize_book(book, request) for book in top_rated_books],
        'genres_with_books': genres_data,
        'popular_webnovels': [_serialize_book(book, request) for book in popular_webnovels],
        'new_webnovels': [_serialize_book(book, request) for book in new_webnovels],
        'genre_webnovels': genre_webnovels,
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
    books = Books.objects.filter(book_type='audiobook', is_deleted=False).select_related('user').prefetch_related('genres').annotate(
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
        book_type='audiobook', is_deleted=False, created_at__lte=seven_days_ago
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
        book_type='audiobook', is_deleted=False, created_at__gte=thirty_days_ago
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
    book_type = request.GET.get('book_type', 'audiobook')
    books = Books.objects.filter(
        book_type=book_type, is_deleted=False, book_score__gt=0
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
        {'id': g.id, 'name': g.name, 'description': '', "color": g.genres_color}
        for g in genres
    ]
    return api_response(genres_data)


@require_api_key
def api_genre_books(request, genre_id):
    """
    특정 장르의 책 목록 API

    Query Parameters:
        - limit: 결과 개수 (기본: 20)
        - book_type: 'audiobook' | 'webnovel' (기본: 전체)

    Example:
        GET /book/api/genres/1/books/?limit=20&book_type=audiobook
    """
    limit = int(request.GET.get('limit', 20))
    book_type = request.GET.get('book_type', '')

    qs = Books.objects.filter( 
        genres__id=genre_id, is_deleted=False
    ).select_related('user').prefetch_related('genres')

    if book_type in ('audiobook', 'webnovel'):
        qs = qs.filter(book_type=book_type)

    books = qs.order_by('-book_score', '-created_at')[:limit]

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

    검색 범위: 작품명, 작가명, 태그명, 장르명
    """
    from django.db.models import Q

    query = request.GET.get('q', '').strip()
    book_type = request.GET.get('book_type', '')  # 'audiobook' or 'webnovel' or ''

    if not query:
        return api_response([])

    # 책 검색 (제목, 설명, 작가명, 태그명, 장르명으로 검색)
    books = Books.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(user__nickname__icontains=query) |
        Q(tags__name__icontains=query) |
        Q(genres__name__icontains=query)
    ).select_related('user').prefetch_related('genres', 'tags').filter(is_deleted=False).distinct()

    if book_type in ('audiobook', 'webnovel'):
        books = books.filter(book_type=book_type)

    return api_response([_serialize_book(book, request) for book in books[:50]])


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

    snaps = BookSnap.objects.select_related('user', 'book', 'story').prefetch_related(
        'booksnap_like', 'comments'
    ).order_by('?')

    # 페이지네이션
    start = (page - 1) * per_page
    end = start + per_page
    total = snaps.count()
    snaps_page = snaps[start:end]

    snaps_data = []
    for snap in snaps_page:
        # book_id 추출: DB에 없으면 book_link에서 UUID 추출
        if snap.book:
            book_id = str(snap.book.public_uuid)
        elif snap.book_link:
            book_id = snap.book_link.rstrip('/').split('/')[-1]
        else:
            book_id = None

        snaps_data.append({
            'id': str(snap.public_uuid),
            'snap_title': snap.snap_title,
            'snap_video': request.build_absolute_uri(snap.snap_video.url) if snap.snap_video else None,
            'thumbnail': request.build_absolute_uri(snap.thumbnail.url) if snap.thumbnail else None,
            'likes_count': snap.booksnap_like.count(),
            'views': snap.views,
            'shares': snap.shares,
            'comments_count': snap.comments.count(),
            'allow_comments': snap.allow_comments,
            'book_id': book_id,
            'book_public_uuid': book_id,
            'book_type': snap.book.book_type if snap.book else ('webnovel' if snap.book_link and 'webnovel' in snap.book_link else 'audiobook' if snap.book_link else None),
            'story_id': str(snap.story.public_uuid) if snap.story else None,
            'linked_type': 'story' if snap.story else ('book' if book_id else None),
            'book_link': snap.book_link,
            'story_link': snap.story_link,
            'book_comment': snap.book_comment,
            'duration': snap.duration,
            'created_at': snap.created_at.isoformat(),
            'user': {
                'id': str(snap.user.public_uuid) if snap.user else None,
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
def api_snap_detail(request, snap_uuid):
    """
    스냅 상세 정보 API (UUID 기반)

    Example:
        GET /book/api/snaps/<uuid>/
    """
    from book.models import BookSnap

    # Snap 조회 (UUID)
    snap = get_object_or_404(
        BookSnap.objects.select_related('user', 'book', 'story').prefetch_related(
            'booksnap_like', 'comments__user'
        ),
        public_uuid=snap_uuid
    )

    # 댓글 데이터
    comments_data = []
    for comment in snap.comments.filter(parent__isnull=True).order_by('-created_at')[:50]:
        comments_data.append({
            'id': str(comment.public_uuid) if hasattr(comment, 'public_uuid') else comment.id,  # UUID
            'content': comment.content,
            'likes': comment.likes,
            'created_at': comment.created_at.isoformat(),
            'user': {
                'id': str(comment.user.public_uuid) if comment.user and hasattr(comment.user, 'public_uuid') else None,  # UUID
                'nickname': comment.user.nickname if comment.user else 'Unknown',
                'profile_img': request.build_absolute_uri(comment.user.user_img.url) if comment.user and comment.user.user_img else None,
            },
            'replies_count': comment.replies.count(),
        })

    data = {
        'id': str(snap.public_uuid),  # Snap 자체도 UUID 사용
        'snap_title': snap.snap_title,
        'snap_video': request.build_absolute_uri(snap.snap_video.url) if snap.snap_video else None,
        'thumbnail': request.build_absolute_uri(snap.thumbnail.url) if snap.thumbnail else None,
        'likes_count': snap.booksnap_like.count(),
        'views': snap.views,
        'shares': snap.shares,
        'comments_count': snap.comments.count(),
        'allow_comments': snap.allow_comments,
        'book_id': str(snap.book.public_uuid) if snap.book else None,
        'book_public_uuid': str(snap.book.public_uuid) if snap.book else None,
        'book_type': snap.book.book_type if snap.book else ('webnovel' if snap.book_link and 'webnovel' in snap.book_link else 'audiobook' if snap.book_link else None),
        'story_id': str(snap.story.public_uuid) if snap.story else None,
        'linked_type': 'story' if snap.story_id else ('book' if snap.book_id else None),
        'book_link': snap.book_link,
        'story_link': snap.story_link,
        'book_comment': snap.book_comment,
        'duration': snap.duration,
        'created_at': snap.created_at.isoformat(),
        'user': {
            'id': str(snap.user.public_uuid) if snap.user and hasattr(snap.user, 'public_uuid') else None,  # 유저 UUID
            'nickname': snap.user.nickname if snap.user else 'Unknown',
            'profile_img': request.build_absolute_uri(snap.user.user_img.url) if snap.user and snap.user.user_img else None,
        } if snap.user else None,
        'comments': comments_data,
    }

    return api_response(data)


@csrf_exempt
@api_view(['POST'])
def api_snap_like(request, snap_uuid):
    """
    스냅 좋아요 토글 API

    Example:
        POST /book/api/snaps/<uuid>/like/
    """
    from book.models import BookSnap, APIKey

    snap = get_object_or_404(BookSnap, public_uuid=snap_uuid)

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

@csrf_exempt
@api_view(['POST'])
def api_snap_comment(request, snap_uuid):
    from book.models import BookSnap, BookSnapComment, APIKey
    import json

    snap = get_object_or_404(BookSnap, public_uuid=snap_uuid)


    # API Key로 유저 가져오기
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
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
from django.http import JsonResponse

def snap_main_view(request):
    snap_qs = BookSnap.objects.all().order_by("?")
    snap_list = []
    for s in snap_qs:
        snap_list.append({
            'id': str(s.public_uuid),  # UUID 사용
            'snap_title': s.snap_title,
            'snap_video': request.build_absolute_uri(s.snap_video.url) if s.snap_video else None,
            'thumbnail': request.build_absolute_uri(s.thumbnail.url) if s.thumbnail else None,
        })
    return JsonResponse({'snaps': snap_list})



from main.models import SnapBtn, Advertisment

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
from django.http import JsonResponse
from book.service.recommendation import recommend_books

User = get_user_model()

# AI 추천 책들
def api_ai_recommend(request, user_id):
    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    
    recommended = recommend_books(user)
    
    data = []
    for book in recommended:
        data.append({
            "id": str(book.public_uuid),  # UUID 사용
            "name": book.name,
            'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
            "genres": [g.name for g in book.genres.all()],
            "book_score": book.book_score,
            "author": {
                "id": book.user.user_id,
                "nickname": book.author_name or book.user.nickname,
                "email": book.user.email,
            }
        })
    return JsonResponse({"ai_recommended": data}, json_dumps_params={'ensure_ascii': False})



# 시 공모전 작품
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
# ==================== 🔍 통합 검색 API (웹용 + 앱용) ====================

from django.db.models import Q
from django.http import JsonResponse
from register.models import Users
from book.models import Books, BookSnap
from character.models import Story  # Snap 대체 LLM

def api_search(request):
    """
    통합 검색 API - 작품, 스토리, Snap, 유저, 태그 검색

    Query Parameters:
        - q: 검색어 (필수)
        - filter: 검색 필터 - 'all', 'book', 'story', 'snap', 'user' (기본: 'all')
    """
    query = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')

    if not query:
        return JsonResponse({'success': True, 'results': [], 'counts': {}})

    results = []
    counts = {'book': 0, 'audiobook': 0, 'webnovel': 0, 'story': 0, 'snap': 0, 'user': 0}

    added_book_ids = set()
    added_story_ids = set()
    added_snap_ids = set()
    added_user_ids = set()

    # ========== 유저 검색 ========== 
    if filter_type in ['all', 'user']:
        matched_users = Users.objects.filter(
            Q(nickname__icontains=query) |
            Q(username__icontains=query)
        ).distinct()[:20]

        for user in matched_users:
            if user.public_uuid and str(user.public_uuid) not in added_user_ids:
                added_user_ids.add(str(user.public_uuid))
                book_count = Books.objects.filter(user=user).count()
                story_count = Story.objects.filter(user=user).count()
                snap_count = BookSnap.objects.filter(user=user).count()

                results.append({
                    'type': 'user',
                    'id': str(user.public_uuid),
                    'nickname': user.nickname or user.username,
                    'username': user.username,
                    'profile_image': request.build_absolute_uri(user.user_img.url) if user.user_img else None,
                    'book_count': book_count,
                    'story_count': story_count,
                    'snap_count': snap_count
                })
                counts['user'] += 1

            # 유저 콘텐츠 추가
            if filter_type in ['all', 'user']:
                # 유저 책
                for book in Books.objects.filter(user=user).select_related('user').prefetch_related('genres')[:10]:
                    if str(book.public_uuid) not in added_book_ids:
                        added_book_ids.add(str(book.public_uuid))
                        genres = ', '.join([g.name for g in book.genres.all()[:2]]) or '기타'
                        results.append({
                            'type': 'book',
                            'id': str(book.public_uuid),
                            'title': book.name,
                            'description': book.description[:100] if book.description else '',
                            'author': book.user.nickname if book.user else '알 수 없음',
                            'author_id': str(book.user.public_uuid) if book.user else None,
                            'cover_image': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
                            'genre': genres,
                            'book_score': float(book.book_score) if book.book_score else 0
                        })
                        counts['book'] += 1

                # 유저 스토리
                for story in Story.objects.filter(user=user, is_public=True).select_related('user').prefetch_related('genres', 'characters')[:10]:
                    if str(story.public_uuid) not in added_story_ids:
                        added_story_ids.add(str(story.public_uuid))
                        genres = ', '.join([g.name for g in story.genres.all()[:2]]) or 'AI 스토리'
                        image = request.build_absolute_uri(story.cover_image.url) if getattr(story, 'cover_image', None) else None
                        results.append({
                            'type': 'story',
                            'id': str(story.public_uuid),
                            'title': story.title,
                            'description': story.description[:100] if story.description else '',
                            'author': story.user.nickname if story.user else '알 수 없음',
                            'author_id': str(story.user.public_uuid) if story.user else None,
                            'cover_image': image,
                            'genre': genres,
                            'character_count': story.characters.count()
                        })
                        counts['story'] += 1

                # 유저 Snap
                for snap in BookSnap.objects.filter(user=user).select_related('user', 'story', 'book')[:10]:
                    if str(snap.public_uuid) not in added_snap_ids:
                        added_snap_ids.add(str(snap.public_uuid))
                        thumb = request.build_absolute_uri(snap.thumbnail.url) if getattr(snap, 'thumbnail', None) else None
                        comments_count = snap.comments.count() if hasattr(snap, 'comments') else 0
                        results.append({
                            'type': 'snap',
                            'id': str(snap.public_uuid),
                            'snap_title': snap.snap_title or getattr(snap, 'name', ''),
                            'snap_video': request.build_absolute_uri(snap.snap_video.url) if snap.snap_video else None,
                            'thumbnail': thumb,
                            'likes_count': getattr(snap, 'likes_count', 0),
                            'views': snap.views,
                            'shares': snap.shares,
                            'comments_count': comments_count,
                            'allow_comments': snap.allow_comments,
                            'book_id': str(snap.book.public_uuid) if snap.book else None,
                            'story_id': str(snap.story.public_uuid) if snap.story else None,
                            'linked_type': 'book' if snap.book else 'story' if snap.story else None,
                            'book_comment': snap.book_comment,
                            'duration': snap.duration,
                            'created_at': snap.created_at.isoformat(),
                            'user': {
                                'id': str(snap.user.public_uuid),
                                'nickname': snap.user.nickname,
                                'profile_img': request.build_absolute_uri(snap.user.user_img.url) if snap.user.user_img else None
                            } if snap.user else None
                        })
                        counts['snap'] += 1

    # ========== 책 검색 ==========
    if filter_type in ['all', 'book', 'audiobook', 'webnovel']:
        book_qs = Books.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(user__nickname__icontains=query) |
            Q(tags__name__icontains=query) |
            Q(genres__name__icontains=query)
        ).select_related('user').prefetch_related('genres', 'tags').filter(is_deleted=False).distinct()

        if filter_type == 'audiobook':
            book_qs = book_qs.filter(book_type='audiobook')
        elif filter_type == 'webnovel':
            book_qs = book_qs.filter(book_type='webnovel')

        for book in book_qs[:30]:
            if str(book.public_uuid) not in added_book_ids:
                added_book_ids.add(str(book.public_uuid))
                genres = ', '.join([g.name for g in book.genres.all()[:2]]) or '기타'
                btype = getattr(book, 'book_type', 'audiobook')
                results.append({
                    'type': btype,  # 'audiobook' or 'webnovel'
                    'id': str(book.public_uuid),
                    'title': book.name,
                    'description': book.description[:100] if book.description else '',
                    'author': book.user.nickname if book.user else '알 수 없음',
                    'author_id': str(book.user.public_uuid) if book.user else None,
                    'cover_image': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
                    'genre': genres,
                    'book_score': float(book.book_score) if book.book_score else 0,
                    'adult_choice': getattr(book, 'adult_choice', False),
                })
                counts['book'] += 1
                if btype == 'webnovel':
                    counts['webnovel'] += 1
                else:
                    counts['audiobook'] += 1

    # ========== 스토리 검색 ========== 
    if filter_type in ['all', 'story']:
        for story in Story.objects.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(genres__name__icontains=query) |
            Q(tags__name__icontains=query) |
            Q(user__nickname__icontains=query),
            is_public=True
        ).select_related('user').prefetch_related('genres', 'characters').distinct()[:30]:
            if str(story.public_uuid) not in added_story_ids:
                added_story_ids.add(str(story.public_uuid))
                genres = ', '.join([g.name for g in story.genres.all()[:2]]) or 'AI 스토리'
                image = request.build_absolute_uri(story.cover_image.url) if getattr(story, 'cover_image', None) else None
                results.append({
                    'type': 'story',
                    'id': str(story.public_uuid),
                    'title': story.title,
                    'description': story.description[:100] if story.description else '',
                    'author': story.user.nickname if story.user else '알 수 없음',
                    'author_id': str(story.user.public_uuid) if story.user else None,
                    'cover_image': image,
                    'genre': genres,
                    'character_count': story.characters.count(),
                    'adult_choice': getattr(story, 'adult_choice', False),
                })
                counts['story'] += 1

    # ========== Snap 검색 ========== 
    if filter_type in ['all', 'snap']:
        for snap in BookSnap.objects.filter(
            Q(snap_title__icontains=query) |
            Q(book_comment__icontains=query) |
            Q(book__name__icontains=query) |
            Q(user__nickname__icontains=query)
        ).select_related('user', 'story', 'book').distinct()[:30]:
            if str(snap.public_uuid) not in added_snap_ids:
                added_snap_ids.add(str(snap.public_uuid))
                thumb = request.build_absolute_uri(snap.thumbnail.url) if getattr(snap, 'thumbnail', None) else None
                comments_count = snap.comments.count() if hasattr(snap, 'comments') else 0
                results.append({
                    'type': 'snap',
                    'id': str(snap.public_uuid),
                    'snap_title': snap.snap_title,
                    'snap_video': request.build_absolute_uri(snap.snap_video.url) if snap.snap_video else None,
                    'thumbnail': thumb,
                    'likes_count': getattr(snap, 'likes_count', 0),
                    'views': snap.views,
                    'shares': snap.shares,
                    'comments_count': comments_count,
                    'allow_comments': snap.allow_comments,
                    'book_id': str(snap.book.public_uuid) if snap.book else None,
                    'story_id': str(snap.story.public_uuid) if snap.story else None,
                    'linked_type': 'book' if snap.book else 'story' if snap.story else None,
                    'book_comment': snap.book_comment,
                    'duration': snap.duration,
                    'created_at': snap.created_at.isoformat(),
                    'user': {
                        'id': str(snap.user.public_uuid),
                        'nickname': snap.user.nickname,
                        'profile_img': request.build_absolute_uri(snap.user.user_img.url) if snap.user.user_img else None
                    } if snap.user else None,
                    'adult_choice': getattr(snap, 'adult_choice', False),
                })
                counts['snap'] += 1

    return JsonResponse({
        'success': True,
        'results': results,
        'counts': counts
    })


# ==================== 💬 Book Comments API ====================

@csrf_exempt
@api_view(['GET', 'POST'])
def api_book_comments(request, book_uuid):
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

    book = get_object_or_404(Books, public_uuid=book_uuid)

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
                'id': str(book.public_uuid),
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
                    'id': str(user.public_uuid),
                    'nickname': user.nickname,
                    'profile_img': request.build_absolute_uri(user.user_img.url) if user.user_img else None,
                },
                'replies_count': 0
            }
        })
# ==================== ⭐ Book Reviews Create/Update API ====================

from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from django.http import JsonResponse
from book.models import Books, BookReview, APIKey
import json

def _update_book_score(book):
    """책의 전체 평점 업데이트"""
    reviews = BookReview.objects.filter(book=book)
    if reviews.exists():
        book.book_score = round(sum(r.rating for r in reviews) / reviews.count(), 1)
    else:
        book.book_score = 0.0
    book.save()

@csrf_exempt
@api_view(['POST', 'PATCH', 'DELETE'])
def api_book_review_create(request, book_uuid):
    """
    책 리뷰/평가 작성/수정/삭제 API

    POST: 리뷰 작성
    PATCH: 리뷰 수정
    DELETE: 리뷰 삭제
    """
    book = get_object_or_404(Books, public_uuid=book_uuid)

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
            rating = data.get('rating')
            review_text = data.get('review_text', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

        if not rating:
            return JsonResponse({'success': False, 'error': 'Rating is required'}, status=400)

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Rating must be between 1 and 5'}, status=400)

        existing_review = BookReview.objects.filter(user=user, book=book).first()
        if existing_review:
            return JsonResponse({'success': False, 'error': 'You have already reviewed this book. Use PATCH to update.'}, status=400)

        review = BookReview.objects.create(
            user=user,
            book=book,
            rating=rating,
            review_text=review_text
        )

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
                },
                'book': {
                    'id': str(book.public_uuid),  # UUID 사용
                    'name': book.name
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

        if rating is not None:
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    raise ValueError
                review.rating = rating
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Rating must be between 1 and 5'}, status=400)

        if review_text is not None:
            review.review_text = review_text.strip()

        review.save()
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
                },
                'book': {
                    'id': str(book.public_uuid),  # UUID 사용
                    'name': book.name
                }
            }
        })

    # DELETE: 리뷰 삭제
    elif request.method == 'DELETE':
        try:
            review = BookReview.objects.get(user=user, book=book)
            review.delete()
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

@csrf_exempt
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
    from book.models import APIKey

    if request.method != 'POST':
        return JsonResponse({'error': 'POST 요청만 허용됩니다'}, status=405)

    # API 키로 사용자 확인
    api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API key required'}, status=401)

    try:
        api_key_obj = APIKey.objects.get(key=api_key, is_active=True)
        user = api_key_obj.user
    except APIKey.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid API Key'}, status=401)

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
            'user_id': str(follower.public_uuid),
            'nickname': follower.nickname,
            'profile_img': request.build_absolute_uri(follower.user_img.url) if follower.user_img else None,
            'followed_at': follow.created_at.isoformat()
        })

    return api_response({
        'followers': followers_data,
        'pagination': result['pagination']
    })


@require_api_key
def api_user_following(request, user_uuid):
    """
    특정 사용자가 팔로우하는 작가 목록 API (UUID 기준)

    GET /api/users/<uuid>/following/?page=1&per_page=20
    """
    from register.models import CustomUser

    try:
        target_user = CustomUser.objects.get(public_uuid=user_uuid)
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': '사용자를 찾을 수 없습니다'}, status=404)

    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    # 팔로잉 목록
    following = Follow.objects.filter(follower=target_user).select_related('following')
    result = paginate(following, page, per_page)

    following_data = []
    for follow in result['items']:
        author = follow.following
        books_count = Books.objects.filter(user=author).count()
        followers_count = Follow.objects.filter(following=author).count()

        following_data.append({
            'id': str(author.public_uuid),
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
    팔로우한 작가들의 최신 책 피드 API (UUID 기준)

    GET /api/following/feed/?page=1&per_page=20

    팔로우한 작가들이 작성한 책을 최신순으로 반환
    """
    user = request.api_user
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    # 팔로우한 작가들의 UUID 목록
    following_uuids = Follow.objects.filter(follower=user).values_list('following__public_uuid', flat=True)

    if not following_uuids:
        return api_response({
            'books': [],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': 0,
                'total_pages': 0,
                'has_next': False,
                'has_prev': False
            }
        })

    # 팔로우한 작가들의 책 목록
    books = Books.objects.filter(
        user__public_uuid__in=following_uuids
    ).select_related('user').prefetch_related('genres', 'tags').annotate(
        episodes_count=Count('contents'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-created_at')

    result = paginate(books, page, per_page)

    books_data = []
    for book in result['items']:
        books_data.append({
            'id': str(book.public_uuid),
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
                'id': str(book.user.public_uuid),
                'nickname': book.author_name or book.user.nickname,
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

@csrf_exempt
def api_bookmark_toggle(request, book_uuid):
    """
    책 북마크(나중에 보기) 토글 API

    POST /api/books/<uuid>/bookmark/

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
        from book.models import APIKey
        import traceback

        print(f"📍 [BOOKMARK] book_uuid={book_uuid}, method={request.method}")

        if request.method != 'POST':
            return JsonResponse({'error': 'POST 요청만 허용됩니다'}, status=405)

        # API 키로 사용자 확인
        api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
        print(f"📍 [BOOKMARK] API Key: {api_key[:20] if api_key else 'None'}...")

        if not api_key:
            print(f"❌ [BOOKMARK] No API key")
            return JsonResponse({'success': False, 'error': 'API key required'}, status=401)

        try:
            api_key_obj = APIKey.objects.get(key=api_key, is_active=True)
            user = api_key_obj.user
            print(f"✅ [BOOKMARK] User: {user.email}")
        except APIKey.DoesNotExist:
            print(f"❌ [BOOKMARK] Invalid API key")
            return JsonResponse({'success': False, 'error': 'Invalid API Key'}, status=401)

        # 책 확인
        try:
            book = Books.objects.get(public_uuid=book_uuid)
            print(f"✅ [BOOKMARK] Book: {book.name}")
        except Books.DoesNotExist:
            print(f"❌ [BOOKMARK] Book not found")
            return JsonResponse({'success': False, 'error': '책을 찾을 수 없습니다'}, status=404)

        # 요청 바디에서 메모 추출 (선택사항)
        note = None
        if request.body:
            try:
                data = json.loads(request.body)
                note = data.get('note', '')
            except json.JSONDecodeError:
                pass

        # 북마크 토글
        print(f"📍 [BOOKMARK] Toggling bookmark...")
        bookmark, created = BookmarkBook.objects.get_or_create(
            user=user,
            book=book,
            defaults={'note': note or ''}
        )
        print(f"✅ [BOOKMARK] created={created}")

        if not created:
            # 이미 북마크되어 있으면 제거
            bookmark.delete()
            is_bookmarked = False
        else:
            is_bookmarked = True

        print(f"✅ [BOOKMARK] Success: is_bookmarked={is_bookmarked}")
        return JsonResponse({
            'success': True,
            'is_bookmarked': is_bookmarked
        })
    except Exception as e:
        print(f"❌❌❌ [BOOKMARK ERROR] {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'서버 오류: {str(e)}'
        }, status=500)


@csrf_exempt
def api_bookmark_update_note(request, book_uuid):
    """
    북마크 메모 업데이트 API (UUID 기준)

    PATCH /api/books/<uuid>/bookmark/note/

    Body:
        {
            "note": "새로운 메모 내용"
        }
    """
    from book.models import APIKey, Books, BookmarkBook
    import json

    if request.method != 'PATCH':
        return JsonResponse({'error': 'PATCH 요청만 허용됩니다'}, status=405)

    # API 키로 사용자 확인
    api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API key required'}, status=401)

    try:
        api_key_obj = APIKey.objects.get(key=api_key, is_active=True)
        user = api_key_obj.user
    except APIKey.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid API Key'}, status=401)

    # 책 찾기 (UUID 기준)
    book = get_object_or_404(Books, public_uuid=book_uuid)

    # 북마크 확인
    try:
        bookmark = BookmarkBook.objects.get(user=user, book=book)
    except BookmarkBook.DoesNotExist:
        return JsonResponse({'success': False, 'error': '북마크를 찾을 수 없습니다'}, status=404)

    # 요청 본문에서 note 가져오기
    try:
        data = json.loads(request.body)
        note = data.get('note', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    # 메모 업데이트
    bookmark.note = note
    bookmark.save()

    return JsonResponse({
        'success': True,
        'data': {
            'book_id': str(book.public_uuid),
            'note': bookmark.note,
            'updated_at': bookmark.updated_at.isoformat() if hasattr(bookmark, 'updated_at') else bookmark.created_at.isoformat()
        }
    })



@require_api_key
def api_user_bookmarks(request):
    """
    사용자의 북마크 목록 API (UUID 기준)

    GET /api/bookmarks/?page=1&per_page=20

    Returns bookmarked books with notes
    """
    from book.models import BookmarkBook, Books, Content, BookReview
    from django.db.models import Avg

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
                'id': str(book.public_uuid),  # UUID로 반환
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
                    'nickname': book.author_name or book.user.nickname,
                    'profile_img': request.build_absolute_uri(book.user.user_img.url) if book.user.user_img else None,
                },
                'genres': [
                    {'id': g.id, 'name': g.name, 'color': g.genres_color}
                    for g in book.genres.all()
                ],
                'tags': [
                    {'id': t.id, 'name': t.name}
                    for t in book.tags.all()
                ],
                'book_type': book.book_type,
                'adult_choice': book.adult_choice,
            }
        })

    return api_response({
        'bookmarks': bookmarks_data,
        'pagination': result['pagination']
    })


# ==================== 📖 Webnovel API ====================

@require_api_key
def api_webnovel_list(request):
    """
    웹소설 목록 API

    Query Parameters:
        - page: 페이지 번호 (기본: 1)
        - per_page: 페이지당 아이템 수 (기본: 20)
        - genre: 장르 ID (선택)
        - search: 검색어 (선택)
    """
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    genre_id = request.GET.get('genre')
    search = request.GET.get('search', '').strip()

    novels = Books.objects.filter(
        book_type='webnovel', is_deleted=False
    ).select_related('user').prefetch_related('genres', 'tags')

    if genre_id:
        novels = novels.filter(genres__id=genre_id)
    if search:
        from django.db.models import Q
        novels = novels.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(user__nickname__icontains=search) |
            Q(tags__name__icontains=search)
        ).distinct()

    novels = novels.order_by('-created_at')
    result = paginate(novels, page, per_page)

    data = []
    for novel in result['items']:
        data.append({
            'id': str(novel.public_uuid),
            'name': novel.name,
            'description': novel.description or '',
            'cover_img': request.build_absolute_uri(novel.cover_img.url) if novel.cover_img else None,
            'book_type': 'webnovel',
            'book_score': float(novel.book_score) if novel.book_score else 0.0,
            'episode_count': novel.contents.count(),
            'status': novel.status,
            'status_display': novel.get_status_display(),
            'created_at': novel.created_at.isoformat(),
            'author': {
                'id': novel.user.user_id,
                'nickname': novel.author_name or novel.user.nickname,
            },
            'genres': [{'id': g.id, 'name': g.name, 'color': g.genres_color} for g in novel.genres.all()],
            'tags': [{'id': t.id, 'name': t.name} for t in novel.tags.all()],
        })

    return api_response({'novels': data, 'pagination': result['pagination']})


@require_api_key
def api_webnovel_episode(request, content_uuid):
    """
    웹소설 에피소드 본문 API (감정 태그 제거된 순수 텍스트 반환)

    Example:
        GET /book/api/webnovel/episode/<uuid>/
    """
    import re
    from book.models import Content
    content = get_object_or_404(Content, public_uuid=content_uuid)
    book = content.book

    raw_text = content.text or ''
    clean_text = re.sub(r'\[[^\]]+\]', '', raw_text)
    paragraphs = [p.strip() for p in clean_text.split('\n') if p.strip()]

    # 이전/다음 에피소드
    prev_ep = Content.objects.filter(book=book, number=content.number - 1).first()
    next_ep = Content.objects.filter(book=book, number=content.number + 1).first()

    return api_response({
        'episode': {
            'id': str(content.public_uuid),
            'title': content.title,
            'number': content.number,
            'paragraphs': paragraphs,
            'llm_provider': content.llm_provider or '',
            'created_at': content.created_at.isoformat(),
        },
        'book': {
            'id': str(book.public_uuid),
            'name': book.name,
            'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
        },
        'prev_episode': {'id': str(prev_ep.public_uuid), 'title': prev_ep.title, 'number': prev_ep.number} if prev_ep else None,
        'next_episode': {'id': str(next_ep.public_uuid), 'title': next_ep.title, 'number': next_ep.number} if next_ep else None,
    })


@require_api_key
def api_webnovel_detail(request, book_uuid):
    """
    웹소설 상세 API (에피소드 목록 포함)

    Example:
        GET /book/api/webnovels/<uuid>/
    """
    from django.db.models import Avg, Count as DCount
    from book.models import BookReview, ReadingProgress

    book = get_object_or_404(
        Books.objects.select_related('user').prefetch_related('genres', 'tags'),
        public_uuid=book_uuid,
        book_type='webnovel',
        is_deleted=False
    )

    avg_rating = book.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    review_count = book.reviews.count()
    episode_count = book.contents.filter(is_deleted=False).count()

    episodes = []
    for ep in book.contents.filter(is_deleted=False).order_by('-number'):
        episodes.append({
            'id': str(ep.public_uuid),
            'number': ep.number,
            'title': ep.title,
            'created_at': ep.created_at.isoformat(),
            'llm_provider': ep.llm_provider or '',
        })

    is_bookmarked = False
    if request.user and request.user.is_authenticated:
        from book.models import BookmarkBook
        is_bookmarked = BookmarkBook.objects.filter(user=request.user, book=book).exists()

    return api_response({
        'id': str(book.public_uuid),
        'name': book.name,
        'description': book.description or '',
        'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
        'book_type': 'webnovel',
        'status': book.status,
        'status_display': book.get_status_display(),
        'book_score': float(book.book_score) if book.book_score else 0.0,
        'avg_rating': round(float(avg_rating), 1),
        'review_count': review_count,
        'episode_count': episode_count,
        'created_at': book.created_at.isoformat(),
        'author': {
            'id': book.user.user_id,
            'nickname': book.author_name or book.user.nickname,
            'profile_img': request.build_absolute_uri(book.user.user_img.url) if book.user.user_img else None,
        },
        'genres': [{'id': g.id, 'name': g.name, 'color': g.genres_color} for g in book.genres.all()],
        'tags': [{'id': t.id, 'name': t.name} for t in book.tags.all()],
        'episodes': episodes,
        'is_bookmarked': is_bookmarked,
        'adult_choice': book.adult_choice,
    })
