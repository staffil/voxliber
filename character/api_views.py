from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Max, Q
from django.views.decorators.csrf import csrf_exempt
from character.models import LLM, Story, CharacterMemory, Conversation, ConversationMessage, ConversationState, HPImageMapping, LLMSubImage, LoreEntry, LLMPrompt, StoryLike, StoryComment, StoryBookmark,  Prompt,  Comment, LLMLike, UserLastWard
from book.api_utils import require_api_key, paginate, api_response, require_api_key_secure
from rest_framework.decorators import api_view
import json
from django.utils import timezone
from django.db.models import Prefetch
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Story


def _get_request_user(request):
    """API key 또는 세션에서 유저를 가져옴 (앱/웹 공통)"""
    from book.models import APIKey
    api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
    if api_key:
        try:
            api_key_obj = APIKey.objects.select_related('user').get(key=api_key, is_active=True)
            return api_key_obj.user
        except APIKey.DoesNotExist:
            print(f"[_get_request_user] API Key 없음 또는 비활성: {api_key[:10]}...")
        except Exception as e:
            print(f"[_get_request_user] API Key 조회 오류: {e}")
    if hasattr(request, 'user') and request.user.is_authenticated:
        return request.user
    return None

@csrf_exempt
@require_api_key_secure
def public_story_list(request):
    """
    공개 Story 목록 API (로그인 불필요)
    모든 유저의 공개 Story를 반환합니다.
    Query Parameters:
        - page: 페이지 번호 (default 1)
        - per_page: 페이지당 항목 수 (default 20)
    """
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    # 모든 공개 Story
    stories = Story.objects.all().order_by("?")
    result = paginate(stories, page, per_page)

    stories_data = []
    for story in result['items']:
        stories_data.append({
            'id': str(story.public_uuid),
            'title': story.title,
            'description': story.description,
            'cover_image': request.build_absolute_uri(story.cover_image.url) if story.cover_image else None,
            'story_desc_video': request.build_absolute_uri(story.story_desc_video.url) if story.story_desc_video else None,
            'story_desc_img': request.build_absolute_uri(story.story_desc_img.url) if story.story_desc_img else None,
            'genres': [{'name': g.name, 'color': getattr(g, 'genres_color', None)} for g in story.genres.all()],
            'tags': [t.name for t in story.tags.all()],
            'user_id': str(story.user.public_uuid),  # 작성자 정보
            'username': story.user.username,         # 작성자 정보
            'created_at': story.created_at.isoformat(),
            'adult_choice': story.adult_choice,
        })

    return JsonResponse({
        'stories': stories_data,
        'pagination': result['pagination']
    })



import json
from django.views.decorators.csrf import csrf_exempt
from book.api_utils import require_api_key_secure, api_response
from django.views.decorators.csrf import csrf_exempt
from book.api_utils import require_api_key_secure, api_response
from character.models import Story
import json

@csrf_exempt
@require_api_key_secure
def public_llm_list(request):
    """
    공개 LLM 목록 API (로그인 불필요)
    Query Parameters:
        - page
        - per_page
    """
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    llms = LLM.objects.all()
    result = paginate(llms, page, per_page)

    llms_data = []
    for llm in result['items']:
        llms_data.append({
            'id': str(llm.public_uuid),
            'name': llm.name,
            'model': llm.model,
            'prompt_preview': llm.prompt[:100],  # 일부만 공개
            'is_public': llm.is_public,
            'created_at': llm.created_at.isoformat(),
            'story_id': str(llm.story.public_uuid) if llm.story else None,
            'narrator_voice': llm.narrator_voice.name if llm.narrator_voice else None
        })

    return api_response({
        'llms': llms_data,
        'pagination': result['pagination']
    })
    
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
import logging

from character.models import (
    Conversation, ConversationMessage, ConversationState, UserLastWard, ArchivedConversation
)
from character.views import archive_conversation

