from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from book.models import APIKey
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from book.api_utils import require_api_key, paginate, api_response, require_api_key_secure
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from register.models import Users
from book.models import Books, BookSnap, Follow, ListeningHistory, Content
from django.db.models import Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
from datetime import datetime, timedelta

@api_view(['GET', 'PATCH'])
def api_user_info(request):
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')

    if not api_key:
        return Response({"error": "로그인이 필요합니다."}, status=401)

    try:
        api_key_obj = APIKey.objects.select_related('user').get(
            key=api_key,
            is_active=True
        )
        user = api_key_obj.user
    except APIKey.DoesNotExist:
        return Response({"error": "잘못된 API Key입니다."}, status=401)

    # 🔹 조회
    if request.method == 'GET':
        return Response({
            "id": str(user.public_uuid),
            "username": user.username,
            "email": user.email,
            "nickname": user.nickname,
            "gender": user.gender,
            "age": user.age,
            "birthdate": user.birthdate,
            "user_img": user.user_img.url if user.user_img else None,
            "cover_img": user.cover_img.url if user.cover_img else None,
            "follow_count": user.follow_count,
            "status": user.status,
            "oauth_provider": user.oauth_provider,
            "is_adult": user.is_adult(),
            "created_at": user.created_at.isoformat(),
        })

    # 🔥 수정
    elif request.method == 'PATCH':
        data = request.data

        user.nickname = data.get('nickname', user.nickname)
        user.gender = data.get('gender', user.gender)
        user.birthdate = data.get('birthdate', user.birthdate)

        
        if Users.objects.filter(nickname=user.nickname).exists():
            return JsonResponse({"error": "이미 존재하는 닉네임입니다."}, status=400)
        if 'user_img' in request.FILES:
            user.user_img = request.FILES['user_img']
        user.save()

        return Response({"success": True})



