from django.shortcuts import render,redirect,get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import requests
import json
import base64
from django.views.decorators.csrf import csrf_exempt
import os
from django.utils import timezone
from uuid import uuid4
from django.conf import settings
from main.models import SnapBtn, Advertisment, Event
from book.models import Books,ReadingProgress, BookSnap, Content, Poem_list, BookTag, Tags, BookSnippet, VoiceList, VoiceType, Genres, Tags
from book.service.recommendation import recommend_books
from character.models import LLM, LLMPrompt, Prompt, LLMSubImage, Conversation, ConversationState, CharacterMemory, LoreEntry ,HPImageMapping, Story, ConversationMessage, Comment, LLMLike, StoryComment, StoryLike, StoryBookmark
from django.core.files.base import ContentFile
from PIL import Image
import io
from character.utils import generate_response_grok,generate_response_gpt,split_narration_dialogue,narrate_audio,character_audio,merge_audio,parse_hp_from_response,generate_sequential_tts
import logging
import traceback
from register.decorator import login_required_to_main
from register.models import Users


def _get_auth_user(request):
    """API key 또는 세션에서 유저를 가져옴 (앱/웹 공통)"""
    api_key = request.GET.get('api_key') or request.headers.get('X-API-Key')
    if api_key:
        try:
            from book.models import APIKey
            return APIKey.objects.select_related('user').get(key=api_key, is_active=True).user
        except Exception:
            pass
    if hasattr(request, 'user') and request.user.is_authenticated:
        return request.user
    return None


@login_required_to_main
def character_terms(request):
    return render(request, "character/termsAI.html")


@login_required_to_main
def make_ai_story(request, story_uuid=None):
    """
    스토리 생성 / 편집
    """
    voice_list = VoiceList.objects.filter(types__name="나레이션")
    genre_list = Genres.objects.all()
    tag_list = Tags.objects.all()

    story = None
    llm = None

    # 초기값
    initial_voice_id = None
    initial_genres = []
    initial_tags = []

    if story_uuid:
        story = get_object_or_404(Story, public_uuid=story_uuid)
        llm = story.characters.first()
        if llm and llm.narrator_voice:
            initial_voice_id = llm.narrator_voice.voice_id
        initial_genres = list(story.genres.values_list('id', flat=True))
        initial_tags = list(story.tags.values_list('id', flat=True))

    if request.method == "POST":
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        cover_image = request.FILES.get('cover_image')
        genres = request.POST.getlist('genres')
        tags = request.POST.getlist('tags')
        voice_id = request.POST.get('voice_id')
        is_adult = request.POST.get("adult_choice") == "on"
        media_file = request.FILES.get("cover_media")
        desc_img = request.FILES.get("desc_img")
        print(f"[DEBUG] is_adult 값: {is_adult}")      

        if not title:
            return JsonResponse({"error": "스토리 제목을 입력해주세요."}, status=400)

        # 생성 vs 편집
        if story is None:
            story = Story.objects.create(user=request.user, title=title, description=description, adult_choice = is_adult)
            llm = LLM.objects.create(user=request.user, story=story)
        else:
            story.title = title
            story.description = description
            story.adult_choice = is_adult




        # Cover Image
        if cover_image:
            try:
                ext = cover_image.name.split('.')[-1]
                safe_name = f"cover_{story.id}.{ext}"
                story.cover_image.save(safe_name, cover_image)
            except Exception as e:
                print("이미지 저장 실패:", e)

        # 장르 & 태그
        if genres:
            genre_ids = [int(g) for g in genres if g.strip().isdigit()]
            story.genres.set(Genres.objects.filter(id__in=genre_ids))
        if tags:
            tag_ids = [int(t) for t in tags if t.strip().isdigit()]
            story.tags.set(Tags.objects.filter(id__in=tag_ids))

        # 나레이터 Voice 업데이트
        if voice_id and llm:
            narrator_voice = VoiceList.objects.filter(voice_id=voice_id).first()
            if narrator_voice:
                llm.narrator_voice = narrator_voice
                llm.save()

        if desc_img:
            try:
                ext = desc_img.name.split('.')[-1]
                safe_name = f"cover_{story.id}.{ext}"
                story.story_desc_img.save(safe_name, desc_img)
            except Exception as e:
                print("이미지 저장 실패:", e)


        if media_file:
            file_type = media_file.content_type
            if 'image' in file_type:
                story.cover_image = media_file
            elif 'video' in file_type:
                story.story_desc_video = media_file
                print("media_file 성공:", media_file)


        story.save()
        return redirect('character:story_detail', story_uuid=story.public_uuid)

    # GET: 초기값 전달
    context = {
        "story": story,
        "story_uuid": story_uuid,
        "llm": llm,
        "voice_list": voice_list,
        "genre_list": genre_list,
        "tag_list": tag_list,
        "initial_voice_id": initial_voice_id,
        "initial_genres": initial_genres,
        "initial_tags": initial_tags,
    }
    return render(request, "character/make_ai_story.html", context)



