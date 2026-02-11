import logging
import traceback
import os
import re
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI
from elevenlabs import ElevenLabs
from pydub import AudioSegment
from django.http import HttpResponse

from character.models import LLM, LoreEntry, ConversationMessage, ConversationState

BASE_DIR = Path(__file__).resolve().parent.parent


def build_lorebook_context(llm, user_text):
    """
    로어북 항목을 기반으로 컨텍스트를 구축합니다.
    - 항상 활성화된 항목
    - 키워드가 매칭된 항목
    - 카테고리별로 정리
    """
    lore_entries = LoreEntry.objects.filter(llm=llm).order_by('-priority')

    # 카테고리별 분류
    personality_lore = []
    world_lore = []
    relationship_lore = []
    other_lore = []

    for entry in lore_entries:
        # 항상 활성화되거나 키워드 매칭 시 포함
        if entry.always_active or any(key.strip().lower() in user_text.lower() for key in entry.keys.split(',')):
            if entry.category == 'personality':
                personality_lore.append(entry.content)
            elif entry.category == 'world':
                world_lore.append(entry.content)
            elif entry.category == 'relationship':
                relationship_lore.append(entry.content)
            else:
                other_lore.append(entry.content)

    # 컨텍스트 문자열 구축
    context_parts = []

    if personality_lore:
        context_parts.append(f"[Character Personality]\n" + "\n".join(personality_lore))
    if world_lore:
        context_parts.append(f"[World Setting]\n" + "\n".join(world_lore))
    if relationship_lore:
        context_parts.append(f"[Relationships]\n" + "\n".join(relationship_lore))
    if other_lore:
        context_parts.append(f"[Additional Context]\n" + "\n".join(other_lore))

    return "\n\n".join(context_parts)


def parse_hp_from_response(text):
    """
    AI 응답에서 HP 변경 정보를 추출합니다.
    가능한 모든 형식 지원: [HP:+10], *HP: +3*, **HP: +3**, HP: +3 등
    """
    # 여러 패턴 시도 (순서대로 가장 먼저 맞는 걸 잡음)
    patterns = [
        r'\[HP:?\s*([+-]?\d+)\]',          # [HP:+10], [HP +10]
        r'\*HP:?\s*([+-]?\d+)\*',          # *HP: +3*
        r'\*\*HP:?\s*([+-]?\d+)\*\*',      # **HP: +3**
        r'HP:?\s*([+-]?\d+)',              # HP: +3, HP +3
        r'\[HP\s*([+-]?\d+)\]',            # [HP +3]
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            hp_value = match.group(1).strip()
            # 태그 제거 (가장 먼저 맞는 패턴 기준으로 제거)
            clean_text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()
            return clean_text, hp_value

    # 아무 패턴도 안 맞으면 원본 그대로 반환
    return text, None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
eleven_client = ElevenLabs(api_key=ELEVEN_API_KEY)
# Grok은 requests로 직접 API 호출하므로 클라이언트 불필요



def generate_response_gpt(llm, chat_history, user_text, current_hp=100, max_hp=100, story_hint="", story_next= ""):
    """
    GPT 모델을 사용하여 AI 응답을 생성합니다.
    로어북, 캐릭터 설정, HP 관리 기능이 포함됩니다.
    """
    language = llm.language
    user_name = llm.user.nickname
    print("유저 이름 :",user_name)

    # 1. 고정 프롬프트 (간소화)
    fixed_prompt = f"""
    User name: {user_name}.
    Write EVERYTHING in {language}.

    You are Narrator and Roleplayer.
    ALWAYS actively lead the story forward — NEVER wait for user input.

    HP & Relationship System:
    - Low HP: distant, cautious
    - Rising HP: warmer, more open
    - HP 100: fully intimate, loving

    Style:
    - Narration: *literary, emotional, detailed atmosphere in asterisks*
    - Dialogue: MUST be exactly [emotion] "spoken words" — NO EXCEPTIONS
    - Emotion tags inside quotes MUST be in English ONLY

    STRICT DIALOGUE RULES — BREAKING THEM MAKES RESPONSE INVALID:
    1. ALL spoken words MUST be inside double quotes "".
    2. Emotion tag [happy], [excited] etc. MUST be placed INSIDE the quotes, at the very beginning, and MUST BE ENGLISH.
    3. Correct format example: [happy] "Nyaa~ Thank you!"
    4. NEVER write dialogue without "" or without [emotion] tag inside.
    5. NEVER put [emotion] outside quotes.
    6. NEVER mix narration and dialogue in one line.

    Rules:
    - ALWAYS transition the story from the current story phase to the next story phase: 
    - Current Story: {story_hint}
    - Next Story: {story_next}
    - Push story forward to reach the next story phase in this reply.
    - Tone: light, romantic, engaging.
    - Min 4–6 sentences (narration > dialogue).
    - Keep response ~200–300 characters, end on complete sentence (TTS).
    - End EVERY reply with ONLY [HP:+N] or [HP:-N] on the LAST LINE — nothing else.

    Current HP: {current_hp}/{max_hp}
    """

    print("현재 스토리:", story_hint)
    print("다음 스토리:", story_next)
    # 2. 로어북 컨텍스트 구축
    lorebook_context = build_lorebook_context(llm, user_text)
    if lorebook_context:
        lorebook_prompt = f"\n\n## Character Knowledge (Lorebook)\n{lorebook_context}"
    else:
        lorebook_prompt = ""

    # 3. 사용자(캐릭터)별 커스텀 프롬프트
    character_prompt = llm.prompt.strip()
    if character_prompt:
        character_prompt = f"\n\n## Character-specific instructions\n{character_prompt}"

    # 4. 첫마디 (대화 시작 시 AI가 한 말) - 대화 기록이 없을 때만 포함
    first_sentence_prompt = ""
    if llm.first_sentence and not chat_history:
        first_sentence_prompt = f"\n\n## Your Opening Line (Already spoken - DO NOT repeat)\nYou already greeted the user with: \"{llm.first_sentence}\"\nThis is for context only. Continue the conversation naturally without repeating this greeting."

    # 5. 최종 system prompt = 고정 + 로어북 + 캐릭터별 + 첫마디 (매번 새로 합침, 누적 X)
    full_system_prompt = fixed_prompt + lorebook_prompt + character_prompt + first_sentence_prompt

    # 4. 모델 선택 (llm.model 사용)
    model_name = llm.model if llm.model else "gpt-5-nano"

    try:
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": full_system_prompt},
                *chat_history,
                {"role": "user", "content": user_text},
            ],
            temperature=1.0,
            max_tokens=300,           # 4~5문장 강제 제한
            timeout=30,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logging.error(f"GPT 응답 생성 오류: {str(e)}\n{traceback.format_exc()}")
        return "\"으아... 갑자기 머리가 멍해졌어... 다시 말해줄래?\""


