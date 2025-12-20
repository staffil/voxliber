# tts 생성 (디버깅용)
import os
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



def generate_tts(novel_text, voice_id,language_code,speed_value ):
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
                "similarity": 0.5,
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
    ffmpeg concat 기반 오디오 병합 + 타임스탬프 유지
    """
    import os
    import subprocess
    from uuid import uuid4
    from django.conf import settings

    print("🎵 오디오 합치기 시작...")
    print(f"📊 총 {len(audio_files)}개의 오디오 파일")

    if not audio_files:
        return None, None

    temp_dir = os.path.join(settings.MEDIA_ROOT, "audio")
    os.makedirs(temp_dir, exist_ok=True)

    concat_list_path = os.path.join(temp_dir, f"concat_{uuid4().hex}.txt")
    output_path = os.path.join(temp_dir, f"merged_{uuid4().hex}.mp3")

    timestamps_info = []
    cumulative_time = 3000  # intro silence 기준

    # 침묵 파일 준비
    intro_silence = os.path.join(temp_dir, "intro_3000ms.mp3")
    middle_silence = os.path.join(temp_dir, "middle_500ms.mp3")
    outro_silence = os.path.join(temp_dir, "outro_3000ms.mp3")

    def create_silence(duration_ms, path):
        if os.path.exists(path):
            return
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration_ms / 1000),
            "-q:a", "9",
            path
        ], check=True)

    create_silence(3000, intro_silence)
    create_silence(500, middle_silence)
    create_silence(3000, outro_silence)

    with open(concat_list_path, "w", encoding="utf-8") as f:
        f.write(f"file '{intro_silence}'\n")

        for idx, audio_file in enumerate(audio_files):
            temp_audio_path = os.path.join(temp_dir, f"voice_{uuid4().hex}.mp3")

            audio_file.seek(0)
            if hasattr(audio_file, "chunks"):
                with open(temp_audio_path, "wb") as out:
                    for chunk in audio_file.chunks():
                        out.write(chunk)
            else:
                with open(temp_audio_path, "wb") as out:
                    out.write(audio_file.read())

            duration_sec = float(subprocess.check_output([
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                temp_audio_path
            ]).decode().strip())

            duration_ms = int(duration_sec * 1000)

            if idx > 0:
                cumulative_time += 500
                f.write(f"file '{middle_silence}'\n")

            start_time = cumulative_time
            cumulative_time += duration_ms

            timestamps_info.append({
                "pageIndex": idx,
                "startTime": start_time,
                "endTime": cumulative_time,
                "text": pages_text[idx] if pages_text and idx < len(pages_text) else None
            })

            f.write(f"file '{temp_audio_path}'\n")

        f.write(f"file '{outro_silence}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        output_path
    ], check=True)

    print(f"🎉 최종 오디오 저장 완료: {output_path}")
    return output_path, timestamps_info



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
            duration_seconds=duration_seconds,  # 자동 길이
            prompt_influence=1.0
        )

        print("✅ 사운드 이팩트 생성 완료")
        return audio_stream

    except Exception as e:
        print(f"❌ 사운드 이팩트 생성 오류: {e}")
        traceback.print_exc()
        return None
    

import requests
import traceback

# 배경음

def background_music(music_name, music_description, duration_seconds=30):
    """
    배경음 생성 함수 (REST API 기반)
    music_name: 음악 이름
    music_description: 음악 설명
    duration_seconds: 음악 길이 (초)
    """
    try:
        print(f"🎵 배경음 생성: {music_name} - {music_description} ({duration_seconds}초)")

        url = "https://api.elevenlabs.io/v1/music/generate"
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

        # 안전장치: 450자 초과 시 자동 자르기
        refined_prompt = refined_prompt[:430]
        print("ai 가 생성한 배경음:", refined_prompt)

        payload = {
            "prompt": refined_prompt,
            "duration_seconds": duration_seconds,
            "generation_settings": {
                "prompt_influence": 1.0,
            }
        }

        headers = {
            "xi-api-key": ELEVEN_API_KEY,
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=payload, stream=True)

        if response.status_code != 200:
            print("❌ Music API Error:", response.text)
            return None

        print("✅ 배경음 생성 완료")
        return response.iter_content(chunk_size=1024)

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

