from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Max, Q
from django.views.decorators.csrf import csrf_exempt
from character.models import LLM, Story, CharacterMemory, Conversation, ConversationMessage, ConversationState, HPImageMapping, LLMSubImage, LoreEntry, LLMPrompt, StoryLike, StoryComment, StoryBookmark,  Prompt,  Comment, LLMLike
from book.api_utils import require_api_key, paginate, api_response, require_api_key_secure
from rest_framework.decorators import api_view
import json
from django.utils import timezone
from django.conf import settings

from django.db.models import Prefetch
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Story

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
            'genres': [g.name for g in story.genres.all()],
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

    data = {
        'id': str(story.public_uuid),
        'title': story.title,
        'description': story.description,
        'cover_image': request.build_absolute_uri(story.cover_image.url) if story.cover_image else None,
        'story_desc_video': request.build_absolute_uri(story.story_desc_video.url) if story.story_desc_video else None,
        'story_desc_img': request.build_absolute_uri(story.story_desc_img.url) if story.story_desc_img else None,
        'created_at': story.created_at.isoformat(),
        'genres': [g.name for g in story.genres.all()],
        'tags': [t.name for t in story.tags.all()],
        'adult_choice': story.adult_choice,
        'username': story.user.nickname,          # 추가 추천
        'llms': llms_data,                        # ← 여기! LLM 배열 추가
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

    # 최신 공개 대화(conversation) 가져오기
    latest_shared = Conversation.objects.filter(llm=llm, is_public=True).order_by('-shared_at').first()
    conv_id = latest_shared.id if latest_shared else None

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

        # 같은 스토리의 다른 LLM 목록
        'other_llms': other_llms_data,
    }

    return api_response(data)





from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from character.models import Conversation, ConversationMessage, HPImageMapping, LLM
from book.api_utils import api_response, require_api_key_secure  # 기존 데코레이터 사용 (필요 시 제거 가능)

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

        # 1️⃣ 웹 로그인 사용자 (본인)
        if request.user.is_authenticated and request.user == owner:
            authorized = True

        # 2️⃣ 앱 요청 (API KEY)
        api_key = request.GET.get("api_key") or request.headers.get("X-API-Key")
        if api_key == settings.API_KEY:
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

    # 비공개 대화 접근 제한 (API 키 또는 본인만 접근 가능)
    if not conversation.is_public:
        authorized = False

        # 1️⃣ 웹 로그인 사용자 (본인)
        if request.user.is_authenticated and request.user == owner:
            authorized = True

        # 2️⃣ 앱 요청 (API KEY)
        api_key = request.GET.get("api_key") or request.headers.get("X-API-Key")
        if api_key == settings.API_KEY:
            authorized = True

        # 3️⃣ owner가 None인 경우 (익명 대화) - 누구나 접근 가능
        if owner is None:
            authorized = True

        if not authorized:
            return api_error("권한이 없습니다.", status=403)

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
    }

    return api_response(data)




@api_view(['GET'])
def api_chat_view(request, llm_uuid):
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)

    # conversation_id 파라미터로 기존 대화 가져오기
    conversation_id = request.GET.get('conversation_id')

    if conversation_id:
        # conversation_id가 있으면 해당 대화 가져오기
        try:
            conversation = Conversation.objects.get(id=conversation_id, llm=llm)
        except Conversation.DoesNotExist:
            # 없으면 새로 생성
            conversation = Conversation.objects.create(
                user=request.user if request.user.is_authenticated else None,
                llm=llm,
                created_at=timezone.now()
            )
    elif request.user.is_authenticated:
        # 로그인 사용자는 기존 대화 가져오기
        conversation, _ = ConversationMessage.objects.get_or_create(
            user=request.user,
            llm=llm,
        )
    else:
        # 비로그인 + conversation_id 없으면 새 대화 생성
        conversation = Conversation.objects.create(
            user=None,
            llm=llm,
            created_at=timezone.now()
        )

    # 나머지 로직 그대로...
    conv_state, _ = ConversationState.objects.get_or_create(
        conversation=conversation,
        defaults={'character_stats': {'hp': 100, 'max_hp': 100}}
    )
    
    current_hp = conv_state.character_stats.get('hp', 0)
    max_hp = conv_state.character_stats.get('max_hp', 100)

    messages = conversation.messages.order_by('created_at')[:50]

    sub_images_data = []
    for sub in llm.sub_images.all():
        hp_mapping = HPImageMapping.objects.filter(sub_image=sub).first()
        sub_images_data.append({
            'image_url': request.build_absolute_uri(sub.image.url) if sub.image else '',
            'min_hp': hp_mapping.min_hp if hp_mapping and hp_mapping.min_hp is not None else 0,
            'max_hp': hp_mapping.max_hp if hp_mapping and hp_mapping.max_hp is not None else 100,
            'title': sub.title or '',
        })

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
            } for msg in messages
        ],
        'sub_images': sub_images_data,
    }

    return JsonResponse(data)


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
                    user=None,
                    llm=llm,
                    created_at=timezone.now()
                )
        else:
            # 새 대화 생성
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
            defaults={'character_stats': {'hp': 100, 'max_hp': 100}}
        )
        current_hp = conv_state.character_stats.get('hp', 100)
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

    # 새 대화 생성
    conversation = Conversation.objects.create(
        user=None,
        llm=llm,
        created_at=timezone.now()
    )

    # 초기 HP 상태 생성
    ConversationState.objects.create(
        conversation=conversation,
        character_stats={'hp': 100, 'max_hp': 100}
    )

    return JsonResponse({
        'success': True,
        'conversation_id': conversation.id,
        'hp': 100,
        'max_hp': 100,
    })