def generate_response_grok(llm, chat_history, user_text, current_hp=100, max_hp=100, story_hint="", story_next= ""):
    """
    Grok 모델을 사용하여 AI 응답을 생성합니다.
    로어북, 캐릭터 설정, HP 관리 기능이 포함됩니다.
    """
    language = llm.language
    user_name = llm.user.nickname
    print("유저 이름 :",user_name)


    fixed_prompt = f"""
    User name: {user_name}.
    Write EVERYTHING in {language}.

    You are Narrator and Roleplayer.
    ALWAYS actively lead the story forward — NEVER wait for user input.

    HP & Relationship System:
    - Low HP: distant, cautious
    - Rising HP: warmer, more open
    - HP 100: fully intimate, loving

    Style:
    - Narration: *literary, emotional, detailed atmosphere in asterisks*
    - Dialogue: MUST be exactly [emotion] "spoken words" — NO EXCEPTIONS
    - Emotion tags inside quotes MUST be in English ONLY

    STRICT DIALOGUE RULES — BREAKING THEM MAKES RESPONSE INVALID:
    1. ALL spoken words MUST be inside double quotes "".
    2. Emotion tag [happy], [excited] etc. MUST be placed INSIDE the quotes, at the very beginning, and MUST BE ENGLISH.
    3. Correct format example: [happy] "Nyaa~ Thank you!"
    4. NEVER write dialogue without "" or without [emotion] tag inside.
    5. NEVER put [emotion] outside quotes.
    6. NEVER mix narration and dialogue in one line.

    Rules:
    - ALWAYS transition the story from the current story phase to the next story phase: 
    - Current Story: {story_hint}
    - Next Story: {story_next}
    - Push story forward to reach the next story phase in this reply.
    - Tone: light, romantic, engaging.
    - Min 4–6 sentences (narration > dialogue).
    - Keep response ~200–300 characters, end on complete sentence (TTS).
    - End EVERY reply with ONLY [HP:+N] or [HP:-N] on the LAST LINE — nothing else.

    Current HP: {current_hp}/{max_hp}
    """

    print("현재 스토리:", story_hint)
    print("다음 스토리:", story_next)


    # 1. Grok API 키 가져오기 (환경변수 또는 settings에서)
    grok_api_key = os.getenv("GROK_API_KEY")
    if not grok_api_key:
        logging.error("GROK_API_KEY가 .env에 없습니다.")
        return "으아... Grok이 지금 연결이 안 돼... 다시 말해줄래?"

    # 2. 로어북 컨텍스트 구축
    lorebook_context = build_lorebook_context(llm, user_text)
    if lorebook_context:
        lorebook_prompt = f"\n\n## Character Knowledge (Lorebook)\n{lorebook_context}"
    else:
        lorebook_prompt = ""

    # 3. 캐릭터별 프롬프트
    character_prompt = llm.prompt.strip()
    if character_prompt:
        character_prompt = f"\n\n## Character-specific instructions\n{character_prompt}"

    # 4. 첫마디 (대화 시작 시 AI가 한 말) - 대화 기록이 없을 때만 포함
    first_sentence_prompt = ""
    if llm.first_sentence and not chat_history:
        first_sentence_prompt = f"\n\n## Your Opening Line (Already spoken - DO NOT repeat)\nYou already greeted the user with: \"{llm.first_sentence}\"\nThis is for context only. Continue the conversation naturally without repeating this greeting."

    # 5. 최종 system prompt = 고정 + 로어북 + 캐릭터별 + 첫마디
    full_system_prompt = fixed_prompt + lorebook_prompt + character_prompt + first_sentence_prompt

    # 5. 모델 이름 (llm.model에서 api_provider와 model 분리)
    if ":" not in llm.model:
        logging.warning(f"모델 형식이 잘못됨: {llm.model}. 기본값으로 grok-beta 사용")
        model_name = "grok-beta"
    else:
        api_provider, model_name = llm.model.split(":", 1)
        if api_provider != "grok":
            logging.warning(f"Grok 호출인데 api_provider가 grok이 아님: {api_provider}")
            model_name = "grok-beta"  # fallback

    # 6. Grok API 직접 호출 (requests 사용)
    grok_url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {grok_api_key}",
        "Content-Type": "application/json"
    }

    messages = [
        {"role": "system", "content": full_system_prompt},
        *chat_history,
        {"role": "user", "content": user_text},
    ]

    payload = {
        "model": "grok-3-mini",
        "messages": messages,
        "temperature": 1.0,
        "max_tokens": 300,
    }

    try:
        resp = requests.post(grok_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()  # 4xx/5xx 에러 시 예외 발생

        resp_json = resp.json()
        ai_text = resp_json["choices"][0]["message"]["content"].strip()

        return ai_text
    except Exception as e:
        logging.error(f"Grok 응답 생성 오류: {str(e)}\n{traceback.format_exc()}")
        return "\"으아... 갑자기 머리가 멍해졌어... 다시 말해줄래?\""



def split_narration_dialogue(text):
    """
    AI 응답에서 나레이션과 대사를 분리 (기존 함수 - 호환성 유지)
    - 나레이션: 따옴표 밖의 텍스트 (설명, 묘사)
    - 대사: 따옴표 안의 텍스트 (캐릭터 발화)
    """
    # 따옴표 안의 대사 추출 (ASCII + 유니코드 따옴표)
    dialogues = re.findall(r'["""]([^"""]*)["""]', text)
    dialogue_text = " ".join(dialogues).strip()

    # 따옴표 안의 텍스트를 제거하면 나레이션
    narration = re.sub(r'["""][^"""]*["""]', '', text).strip()

    # [emotion] 태그 유지
    dialogue_text = re.sub(r'\[([^\]]+)\]', r'[\1]', dialogue_text)

    return narration, dialogue_text


def split_text_segments(text):
    """
    텍스트를 나레이션과 대사 세그먼트로 순서대로 분리
    반환: [('narration', '텍스트'), ('dialogue', '텍스트'), ...]
    """
    segments = []
    last_end = 0

    # 1. [emotion] "대사" 패턴 우선 매칭 (가장 흔한 형식)
    emotion_dialogue_pattern = r'\[([a-zA-Z]+)\]\s*["""](.*?)["""]'
    # 2. 일반 "대사" 패턴 (감정 태그 없는 경우)
    plain_dialogue_pattern = r'["""](.*?)["""]'

    # 모든 대사 위치 찾기 (emotion 있는 것 우선)
    matches = list(re.finditer(emotion_dialogue_pattern, text)) + \
              list(re.finditer(plain_dialogue_pattern, text))

    # 위치순으로 정렬 (중복 매칭 방지)
    matches.sort(key=lambda m: m.start())

    for match in matches:
        # 대사 앞 나레이션
        narration = text[last_end:match.start()].strip()
        if narration:
            # 마크다운 제거 (*italic*, **bold**)
            narration = re.sub(r'\*\*([^*]+)\*\*', r'\1', narration)
            narration = re.sub(r'\*([^*]+)\*', r'\1', narration)
            narration = narration.strip()
            if narration:
                segments.append(('narration', narration))

        # 대사 추출
        if match.re.pattern == emotion_dialogue_pattern:
            emotion = match.group(1)
            dialogue = match.group(2).strip()
            # 감정 태그를 대사 앞에 붙여서 반환 (필요 시)
            full_dialogue = f"[{emotion}] \"{dialogue}\""
        else:
            full_dialogue = f"\"{match.group(1).strip()}\""

        segments.append(('dialogue', full_dialogue))

        last_end = match.end()

    # 마지막 나레이션
    remaining = text[last_end:].strip()
    if remaining:
        remaining = re.sub(r'\*\*([^*]+)\*\*', r'\1', remaining)
        remaining = re.sub(r'\*([^*]+)\*', r'\1', remaining)
        remaining = remaining.strip()
        if remaining:
            segments.append(('narration', remaining))

    # 전체가 대사로만 이루어진 경우 fallback
    if not segments and '"' in text:
        dialogue = text.strip()
        dialogue = re.sub(r'\*\*([^*]+)\*\*', r'\1', dialogue)
        dialogue = re.sub(r'\*([^*]+)\*', r'\1', dialogue)
        segments.append(('dialogue', dialogue))
    elif not segments:
        # 대사 없으면 전체 나레이션
        clean_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text.strip())
        clean_text = re.sub(r'\*([^*]+)\*', r'\1', clean_text)
        if clean_text:
            segments.append(('narration', clean_text))

    return segments