def story_detail(request, story_uuid):
    story = get_object_or_404(Story, public_uuid=story_uuid, user=request.user)
    characters = story.characters.all().order_by('created_at')
    story_list = Story.objects.filter(public_uuid=story_uuid)

    if request.method == 'POST' and request.POST.get('action') == 'publish':
        # 출시 버튼 눌렀을 때만 처리
        if not characters.exists():
            return JsonResponse({"error": "최소 1개 이상의 캐릭터가 필요합니다."}, status=400)

        story.is_public = True
        story.save()

        return redirect('/')
    # GET 요청: 그냥 페이지 보여주기


    context = {
        'story': story,
        'characters': characters,
        'can_publish': characters.exists(),
        "story_list":story_list
    }
    return render(request, 'character/story_detail.html', context)

# AI 채팅 설정
@login_required_to_main
def make_ai(request, story_uuid):
    # 1. 스토리 필수로 가져오기 (없으면 404)
    story = get_object_or_404(Story, public_uuid=story_uuid, user=request.user)

    # 2. 선택지 데이터 로드
    voice_list = VoiceList.objects.prefetch_related('types').all()
    voice_types = VoiceType.objects.all()
    genre_list = Genres.objects.all()
    tag_list = Tags.objects.all()

    if request.method == "POST":
        # 필수 입력값
        ai_name = request.POST.get('ai_name')
        prompt = request.POST.get('prompt')
        language = request.POST.get('language', 'ko')
        voice_id = request.POST.get('voice_id')
        model = request.POST.get('model', 'gpt-4o-mini')
        first_sentence = request.POST.get('first_sentence', '')
        description = request.POST.get('description', '')  # distribute → description

        # 필수 검증
        if not ai_name:
            return JsonResponse({"error": "AI 이름을 입력해주세요."}, status=400)
        if not prompt:
            return JsonResponse({"error": "프롬프트를 입력해주세요."}, status=400)

        # LLM 생성
        llm = LLM.objects.create(
            user=request.user,
            name=ai_name,
            prompt=prompt,
            first_sentence=first_sentence,
            language=language,
            model=model,
            description=description,
            voice=VoiceList.objects.filter(voice_id=voice_id).first(),
            narrator_voice=VoiceList.objects.filter(voice_id=request.POST.get('narrator_voice_id')).first(),
            story=story,
        )

        # 프로필 이미지 처리
        llm_image = request.FILES.get('llm_image') or request.FILES.get('user_image')
        if llm_image:
            try:
                img = Image.open(llm_image).convert("RGB")
                webp_io = io.BytesIO()
                img.save(webp_io, format='WEBP', quality=85)
                webp_content = webp_io.getvalue()
                webp_name = f"{ai_name}_{llm.id}.webp"
                llm.llm_image.save(webp_name, ContentFile(webp_content))
            except Exception as e:
                logging.warning(f"이미지 저장 실패: {e}")

        # 장르 & 태그
        genres = request.POST.getlist('genres')
        tags = request.POST.getlist('tags')
        if genres:
            try:
                genre_ids = [int(g) for g in genres if g.strip().isdigit()]
                llm.genres.set(Genres.objects.filter(id__in=genre_ids))
            except ValueError:
                logging.warning("장르 ID 변환 실패")
        if tags:
            try:
                tag_ids = [int(t) for t in tags if t.strip().isdigit()]
                llm.tags.set(Tags.objects.filter(id__in=tag_ids))
            except ValueError:
                logging.warning("태그 ID 변환 실패")

        # 로어북 여러 개 저장
        lore_keys = request.POST.getlist('lore_keys[]')
        lore_contents = request.POST.getlist('lore_content[]')
        lore_priorities = request.POST.getlist('lore_priority[]')
        lore_always = request.POST.getlist('lore_always_active[]')
        lore_categories = request.POST.getlist('lore_category[]')

        for i in range(len(lore_keys)):
            key = lore_keys[i].strip()
            content = lore_contents[i].strip()
            if key and content:
                LoreEntry.objects.create(
                    llm=llm,
                    keys=key,
                    content=content,
                    priority=int(lore_priorities[i]) if i < len(lore_priorities) and lore_priorities[i] else 0,
                    always_active=bool(lore_always[i]) if i < len(lore_always) else False,
                    category=lore_categories[i] if i < len(lore_categories) else '',
                )

        # 서브 이미지 + HP 매핑 여러 개 저장
        sub_images = request.FILES.getlist('sub_images')
        min_hps = request.POST.getlist('min_hp[]')
        max_hps = request.POST.getlist('max_hp[]')
        sub_titles = request.POST.getlist('sub_image_title[]')

        for i, img in enumerate(sub_images):
            if img:
                sub_img = LLMSubImage.objects.create(
                    llm=llm,
                    image=img,
                    title=sub_titles[i] if i < len(sub_titles) else f"서브 {i+1}",
                )

                # HP 매핑
                min_hp = min_hps[i] if i < len(min_hps) else None
                max_hp = max_hps[i] if i < len(max_hps) else None
                if min_hp or max_hp:
                    HPImageMapping.objects.create(
                        llm=llm,
                        sub_image=sub_img,
                        min_hp=int(min_hp) if min_hp and min_hp.strip().isdigit() else None,
                        max_hp=int(max_hp) if max_hp and max_hp.strip().isdigit() else None,
                    )

        llm.save()

        # 성공 시 스토리 상세 페이지로 리다이렉트
        return redirect('character:story_detail', story_uuid=story.public_uuid)


    # GET: 폼 렌더링
    context = {
        "voice_list": voice_list,
        "voice_types": voice_types,
        "genre_list": genre_list,
        "tag_list": tag_list,
        "story": story,
        "story_uuid": story.public_uuid,
        "is_edit_mode": False,
    }
    return render(request, "character/make_ai.html", context)


