from django.shortcuts import render
import os
from dotenv import load_dotenv
from django.conf import settings
from uuid import uuid4
from elevenlabs import ElevenLabs
from django.http import FileResponse
from django.views.decorators.csrf import csrf_exempt
import json
from pydub import AudioSegment

# .env에서 API 키 로드
load_dotenv()
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
eleven_client = ElevenLabs(api_key=ELEVEN_API_KEY)

# ------------------------
# 사운드 효과 생성 함수
# ------------------------
def generate_sound_effect(sound_input):
    sound_dir = os.path.join(settings.MEDIA_ROOT, "effectSound")
    os.makedirs(sound_dir, exist_ok=True)
    filename = f"sound_{uuid4().hex}.mp3"
    sound_path = os.path.join(sound_dir, filename)

    sound_effect = eleven_client.text_to_sound_effects.convert(
        text=sound_input,
        duration_seconds=10,
        prompt_influence=1,
        model_id='eleven_text_to_sound_v2'

    )

    with open(sound_path, 'wb') as f:
        for chunk in sound_effect:
            f.write(chunk)

    return sound_path

# ------------------------
# TTS 생성 함수
# ------------------------
def generate_tts(textinput):
    audio_dir = os.path.join(settings.MEDIA_ROOT, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    filename = f"audio_{uuid4().hex}.mp3"
    audio_path = os.path.join(audio_dir, filename)

    audio_make = eleven_client.text_to_speech.convert(
        voice_id="si0svtk05vPEuvwAW93c",
        model_id="eleven_v3",
        text=textinput,
        language_code="ko",
        voice_settings={
            "stability": 1,
            "style": 1,
            "speed": 1.2,
            "use_speaker_boost": True
        }
    )

    with open(audio_path, 'wb') as f:
        for chunk in audio_make:
            f.write(chunk)

    return audio_path

# ------------------------
# TTS 전용 엔드포인트
# ------------------------
@csrf_exempt
def test_tts(request):
    if request.method == "POST":
        data = json.loads(request.body)
        textinput = data.get("text", "테스트용 기본 텍스트")

        audio_path = generate_tts(textinput)
        return FileResponse(open(audio_path, "rb"), content_type="audio/mpeg")

    return render(request, "testpj/test_tts.html")

# ------------------------
# 사운드 효과 전용 엔드포인트
# ------------------------
@csrf_exempt
def soundpg(request):
    if request.method == "POST":
        data = json.loads(request.body)
        sound_input = data.get("soundText", "none")

        sound_path = generate_sound_effect(sound_input)
        return FileResponse(open(sound_path, "rb"), content_type="audio/mpeg")

    return render(request, "testpj/test.html")

# ------------------------
# 편집 합성 엔드포인트
# ------------------------
@csrf_exempt
def render_audio(request):
    if request.method=="POST":
        data = json.loads(request.body)
        tracks = data.get("tracks", [])
        final_audio = None

        for clip in tracks:
            seg = AudioSegment.from_file(clip['file'])
            volume = clip.get('volume', 0)
            seg = seg + volume
            start_ms = int(clip.get('start', 0) * 1000)
            if final_audio is None:
                final_audio = AudioSegment.silent(duration=start_ms) + seg
            else:
                final_audio = final_audio.overlay(seg, position=start_ms)

        output_path = os.path.join(settings.MEDIA_ROOT, f"final_{uuid4().hex}.mp3")
        final_audio.export(output_path, format="mp3")
        return FileResponse(open(output_path,'rb'), content_type="audio/mpeg")