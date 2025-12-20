from celery import shared_task
from book.utils import generate_tts, merge_audio_files
import os
from django.conf import settings

@shared_task(bind=True)
def generate_tts_task(
    self,
    text,
    voice_id,
    language_code,
    speed
):
    audio_path = generate_tts(
        novel_text=text,
        voice_id=voice_id,
        language_code=language_code,
        speed_value=speed
    )

    if audio_path and os.path.exists(audio_path):
        rel_path = os.path.relpath(audio_path, settings.MEDIA_ROOT)
        audio_url = settings.MEDIA_URL + rel_path.replace("\\", "/")
    else:
        audio_url = None

    return {
        "audio_path": audio_path,
        "audio_url": audio_url
    }


@shared_task
def generate_full_audio_pipeline(text_list, voice_id, lang, speed):
    audio_paths = []

    for text in text_list:
        path = generate_tts(text, voice_id, lang, speed)
        audio_paths.append(path)

    merged_path, timestamps = merge_audio_files(audio_paths, text_list)

    return {
        "audio_path": merged_path,
        "timestamps": timestamps
    }