@login_required_to_main
def make_ai_update(request, llm_uuid):
    """
    AI 캐릭터 편집 뷰 (make_ai.html 템플릿 재사용)
    """
    llm = get_object_or_404(LLM, public_uuid=llm_uuid, user=request.user)
    voice_list = VoiceList.objects.prefetch_related('types').all()
    voice_types = VoiceType.objects.all()
    genre_list = Genres.objects.all()
    tag_list = Tags.objects.all()

    if request.method == "POST":
        # 폼 데이터 받기
        ai_name = request.POST.get('ai_name')
        prompt = request.POST.get('prompt')
        language = request.POST.get('language', llm.language)
        voice_id = request.POST.get('voice_id')
        model = request.POST.get('model', llm.model)
        first_sentence = request.POST.get('first_sentence', llm.first_sentence)
        description = request.POST.get('description', llm.description)  # Fixed: distribute → description
        narrator_voice_id = request.POST.get('narrator_voice_id')

        # 필수값 검증
        if not ai_name:
            return JsonResponse({"error": "AI 이름을 입력해주세요."}, status=400)
        if not prompt:
            return JsonResponse({"error": "프롬프트를 입력해주세요."}, status=400)

        # LLM 필드 업데이트
        llm.name = ai_name
        llm.prompt = prompt
        llm.language = language
        llm.model = model
        llm.first_sentence = first_sentence
        llm.description = description

        # 목소리 업데이트
        if voice_id and voice_id.strip():
            voice_obj = VoiceList.objects.filter(voice_id=voice_id.strip()).first()
            if voice_obj:
                llm.voice = voice_obj
        if narrator_voice_id and narrator_voice_id.strip():
            narrator_obj = VoiceList.objects.filter(voice_id=narrator_voice_id.strip()).first()
            if narrator_obj:
                llm.narrator_voice = narrator_obj

        # 프로필 이미지 처리 (llm_image 또는 user_image 둘 중 하나만)
        profile_image = request.FILES.get('llm_image') or request.FILES.get('user_image')
        if profile_image:
            try:
                img = Image.open(profile_image).convert("RGB")
                webp_io = io.BytesIO()
                img.save(webp_io, format='WEBP', quality=85)
                webp_content = webp_io.getvalue()
                webp_name = f"{ai_name}_{llm.id}.webp"
                llm.llm_image.save(webp_name, ContentFile(webp_content))
            except Exception as e:
                print("이미지 저장 실패:", e)

        # 장르 & 태그 업데이트 (LLM에도 저장)
        genres = request.POST.getlist('genres')
        tags = request.POST.getlist('tags')

        if genres:
            try:
                genre_ids = [int(g) for g in genres if g.strip().isdigit()]
                llm.genres.set(Genres.objects.filter(id__in=genre_ids))
            except ValueError:
                pass

        if tags:
            try:
                tag_ids = [int(t) for t in tags if t.strip().isdigit()]
                llm.tags.set(Tags.objects.filter(id__in=tag_ids))
            except ValueError:
                pass

        # ========================================
        # 로어북 업데이트 (기존 삭제 후 재생성)
        # ========================================
        lore_keys = request.POST.getlist('lore_keys[]')
        lore_contents = request.POST.getlist('lore_content[]')
        lore_priorities = request.POST.getlist('lore_priority[]')
        lore_always = request.POST.getlist('lore_always_active[]')
        lore_categories = request.POST.getlist('lore_category[]')

        # 기존 로어북 삭제
        LoreEntry.objects.filter(llm=llm).delete()

        # 새로 저장
        for i in range(len(lore_keys)):
            key = lore_keys[i].strip() if i < len(lore_keys) else ''
            content = lore_contents[i].strip() if i < len(lore_contents) else ''
            if key and content:
                LoreEntry.objects.create(
                    llm=llm,
                    keys=key,
                    content=content,
                    priority=int(lore_priorities[i]) if i < len(lore_priorities) and lore_priorities[i] else 0,
                    always_active=bool(lore_always[i]) if i < len(lore_always) else False,
                    category=lore_categories[i] if i < len(lore_categories) else '',
                )

        # ========================================
        # 서브 이미지 + HP 매핑 업데이트
        # ========================================
        sub_images = request.FILES.getlist('sub_images')
        min_hps = request.POST.getlist('min_hp[]')
        max_hps = request.POST.getlist('max_hp[]')
        sub_titles = request.POST.getlist('sub_image_title[]')

        # 새 서브 이미지가 있는지 확인 (실제 파일이 있는 것만 카운트)
        has_new_images = any(img for img in sub_images if img)

        if has_new_images:
            # 기존 HP 매핑 삭제
            HPImageMapping.objects.filter(llm=llm).delete()
            # 기존 서브 이미지 삭제
            LLMSubImage.objects.filter(llm=llm).delete()

            for i, img in enumerate(sub_images):
                if img:
                    sub_img = LLMSubImage.objects.create(
                        llm=llm,
                        image=img,
                        title=sub_titles[i] if i < len(sub_titles) else f"서브 {i+1}",
                    )

                    # HP 매핑
                    min_hp = min_hps[i] if i < len(min_hps) else None
                    max_hp = max_hps[i] if i < len(max_hps) else None
                    if min_hp or max_hp:
                        HPImageMapping.objects.create(
                            llm=llm,
                            sub_image=sub_img,
                            min_hp=int(min_hp) if min_hp and min_hp.strip().isdigit() else None,
                            max_hp=int(max_hp) if max_hp and max_hp.strip().isdigit() else None,
                        )
        else:
            # 새 이미지가 없으면 기존 서브 이미지의 HP와 제목만 업데이트
            existing_subs = list(LLMSubImage.objects.filter(llm=llm).order_by('id'))
            for i, sub_img in enumerate(existing_subs):
                # 제목 업데이트
                if i < len(sub_titles) and sub_titles[i]:
                    sub_img.title = sub_titles[i]
                    sub_img.save()

                # HP 매핑 업데이트
                hp_mapping = HPImageMapping.objects.filter(sub_image=sub_img).first()
                min_hp = min_hps[i] if i < len(min_hps) else None
                max_hp = max_hps[i] if i < len(max_hps) else None

                if min_hp or max_hp:
                    if hp_mapping:
                        hp_mapping.min_hp = int(min_hp) if min_hp and min_hp.strip().isdigit() else None
                        hp_mapping.max_hp = int(max_hp) if max_hp and max_hp.strip().isdigit() else None
                        hp_mapping.save()
                    else:
                        HPImageMapping.objects.create(
                            llm=llm,
                            sub_image=sub_img,
                            min_hp=int(min_hp) if min_hp and min_hp.strip().isdigit() else None,
                            max_hp=int(max_hp) if max_hp and max_hp.strip().isdigit() else None,
                        )

        # 최종 저장
        llm.save()

        # 리다이렉트
        if llm.story:
            return redirect('character:story_detail', story_uuid=llm.story.public_uuid)
        else:
            return redirect('character:ai_preview', llm_uuid=llm.public_uuid)

    # GET 요청: 편집 폼 초기값 채우기
    # 기존 로어북 항목 가져오기
    lore_entries = LoreEntry.objects.filter(llm=llm).order_by('priority')

    # 기존 서브 이미지 + HP 매핑 가져오기
    sub_images = LLMSubImage.objects.filter(llm=llm)
    sub_images_with_hp = []
    for sub_img in sub_images:
        hp_mapping = HPImageMapping.objects.filter(sub_image=sub_img).first()
        sub_images_with_hp.append({
            'sub_image': sub_img,
            'min_hp': hp_mapping.min_hp if hp_mapping else None,
            'max_hp': hp_mapping.max_hp if hp_mapping else None,
        })

    context = {
        "voice_list": voice_list,
        "voice_types": voice_types,
        "genre_list": genre_list,
        "tag_list": tag_list,
        "llm": llm,
        "story": llm.story,
        "story_uuid": llm.story.public_uuid if llm.story else None,
        "initial_voice_id": llm.voice.voice_id if llm.voice else None,
        "initial_narrator_voice_id": llm.narrator_voice.voice_id if llm.narrator_voice else None,
        "is_edit_mode": True,
        "lore_entries": lore_entries,
        "sub_images_with_hp": sub_images_with_hp,
    }
    return render(request, "character/make_ai.html", context)