@csrf_exempt
@require_api_key_secure
def public_user_profile(request, user_uuid):

    target_user = get_object_or_404(Users, public_uuid=user_uuid)

    # 책 / 스토리 / 스냅
    book_list = Books.objects.filter(user=target_user)
    story_list = Story.objects.filter(user=target_user)
    snap_list = BookSnap.objects.filter(user=target_user).select_related('book', 'story').order_by('-created_at')

    # 공개된 대화 (최근 20개)
    user_share_list = Conversation.objects.filter(
        user=target_user,
        is_public=True
    ).select_related(
        'llm'
    ).prefetch_related(
        Prefetch(
            'messages',
            queryset=ConversationMessage.objects.order_by('created_at'),
            to_attr='all_messages'
        )
    ).order_by('-shared_at')[:20]

    # 팔로워 / 팔로잉
    follower_count = Follow.objects.filter(following=target_user).count()
    following_count = Follow.objects.filter(follower=target_user).count()

    # 로그인 유저 기준 정보 (API key 또는 세션 인증)
    is_following = False
    is_own_profile = False
    current_user = getattr(request, 'api_user', None)
    if current_user is None and hasattr(request, 'user') and request.user.is_authenticated:
        current_user = request.user
    if current_user:
        is_following = Follow.objects.filter(
            follower=current_user,
            following=target_user
        ).exists()
        is_own_profile = current_user.pk == target_user.pk

    # ---------------------------
    # 응답 데이터 구성
    # ---------------------------

    data = {
        'user': {
            'id': str(target_user.public_uuid),
            'nickname': target_user.nickname if hasattr(target_user, 'nickname') else target_user.username,
            'profile_image': request.build_absolute_uri(target_user.user_img.url) if getattr(target_user, 'user_img', None) else None,
            'bio': getattr(target_user, 'bio', ''),
            'created_at': target_user.created_at.isoformat() if hasattr(target_user, 'created_at') else None,
        },

        'counts': {
            'followers': follower_count,
            'following': following_count,
            'books': book_list.count(),
            'stories': story_list.count(),
            'snaps': snap_list.count(),
        },

        'relation': {
            'is_following': is_following,
            'is_own_profile': is_own_profile,
        },

        # -------------------
        # 책
        # -------------------
        'books': [
            {
                'id': book.public_uuid,
                'title': book.name,
                'description': book.description,
                'cover_image': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
                'adult_choice': book.adult_choice,
                'created_at': book.created_at.isoformat(),
            }
            for book in book_list
        ],

        # -------------------
        # 스토리
        # -------------------
        'stories': [
            {
                'id': story.public_uuid,
                'title': story.title,
                'created_at': story.created_at.isoformat(),
                'cover_image': request.build_absolute_uri(story.cover_image.url) if story.cover_image else None,
                'story_desc_img': request.build_absolute_uri(story.story_desc_img.url) if story.story_desc_img else None,
                'story_desc_video': request.build_absolute_uri(story.story_desc_video.url) if story.story_desc_video else None,
                'characters_count': story.characters.count(),
                'adult_choice': story.adult_choice,
            }
            for story in story_list
        ],

        # -------------------
        # 스냅
        # -------------------
        'snaps': [
            {
                'id': str(snap.public_uuid),
                'snap_title': snap.snap_title,
                'snap_video': request.build_absolute_uri(snap.snap_video.url) if snap.snap_video else None,
                'thumbnail': request.build_absolute_uri(snap.thumbnail.url) if snap.thumbnail else None,
                'likes_count': snap.booksnap_like.count(),
                'views': snap.views,
                'shares': snap.shares,
                'comments_count': snap.comments.count() if hasattr(snap, 'comments') else 0,
                'allow_comments': snap.allow_comments,
                'book_id': str(snap.book.public_uuid) if snap.book else None,
                'story_id': str(snap.story.public_uuid) if snap.story else None,
                'linked_type': 'story' if snap.story_id else ('book' if snap.book_id else None),
                'book_comment': snap.book_comment,
                'duration': snap.duration,
                'created_at': snap.created_at.isoformat(),
                'user': {
                    'id': str(snap.user.public_uuid) if snap.user else None,
                    'nickname': snap.user.nickname if snap.user else 'Unknown',
                    'profile_img': request.build_absolute_uri(snap.user.user_img.url) if snap.user and snap.user.user_img else None,
                } if snap.user else None,
            }
            for snap in snap_list
        ],

        # -------------------
        # 공개 대화
        # -------------------
        'shared_conversations': [
            {
                'conversation_id': conv.id,
                'shared_at': conv.shared_at.isoformat() if conv.shared_at else conv.created_at.isoformat(),

                'llm': {
                    'id': str(conv.llm.public_uuid),
                    'name': conv.llm.name,
                    'description': conv.llm.description or '',
                    'first_sentence': conv.llm.first_sentence or '',
                    'llm_image': request.build_absolute_uri(conv.llm.llm_image.url) if conv.llm.llm_image else None,
                    'llm_background_image': request.build_absolute_uri(conv.llm.llm_background_image.url) if conv.llm.llm_background_image else None,
                },

                'messages': [
                    {
                        'role': msg.role,
                        'content': msg.content,
                        'created_at': msg.created_at.isoformat(),
                        'audio_url': request.build_absolute_uri(msg.audio.url) if msg.audio else None,
                    }
                    for msg in getattr(conv, 'all_messages', [])
                ],

                'message_count': len(getattr(conv, 'all_messages', [])),
            }
            for conv in user_share_list
        ]
    }

    return api_response(data)


@csrf_exempt
@require_api_key_secure
def toggle_follow_api(request, user_uuid):
    """앱용 팔로우/언팔로우 토글 API (UUID 기반)"""
    if request.method != 'POST':
        return api_response(error='POST 요청만 가능합니다.', status=405)

    current_user = getattr(request, 'api_user', None)
    if not current_user:
        return api_response(error='로그인이 필요합니다.', status=401)

    target_user = get_object_or_404(Users, public_uuid=user_uuid)

    if current_user.pk == target_user.pk:
        return api_response(error='자기 자신을 팔로우할 수 없습니다.', status=400)

    follow, created = Follow.objects.get_or_create(
        follower=current_user,
        following=target_user
    )

    if not created:
        follow.delete()
        is_following = False
    else:
        is_following = True

    follower_count = Follow.objects.filter(following=target_user).count()

    return api_response({
        'is_following': is_following,
        'follower_count': follower_count,
    })