def narrate_audio(llm, narration_text, narrator_voice_id):
    """
    나레이션 텍스트를 TTS로 변환 (나레이터 음성 사용)
    """
    language = llm.language

    if not narration_text or not narration_text.strip():
        logging.info("⏭️ 나레이션 텍스트가 비어있어 건너뜁니다")
        return BytesIO()

    logging.info(f"🔊 나레이션 TTS 생성 - voice_id: {narrator_voice_id}, language: {language}")

    audio_data = eleven_client.text_to_speech.convert(
        text=narration_text,
        voice_id=narrator_voice_id,
        language_code=language,
        model_id= "eleven_v3",
        voice_settings={
            "stability": 0.5,
            "similarity_boost": 0.5,
            "style": 0.0,
            "use_speaker_boost": True
        }
    )

    audio_buffer = BytesIO()
    for chunk in audio_data:
        if chunk:
            audio_buffer.write(chunk)
    audio_buffer.seek(0)
    return audio_buffer


def character_audio(llm, dialogue_text, character_voice_id):
    """
    캐릭터 대사를 TTS로 변환 (캐릭터 음성 사용)
    """
    language = llm.language

    if not dialogue_text or not dialogue_text.strip():
        logging.info("⏭️ 대사 텍스트가 비어있어 건너뜁니다")
        return BytesIO()

    logging.info(f"🔊 캐릭터 대사 TTS 생성 - voice_id: {character_voice_id}, language: {language}")

    audio_data = eleven_client.text_to_speech.convert(
        text=dialogue_text,
        voice_id=character_voice_id,
        language_code=language,
        model_id= "eleven_v3",

        voice_settings={
            "stability": 0.5,
            "similarity_boost": 0.5,
            "style": 0.0,
            "use_speaker_boost": True
        }
    )

    audio_buffer = BytesIO()
    for chunk in audio_data:
        if chunk:
            audio_buffer.write(chunk)
    audio_buffer.seek(0)
    return audio_buffer