@login_required_to_main
def ai_preview(request, llm_uuid):
    """AI 캐릭터 소개 미리보기 페이지"""
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)
    is_preview = request.GET.get('preview', False)

    other_llms =  llm.story.characters.exclude(id=llm.id) if llm.story else LLM.objects.none()

    context = {
        "llm": llm,
        "is_preview": is_preview,
        "llm_list":other_llms
    }

    return render(request, "character/ai_intro_preview.html", context)


@csrf_exempt
def chat_logic(request, llm_uuid):
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_text = data.get('message', '').strip()
            conversation_id = data.get('conversation_id')  # 앱에서 전달받은 conversation_id

            if not user_text:
                return JsonResponse({'error': '메시지를 입력해주세요.'}, status=400)

            # 1. 대화 기록 가져오기 (최근 10개)
            # 로그인 사용자 또는 conversation_id로 대화 찾기
            if request.user.is_authenticated:
                conversation = Conversation.objects.get(user=request.user, llm=llm)
            elif conversation_id:
                # conversation_id가 있으면 해당 대화 사용
                conversation = Conversation.objects.get(id=conversation_id, llm=llm)
            else:
                # 비로그인 + conversation_id 없음 → 새 대화 생성
                conversation = Conversation.objects.create(user=None, llm=llm, created_at=timezone.now())
            chat_history = list(conversation.messages.order_by('-created_at')[:10].values('role', 'content'))
            chat_history.reverse()

            # 2. ConversationState에서 현재 HP 가져오기
            conv_state, _ = ConversationState.objects.get_or_create(
                conversation=conversation,
                defaults={'character_stats': {'hp': 0, 'max_hp': 100}}
            )
            current_hp = conv_state.character_stats.get('hp', 100)
            max_hp = conv_state.character_stats.get('max_hp', 100)

            story_title = ""  # 기본값: 빈 문자열

            # HPImageMapping에서 current_hp가 속한 구간 찾기
            hp_mapping = HPImageMapping.objects.filter(
                llm=llm,                    # 현재 LLM
                min_hp__lte=current_hp,     # min_hp <= current_hp
                max_hp__gte=current_hp      # max_hp >= current_hp
            ).select_related('sub_image').first()  # 가장 먼저 매칭되는 하나만 가져옴

            if hp_mapping and hp_mapping.sub_image:
                # title이 있으면 title 사용, 없으면 description 사용 (또는 둘 다)
                story_title = hp_mapping.sub_image.title.strip() if hp_mapping.sub_image.title else ""


            sub_images = list(llm.sub_images.all().order_by('order', 'created_at'))

            # 현재 스토리 인덱스 찾기
            current_index = 0
            for i, si in enumerate(sub_images):
                if si.title.strip() == story_title:
                    current_index = i
                    break

            # 다음 스토리
            story_second = sub_images[current_index + 1].title.strip() if current_index + 1 < len(sub_images) else "next story is none just finish this story"

                
                # 만약 description도 함께 쓰고 싶다면:
                # story_description = hp_mapping.sub_image.description.strip() if hp_mapping.sub_image.description else ""
                # story_title = f"{story_title} | {story_description}".strip(" | ")

            # 디버깅용 로그 (필요할 때만)
            print(f"[DEBUG] Current HP: {current_hp}, Found mapping: {hp_mapping}, story_title: '{story_title}'")
            # 3. 응답 생성 (HP 정보 포함)
            if "grok" in llm.model.lower():
                raw_response = generate_response_grok(llm, chat_history, user_text, current_hp, max_hp, story_hint=story_title, story_next= story_second)
            else:
                raw_response = generate_response_gpt(llm, chat_history, user_text, current_hp, max_hp, story_hint=story_title, story_next= story_second)

            # 4. HP 변경 파싱 및 처리
            clean_response, hp_change = parse_hp_from_response(raw_response)
            print(f"[HP DEBUG] raw_response (끝부분): ...{raw_response[-200:]}")
            print(f"[HP DEBUG] parsed hp_change: {hp_change}")

            new_hp = current_hp
            if hp_change:
                hp_change_str = hp_change.strip()
                if hp_change_str.startswith('+'):
                    new_hp = min(current_hp + int(hp_change_str[1:]), max_hp)
                elif hp_change_str.startswith('-'):
                    new_hp = max(current_hp - int(hp_change_str[1:]), 0)
                else:
                    new_hp = max(0, min(int(hp_change_str), max_hp))

                # HP 업데이트 저장
                conv_state.character_stats['hp'] = new_hp
                conv_state.save()
                current_hp = new_hp
                print(f"[DEBUG] HP 변경: {hp_change} -> 새 HP: {new_hp}")
            else:
                print("[HP DEBUG] HP 변화 없음 - 태그 못 찾음")

            # 5. HP 구간 매핑 찾기
            hp_mapping = None
            for mapping in HPImageMapping.objects.filter(llm=llm).order_by('min_hp'):
                min_hp = mapping.min_hp if mapping.min_hp is not None else 0
                max_hp = mapping.max_hp if mapping.max_hp is not None else 100
                if min_hp <= current_hp <= max_hp:
                    hp_mapping = mapping
                    break

            # 6. 대화 기록 저장 (HP 구간 정보 함께 저장)
            ConversationMessage.objects.create(
                conversation=conversation,
                role='user',
                content=user_text,
                created_at=timezone.now(),
                hp_after_message=current_hp,  # 사용자 메시지 후 HP (변화 전)
                hp_range_min=hp_mapping.min_hp if hp_mapping else None,
                hp_range_max=hp_mapping.max_hp if hp_mapping else None,
            )

            ai_message = ConversationMessage.objects.create(
                conversation=conversation,
                role='assistant',
                content=clean_response,
                created_at=timezone.now(),
                hp_after_message=current_hp,  # AI 응답 후 HP
                hp_range_min=hp_mapping.min_hp if hp_mapping else None,
                hp_range_max=hp_mapping.max_hp if hp_mapping else None,
            )

            # 7. 텍스트와 HP 반환 (conversation_id 포함 - 비로그인 사용자용)
            return JsonResponse({
                'success': True,
                'text': clean_response,
                'message_id': ai_message.id,
                'conversation_id': conversation.id,
                'hp': current_hp,
                'max_hp': max_hp,
            })

        except Exception as e:
            logging.error(f"채팅 처리 오류: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({'error': '서버 오류가 발생했습니다.'}, status=500)

    return JsonResponse({'error': '잘못된 요청입니다.'}, status=400)




def chat_view(request, llm_uuid):
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)

    if request.method == 'GET':
        # 채팅 페이지 최초 로드
        # 로그인 사용자면 기존 대화 가져오기, 비로그인이면 새로 생성
        if request.user.is_authenticated:
            conversation, _ = Conversation.objects.get_or_create(
                user=request.user,
                llm=llm,
                defaults={'created_at': timezone.now()}
            )
        else:
            # 비로그인 사용자 → 새 대화 생성
            conversation = Conversation.objects.create(
                user=None,
                llm=llm,
                created_at=timezone.now()
            )

        # ConversationState 가져오기 또는 생성 (HP 저장용)
        conv_state, _ = ConversationState.objects.get_or_create(
            conversation=conversation,
            defaults={'character_stats': {'hp': 0, 'max_hp': 100}}
        )
        
        # HP 값 가져오기
        current_hp = conv_state.character_stats.get('hp', 0)
        max_hp = conv_state.character_stats.get('max_hp', 100)

        # 최근 20개 메시지
        messages = conversation.messages.order_by('created_at')

        # 서브 이미지 + HP 매핑 가져오기
        sub_images_data = []
        all_sub_images = llm.sub_images.all()
        print(f"[DEBUG] LLM: {llm.name}, 서브 이미지 개수: {all_sub_images.count()}")

        for sub in all_sub_images:
            hp_mapping = HPImageMapping.objects.filter(sub_image=sub).first()
            min_hp_val = hp_mapping.min_hp if hp_mapping and hp_mapping.min_hp is not None else 0
            max_hp_val = hp_mapping.max_hp if hp_mapping and hp_mapping.max_hp is not None else 100

            image_url = sub.image.url if sub.image else ''
            print(f"[DEBUG] 서브이미지 ID:{sub.id}, image_url: {image_url}, min_hp: {min_hp_val}, max_hp: {max_hp_val}")

            sub_images_data.append({
                'image_url': image_url,
                'min_hp': min_hp_val,
                'max_hp': max_hp_val,
                'title': sub.title or '',
            })

        loarbook_list = LoreEntry.objects.filter(llm_id = llm)


        print(f"[DEBUG] 최종 sub_images_data: {sub_images_data}")
        print(f"[DEBUG] llm.llm_image: {llm.llm_image.url if llm.llm_image else '없음'}")
        print(f"[DEBUG] current_hp: {current_hp}")

        context = {
            'llm': llm,
            'conversation': conversation,
            'messages': messages,
            'sub_images_data': sub_images_data,
            'current_hp': current_hp,
            'max_hp': max_hp,
            "loarbook_list" :loarbook_list
        }
        return render(request, "character/chat.html", context)