@require_api_key_secure
def api_listening_stats(request):
    """
    GET /mypage/api/listening-stats/
    일별(최근 30일) + 월별(최근 12개월) + 연도별 TTS/청취 통계 반환
    웹 my_profile 통계와 동일한 구조
    """
    user = request.api_user
    now = datetime.now()

    thirty_days_ago = now - timedelta(days=30)
    twelve_months_ago = now - timedelta(days=365)

    # ── TTS 일별 ──────────────────────────────
    tts_daily = list(
        Content.objects
        .filter(book__user=user, created_at__gte=thirty_days_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('duration_seconds'))
        .order_by('day')
    )
    # ── 청취 일별 ──────────────────────────────
    listening_daily = list(
        ListeningHistory.objects
        .filter(user=user, listened_at__gte=thirty_days_ago)
        .annotate(day=TruncDate('listened_at'))
        .values('day')
        .annotate(total=Sum('listened_seconds'))
        .order_by('day')
    )

    # ── TTS 월별 ──────────────────────────────
    tts_monthly = list(
        Content.objects
        .filter(book__user=user, created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('duration_seconds'))
        .order_by('month')
    )
    # ── 청취 월별 ──────────────────────────────
    listening_monthly = list(
        ListeningHistory.objects
        .filter(user=user, listened_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('listened_at'))
        .values('month')
        .annotate(total=Sum('listened_seconds'))
        .order_by('month')
    )

    # ── TTS 연도별 ──────────────────────────────
    tts_yearly = list(
        Content.objects
        .filter(book__user=user)
        .annotate(year=TruncYear('created_at'))
        .values('year')
        .annotate(total=Sum('duration_seconds'))
        .order_by('year')
    )
    # ── 청취 연도별 ──────────────────────────────
    listening_yearly = list(
        ListeningHistory.objects
        .filter(user=user)
        .annotate(year=TruncYear('listened_at'))
        .values('year')
        .annotate(total=Sum('listened_seconds'))
        .order_by('year')
    )

    tts_daily_min   = round(sum((x['total'] or 0) for x in tts_daily) / 60, 1)
    listen_daily_min = round(sum((x['total'] or 0) for x in listening_daily) / 60, 1)
    tts_monthly_min  = round(sum((x['total'] or 0) for x in tts_monthly) / 60, 1)
    listen_monthly_hr = round(sum((x['total'] or 0) for x in listening_monthly) / 3600, 1)

    return api_response({
        'daily': {
            'tts': {
                'labels': [x['day'].strftime('%m/%d') for x in tts_daily],
                'data':   [round((x['total'] or 0) / 60, 1) for x in tts_daily],
                'unit': '분',
            },
            'listening': {
                'labels': [x['day'].strftime('%m/%d') for x in listening_daily],
                'data':   [round((x['total'] or 0) / 60, 1) for x in listening_daily],
                'unit': '분',
            },
        },
        'monthly': {
            'tts': {
                'labels': [x['month'].strftime('%y.%m') for x in tts_monthly],
                'data':   [round((x['total'] or 0) / 60, 1) for x in tts_monthly],
                'unit': '분',
            },
            'listening': {
                'labels': [x['month'].strftime('%y.%m') for x in listening_monthly],
                'data':   [round((x['total'] or 0) / 3600, 1) for x in listening_monthly],
                'unit': '시간',
            },
        },
        'yearly': {
            'tts': {
                'labels': [str(x['year'].year) for x in tts_yearly],
                'data':   [round((x['total'] or 0) / 3600, 1) for x in tts_yearly],
                'unit': '시간',
            },
            'listening': {
                'labels': [str(x['year'].year) for x in listening_yearly],
                'data':   [round((x['total'] or 0) / 3600, 1) for x in listening_yearly],
                'unit': '시간',
            },
        },
        'summary': {
            'tts_30d_minutes':      tts_daily_min,
            'listening_30d_minutes': listen_daily_min,
            'tts_12m_minutes':      tts_monthly_min,
            'listening_12m_hours':  listen_monthly_hr,
        }
    })