@require_api_key_secure
@api_view(['DELETE'])
def api_delete_conversation(request, conv_id):
    """
    사용자 Conversation 삭제 → ArchivedConversation으로 아카이브 후 원본 삭제
    """

    request_user = _get_request_user(request)

    if not request_user:
        return Response(
            {"error": "인증 실패"},
            status=401
        )

    conversation = get_object_or_404(
        Conversation,
        id=conv_id,
        user=request_user   # ✅ 수정
    )

    llm = conversation.llm

    try:
        with transaction.atomic():

            # 1️⃣ 아카이브 저장
            archive_conversation(conversation)

            # 2️⃣ 메시지 삭제
            ConversationMessage.objects.filter(
                conversation=conversation
            ).delete()

            # 3️⃣ 상태 삭제
            ConversationState.objects.filter(
                conversation=conversation
            ).delete()

            # 4️⃣ 공개 여부 업데이트
            UserLastWard.objects.filter(
                user=request_user,   # ✅ 수정
                last_ward__llm=llm
            ).update(is_public=False)

            # 5️⃣ Conversation 삭제
            conversation.delete()

    except Exception as e:
        logging.error(
            f"[API DELETE] Conversation 삭제 실패: {e}",
            exc_info=True
        )
        return Response(
            {'error': '대화 삭제 중 오류가 발생했습니다.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response(
        {"success": True},
        status=status.HTTP_204_NO_CONTENT
    )


@csrf_exempt
@require_api_key_secure
def public_story_detail(request, story_uuid):
    """
    공개 Story 상세 API (로그인 불필요)
    - 연결된 LLM 목록도 함께 반환
    """
    try:
        story = Story.objects.get(public_uuid=story_uuid)
    except Story.DoesNotExist:
        return api_response(error="스토리를 찾을 수 없습니다.", status=404)

    # 연결된 LLM 목록 가져오기
    llms = LLM.objects.filter(story=story)  # story에 연결된 LLM들

    llms_data = []
    for llm in llms:
        llms_data.append({
            'id': str(llm.public_uuid),
            'name': llm.name,
            'title': llm.title,
            'description': llm.description,
            'model': llm.model,
            'narrator_voice': llm.narrator_voice.voice_name if llm.narrator_voice else None,
            'voice': llm.voice.voice_name if llm.voice else None,
            'llm_image': request.build_absolute_uri(llm.llm_image.url) if llm.llm_image else None,
            'llm_background_image': request.build_absolute_uri(llm.llm_background_image.url) if llm.llm_background_image else None,
            'first_sentence': llm.first_sentence,
            'language': llm.language,
            'temperature': llm.temperature,
            'stability': llm.stability,
            'speed': llm.speed,
            'style': llm.style,
            'is_public': llm.is_public,
            'created_at': llm.created_at.isoformat() if llm.created_at else None,
            # 필요하면 더 추가 (prompt는 보안상 노출 안 하는 게 좋음)
        })

    # 현재 유저 확인 (좋아요/북마크 상태)
    request_user = _get_request_user(request)
    is_liked = False
    is_bookmarked = False
    if request_user:
        is_liked = StoryLike.objects.filter(user=request_user, story=story).exists()
        is_bookmarked = StoryBookmark.objects.filter(user=request_user, story=story).exists()

    # 댓글 가져오기
    comments_qs = StoryComment.objects.filter(story=story).select_related('user').order_by('-created_at')[:50]
    comments_data = []
    for c in comments_qs:
        comments_data.append({
            'id': c.id,
            'content': c.content,
            'user_name': c.user.nickname or c.user.username,
            'user_profile_image': request.build_absolute_uri(c.user.user_img.url) if c.user.user_img else None,
            'created_at': c.created_at.isoformat(),
            'parent_id': c.parent_comment_id,
        })

    data = {
        'id': str(story.public_uuid),
        'title': story.title,
        'description': story.description,
        'cover_image': request.build_absolute_uri(story.cover_image.url) if story.cover_image else None,
        'story_desc_video': request.build_absolute_uri(story.story_desc_video.url) if story.story_desc_video else None,
        'story_desc_img': request.build_absolute_uri(story.story_desc_img.url) if story.story_desc_img else None,
        'created_at': story.created_at.isoformat(),
        'genres': [{'name': g.name, 'color': getattr(g, 'genres_color', None)} for g in story.genres.all()],
        'tags': [t.name for t in story.tags.all()],
        'adult_choice': story.adult_choice,
        'username': story.user.nickname,
        'llms': llms_data,
        'is_liked': is_liked,
        'is_bookmarked': is_bookmarked,
        'like_count': StoryLike.objects.filter(story=story).count(),
        'comments': comments_data,
    }

    return api_response(data)


from django.views.decorators.csrf import csrf_exempt
from book.api_utils import api_response
from character.models import LLM


def api_response(data=None, error=None, status=200):
    """일관된 API 응답"""
    if error:
        return JsonResponse({'success': False, 'error': error}, status=status)
    return JsonResponse({'success': True, 'data': data}, status=status)


@require_api_key_secure
def public_llm_detail(request, llm_uuid):
    """
    LLM 상세 API + 같은 스토리의 다른 LLM 목록 포함
    - 로그인 없이 접근 가능
    - 무조건 같은 story 내 다른 LLM만 보여줌 (자기 자신 제외)
    - 최신 공개 대화(convId) 포함
    """
    try:
        llm = LLM.objects.select_related('story', 'user', 'voice', 'narrator_voice').get(public_uuid=llm_uuid)
    except LLM.DoesNotExist:
        return api_response(error="LLM을 찾을 수 없습니다.", status=404)

    # 같은 스토리의 다른 LLM들 (자기 자신 제외, 공개된 것만)
    other_llms = []
    if llm.story:
        other_llms = LLM.objects.filter(
            story=llm.story,
        ).exclude(public_uuid=llm_uuid).select_related('user')[:10]  # 최대 10개

    other_llms_data = [
        {
            'id': str(other.public_uuid),
            'name': other.name,
            'title': other.title or '',
            'description': other.description or '',
            'first_sentence': other.first_sentence or '',
            'llm_image': request.build_absolute_uri(other.llm_image.url) if other.llm_image else None,
            'llm_background_image': request.build_absolute_uri(other.llm_background_image.url) if other.llm_background_image else None,
            'is_public': other.is_public,
            'llm_like_count': other.llm_like_count,
            'invest_count': other.invest_count,
            'created_at': other.created_at.isoformat() if other.created_at else None,
        }
        for other in other_llms
    ]

    # 현재 유저의 대화 가져오기 (본인 대화 우선)
    conv_id = None
    request_user = _get_request_user(request)
    is_liked = False
    if request_user:
        user_conv = Conversation.objects.filter(llm=llm, user=request_user).order_by('-created_at').first()
        if user_conv:
            conv_id = user_conv.id
        is_liked = LLMLike.objects.filter(user=request_user, llm=llm).exists()

    # 댓글 가져오기
    comments_qs = Comment.objects.filter(llm=llm).select_related('user').order_by('-created_at')[:50]
    comments_data = []
    for c in comments_qs:
        comments_data.append({
            'id': c.id,
            'content': c.content,
            'user_name': c.user.nickname or c.user.username,
            'user_profile_image': request.build_absolute_uri(c.user.user_img.url) if c.user.user_img else None,
            'created_at': c.created_at.isoformat(),
            'parent_id': c.parent_comment_id,
        })

    # 메인 LLM 데이터
    data = {
        'id': str(llm.public_uuid),
        'name': llm.name,
        'title': llm.title,
        'description': llm.description,
        'prompt': llm.prompt,  # 필요 시 프론트에서 숨기기
        'story': {
            'id': str(llm.story.public_uuid) if llm.story else None,
            'title': llm.story.title if llm.story else None,
        },
        'narrator_voice': {
            'id': llm.narrator_voice.id if llm.narrator_voice else None,
            'name': llm.narrator_voice.voice_name if llm.narrator_voice else None,
        },
        'voice': {
            'id': llm.voice.id if llm.voice else None,
            'name': llm.voice.voice_name if llm.voice else None,
        },
        'created_at': llm.created_at.isoformat() if llm.created_at else None,
        'update_at': llm.update_at.isoformat() if llm.update_at else None,
        'llm_image': request.build_absolute_uri(llm.llm_image.url) if llm.llm_image else None,
        'llm_background_image': request.build_absolute_uri(llm.llm_background_image.url) if llm.llm_background_image else None,
        'response_mp3': llm.response_mp3,
        'model': llm.model,
        'language': llm.language,
        'temperature': llm.temperature,
        'stability': llm.stability,
        'speed': llm.speed,
        'style': llm.style,
        'is_public': llm.is_public,
        'first_sentence': llm.first_sentence,
        'llm_like_count': llm.llm_like_count,
        'invest_count': llm.invest_count,

        # 핵심: 최신 공개 대화 ID
        'conv_id': conv_id,

        # 성인 콘텐츠 여부
        'adult_choice': llm.story.adult_choice if llm.story else False,

        # 같은 스토리의 다른 LLM 목록
        'other_llms': other_llms_data,

        # 유저 상호작용 상태
        'is_liked': is_liked,
        'comments': comments_data,
    }

    return api_response(data)





from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from character.models import Conversation, ConversationMessage, HPImageMapping, LLM
from book.api_utils import api_response, require_api_key_secure  # 기존 데코레이터 사용 (필요 시 제거 가능)
from character.models import LastWard as _LastWard

def _build_last_wards(request, conversation):
    """Conversation의 last_wards 데이터를 빌드 (HP >= 100 시)"""
    try:
        from character.models import ConversationState
        conv_state = ConversationState.objects.get(conversation=conversation)
        current_hp = conv_state.character_stats.get('hp', 0)
        if current_hp >= 100:
            wards = _LastWard.objects.filter(llm=conversation.llm).order_by('order')
            return [
                {
                    'id': w.id,
                    'image_url': request.build_absolute_uri(w.image.url) if w.image else None,
                    'ward': w.ward or '',
                    'description': w.description or '',
                    'order': w.order,
                }
                for w in wards
            ]
    except Exception:
        pass
    return []


@csrf_exempt
@require_api_key_secure
def api_chat_to_audio(request, conv_id):
    """앱용: 기존 생성된 오디오만 병합 → Conversation.merged_audio에 저장"""
    import os
    from uuid import uuid4
    from django.core.files.base import ContentFile
    from django.conf import settings

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST only'}, status=405)

    request_user = _get_request_user(request)
    if not request_user:
        return JsonResponse({'success': False, 'error': '인증 필요'}, status=401)

    conversation = get_object_or_404(Conversation, id=conv_id, user=request_user)

    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        body = {}

    audio_title = (body.get('audio_title') or '').strip()
    bgm_id = body.get('bgm_id', '')

    if not audio_title:
        return JsonResponse({'success': False, 'error': 'audio_title 필요'}, status=400)

    messages_qs = conversation.messages.order_by('created_at')

    from book.utils import merge_audio_files, mix_audio_with_background
    from book.models import BackgroundMusicLibrary

    audio_files = []
    pages_text = []

    for msg in messages_qs:
        if msg.audio and msg.audio.name:
            audio_path = msg.audio.path
            if os.path.exists(audio_path):
                audio_files.append(audio_path)
                pages_text.append(msg.content[:200])

    if not audio_files:
        return JsonResponse({'success': False, 'error': '병합할 오디오가 없습니다.'}, status=400)

    merged_path, timestamps, duration_seconds = merge_audio_files(audio_files, pages_text)
    if not merged_path:
        return JsonResponse({'success': False, 'error': '오디오 병합 실패'}, status=500)

    if bgm_id:
        try:
            bgm_obj = BackgroundMusicLibrary.objects.get(id=int(bgm_id))
            if bgm_obj.audio_file and bgm_obj.audio_file.name:
                bgm_path = bgm_obj.audio_file.path
                if not os.path.exists(bgm_path):
                    print(f"[api_chat_to_audio] BGM 파일 없음 (무시): {bgm_path}")
                else:
                    bg_tracks = [{
                        'audioPath': bgm_path,
                        'startTime': 0,
                        'endTime': int((duration_seconds or 0) * 1000),
                        'volume': -12,
                    }]
                    mixed = mix_audio_with_background(merged_path, bg_tracks)
                    if mixed and mixed != merged_path:
                        merged_path = mixed
        except Exception as e:
            print(f"[api_chat_to_audio] BGM 실패(무시): {e}")

    conversation.merged_audio_title = audio_title
    with open(merged_path, 'rb') as f:
        file_name = f"conv_{conversation.id}_{uuid4().hex[:8]}.mp3"
        conversation.merged_audio.save(file_name, ContentFile(f.read()), save=False)
    conversation.save(update_fields=['merged_audio', 'merged_audio_title'])

    return JsonResponse({
        'success': True,
        'audio_url': request.build_absolute_uri(conversation.merged_audio.url),
        'audio_title': audio_title,
        'message': f'"{audio_title}" 오디오가 생성되었습니다.',
    })


@csrf_exempt
def api_shared_novel(request, conv_id):

# 1. 공개된 Conversation 조회
    conversation = get_object_or_404(
        Conversation.objects.select_related('llm', 'user', 'llm__user'),
        id=conv_id,
        is_public=True
    )

    llm = conversation.llm
    user = conversation.user  # 대화를 공개한 사용자

    # 2. LLM 서브 이미지 전체 (order 순)
    sub_images = LLMSubImage.objects.filter(llm=llm).order_by('order', 'created_at')
    sub_images_data = [
        {
            'id': sub.id,
            'image_url': request.build_absolute_uri(sub.image.url) if sub.image else None,
            'title': sub.title or '',
            'description': sub.description or '',
            'order': sub.order,
            'is_public': sub.is_public,
        }
        for sub in sub_images
    ]

    # 3. LLM 로어북 전체 (LoreEntry) - priority 높은 순
    lore_entries = LoreEntry.objects.filter(llm=llm).order_by('-priority')
    lore_data = [
        {
            'keys': lore.keys,
            'content': lore.content,
            'priority': lore.priority,
            'always_active': lore.always_active,
            'category': lore.category,
        }
        for lore in lore_entries
    ]

    # 4. LLM HP 매핑 전체 (HPImageMapping) - priority + min_hp 순
    hp_mappings = HPImageMapping.objects.filter(llm=llm).select_related('sub_image').order_by('-priority', 'min_hp')
    hp_data = [
        {
            'min_hp': mapping.min_hp,
            'max_hp': mapping.max_hp,
            'extra_condition': mapping.extra_condition or '',
            'sub_image_id': mapping.sub_image.id if mapping.sub_image else None,
            'sub_image_url': request.build_absolute_uri(mapping.sub_image.image.url) if mapping.sub_image and mapping.sub_image.image else None,
            'note': mapping.note or '',
            'priority': mapping.priority,
        }
        for mapping in hp_mappings
    ]

    # 5. 대화 메시지 전체 (시간순)
    messages = ConversationMessage.objects.filter(conversation=conversation).order_by('created_at')
    messages_data = [
        {
            'role': msg.role,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
            'audio_url': request.build_absolute_uri(msg.audio.url) if msg.audio else None,
            'hp_after': msg.hp_after_message,
            'hp_range_min': msg.hp_range_min,
            'hp_range_max': msg.hp_range_max,
        }
        for msg in messages
    ]

    # 최종 응답 데이터
    data = {
        'conversation_id': conv_id,
        'shared_at': conversation.shared_at.isoformat() if conversation.shared_at else conversation.created_at.isoformat(),
        
        # 연결된 LLM 정보
        'llm': {
            'id': str(llm.public_uuid),
            'name': llm.name,
            'description': llm.description or '',
            'first_sentence': llm.first_sentence or '',
            'llm_image': request.build_absolute_uri(llm.llm_image.url) if llm.llm_image else None,
            'llm_background_image': request.build_absolute_uri(llm.llm_background_image.url) if llm.llm_background_image else None,
            'model': llm.model,
            'language': llm.language,
            'is_public': llm.is_public,
        },
        
        # 대화를 공개한 사용자 정보
        'shared_by': {
            'nickname': user.nickname if hasattr(user, 'nickname') else user.username,
            'profile_image': request.build_absolute_uri(user.user_img.url) if hasattr(user, 'user_img') and user.user_img else None,
        },
        
        # 대화 전체 메시지
        'messages': messages_data,
        'message_count': len(messages_data),

        # LLM 추가 데이터 (서브 이미지, 로어북, HP 매핑)
        'sub_images': sub_images_data,
        'lore_entries': lore_data,
        'hp_mappings': hp_data,
        'last_wards': _build_last_wards(request, conversation),
        'merged_audio_url': request.build_absolute_uri(conversation.merged_audio.url) if conversation.merged_audio else None,
        'merged_audio_title': conversation.merged_audio_title or None,
    }

    return api_response(data)




@csrf_exempt
@require_api_key_secure  # 필요 없으면 제거 가능 (공개 목록이니)
def public_shared_llm_conversations(request):

    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    # 공개된 Conversation만 가져오기
    conversations = Conversation.objects.filter(
        is_public=True
    ).select_related(
        'llm',          # LLM 정보
        'user',         # 대화를 공개한 사용자
        'llm__user'     # LLM 만든 사용자 (필요 시)
    ).prefetch_related(
        Prefetch(
            'messages',
            queryset=ConversationMessage.objects.order_by('created_at'),
            to_attr='all_messages'
        )
    ).order_by('-shared_at', '-created_at')  # 최신 공유/생성 순

    result = paginate(conversations, page, per_page)

    conv_data = []
    for conv in result['items']:
        llm = conv.llm
        user = conv.user  # 대화를 공개한 사람

        conv_item = {
            'conversation_id': conv.id,
            'shared_at': conv.shared_at.isoformat() if conv.shared_at else conv.created_at.isoformat(),
            
            # LLM 정보
            'llm': {
                'id': str(llm.public_uuid),
                'name': llm.name,
                'description': llm.description or '',
                'first_sentence': llm.first_sentence or '',
                'llm_image': request.build_absolute_uri(llm.llm_image.url) if llm.llm_image else None,
                'llm_background_image': request.build_absolute_uri(llm.llm_background_image.url) if llm.llm_background_image else None,
            },
            
            # 대화를 공개한 사용자 정보
            'shared_by': {
                'nickname': user.nickname if hasattr(user, 'nickname') else user.username,
                'profile_image': request.build_absolute_uri(user.user_img.url) if hasattr(user, 'user_img') and user.user_img else None,
            },
            
            # 전체 메시지 (role, content, created_at 등)
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

        conv_data.append(conv_item)

    return api_response({
        'shared_conversations': conv_data,
        'pagination': result['pagination']
    })





from character.models import LastWard

def api_response(data, status=200):
    return JsonResponse({'success': True, 'data': data}, status=status)

def api_error(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)

@csrf_exempt
def api_novel_result(request, conv_id):
    """
    GET  : 대화 상세 조회
    POST : 공개 / 비공개 토글
    """

    conversation = get_object_or_404(
        Conversation.objects.select_related("llm", "user"),
        id=conv_id
    )

    llm = conversation.llm
    owner = conversation.user

    # =====================================================
    # POST : 공개 / 비공개 토글
    # =====================================================
    if request.method == "POST":

        authorized = False
        request_user = _get_request_user(request)

        # 웹 또는 앱 사용자 (본인 확인)
        if request_user and request_user == owner:
            authorized = True

        if not authorized:
            return api_error("권한이 없습니다.", status=403)

        # JSON body
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = {}

        share_choice = body.get("share_choice") is True

        conversation.is_public = share_choice
        conversation.shared_at = timezone.now() if share_choice else None
        conversation.save()

        return api_response({
            "conversationId": conv_id,
            "isPublic": conversation.is_public,
            "sharedAt": conversation.shared_at.isoformat() if conversation.shared_at else None
        })

    # =====================================================
    # GET : 대화 조회
    # =====================================================

    # 비공개 대화 접근 제한 (본인만 접근 가능)
    if not conversation.is_public:
        request_user = _get_request_user(request)

        # owner가 None인 경우 (익명 대화) - 누구나 접근 가능
        if owner is None:
            pass  # allow
        elif request_user is None:
            api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
            if api_key:
                print(f"[api_novel_result] API key 있지만 인증 실패 (conv_id={conv_id})")
                return api_error("API 키가 유효하지 않습니다. 앱을 재로그인 해주세요.", status=401)
            return api_error("로그인이 필요합니다.", status=401)
        elif request_user != owner:
            print(f"[api_novel_result] 소유자 불일치: request_user={request_user.pk}, owner={owner.pk}, conv_id={conv_id}")
            return api_error("이 대화에 접근 권한이 없습니다.", status=403)
        # else: request_user == owner → OK

    # -------------------------
    # 서브 이미지
    # -------------------------
    sub_images = LLMSubImage.objects.filter(llm=llm).order_by("order", "created_at")
    sub_images_data = [
        {
            "id": img.id,
            "title": img.title or "",
            "description": img.description or "",
            "imageUrl": request.build_absolute_uri(img.image.url) if img.image else None,
            "order": img.order,
            "isPublic": img.is_public,
        }
        for img in sub_images
    ]

    # -------------------------
    # 로어북
    # -------------------------
    lore_entries = LoreEntry.objects.filter(llm=llm).order_by("-priority")
    lore_data = [
        {
            "keys": lore.keys,
            "content": lore.content,
            "priority": lore.priority,
        }
        for lore in lore_entries
    ]

    # -------------------------
    # HP 매핑
    # -------------------------
    hp_mappings = HPImageMapping.objects.filter(llm=llm).select_related("sub_image")
    hp_data = [
        {
            "minHp": hp.min_hp,
            "maxHp": hp.max_hp,
            "subImageUrl": (
                request.build_absolute_uri(hp.sub_image.image.url)
                if hp.sub_image and hp.sub_image.image else None
            ),
        }
        for hp in hp_mappings
    ]

    # -------------------------
    # 메시지
    # -------------------------
    messages = ConversationMessage.objects.filter(
        conversation=conversation
    ).order_by("created_at")

    messages_data = [
        {
            "role": msg.role,
            "speaker": llm.name if msg.role == "assistant" else "너",
            "content": msg.content,
            "createdAt": msg.created_at.isoformat(),
            "audio": request.build_absolute_uri(msg.audio.url) if msg.audio else None,
            "hpAfter": msg.hp_after_message,
            "hpRangeMin": msg.hp_range_min,
            "hpRangeMax": msg.hp_range_max,
        }
        for msg in messages
    ]

    # -------------------------
    # 마지막 말 (Last Ward)
    # -------------------------
    last_wards_data = []
    try:
        conv_state = ConversationState.objects.get(conversation=conversation)
        current_hp = conv_state.character_stats.get('hp', 0)

        if current_hp >= 100:
            last_wards = LastWard.objects.filter(llm=conversation.llm).order_by('order')
            last_wards_data = [
                {
                    "id": ward.id,
                    "imageUrl": request.build_absolute_uri(ward.image.url) if ward.image else None,
                    "ward": ward.ward or "",
                    "description": ward.description or "",
                    "order": ward.order,
                    "isPublic": ward.is_public,
                }
                for ward in last_wards
            ]
    except ConversationState.DoesNotExist:
        pass

    # -------------------------
    # 최종 응답
    # -------------------------
    data = {
        "conversationId": conv_id,
        "sharedAt": conversation.shared_at.isoformat()
        if conversation.shared_at else conversation.created_at.isoformat(),
        "isPublic": conversation.is_public,

        "llm": {
            "id": str(llm.public_uuid),
            "name": llm.name,
            "description": llm.description or "",
            "firstSentence": llm.first_sentence or "",
            "llmImage": request.build_absolute_uri(llm.llm_image.url)
            if llm.llm_image else None,
            "llmBackgroundImage": request.build_absolute_uri(llm.llm_background_image.url)
            if llm.llm_background_image else None,
            "model": llm.model,
            "language": llm.language,
            "isPublic": llm.is_public,
        },

        "sharedBy": {
            "nickname": (owner.nickname if hasattr(owner, "nickname") else owner.username) if owner else "익명",
            "profileImage": (request.build_absolute_uri(owner.user_img.url)
            if hasattr(owner, "user_img") and owner.user_img else None) if owner else None,
        },

        "messages": messages_data,
        "messageCount": len(messages_data),
        "subImages": sub_images_data,
        "loreEntries": lore_data,
        "hpMappings": hp_data,
        "lastWards": last_wards_data,
        "mergedAudioUrl": request.build_absolute_uri(conversation.merged_audio.url) if conversation.merged_audio else None,
        "mergedAudioTitle": conversation.merged_audio_title or None,
    }

    return api_response(data)



def api_chat_view(request, llm_uuid):
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)
    conversation_id = request.GET.get('conversation_id')

    # API key 또는 세션에서 유저 식별
    user = _get_request_user(request)

    if user:
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, llm=llm, user=user)
            except Conversation.DoesNotExist:
                conversation, _ = Conversation.objects.get_or_create(user=user, llm=llm)
        else:
            conversation, _ = Conversation.objects.get_or_create(user=user, llm=llm)
    else:
        if not conversation_id:
            return JsonResponse({'success': False, 'error': '비로그인 사용자는 conversation_id가 필요합니다.'}, status=403)
        try:
            conversation = Conversation.objects.get(id=conversation_id, llm=llm, user=None)
        except Conversation.DoesNotExist:
            return JsonResponse({'success': False, 'error': '유효하지 않은 conversation_id입니다.'}, status=404)

    conv_state, _ = ConversationState.objects.get_or_create(
        conversation=conversation,
        defaults={'character_stats': {'hp': 0, 'max_hp': 100}}
    )

    lore_entries = llm.lore_entries.all().order_by('-priority')

    lorebook_data = [
        {
            'id': lore.id,
            'keys': lore.keys,
            'category': lore.category,
            'priority': lore.priority,
            'always_active': lore.always_active,
        }
        for lore in lore_entries
    ]

    current_hp = conv_state.character_stats.get('hp', 100)
    max_hp = conv_state.character_stats.get('max_hp', 100)

    messages = conversation.messages.order_by('created_at')[:50]

    # 서브 이미지
    sub_images_data = []
    for sub in llm.sub_images.all():
        hp_mapping = HPImageMapping.objects.filter(sub_image=sub).first()
        sub_images_data.append({
            'image_url': request.build_absolute_uri(sub.image.url) if sub.image else '',
            'min_hp': hp_mapping.min_hp if hp_mapping and hp_mapping.min_hp is not None else 0,
            'max_hp': hp_mapping.max_hp if hp_mapping and hp_mapping.max_hp is not None else 100,
            'title': sub.title or '',
        })

    # ✅✅✅ UserLastWard 처리 추가 ✅✅✅
    last_ward_is_public = False
    conversation_has = False
    
    if user:
        # UserLastWard 가져오기 (없으면 생성)
        user_last_wards = UserLastWard.objects.filter(
            user=user,
            last_ward__llm=llm
        )
        
        if not user_last_wards.exists():
            # LastWard가 있으면 UserLastWard 생성
            for ward in llm.last_ward.all():
                UserLastWard.objects.create(
                    user=user,
                    last_ward=ward,
                    is_public=False
                )
            user_last_wards = UserLastWard.objects.filter(
                user=user,
                last_ward__llm=llm
            )
        
        # ✅ HP가 max_hp 이상이면 자동 공개
        if current_hp >= max_hp and user_last_wards.filter(is_public=False).exists():
            updated_count = user_last_wards.filter(is_public=False).update(is_public=True)
            print(f"✅ [api_chat_view] HP {current_hp}/{max_hp} 도달, UserLastWard {updated_count}개 공개 처리")
        
        # last_ward_is_public 계산 (모든 UserLastWard가 공개되었는지)
        last_ward_is_public = not user_last_wards.filter(is_public=False).exists()
        
        # conversation_has 계산
        conversation_has = ConversationMessage.objects.filter(
            conversation__llm=llm,
            conversation__user=user
        ).exists()
        
        print(f"🔍 [api_chat_view] last_ward_is_public: {last_ward_is_public}")
        print(f"🔍 [api_chat_view] conversation_has: {conversation_has}")
        print(f"🔍 [api_chat_view] current_hp: {current_hp}/{max_hp}")

    # ★ last_wards 데이터 (기존 유지)
    last_wards_qs = llm.last_ward.all()
    last_wards_data = [
        {
            'id': lw.id,
            'image_url': request.build_absolute_uri(lw.image.url) if lw.image else None,
            'ward': lw.ward or '',
            'description': lw.description or '',
            'order': lw.order,
            'created_at': lw.created_at.isoformat() if lw.created_at else None,
            'is_public': lw.is_public,  # LastWard 모델의 is_public (참고용)
        }
        for lw in last_wards_qs
    ]

    data = {
        'success': True,
        'llm': {
            'uuid': str(llm.public_uuid),
            'name': llm.name,
            'description': llm.description or '',
            'first_sentence': llm.first_sentence or '',
            'llm_image': request.build_absolute_uri(llm.llm_image.url) if llm.llm_image else None,
        },
        'conversation_id': conversation.id,
        'current_hp': current_hp,
        'max_hp': max_hp,
        'messages': [
            {
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'audio_url': request.build_absolute_uri(msg.audio.url) if msg.audio else None,
                'created_at': msg.created_at.isoformat(),
            } for msg in messages
        ],
        'sub_images': sub_images_data,
        'lorebook': lorebook_data,
        'last_wards': last_wards_data,
        # ✅✅✅ 추가 필드 ✅✅✅
        'last_ward_is_public': last_ward_is_public,
        'conversation_has': conversation_has,
    }

    return JsonResponse(data)