from pydub import AudioSegment


@csrf_exempt
def chat_tts(request, llm_uuid):
    """별도의 TTS 생성 엔드포인트 - 텍스트 응답 후 비동기로 호출"""
    if request.method != 'POST':
        return JsonResponse({'error': '잘못된 요청입니다.'}, status=400)
    print("__________TTS 생성 중_______________")

    try:
        llm = get_object_or_404(LLM, public_uuid=llm_uuid)
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        message_id = data.get('message_id')

        if not text:
            return JsonResponse({'error': '텍스트가 없습니다.'}, status=400)

        # TTS 목소리 선택 - 캐릭터 설정 우선, 없으면 같은 스토리의 다른 캐릭터, 없으면 기본값
        DEFAULT_VOICE = "LruHrtVF6PSyGItzMNHS"

        # 캐릭터 음성
        character_voice = llm.voice.voice_id if llm.voice else DEFAULT_VOICE

        # 나레이터 음성 - 우선순위: 캐릭터 설정 > 스토리 내 다른 캐릭터 > 기본값
        narrator_voice = DEFAULT_VOICE
        if llm.narrator_voice and llm.narrator_voice.voice_id:
            narrator_voice = llm.narrator_voice.voice_id
        elif llm.story:
            # 같은 스토리의 다른 캐릭터 중 나레이터 음성이 설정된 것 찾기
            story_llm_with_narrator = LLM.objects.filter(
                story=llm.story,
                narrator_voice__isnull=False
            ).exclude(id=llm.id).first()
            if story_llm_with_narrator and story_llm_with_narrator.narrator_voice:
                narrator_voice = story_llm_with_narrator.narrator_voice.voice_id

        logging.info(f"🎙️ TTS 음성 - 나레이터: {narrator_voice}, 캐릭터: {character_voice}")

        # 순차적 TTS 생성 (나레이션→대사→나레이션→대사... 순서 유지)
        final_audio_buffer = generate_sequential_tts(llm, text, narrator_voice, character_voice)

        # base64 변환
        final_audio_buffer.seek(0)
        audio_base64 = base64.b64encode(final_audio_buffer.read()).decode('utf-8')



        final_audio_buffer.seek(0)
        audio_segment = AudioSegment.from_file(final_audio_buffer, format="mp3")
        duration_sec = len(audio_segment) / 1000
        print("오디오 길이:", duration_sec)
        # 오디오를 DB에 저장
        audio_url = None
        if message_id:
            try:
                from django.core.files.base import ContentFile
                message = ConversationMessage.objects.get(id=message_id)
                final_audio_buffer.seek(0)
                audio_content = final_audio_buffer.read()
                filename = f"tts_{message_id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.mp3"
                message.audio.save(filename, ContentFile(audio_content), save=True)
                audio_url = message.audio.url
                message.audio_duration = duration_sec
                message.save() 
                logging.info(f"✅ TTS 오디오 저장 완료: {audio_url}")
            except ConversationMessage.DoesNotExist:
                logging.warning(f"⚠️ 메시지를 찾을 수 없음: {message_id}")
            except Exception as save_error:
                logging.error(f"❌ 오디오 저장 실패: {save_error}")

        return JsonResponse({
            'success': True,
            'audio': f'data:audio/mpeg;base64,{audio_base64}',
            'audio_url': audio_url,
            'message_id': message_id,
        })

    except Exception as e:
        logging.error(f"TTS 생성 오류: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'error': 'TTS 생성 실패'}, status=500)



def ai_intro(request, llm_uuid):
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)
    is_preview = request.GET.get('preview', False)

    other_llms = llm.story.characters.exclude(id=llm.id) if llm.story else LLM.objects.none()


    
    try:
        conversation_has = ConversationMessage.objects.filter(
        conversation__llm=llm,
        conversation__user=request.user
    ).exists()
        conv = Conversation.objects.get(
            llm=llm,
            user=request.user
        )
        conv_id = conv.id
    except Conversation.DoesNotExist:
        conv = None
        conv_id = None
    
    
    # 댓글 목록
    comments = Comment.objects.filter(llm=llm, parent_comment__isnull=True).select_related('user')
    print("conversation_has:", conv)
   # 좋아요 여부 및 카운트
    user_liked = False
    if request.user.is_authenticated:
        user_liked = LLMLike.objects.filter(user=request.user, llm=llm).exists()
    like_count = LLMLike.objects.filter(llm=llm).count()

    context = {
        "llm": llm,
        "is_preview": is_preview,
        "other_llms": other_llms,
        "comments": comments,
        "user_liked": user_liked,
        "like_count": like_count,
        "conversation_has":conversation_has,
        "conv_id":conv_id

    }

    return render(request, "character/ai_intro.html", context)


