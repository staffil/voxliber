from celery import shared_task
from book.utils import merge_audio_files, mix_audio_with_background

@shared_task(bind=True)
def generate_full_audio_task(
    self,
    audio_files_info,
    pages_text,
    background_tracks_info=None
):
    merged_path, timestamps = merge_audio_files(
        audio_files_info,
        pages_text
    )

    if background_tracks_info:
        merged_path = mix_audio_with_background(
            merged_path,
            background_tracks_info
        )

    return {
        "audio_path": merged_path,
        "timestamps": timestamps
    }