@require_api_key_secure
@api_view(['GET', 'POST'])
def api_last_ward(request, llm_uuid):

    request_user = _get_request_user(request)
    if not request_user:
        return Response({"error": "인증 실패"}, status=401)

    llm = get_object_or_404(LLM, public_uuid=llm_uuid)

    # UserLastWard 가져오기
    user_last_wards = UserLastWard.objects.filter(
        user=request_user,
        last_ward__llm=llm
    )

    # 없으면 생성
    if not user_last_wards.exists():
        for ward in llm.last_ward.all():
            UserLastWard.objects.create(
                user=request_user,
                last_ward=ward,
                is_public=False
            )
        user_last_wards = UserLastWard.objects.filter(
            user=request_user,
            last_ward__llm=llm
        )

    # ---------------------------
    # POST: 이어서 대화하기
    # ---------------------------
    if request.method == 'POST':
        try:
            data = request.data
            if data.get('action') == 'continue_chat':
                user_last_wards.filter(is_public=False).update(is_public=True)
                return Response({'success': True}, status=200)
            return Response({'error': 'Invalid action'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ---------------------------
    # GET 처리
    # ---------------------------

    # 공개 여부 판단
    last_ward_is_public = not user_last_wards.filter(is_public=False).exists()

    # 실제 ward 데이터 정렬 (웹과 동일)
    last_wards_qs = user_last_wards.select_related(
        'last_ward'
    ).order_by(
        'last_ward__order',
        'last_ward__created_at'
    )

    last_ward_data = [
        {
            'id': ulw.last_ward.id,
            'image_url': request.build_absolute_uri(
                ulw.last_ward.image.url
            ) if ulw.last_ward.image else None,
            'ward': ulw.last_ward.ward or '',
            'description': ulw.last_ward.description or '',
            'order': ulw.last_ward.order,
            'created_at': ulw.last_ward.created_at.isoformat()
            if ulw.last_ward.created_at else None,
            'is_public': ulw.is_public,
        }
        for ulw in last_wards_qs
    ]

    # Conversation 존재 여부
    conversation_has = ConversationMessage.objects.filter(
        conversation__llm=llm,
        conversation__user=request_user
    ).exists()

    try:
        conv = Conversation.objects.get(
            llm=llm,
            user=request_user
        )
        conv_id = conv.id
    except Conversation.DoesNotExist:
        conv_id = None
    story_id = None
    if llm.story:
        story_id = llm.story.public_uuid
    elif hasattr(llm, 'ai_story') and llm.ai_story:  # 만약 관계 이름이 다르다면
        story_id = llm.ai_story.public_uuid
    return Response({
        "success": True,
        "conversation_id": conv_id,
        "conversation_has": conversation_has,
        "last_ward_is_public": last_ward_is_public,
        "last_wards": last_ward_data,
        "story_id": story_id,
    })


# ==================== 비로그인 채팅 API ====================

from character.utils import generate_response_grok, generate_response_gpt, parse_hp_from_response

@csrf_exempt
@api_view(['POST'])
def api_chat_send(request, llm_uuid):
    """
    채팅 메시지 전송 API (로그인 불필요)
    - conversation_id가 없으면 새 대화 생성
    - conversation_id가 있으면 기존 대화에 메시지 추가
    """
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)
    print("🔥 api_chat_send HIT")

    # API key 또는 세션에서 유저 식별
    user = _get_request_user(request)

    try:
        data = json.loads(request.body)
        user_text = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')

        if not user_text:
            return JsonResponse({'success': False, 'error': '메시지를 입력해주세요.'}, status=400)

        # 대화 가져오기 또는 생성
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, llm=llm)
            except Conversation.DoesNotExist:
                # conversation_id가 유효하지 않으면 새로 생성
                conversation = Conversation.objects.create(
                    user=user,
                    llm=llm,
                    created_at=timezone.now()
                )
        else:
            if user:
                # 로그인 유저: 기존 대화 가져오기 또는 새로 생성
                conversation, _ = Conversation.objects.get_or_create(
                    user=user,
                    llm=llm,
                    defaults={'created_at': timezone.now()}
                )
            else:
                # 비로그인: 새 대화 생성
                conversation = Conversation.objects.create(
                    user=None,
                    llm=llm,
                    created_at=timezone.now()
                )

        # 대화 기록 가져오기 (최근 10개)
        chat_history = list(conversation.messages.order_by('-created_at')[:10].values('role', 'content'))
        chat_history.reverse()

        # ConversationState에서 현재 HP 가져오기
        conv_state, _ = ConversationState.objects.get_or_create(
            conversation=conversation,
            defaults={'character_stats': {'hp': 0, 'max_hp': 100}}
        )
        current_hp = conv_state.character_stats.get('hp', 0)
        max_hp = conv_state.character_stats.get('max_hp', 100)

        # 응답 생성
        if "grok" in llm.model.lower():
            raw_response = generate_response_grok(llm, chat_history, user_text, current_hp, max_hp)
        else:
            raw_response = generate_response_gpt(llm, chat_history, user_text, current_hp, max_hp)

        # HP 변경 파싱 및 처리
        clean_response, hp_change = parse_hp_from_response(raw_response)

        new_hp = current_hp
        if hp_change:
            hp_change_str = hp_change.strip()
            if hp_change_str.startswith('+'):
                new_hp = min(current_hp + int(hp_change_str[1:]), max_hp)
            elif hp_change_str.startswith('-'):
                new_hp = max(current_hp - int(hp_change_str[1:]), 0)
            else:
                new_hp = max(0, min(int(hp_change_str), max_hp))

            conv_state.character_stats['hp'] = new_hp
            conv_state.save()
            current_hp = new_hp



        if user and current_hp >= max_hp:
            user_last_wards = UserLastWard.objects.filter(
                user=user,
                last_ward__llm=llm,
                is_public=False
            )
            
            if user_last_wards.exists():
                updated_count = user_last_wards.update(is_public=True)
                print(f"✅ [api_chat_send] HP {current_hp}/{max_hp} 도달, UserLastWard {updated_count}개 공개")
        # HP 구간 매핑 찾기
        hp_mapping = None
        for mapping in HPImageMapping.objects.filter(llm=llm).order_by('min_hp'):
            min_hp_val = mapping.min_hp if mapping.min_hp is not None else 0
            max_hp_val = mapping.max_hp if mapping.max_hp is not None else 100
            if min_hp_val <= current_hp <= max_hp_val:
                hp_mapping = mapping
                break

        # 대화 기록 저장
        ConversationMessage.objects.create(
            conversation=conversation,
            role='user',
            content=user_text,
            created_at=timezone.now(),
            hp_after_message=current_hp,
            hp_range_min=hp_mapping.min_hp if hp_mapping else None,
            hp_range_max=hp_mapping.max_hp if hp_mapping else None,
        )

        ai_message = ConversationMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=clean_response,
            created_at=timezone.now(),
            hp_after_message=current_hp,
            hp_range_min=hp_mapping.min_hp if hp_mapping else None,
            hp_range_max=hp_mapping.max_hp if hp_mapping else None,
        )

        return JsonResponse({
            'success': True,
            'text': clean_response,
            'message_id': ai_message.id,
            'conversation_id': conversation.id,
            'hp': current_hp,
            'max_hp': max_hp,
        })

    except Exception as e:
        import traceback
        print(f"채팅 API 오류: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': '서버 오류가 발생했습니다.'}, status=500)


@csrf_exempt
@api_view(['POST'])
def api_chat_reset(request, llm_uuid):
    """
    대화 초기화 API (새 대화 시작)
    - 기존 conversation_id가 있어도 새 대화 생성
    """
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)

    # API key 또는 세션에서 유저 식별
    user = _get_request_user(request)

    # 새 대화 생성
    conversation = Conversation.objects.create(
        user=user,
        llm=llm,
        created_at=timezone.now()
    )

    # 초기 HP 상태 생성
    ConversationState.objects.create(
        conversation=conversation,
        character_stats={'hp': 0, 'max_hp': 100}
    )

    return JsonResponse({
        'success': True,
        'conversation_id': conversation.id,
        'hp': 100,
        'max_hp': 100,
    })