@csrf_protect
@require_http_methods(["DELETE"])
def delete_conversation(request, conv_id):
    conversation = get_object_or_404(
        Conversation,
        id=conv_id,
        user=request.user
    )

    llm = conversation.llm  # 어떤 캐릭터인지 기억

    # 1️⃣ 메시지 삭제
    ConversationMessage.objects.filter(conversation=conversation).delete()

    # 2️⃣ 상태(HP 등) 삭제
    ConversationState.objects.filter(conversation=conversation).delete()

    # 3️⃣ 대화 자체 삭제
    conversation.delete()

    # 4️⃣ 다시 해당 LLM 채팅 페이지로 이동 → 새 conversation 생성됨
    return redirect('character:chat-view', llm_uuid=llm.public_uuid)

    


from django.db.models import Count
def story_intro(request, story_uuid=None):

    # =========================
    # 스토리 기본 정보
    # =========================
    story = get_object_or_404(Story, public_uuid=story_uuid)
    llm_list = LLM.objects.filter(story=story)

    # 성인 콘텐츠 블러 처리
    is_adult_content = story.adult_choice
    is_authorized = request.user.is_authenticated and request.user.is_adult()
    show_blur = is_adult_content and not is_authorized

    # =========================
    # 댓글
    # =========================
    comments = (
        StoryComment.objects
        .filter(story=story, parent_comment__isnull=True)
        .select_related('user')
    )

    # =========================
    # 좋아요
    # =========================
    user_liked = False
    if request.user.is_authenticated:
        user_liked = StoryLike.objects.filter(
            user=request.user,
            story=story
        ).exists()

    like_count = StoryLike.objects.filter(story=story).count()

    # =========================
    # 북마크
    # =========================
    if request.user.is_authenticated:
        story_bookmarks = (
            StoryBookmark.objects
            .filter(user=request.user)
            .select_related('story', 'story__user')
            .prefetch_related('story__genres', 'story__characters')
            .order_by('-created_at')
        )
    else:
        story_bookmarks = StoryBookmark.objects.none()

    # =========================
    # 📊 통계용 데이터
    # =========================

    # 1️⃣ 이 스토리의 LLM과 대화한 사용자 ID들
    user_ids = (
        Conversation.objects
        .filter(llm__story=story)
        .values_list('user_id', flat=True)
        .distinct()
    )

    readers = Users.objects.filter(user_id__in=user_ids)

    # =========================
    # 성별 통계
    # =========================
    gender_data = {
        'M': 0,
        'F': 0,
        'O': 0,
    }

    gender_qs = (
        readers
        .values('gender')
        .annotate(count=Count('user_id'))
    )

    for row in gender_qs:
        if row['gender'] in gender_data:
            gender_data[row['gender']] = row['count']

    # =========================
    # 연령대 통계
    # =========================
    today  = timezone.now().year

    age_data = {
        '어린이': 0,
        '10대': 0,
        '20대': 0,
        '30대': 0,
        '40대': 0,
        '50대 이상': 0,
    }

    for user in readers.exclude(age__isnull=True):
        age = user.age
        if age < 10:
            age_data['어린이'] += 1
        elif age < 20:
            age_data['10대'] += 1
        elif age < 30:
            age_data['20대'] += 1
        elif age < 40:
            age_data['30대'] += 1
        elif age < 50:
            age_data['40대'] += 1
        else:
            age_data['50대 이상'] += 1

    # =========================
    # Chart.js용 JSON
    # =========================
    stats_json = {
        "reader_count": len(user_ids),
        "gender_data": gender_data,
        "age_data": age_data,
    }

    # =========================
    # 템플릿 전달
    # =========================
    context = {
        "story": story,
        "llm_list": llm_list,
        "comments": comments,
        "user_liked": user_liked,
        "like_count": like_count,
        "story_bookmarks": story_bookmarks,
        "show_blur": show_blur,
        "stats_json": json.dumps(stats_json),
    }

    return render(request, "character/story_intro.html", context)


