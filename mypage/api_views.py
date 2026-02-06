from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from book.models import APIKey

from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from book.api_utils import require_api_key, paginate, api_response, require_api_key_secure
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from character.models import Story, Conversation, ConversationMessage
from register.models import Users
from book.models import Books, BookSnap, Follow

@api_view(['GET', 'PATCH'])
def api_user_info(request):
    api_key = request.GET.get('api_key')

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
            "created_at": user.created_at.isoformat(),
        })

    # 🔥 수정
    elif request.method == 'PATCH':
        data = request.data

        user.nickname = data.get('nickname', user.nickname)
        user.gender = data.get('gender', user.gender)
        user.birthdate = data.get('birthdate', user.birthdate)
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
    snap_list = BookSnap.objects.filter(user=target_user).order_by('-created_at')

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

    # 로그인 유저 기준 정보
    is_following = False
    is_own_profile = False
    if request.user.is_authenticated:
        is_following = Follow.objects.filter(
            follower=request.user,
            following=target_user
        ).exists()
        is_own_profile = request.user == target_user

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

            }
            for story in story_list
        ],

        # -------------------
        # 스냅
        # -------------------
        'snaps': [
            {
                'id': snap.public_uuid,
                'image': request.build_absolute_uri(snap.thumbnail.url) if snap.thumbnail else None,
                'content': snap.snap_title,
                'created_at': snap.created_at.isoformat(),
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