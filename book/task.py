from celery import shared_task
from book.utils import generate_tts, merge_audio_files, mix_audio_with_background
import os
import json
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO

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


@shared_task(bind=True, time_limit=7200)  # 2시간 제한
def merge_audio_task(self, audio_files_data, background_tracks_data=None, pages_text=None):
    """
    오디오 파일들을 병합하는 Celery 태스크

    Args:
        audio_files_data: 오디오 파일 경로 리스트
        background_tracks_data: 배경음악 정보 리스트 (optional)
        pages_text: 페이지 텍스트 리스트 (optional)

    Returns:
        dict: {
            'success': bool,
            'merged_audio_path': str,
            'merged_audio_url': str,
            'timestamps': list,
            'error': str (if failed)
        }
    """
    temp_files_to_cleanup = []
    try:
        # 진행률 업데이트
        self.update_state(state='PROGRESS', meta={'status': '오디오 파일 병합 시작...', 'progress': 10})

        # 임시 파일 추적 (나중에 삭제)
        temp_files_to_cleanup.extend(audio_files_data)

        # 오디오 파일 병합
        merged_audio_path, dialogue_durations = merge_audio_files(audio_files_data, pages_text)

        if not merged_audio_path or not os.path.exists(merged_audio_path):
            return {
                'success': False,
                'error': '오디오 병합 실패'
            }

        self.update_state(state='PROGRESS', meta={'status': '오디오 병합 완료, 배경음 처리 중...', 'progress': 60})

        # 배경음 처리
        final_audio_path = merged_audio_path
        if background_tracks_data and dialogue_durations:
            # 배경음 타이밍 정보 계산
            for track in background_tracks_data:
                start_page = track.get('startPage', 0)
                end_page = track.get('endPage', 0)

                # 시작/종료 시간 계산
                start_time = 0 if start_page == 0 else dialogue_durations[start_page - 1]['endTime']
                end_time = dialogue_durations[end_page]['endTime'] if end_page < len(dialogue_durations) else dialogue_durations[-1]['endTime']

                track['startTime'] = start_time
                track['endTime'] = end_time

                # 임시 배경음 파일도 나중에 삭제 목록에 추가
                temp_files_to_cleanup.append(track['audioPath'])

            final_audio_path = mix_audio_with_background(
                merged_audio_path,
                background_tracks_data
            )

            if not final_audio_path:
                final_audio_path = merged_audio_path
            elif final_audio_path != merged_audio_path:
                # 배경음 믹싱 후 원본 대사 오디오 삭제
                if os.path.exists(merged_audio_path):
                    os.remove(merged_audio_path)

        self.update_state(state='PROGRESS', meta={'status': '최종 파일 생성 중...', 'progress': 90})

        # URL 생성
        rel_path = os.path.relpath(final_audio_path, settings.MEDIA_ROOT)
        audio_url = settings.MEDIA_URL + rel_path.replace("\\", "/")

        # 임시 파일 정리
        for temp_file in temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"🗑️ 임시 파일 삭제: {temp_file}")
            except Exception as cleanup_error:
                print(f"⚠️ 임시 파일 삭제 실패: {temp_file}, {cleanup_error}")

        return {
            'success': True,
            'merged_audio_path': final_audio_path,
            'merged_audio_url': audio_url,
            'timestamps': dialogue_durations or []
        }

    except Exception as e:
        import traceback
        error_msg = f"오디오 병합 중 오류 발생: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)

        # 실패시에도 임시 파일 정리
        for temp_file in temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

        return {
            'success': False,
            'error': error_msg
        }