# LLM 좋아요 토글
@csrf_exempt
@require_POST
def toggle_llm_like(request, llm_uuid):
    user = _get_auth_user(request)
    if not user:
        return JsonResponse({'error': '로그인이 필요합니다.'}, status=401)
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)
    like, created = LLMLike.objects.get_or_create(user=user, llm=llm)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    like_count = LLMLike.objects.filter(llm=llm).count()
    return JsonResponse({'liked': liked, 'like_count': like_count})


# LLM 댓글 작성
@csrf_exempt
@require_POST
def add_llm_comment(request, llm_uuid):
    user = _get_auth_user(request)
    if not user:
        return JsonResponse({'error': '로그인이 필요합니다.'}, status=401)
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)

    try:
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        parent_id = data.get('parent_id')

        if not content:
            return JsonResponse({'error': '댓글 내용을 입력해주세요.'}, status=400)

        parent_comment = None
        if parent_id:
            parent_comment = Comment.objects.filter(id=parent_id, llm=llm).first()

        comment = Comment.objects.create(
            user=user,
            llm=llm,
            content=content,
            parent_comment=parent_comment
        )

        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'username': user.nickname or user.username,
                'created_at': comment.created_at.strftime('%Y.%m.%d %H:%M'),
                'is_reply': parent_comment is not None,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# LLM 댓글 삭제