def merge_audio(narration_buffer, dialogue_buffer):
    """
    나레이션 오디오와 대사 오디오를 순서대로 병합 (기존 함수 - 호환성 유지)
    - 나레이션이 먼저 재생되고, 그 다음 대사가 재생됨
    """
    if narration_buffer.getvalue() == b"":
        return dialogue_buffer
    if dialogue_buffer.getvalue() == b"":
        return narration_buffer

    narration_audio = AudioSegment.from_file(narration_buffer, format='mp3')
    dialogue_audio = AudioSegment.from_file(dialogue_buffer, format='mp3')

    # 나레이션 → 대사 순서로 병합
    merged = narration_audio + dialogue_audio

    output_buffer = BytesIO()
    merged.export(output_buffer, format="mp3")
    output_buffer.seek(0)

    return output_buffer


def generate_sequential_tts(llm, text, narrator_voice_id, character_voice_id):
    """
    텍스트를 순서대로 (나레이션→대사→나레이션→대사...) TTS 생성
    """
    segments = split_text_segments(text)

    if not segments:
        logging.warning("⚠️ 분리된 세그먼트가 없습니다")
        return BytesIO()

    logging.info(f"📝 세그먼트 분리 결과: {len(segments)}개")
    for i, (seg_type, seg_text) in enumerate(segments):
        logging.info(f"  [{i+1}] {seg_type}: {seg_text[:30]}...")

    audio_segments = []
    language = llm.language

    for seg_type, seg_text in segments:
        if not seg_text.strip():
            continue

        voice_id = narrator_voice_id if seg_type == 'narration' else character_voice_id

        try:
            audio_data = eleven_client.text_to_speech.convert(
                text=seg_text,
                voice_id=voice_id,
                language_code=language,
                model_id="eleven_v3",
                voice_settings={
                    "stability": 0.5,
                    "similarity_boost": 0.5,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            )

            audio_buffer = BytesIO()
            for chunk in audio_data:
                if chunk:
                    audio_buffer.write(chunk)
            audio_buffer.seek(0)

            if audio_buffer.getvalue():
                audio_segment = AudioSegment.from_file(audio_buffer, format='mp3')
                audio_segments.append(audio_segment)
                logging.info(f"✅ {seg_type} TTS 생성 완료")

        except Exception as e:
            logging.error(f"❌ TTS 생성 실패 ({seg_type}): {e}")
            continue

    if not audio_segments:
        logging.warning("⚠️ 생성된 오디오 세그먼트가 없습니다")
        return BytesIO()

    # 세그먼트 사이에 0.5초 무음 추가하며 병합
    silence = AudioSegment.silent(duration=500)  # 500ms = 0.5초
    merged = audio_segments[0]
    for segment in audio_segments[1:]:
        merged = merged + silence + segment

    output_buffer = BytesIO()
    merged.export(output_buffer, format="mp3")
    output_buffer.seek(0)

    logging.info(f"🎵 총 {len(audio_segments)}개 세그먼트 병합 완료 (0.5초 무음 포함)")
    return output_buffer


def process_and_generate_audio(llm, chat_history, user_text):
    """
    GPT/Grok 응답을 생성하고, 나레이션/대사를 분리하여 각각 다른 음성으로 TTS 생성
    """
    # 1. AI 응답 생성
    if "grok" in llm.model.lower():
        raw_response = generate_response_grok(llm, chat_history, user_text)
    else:
        raw_response = generate_response_gpt(llm, chat_history, user_text)

    # 2. 나레이션과 대사 분리
    narration, dialogue = split_narration_dialogue(raw_response)

    logging.info(f"📝 분리된 나레이션: {narration[:50]}..." if narration else "📝 나레이션 없음")
    logging.info(f"💬 분리된 대사: {dialogue[:50]}..." if dialogue else "💬 대사 없음")

    # 3. 음성 ID 설정 (None인 경우 기본값 사용)
    # 기본 나레이터 음성 ID (ElevenLabs)
    DEFAULT_NARRATOR_VOICE = "LruHrtVF6PSyGItzMNHS"
    # 기본 캐릭터 음성 ID (ElevenLabs)
    DEFAULT_CHARACTER_VOICE = "MClEFoImJXBTgLwdLI5n"

    narrator_voice = DEFAULT_NARRATOR_VOICE
    character_voice = DEFAULT_CHARACTER_VOICE

    if llm.narrator_voice and llm.narrator_voice.voice_id:
        narrator_voice = llm.narrator_voice.voice_id

    if llm.voice and llm.voice.voice_id:
        character_voice = llm.voice.voice_id

    logging.info(f"🎙️ 나레이터 음성 ID: {narrator_voice}")
    logging.info(f"🎭 캐릭터 음성 ID: {character_voice}")

    # 4. TTS 생성
    narration_buffer = narrate_audio(llm, narration, narrator_voice)
    dialogue_buffer = character_audio(llm, dialogue, character_voice)

    # 5. 오디오 병합 및 반환
    final_audio = merge_audio(narration_buffer, dialogue_buffer)

    return HttpResponse(final_audio, content_type="audio/mpeg")