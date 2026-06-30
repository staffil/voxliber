# tts 생성 (디버깅용)
import os
import re
import traceback
from django.conf import settings
from elevenlabs import ElevenLabs
from uuid import uuid4
from dotenv import load_dotenv
from pydub import AudioSegment
from book.models import VoiceList,VoiceType
from openai import OpenAI

load_dotenv()

ELEVEN_API_KEY = os.getenv('ELEVEN_API_KEY')
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
GROK_API_KEY=os.getenv("GROK_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)
eleven_client = ElevenLabs(api_key=ELEVEN_API_KEY)
grok_client = OpenAI(
    api_key=GROK_API_KEY,
    base_url="https://api.x.ai/v1"
)

# print("ElevenLabs 클라이언트 초기화 완료:", eleven_client)
# print("openAI:" , openAI_client)



def generate_tts(novel_text, voice_id,language_code,speed_value, style_value, similarity_value ):
    try:
        # 1️⃣ 입력 확인
        if not novel_text or not isinstance(novel_text, str):
            raise ValueError("novel_text가 비어있거나 문자열이 아닙니다.")

        print("🔊 TTS 생성 요청")
        print("📝 텍스트 길이:", len(novel_text))
        print("📝 텍스트 일부:", novel_text[:200])  # 앞 200글자만 출력
        print("스피드:",speed_value)

        # 2️⃣ 오디오 저장 경로 준비
        audio_dir = os.path.join(settings.MEDIA_ROOT, 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        filename = f"response_{uuid4().hex}.mp3"
        audio_path = os.path.join(audio_dir, filename)
        print("📂 오디오 저장 경로:", audio_path)

        # 3️⃣ ElevenLabs API 호출
        audio_stream = eleven_client.text_to_speech.convert(
            voice_id= voice_id,
            model_id="eleven_v3",
            text=novel_text,
            language_code=language_code,
            voice_settings={
                "stability": 0.5,
                "similarity": similarity_value,
                "style": style_value,
                "use_speaker_boost": False
            }
        )
        print("✅ ElevenLabs API 호출 성공")
        print("🖇️ audio_stream 타입:", type(audio_stream))

        # 4️⃣ 임시 오디오 파일로 저장
        temp_path = audio_path.replace('.mp3', '_temp.mp3')
        with open(temp_path, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)
        print("💾 임시 오디오 저장 완료:", temp_path)

        # 5️⃣ 속도 조절 (pydub 사용)
        try:
            speed_float = float(speed_value)
            speed_float = max(0.5, min(2.0, speed_float))  # 0.5~2.0 범위로 제한
        except:
            speed_float = 1.0

        print(f"🎚️ 속도 조절: {speed_float}x")

        if abs(speed_float - 1.0) > 0.01:  # 속도가 1.0이 아니면 조절
            audio = AudioSegment.from_mp3(temp_path)

            # 속도 조절: frame_rate를 변경하고 원래대로 되돌림
            # speed > 1: 빠르게, speed < 1: 느리게
            new_frame_rate = int(audio.frame_rate * speed_float)
            audio_adjusted = audio._spawn(audio.raw_data, overrides={'frame_rate': new_frame_rate})
            audio_adjusted = audio_adjusted.set_frame_rate(audio.frame_rate)

            # 최종 파일 저장
            audio_adjusted.export(audio_path, format="mp3")
            print(f"✅ 속도 조절 완료: {speed_float}x")

            # 임시 파일 삭제
            os.remove(temp_path)
        else:
            # 속도 조절 불필요시 임시 파일을 최종 파일로 이동
            os.rename(temp_path, audio_path)
            print("✅ 속도 조절 없이 저장")

        return audio_path

    except Exception as e:
        print("❌ TTS 생성 오류 발생:", e)
        traceback.print_exc()  # 🔹 어디서 오류 났는지 자세히 출력
        return None

def merge_audio_files(audio_files, pages_text=None):
    """
    여러 오디오 파일을 하나로 합치는 함수 (타임스탬프 정보 포함)

    Returns:
        tuple: (merged_audio_path, timestamps_info) 또는 (None, None)
        - merged_audio_path: 합쳐진 오디오 파일 경로
        - timestamps_info: 각 대사의 타임스탬프 정보 리스트
    """
    import traceback
    try:
        print("🎵 오디오 합치기 시작...")
        print(f"📊 총 {len(audio_files)}개의 오디오 파일")

        if not audio_files:
            print("⚠️ 합칠 오디오 파일이 없습니다.")
            return None, None, None

        # 임시 저장 폴더 확인
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'audio')
        os.makedirs(temp_dir, exist_ok=True)
        print(f"🗂 임시 폴더 확인: {temp_dir}")

        combined = None
        timestamps_info = []
        intro_silence_duration = 3000  # 시작 침묵 시간 (ms)
        cumulative_time = intro_silence_duration  # 시작 침묵 시간부터 시작

        for idx, audio_file in enumerate(audio_files):
            print(f"🔄 {idx + 1}/{len(audio_files)} 오디오 처리 중...")

            temp_path = None
            is_temp_file = False

            # 파일 경로(문자열) 또는 파일 객체 처리
            try:
                if isinstance(audio_file, str):
                    # 파일 경로인 경우 - 직접 사용
                    if os.path.exists(audio_file):
                        temp_path = audio_file
                        is_temp_file = False
                        print(f"📂 파일 경로 사용: {temp_path}")
                    else:
                        print(f"❌ 파일이 존재하지 않습니다: {audio_file}")
                        return None, None, None
                else:
                    # 파일 객체인 경우 - 임시 파일로 저장
                    temp_path = os.path.join(temp_dir, f'temp_{uuid4().hex}.mp3')
                    is_temp_file = True
                    audio_file.seek(0)  # 파일 포인터 리셋
                    if hasattr(audio_file, 'chunks'):
                        with open(temp_path, 'wb') as f:
                            for chunk in audio_file.chunks():
                                f.write(chunk)
                    else:
                        with open(temp_path, 'wb') as f:
                            f.write(audio_file.read())
                    print(f"💾 임시 파일 저장: {temp_path}")
            except Exception as e:
                print(f"❌ 파일 처리 실패: {e}")
                traceback.print_exc()
                return None, None, None

            # AudioSegment 로드
            try:
                audio_segment = AudioSegment.from_file(temp_path)
                duration = len(audio_segment)  # ms 단위
                print(f"✅ 로드 완료: {duration}ms")

                # 첫 번째가 아니면 대사 사이 침묵 시간 추가
                if idx > 0:
                    cumulative_time += 500

                page_start = cumulative_time  # startTime: 이 페이지 오디오 시작 시점

                # 오디오 길이만큼 누적
                cumulative_time += duration

                timestamp_data = {
                    'pageIndex': idx,
                    'startTime': page_start,
                    'endTime': cumulative_time
                }

                # 페이지 텍스트가 있으면 추가 (TTS용 [] 태그 제거 후 저장)
                if pages_text and idx < len(pages_text):
                    raw = pages_text[idx] or ''
                    timestamp_data['text'] = re.sub(r'\[[^\]]*\]', '', raw).strip()

                timestamps_info.append(timestamp_data)

                # 오디오 병합
                if combined is None:
                    combined = audio_segment
                else:
                    silence = AudioSegment.silent(duration=500)
                    combined = combined + silence + audio_segment

            except Exception as e:
                print(f"❌ AudioSegment 로드 실패: {e}")
                traceback.print_exc()
                # 임시 파일만 삭제 (외부에서 전달받은 파일 경로는 삭제하지 않음)
                if is_temp_file and temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                return None, None, None

            # 임시 파일만 삭제 (외부에서 전달받은 파일 경로는 삭제하지 않음)
            if is_temp_file and temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

        # 최종 오디오 export

        intro_silence = AudioSegment.silent(duration=3000)  # 원하는 길이 지정(ms)
        outro_silence  = AudioSegment.silent(duration=3000)  # 원하는 길이 지정(ms)
        combined = intro_silence + combined +outro_silence 
        output_filename = f"merged_{uuid4().hex}.mp3"
        output_path = os.path.join(temp_dir, output_filename)
        combined.export(output_path, format="mp3", bitrate="128k")  # 비트레이트 최적화
        total_duration = len(combined) / 1000
        print(f"🎉 최종 오디오 저장 완료: {output_path}")
        print(f"⏱️ 타임스탬프 정보 {len(timestamps_info)}개 생성 완료")
        print("🔥 RETURNING 3 VALUES")
        return output_path, timestamps_info,total_duration

    except Exception as e:
        print(f"❌ 오디오 합치기 최종 에러: {e}")
        traceback.print_exc()
        return None, None, None







# 사운드 효과
def sound_effect(effect_name, effect_description, duration_seconds):
    """
    사운드 이팩트 생성 함수
    effect_name: 이팩트 이름
    effect_description: 이팩트 설명
    """

    try:
        print(f"🎵 사운드 이팩트 생성: {effect_name} - {effect_description}")

        detailed_prompt=openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert sound designer. Convert the user's short Korean description "
                        "in the prompt must input the sound  first sentence"
                        "into a highly detailed, professional English prompt optimized for ElevenLabs "
                        "sound-effects generation.\n"
                        "Describe:\n"
                        "- sound source and physical characteristics\n"
                        "- environment and ambience\n"
                        "- acoustic texture (reverb, distance, resonance)\n"
                        "- emotional tone and pacing\n"
                        "Keep it under 3 sentences."
                    )
                },
                {"role": "user", "content": effect_description}
            ],
            max_tokens=120 
        )

        effect_prompt = detailed_prompt.choices[0].message.content.strip()
        effect_prompt = effect_prompt[:440]
        print("ai 가 생성한 사운드 이펙트:", effect_prompt)
        audio_stream = eleven_client.text_to_sound_effects.convert(
            text=effect_prompt,
            duration_seconds=duration_seconds,
            prompt_influence=1.0
        )

        # 파일로 저장
        audio_dir = os.path.join(settings.MEDIA_ROOT, 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        filename = f"sfx_{uuid4().hex}.mp3"
        audio_path = os.path.join(audio_dir, filename)

        with open(audio_path, 'wb') as f:
            for chunk in audio_stream:
                f.write(chunk)

        print(f"✅ 사운드 이팩트 생성 완료: {audio_path}")
        return audio_path

    except Exception as e:
        print(f"❌ 사운드 이팩트 생성 오류: {e}")
        traceback.print_exc()
        return None
    

import requests
import traceback

# 배경음

def background_music(music_name, music_description, duration_seconds=30):
    """
    배경음 생성 함수 (ElevenLabs SDK music.compose 사용)
    music_name: 음악 이름
    music_description: 음악 설명
    duration_seconds: 음악 길이 (초)
    """
    try:
        print(f"🎵 배경음 생성: {music_name} - {music_description} ({duration_seconds}초)")

        detailed_prompt = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "in the prompt must input the sound  first sentence"

                        "You are a professional music director creating concise prompts for AI-generated background music. "
                        "Rewrite the user's Korean description into a detailed English BGM prompt under 350 characters. "
                        "Describe the mood, instruments, tempo, atmosphere, and acoustic space. "
                        "Keep it to 2 sentences and explicitly say 'no vocals, no lyrics'."
                    )
                },
                {
                    "role": "user",
                    "content": music_description
                }
            ],
            max_tokens=120
        )

        # 결과 텍스트만 추출
        refined_prompt = detailed_prompt.choices[0].message.content.strip()

        # 안전장치: 430자 초과 시 자동 자르기
        refined_prompt = refined_prompt[:430]
        print("ai 가 생성한 배경음:", refined_prompt)

        # ElevenLabs SDK music.compose() 사용 (music_length_ms 단위: 밀리초)
        audio_stream = eleven_client.music.compose(
            prompt=refined_prompt,
            music_length_ms=int(duration_seconds * 1000),
            force_instrumental=True,
        )

        # 파일로 저장
        audio_dir = os.path.join(settings.MEDIA_ROOT, 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        filename = f"bgm_{uuid4().hex}.mp3"
        audio_path = os.path.join(audio_dir, filename)

        with open(audio_path, 'wb') as f:
            for chunk in audio_stream:
                f.write(chunk)

        print(f"✅ 배경음 생성 완료: {audio_path}")
        return audio_path

    except Exception as e:
        print(f"❌ 배경음 생성 오류: {e}")
        traceback.print_exc()
        return None


# 배경음과 대사 믹싱 함수
def mix_audio_with_background(dialogue_audio_path, background_tracks_info):
    """
    대사 오디오와 배경음을 믹싱하는 함수
    dialogue_audio_path: 합쳐진 대사 오디오 파일 경로
    background_tracks_info: [{audioPath, startTime, endTime, volume}] 형태의 배경음 정보 리스트
    """
    try:
        print("🎵 배경음 믹싱 시작...")

        # 대사 오디오 로드
        dialogue_audio = AudioSegment.from_mp3(dialogue_audio_path)
        dialogue_duration = len(dialogue_audio)
        print(f"📊 대사 오디오 길이: {dialogue_duration}ms")

        # 배경음이 없으면 원본 그대로 반환
        if not background_tracks_info:
            print("⚠️ 배경음이 없습니다. 원본 오디오를 반환합니다.")
            return dialogue_audio_path

        # 각 배경음 트랙 처리
        for idx, track_info in enumerate(background_tracks_info):
            bg_audio_path = track_info.get('audioPath')
            start_time = track_info.get('startTime', 0)  # ms 단위
            end_time = track_info.get('endTime', dialogue_duration)  # ms 단위
            volume_adjust = track_info.get('volume', -10)  # dB 단위 (기본: -10dB로 배경음 볼륨 낮춤)

            print(f"🎼 배경음 {idx + 1} 처리 중...")
            print(f"   - 시작: {start_time}ms, 종료: {end_time}ms, 볼륨: {volume_adjust}dB")

            # 배경음 로드
            bg_audio = AudioSegment.from_file(bg_audio_path)

            # 배경음 볼륨 조절
            bg_audio = bg_audio + volume_adjust

            # 필요한 길이 계산
            required_duration = end_time - start_time

            # 배경음이 필요한 길이보다 짧으면 반복
            if len(bg_audio) < required_duration:
                repeat_times = (required_duration // len(bg_audio)) + 1
                bg_audio = bg_audio * repeat_times

            # 필요한 길이만큼 자르기
            bg_audio = bg_audio[:required_duration]

            # 페이드 인/아웃 효과 (부드러운 전환)
            fade_duration = min(500, required_duration // 4)  # 500ms 또는 전체 길이의 1/4
            bg_audio = bg_audio.fade_in(fade_duration).fade_out(fade_duration)

            # 배경음을 적절한 위치에 오버레이
            # start_time 위치부터 bg_audio를 믹싱
            dialogue_audio = dialogue_audio.overlay(bg_audio, position=start_time)
            print(f"✅ 배경음 {idx + 1} 믹싱 완료")

        # 최종 믹싱된 오디오 저장
        output_filename = f"mixed_{uuid4().hex}.mp3"
        output_path = os.path.join(settings.MEDIA_ROOT, 'audio', output_filename)
        dialogue_audio.export(output_path, format="mp3")

        print(f"✅ 배경음 믹싱 완료: {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ 배경음 믹싱 오류: {e}")
        traceback.print_exc()
        # 오류 발생 시 원본 대사 오디오 경로 반환
        return dialogue_audio_path
    

import os
import requests
from django.utils import timezone
from django.core.files.base import ContentFile
from book.models import VoiceList, VoiceType
from elevenlabs import ElevenLabs

def sync_voices_with_type():
    """
    ElevenLabs의 User Voice / Default Voice를 DB에 넣고,
    VoiceType도 연결하며 sample_audio까지 저장
    """
    ELEVEN_API_KEY = os.getenv('ELEVEN_API_KEY')
    eleven_client = ElevenLabs(api_key=ELEVEN_API_KEY)
    
    try:
        print("ElevenLabs 클라이언트 초기화 완료:", eleven_client)

        # 1. VoiceType 생성
        user_voice_type, _ = VoiceType.objects.get_or_create(name="User Voice")
        default_voice_type, _ = VoiceType.objects.get_or_create(name="Default Voice")

        # 2. 모든 보이스 가져오기
        all_voices = eleven_client.voices.get_all().voices
        print(f"총 {len(all_voices)}개 보이스 가져옴")

        for v in all_voices:
            voice_id = getattr(v, "voice_id", None)
            if not voice_id:
                print(f"⚠️ voice_id 없음, 스킵: {getattr(v, 'name', 'unknown')}")
                continue

            # 3. DB에 저장
            voice, created = VoiceList.objects.update_or_create(
                voice_id=voice_id,
                defaults={
                    "voice_name": getattr(v, "name", "Unknown"),
                    "voice_description": getattr(v, "description", ""),
                    "language_code": getattr(v, "language", "en"),
                    "created_at": timezone.now(),
                }
            )

            # 4. 타입 연결
            if getattr(v, "is_user", False):
                voice.types.add(user_voice_type)
            else:
                voice.types.add(default_voice_type)

            # 5. sample_audio 저장
            preview_url = getattr(v, "preview_url", None)
            if preview_url:
                try:
                    r = requests.get(preview_url, timeout=10)
                    if r.status_code == 200:
                        filename = f"{voice.voice_name}_{voice.voice_id}.mp3".replace(" ", "_")
                        voice.sample_audio.save(filename, ContentFile(r.content), save=True)
                except Exception as e:
                    print(f"⚠️ 샘플 오디오 다운로드 실패: {voice.voice_name}, {e}")

            print(f"{'생성' if created else '업데이트'}: {voice.voice_name}")

        print("✅ Voice sync 완료")

    except Exception as e:
        print("❌ Voice sync 실패:", e)






from openai import OpenAI
from django.conf import settings
import os
from book.models import VoiceList, Books


def chat_with_character(book_id, message):
    """
    GROK(OpenAI Grok API) 기반 캐릭터 대화 함수
    """

    # 책 내용 로드
    try:
        book = Books.objects.get(id=book_id)
        book_info = book.description or ""
        character_name = book.character_name or "캐릭터"
    except:
        book_info = ""
        character_name = "캐릭터"

    # 프롬프트
    prompt = f"""
당신은 '{character_name}'라는 캐릭터입니다.

아래는 책의 설정입니다:

{book_info}

사용자 메시지에 '{character_name}'의 말투로 자연스럽게 대답하세요.
말투는 캐릭터 성격에 맞추고, 존댓말/반말은 상황에 맞게 자연스럽게 선택하세요.

사용자: {message}
"""

    # --------------------------
    # 🔥 GROK 호출 (grok_client)
    # --------------------------
    try:
        completion = grok_client.chat.completions.create(
            model="grok-4",   # 그록 모델 이름(넣은 키에 맞춰 변경 가능)
            messages=[
                {"role": "system", "content": "너는 소설 속 등장인물처럼 말하는 캐릭터 AI이다."},
                {"role": "user", "content": prompt}
            ]
        )
        ai_text = completion.choices[0].message.content

    except Exception as e:
        ai_text = f"[GROK 오류] {str(e)}"

    # --------------------------
    # 🔊 TTS 처리
    # --------------------------

    voice_id = "WAhoMTNdLdMoq1j3wf3I"
    language_code = "ko"

    audio_path = generate_tts(
        novel_text=ai_text,
        voice_id=voice_id,
        language_code=language_code,
        speed_value=1.0
    )

    # --------------------------
    # URL 변환
    # --------------------------
    if audio_path and os.path.exists(str(audio_path)):
        rel_path = os.path.relpath(str(audio_path), settings.MEDIA_ROOT)
        audio_url = settings.MEDIA_URL + rel_path.replace("\\", "/")
    else:
        audio_url = None

    return {
        "text": ai_text,
        "audio": audio_url,
        "debug": {
            "ai_text": ai_text,
            "audio_path": str(audio_path),
            "audio_url": audio_url,
            "character": character_name,
            "source": "grok"
        }
    }



import json
from book.models import Books
# elevenlabs client import 필요 시 추가
# from elevenlabs import ElevenLabsClient
# eleven_client = ElevenLabsClient(api_key="YOUR_API_KEY")

def chat_with_character_debug(agent_id, character_name, voice_id, book_content, user_input):
    """
    디버그용 래퍼 함수:
    실제 ElevenLabs 호출 없이, TTS 반환 대신 debug용 JSON 반환
    """
    if not agent_id or not character_name or not voice_id or not user_input:
        missing = []
        if not agent_id: missing.append("agent_id")
        if not character_name: missing.append("character_name")
        if not voice_id: missing.append("voice_id")
        if not user_input: missing.append("user_input")
        raise ValueError(f"누락된 필수 필드: {', '.join(missing)}")

    # 실제 API 호출은 주석 처리
    # response = eleven_client.conversational_ai.agents.chat(
    #     agent_id=agent_id,
    #     input=f"캐릭터 {character_name}, 내용: {book_content}, 질문: {user_input}",
    #     tts={"model_id": voice_id}
    # )

    # 디버그용 반환
    debug_response = {
        "agent_id": agent_id,
        "character_name": character_name,
        "voice_id": voice_id,
        "book_content_snippet": book_content[:100] if book_content else "",
        "user_input": user_input,
        "audio": f"오디오_데이터_시뮬레이션_for_{character_name}"
    }

    return json.dumps(debug_response)


# ==================== 서버 사이드 WebAudio 효과 ====================
import numpy as np
from scipy.signal import butter, sosfilt

# 31개 프리셋 파라미터 (webaudio-effects.js와 1:1 매칭)
WEBAUDIO_PRESETS = {
    "normal": {"filter_type": "allpass", "freq": 1000, "Q": 1, "delay": 0, "feedback": 0, "tremolo_rate": 0, "tremolo_depth": 0},
    "phone": {"filter_type": "highpass", "freq": 2000, "Q": 8, "delay": 0, "feedback": 0, "tremolo_rate": 0, "tremolo_depth": 0},
    "cave": {"filter_type": "lowpass", "freq": 600, "Q": 6, "delay": 0.45, "feedback": 0.7, "tremolo_rate": 0, "tremolo_depth": 0},
    "underwater": {"filter_type": "lowpass", "freq": 400, "Q": 2, "delay": 0.15, "feedback": 0.3, "tremolo_rate": 5, "tremolo_depth": 0.6},
    "robot": {"filter_type": "highpass", "freq": 1200, "Q": 1, "delay": 0, "feedback": 0, "tremolo_rate": 30, "tremolo_depth": 1.0},
    "ghost": {"filter_type": "bandpass", "freq": 500, "Q": 9, "delay": 0.5, "feedback": 0.8, "tremolo_rate": 3, "tremolo_depth": 0.7},
    "child": {"filter_type": "allpass", "freq": 1500, "Q": 2, "delay": 0, "feedback": 0, "tremolo_rate": 15, "tremolo_depth": 0.3},
    "old": {"filter_type": "lowpass", "freq": 700, "Q": 3, "delay": 0.2, "feedback": 0.5, "tremolo_rate": 2, "tremolo_depth": 0.2},
    "echo": {"filter_type": "allpass", "freq": 1000, "Q": 1, "delay": 0.6, "feedback": 0.7, "tremolo_rate": 0, "tremolo_depth": 0},
    "protoss": {"filter_type": "allpass", "freq": 1100, "Q": 6, "delay": 0.09, "feedback": 0.42, "tremolo_rate": 0, "tremolo_depth": 0},
    "whisper": {"filter_type": "bandpass", "freq": 1800, "Q": 4, "delay": 0.03, "feedback": 0.2, "tremolo_rate": 4, "tremolo_depth": 0.4},
    "radio": {"filter_type": "bandpass", "freq": 1800, "Q": 2, "delay": 0, "feedback": 0, "tremolo_rate": 6.5, "tremolo_depth": 0.7},
    "megaphone": {"filter_type": "highpass", "freq": 900, "Q": 5, "delay": 0.05, "feedback": 0.35, "tremolo_rate": 0, "tremolo_depth": 0},
    "demon": {"filter_type": "lowpass", "freq": 800, "Q": 3, "delay": 0.07, "feedback": 0.6, "tremolo_rate": 120, "tremolo_depth": 0.9},
    "angel": {"filter_type": "highpass", "freq": 800, "Q": 5, "delay": 0.35, "feedback": 0.65, "tremolo_rate": 1.5, "tremolo_depth": 0.4},
    "vader": {"filter_type": "bandpass", "freq": 400, "Q": 8, "delay": 0.04, "feedback": 0.4, "tremolo_rate": 80, "tremolo_depth": 0.6},
    "giant": {"filter_type": "lowpass", "freq": 300, "Q": 4, "delay": 0.6, "feedback": 0.7, "tremolo_rate": 0, "tremolo_depth": 0},
    "tiny": {"filter_type": "highpass", "freq": 2200, "Q": 6, "delay": 0.02, "feedback": 0.3, "tremolo_rate": 8, "tremolo_depth": 0.4},
    "possessed": {"filter_type": "bandpass", "freq": 600, "Q": 5, "delay": 0.07, "feedback": 0.7, "tremolo_rate": 100, "tremolo_depth": 0.9},
    "horror": {"filter_type": "bandpass", "freq": 620, "Q": 14, "delay": 0.38, "feedback": 0.78, "tremolo_rate": 2.8, "tremolo_depth": 0.85},
    "helium": {"filter_type": "highpass", "freq": 2900, "Q": 7, "delay": 0.015, "feedback": 0.18, "tremolo_rate": 12, "tremolo_depth": 0.5},
    "timewarp": {"filter_type": "lowpass", "freq": 580, "Q": 9, "delay": 0.42, "feedback": 0.89, "tremolo_rate": 0.25, "tremolo_depth": 0.8},
    "glitch": {"filter_type": "bandpass", "freq": 1300, "Q": 22, "delay": 0.008, "feedback": 0.35, "tremolo_rate": 280, "tremolo_depth": 0.98},
    "choir": {"filter_type": "allpass", "freq": 1600, "Q": 5, "delay": 0.28, "feedback": 0.72, "tremolo_rate": 1.1, "tremolo_depth": 0.5},
    "hyperpop": {"filter_type": "highpass", "freq": 3200, "Q": 14, "delay": 0.018, "feedback": 0.42, "tremolo_rate": 220, "tremolo_depth": 0.9},
    "vaporwave": {"filter_type": "lowpass", "freq": 3400, "Q": 2, "delay": 0.38, "feedback": 0.78, "tremolo_rate": 0.35, "tremolo_depth": 0.8},
    "darksynth": {"filter_type": "bandpass", "freq": 950, "Q": 11, "delay": 0.24, "feedback": 0.70, "tremolo_rate": 130, "tremolo_depth": 0.55},
    "lofi-girl": {"filter_type": "lowpass", "freq": 4200, "Q": 1.8, "delay": 0.45, "feedback": 0.62, "tremolo_rate": 0.12, "tremolo_depth": 0.35},
    "bitcrush-voice": {"filter_type": "bandpass", "freq": 2200, "Q": 28, "delay": 0.004, "feedback": 0.25, "tremolo_rate": 420, "tremolo_depth": 0.98},
    "portal": {"filter_type": "allpass", "freq": 750, "Q": 18, "delay": 0.65, "feedback": 0.94, "tremolo_rate": 0.7, "tremolo_depth": 0.9},
    "neoncity": {"filter_type": "bandpass", "freq": 1150, "Q": 9, "delay": 0.52, "feedback": 0.80, "tremolo_rate": 2.8, "tremolo_depth": 0.45},
    "ghost-in-machine": {"filter_type": "bandpass", "freq": 780, "Q": 20, "delay": 0.09, "feedback": 0.58, "tremolo_rate": 190, "tremolo_depth": 0.88},
}


def _apply_biquad_filter(samples, sample_rate, filter_type, freq, Q):
    """scipy butter 필터로 WebAudio BiquadFilter 재현"""
    nyq = sample_rate / 2.0
    freq = min(freq, nyq - 1)

    if filter_type == "allpass":
        return samples  # allpass = 통과
    elif filter_type == "lowpass":
        sos = butter(2, freq / nyq, btype='low', output='sos')
    elif filter_type == "highpass":
        sos = butter(2, freq / nyq, btype='high', output='sos')
    elif filter_type == "bandpass":
        low = max(freq / (Q if Q > 0 else 1), 20) / nyq
        high = min(freq * (Q if Q > 0 else 1), nyq - 1) / nyq
        if low >= high:
            low = max(20 / nyq, 0.001)
            high = min(0.999, freq * 2 / nyq)
        sos = butter(2, [low, high], btype='band', output='sos')
    else:
        return samples

    return sosfilt(sos, samples).astype(np.float32)


def _apply_delay(samples, sample_rate, delay_time, feedback_gain, max_iterations=8):
    """딜레이 + 피드백 효과"""
    if delay_time <= 0 and feedback_gain <= 0:
        return samples

    delay_samples = int(delay_time * sample_rate)
    if delay_samples <= 0:
        return samples

    output = samples.copy()
    delayed = samples.copy()

    for i in range(max_iterations):
        gain = feedback_gain ** (i + 1)
        if gain < 0.01:
            break
        padded = np.zeros(len(samples), dtype=np.float32)
        start = delay_samples * (i + 1)
        if start >= len(samples):
            break
        end = min(start + len(delayed), len(samples))
        padded[start:end] = delayed[:end - start] * gain
        output += padded

    # 클리핑 방지
    max_val = np.max(np.abs(output))
    if max_val > 1.0:
        output = output / max_val
    return output


def _apply_tremolo(samples, sample_rate, rate, depth):
    """트레몰로 (AM 변조) 효과"""
    if rate <= 0 or depth <= 0:
        return samples

    t = np.arange(len(samples)) / sample_rate
    # depth 0~1: 0이면 변조 없음, 1이면 최대 변조
    modulation = 1.0 - depth * 0.5 * (1.0 + np.sin(2 * np.pi * rate * t))
    return (samples * modulation).astype(np.float32)


def generate_silence(duration_seconds):
    """
    지정된 길이의 무음 MP3 파일 생성 (44100Hz stereo — TTS 오디오 포맷에 맞춤).
    silence block이 삽입된 위치에서 BGM은 계속 재생됨 (mix_bgm 단계에서 처리).
    """
    from pydub import AudioSegment
    import tempfile

    ms = int(float(duration_seconds) * 1000)
    # TTS 오디오와 동일한 포맷(44100Hz stereo)으로 생성해야 merge 시 포맷 충돌 없음
    silence = AudioSegment.silent(duration=ms, frame_rate=44100)
    silence = silence.set_channels(2).set_sample_width(2)

    tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    tmp_path = tmp.name
    tmp.close()

    silence.export(tmp_path, format='mp3', bitrate='128k')
    return tmp_path


def merge_duet_audio(audio_paths, mode='alternate'):
    """
    두 캐릭터 음성을 하나로 합치는 함수.
    mode='alternate' : TTS_A → 200ms 침묵 → TTS_B (교차 대화)
    mode='overlap'   : TTS_A + TTS_B 동시 재생 (합창/동시 대사)
    """
    from pydub import AudioSegment
    import tempfile

    if not audio_paths:
        return None

    segments = []
    for p in audio_paths:
        try:
            seg = AudioSegment.from_file(p)
            segments.append(seg)
        except Exception as e:
            print(f"⚠️ 듀엣 오디오 로드 실패: {p} — {e}")

    if not segments:
        return None

    if mode == 'overlap':
        # 모든 세그먼트를 동일 포맷으로 정규화 (frame_rate, channels)
        # AudioSegment.silent() 기본 frame_rate=11025Hz → ElevenLabs TTS와 불일치 방지
        ref = segments[0]
        normalized = []
        for seg in segments:
            if seg.frame_rate != ref.frame_rate or seg.channels != ref.channels:
                seg = seg.set_frame_rate(ref.frame_rate).set_channels(ref.channels)
            normalized.append(seg)

        # 가장 긴 세그먼트 기준으로 동일 포맷 무음 패딩
        max_len = max(len(s) for s in normalized)
        padded = [
            s + AudioSegment.silent(duration=max_len - len(s),
                                    frame_rate=ref.frame_rate).set_channels(ref.channels)
            for s in normalized
        ]

        combined = padded[0]
        for seg in padded[1:]:
            combined = combined.overlay(seg)
    else:  # alternate
        gap = AudioSegment.silent(duration=200)
        combined = segments[0]
        for seg in segments[1:]:
            combined = combined + gap + seg

    tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    tmp_path = tmp.name
    tmp.close()
    combined.export(tmp_path, format='mp3', bitrate='128k')
    return tmp_path


def apply_webaudio_effect(audio_path, effect_name):
    """
    오디오 파일에 WebAudio 프리셋 효과를 적용하여 새 파일로 저장.
    webaudio-effects.js의 31개 프리셋을 서버 사이드로 재현.

    Args:
        audio_path: MP3/WAV 오디오 파일 경로
        effect_name: 프리셋 이름 (e.g. "phone", "cave", "horror")

    Returns:
        새로운 오디오 파일 경로 (effect가 적용된)
    """
    if effect_name == "normal" or effect_name not in WEBAUDIO_PRESETS:
        return audio_path

    preset = WEBAUDIO_PRESETS[effect_name]
    print(f"🎛️ WebAudio 효과 적용: {effect_name}")

    try:
        # 오디오 로드
        audio = AudioSegment.from_file(audio_path)
        sample_rate = audio.frame_rate
        channels = audio.channels

        # numpy 배열로 변환 (float32, -1~1 범위)
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples = samples / (2 ** 15)  # 16bit → float

        # 스테레오면 모노로 처리 후 다시 스테레오로
        if channels == 2:
            left = samples[0::2]
            right = samples[1::2]
            # 양 채널에 동일 효과 적용
            left = _process_channel(left, sample_rate, preset)
            right = _process_channel(right, sample_rate, preset)
            # 인터리브
            samples = np.empty(len(left) + len(right), dtype=np.float32)
            samples[0::2] = left
            samples[1::2] = right
        else:
            samples = _process_channel(samples, sample_rate, preset)

        # float → 16bit int로 변환
        samples = np.clip(samples, -1.0, 1.0)
        samples_int = (samples * (2 ** 15 - 1)).astype(np.int16)

        # AudioSegment로 재조립
        processed = AudioSegment(
            data=samples_int.tobytes(),
            sample_width=2,
            frame_rate=sample_rate,
            channels=channels
        )

        # 새 파일로 저장
        output_filename = f"fx_{effect_name}_{uuid4().hex}.mp3"
        output_path = os.path.join(settings.MEDIA_ROOT, 'audio', output_filename)
        processed.export(output_path, format="mp3", bitrate="192k")

        print(f"✅ WebAudio 효과 적용 완료: {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ WebAudio 효과 적용 오류 ({effect_name}): {e}")
        traceback.print_exc()
        return audio_path


def _process_channel(samples, sample_rate, preset):
    """단일 채널에 필터 + 딜레이 + 트레몰로 체인 적용"""
    # 1. 필터 적용
    filtered = _apply_biquad_filter(
        samples, sample_rate,
        preset["filter_type"],
        preset["freq"],
        preset["Q"]
    )

    # 2. 딜레이 적용
    delayed = _apply_delay(
        filtered, sample_rate,
        preset["delay"],
        preset["feedback"]
    )

    # 3. 트레몰로 적용
    result = _apply_tremolo(
        delayed, sample_rate,
        preset["tremolo_rate"],
        preset["tremolo_depth"]
    )

    return result