@csrf_exempt
@require_POST
def delete_llm_comment(request, comment_id):
    user = _get_auth_user(request)
    if not user:
        return JsonResponse({'error': '로그인이 필요합니다.'}, status=401)
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.user != user:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)

    comment.delete()
    return JsonResponse({'success': True})


# Story 좋아요 토글
@csrf_exempt
@require_POST
def toggle_story_like(request, story_uuid):
    user = _get_auth_user(request)
    if not user:
        return JsonResponse({'error': '로그인이 필요합니다.'}, status=401)
    story = get_object_or_404(Story, public_uuid=story_uuid)
    like, created = StoryLike.objects.get_or_create(user=user, story=story)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    like_count = StoryLike.objects.filter(story=story).count()
    return JsonResponse({'liked': liked, 'like_count': like_count})


# Story 북마크 토글
@csrf_exempt
@require_POST
def toggle_story_bookmark(request, story_uuid):
    user = _get_auth_user(request)
    if not user:
        return JsonResponse({'error': '로그인이 필요합니다.'}, status=401)
    story = get_object_or_404(Story, public_uuid=story_uuid)
    bookmark, created = StoryBookmark.objects.get_or_create(user=user, story=story)

    if not created:
        bookmark.delete()
        bookmarked = False
    else:
        bookmarked = True

    return JsonResponse({'success': True, 'bookmarked': bookmarked})


# Story 댓글 작성
@csrf_exempt
@require_POST
def add_story_comment(request, story_uuid):
    user = _get_auth_user(request)
    if not user:
        return JsonResponse({'error': '로그인이 필요합니다.'}, status=401)
    story = get_object_or_404(Story, public_uuid=story_uuid)

    try:
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        parent_id = data.get('parent_id')

        if not content:
            return JsonResponse({'error': '댓글 내용을 입력해주세요.'}, status=400)

        parent_comment = None
        if parent_id:
            parent_comment = StoryComment.objects.filter(id=parent_id, story=story).first()

        comment = StoryComment.objects.create(
            user=user,
            story=story,
            content=content,
            parent_comment=parent_comment
        )

        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'username': user.nickname or user.username,
                'created_at': comment.created_at.strftime('%Y.%m.%d %H:%M'),
                'is_reply': parent_comment is not None,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Story 댓글 삭제
@csrf_exempt
@require_POST
def delete_story_comment(request, comment_id):
    user = _get_auth_user(request)
    if not user:
        return JsonResponse({'error': '로그인이 필요합니다.'}, status=401)
    comment = get_object_or_404(StoryComment, id=comment_id)

    if comment.user != user:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)

    comment.delete()
    return JsonResponse({'success': True})




@login_required
@require_POST
def delete_story(request, story_uuid):
    story = get_object_or_404(Story, public_uuid=story_uuid)
    if story.user != request.user:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)

    story.delete()

    return redirect('mypage:ai_list')


@login_required
@require_POST
def delete_llm(request, llm_uuid):
    llm = get_object_or_404(LLM, public_uuid=llm_uuid)
    story = llm.story  
    if llm.user != request.user:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)

    llm.delete()

    return redirect('character:story_detail', story_uuid = story.public_uuid)

