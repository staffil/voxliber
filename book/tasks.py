from celery import shared_task
from book.utils import generate_tts, merge_audio_files, mix_audio_with_background, apply_webaudio_effect, sound_effect, background_music, merge_duet_audio
import os
import json
import math
import traceback
from django.conf import settings
from django.core.files import File


@shared_task(bind=True)
def generate_tts_task(self, text, voice_id, language_code, speed):
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
        "timestamps": timestamps,
    }


@shared_task(bind=True, time_limit=7200)
def merge_audio_task(self, audio_files_data, background_tracks_data=None, pages_text=None):
    """
    오디오 파일들을 병합하는 Celery 태스크 (기존 book_serialization용)
    """
    temp_files_to_cleanup = []
    try:
        self.update_state(state='PROGRESS', meta={'status': '오디오 파일 병합 시작...', 'progress': 10})
        temp_files_to_cleanup.extend(audio_files_data)

        merged_audio_path, dialogue_durations, total_duration = merge_audio_files(audio_files_data, pages_text)

        if not merged_audio_path or not os.path.exists(merged_audio_path):
            return {'success': False, 'error': '오디오 병합 실패'}

        self.update_state(state='PROGRESS', meta={'status': '오디오 병합 완료, 배경음 처리 중...', 'progress': 60})

        final_audio_path = merged_audio_path
        if background_tracks_data and dialogue_durations:
            for track in background_tracks_data:
                start_page = track.get('startPage', 0)
                end_page = track.get('endPage', 0)
                start_time = 0 if start_page == 0 else dialogue_durations[start_page - 1]['endTime']
                end_time = dialogue_durations[end_page]['endTime'] if end_page < len(dialogue_durations) else dialogue_durations[-1]['endTime']
                track['startTime'] = start_time
                track['endTime'] = end_time
                temp_files_to_cleanup.append(track['audioPath'])

            final_audio_path = mix_audio_with_background(merged_audio_path, background_tracks_data)

            if not final_audio_path:
                final_audio_path = merged_audio_path
            elif final_audio_path != merged_audio_path:
                if os.path.exists(merged_audio_path):
                    os.remove(merged_audio_path)

        self.update_state(state='PROGRESS', meta={'status': '최종 파일 생성 중...', 'progress': 90})

        rel_path = os.path.relpath(final_audio_path, settings.MEDIA_ROOT)
        audio_url = settings.MEDIA_URL + rel_path.replace("\\", "/")

        for temp_file in temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as cleanup_error:
                print(f"임시 파일 삭제 실패: {temp_file}, {cleanup_error}")

        return {
            'success': True,
            'merged_audio_path': final_audio_path,
            'merged_audio_url': audio_url,
            'timestamps': dialogue_durations or [],
            'total_duration': total_duration
        }

    except Exception as e:
        error_msg = f"오디오 병합 중 오류 발생: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        for temp_file in temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        return {'success': False, 'error': error_msg}


# ==================== Fast 생성기 전용 배치 태스크 ====================
@shared_task(bind=True, time_limit=7200, soft_time_limit=6600)
def process_batch_audiobook(self, data, user_id):
    """
    배치 JSON을 Celery에서 비동기 처리:
    create_bgm → create_sfx → create_episode (TTS + WebAudio) → mix_bgm

    진행률을 실시간으로 업데이트하여 프론트에서 폴링 가능.
    """
    from book.models import BackgroundMusicLibrary, SoundEffectLibrary, Content, Books
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return {'success': False, 'error': '사용자를 찾을 수 없습니다'}

    steps = data.get('steps', [])
    if not steps:
        return {'success': False, 'error': 'steps가 비어있습니다'}

    book_uuid = data.get('book_uuid', '')
    book = None
    if book_uuid:
        book = Books.objects.filter(public_uuid=book_uuid, user=user).first()
        if not book:
            return {'success': False, 'error': f'책을 찾을 수 없습니다: {book_uuid}'}

    total_steps = len(steps)
    results = {}
    warnings = []
    bgm_counter = 0
    sfx_counter = 0
    created_episode_info = None

    for step_idx, step in enumerate(steps):
        action = step.get('action', '')
        progress = int((step_idx / total_steps) * 100)

        try:
            # ==================== BGM 생성 ====================
            if action == 'create_bgm':
                bgm_counter += 1
                music_name = step.get('music_name', f'BGM_{bgm_counter}')
                music_desc = step.get('music_description', '')
                duration = step.get('duration_seconds', 120)

                print(f"🎵 [create_bgm] 시작 — name={repr(music_name)}, desc={repr(music_desc)}, duration={duration}s")

                self.update_state(state='PROGRESS', meta={
                    'status': f'배경음 생성 중: {music_name}',
                    'progress': progress,
                    'current_step': step_idx + 1,
                    'total_steps': total_steps
                })

                audio_path = background_music(music_name, music_desc, duration)
                print(f"🎵 [create_bgm] background_music() 반환값: {repr(audio_path)}")
                if not audio_path:
                    msg = f'배경음 생성 실패: {music_name} (API 오류 — Celery 로그 확인)'
                    print(f"⚠️ {msg}")
                    warnings.append(msg)
                    bgm_counter -= 1  # 카운터 되돌림
                    continue
                bgm_obj = BackgroundMusicLibrary(
                    user=user,
                    music_name=music_name,
                    music_description=music_desc,
                    duration_seconds=duration
                )
                with open(audio_path, 'rb') as f:
                    bgm_obj.audio_file.save(os.path.basename(audio_path), File(f), save=True)
                results[f'$bgm_{bgm_counter}'] = str(bgm_obj.id)
                print(f"✅ 배경음 생성 완료: ID={bgm_obj.id}, $bgm_{bgm_counter} → {bgm_obj.id}")

            # ==================== SFX 생성 ====================
            elif action == 'create_sfx':
                sfx_counter += 1
                effect_name = step.get('effect_name', f'SFX_{sfx_counter}')
                effect_desc = step.get('effect_description', '')
                duration = step.get('duration_seconds', 5)

                print(f"🔊 [create_sfx] 시작 — name={repr(effect_name)}, desc={repr(effect_desc)}, duration={duration}s")

                self.update_state(state='PROGRESS', meta={
                    'status': f'효과음 생성 중: {effect_name}',
                    'progress': progress,
                    'current_step': step_idx + 1,
                    'total_steps': total_steps
                })

                audio_path = sound_effect(effect_name, effect_desc, duration)
                print(f"🔊 [create_sfx] sound_effect() 반환값: {repr(audio_path)}")
                if not audio_path:
                    msg = f'효과음 생성 실패: {effect_name} (API 오류 — Celery 로그 확인)'
                    print(f"⚠️ {msg}")
                    warnings.append(msg)
                    sfx_counter -= 1  # 카운터 되돌림
                    continue
                sfx_obj = SoundEffectLibrary(
                    user=user,
                    effect_name=effect_name,
                    effect_description=effect_desc,
                )
                with open(audio_path, 'rb') as f:
                    sfx_obj.audio_file.save(os.path.basename(audio_path), File(f), save=True)
                results[f'$sfx_{sfx_counter}'] = str(sfx_obj.id)
                print(f"✅ 효과음 생성 완료: ID={sfx_obj.id}, $sfx_{sfx_counter} → {sfx_obj.id}")

            # ==================== 에피소드 생성 (TTS + WebAudio) ====================
            elif action == 'create_episode':
                if not book:
                    return {'success': False, 'error': 'book_uuid가 필요합니다'}

                ep_number = step.get('episode_number', 1)
                ep_title = step.get('episode_title', f'에피소드 {ep_number}')
                pages = step.get('pages', [])

                if not pages:
                    return {'success': False, 'error': '페이지가 비어있습니다'}

                # 페이지별 TTS 생성
                audio_files = []
                successful_texts = []  # TTS 성공한 페이지 텍스트 (timestamps 싱크용)
                page_infos = []  # PageAudio 저장용: audio_files와 동일 순서
                for page_idx, page in enumerate(pages):
                    # 기존 TTS 재사용 (_skip_tts 플래그)
                    if page.get('_skip_tts') and page.get('_existing_content_uuid') and page.get('_existing_page_num'):
                        try:
                            from book.models import PageAudio as _PA
                            existing_pa = _PA.objects.filter(
                                content__public_uuid=page['_existing_content_uuid'],
                                page_number=page['_existing_page_num']
                            ).first()
                            if existing_pa and existing_pa.audio_file:
                                import shutil as _shutil, uuid as _uuid2
                                old_path = existing_pa.audio_file.path
                                new_name = f'tts_reuse_{_uuid2.uuid4().hex}.mp3'
                                new_path = os.path.join(settings.MEDIA_ROOT, 'audio', new_name)
                                _shutil.copy2(old_path, new_path)
                                page_infos.append({
                                    'page_type': existing_pa.page_type or 'tts',
                                    'text': existing_pa.text or page.get('text', ''),
                                    'voice_id': existing_pa.voice_id or page.get('voice_id', ''),
                                    'speed_value': existing_pa.speed_value,
                                    'style_value': existing_pa.style_value,
                                    'similarity_value': existing_pa.similarity_value,
                                    'webaudio_effect': existing_pa.webaudio_effect or '',
                                    'audio_path': new_path,
                                })
                                audio_files.append(new_path)
                                successful_texts.append(existing_pa.text or page.get('text', ''))
                                print(f"♻️ TTS 재사용 (페이지 {page_idx+1})")
                                continue
                        except Exception as e:
                            print(f"⚠️ TTS 재사용 실패, 새로 생성합니다: {e}")

                    # 무음 페이지 처리 (BGM은 mix_bgm 단계에서 merged audio 전체에 걸쳐 재생)
                    silence_seconds = page.get('silence_seconds', 0)
                    if silence_seconds and float(silence_seconds) > 0:
                        try:
                            from book.utils import generate_silence
                            silence_path = generate_silence(float(silence_seconds))
                            if silence_path and os.path.exists(silence_path):
                                audio_files.append(silence_path)
                                successful_texts.append('')
                                page_infos.append({'page_type': 'silence', 'text': '', 'voice_id': '', 'speed_value': 1.0, 'style_value': 0.0, 'similarity_value': 0.75, 'webaudio_effect': 'normal', 'audio_path': silence_path})
                                print(f"🔇 무음 삽입: {silence_seconds}초")
                        except Exception as e:
                            print(f"⚠️ 무음 생성 오류: {e}")
                        continue

                    # 2인 대화(duet) 처리
                    voices = page.get('voices', [])
                    if voices:
                        duet_paths = []
                        for ve in voices:
                            v_text = ve.get('text', '')
                            v_voice_id = ve.get('voice_id', '')
                            if not v_text or not v_voice_id:
                                continue
                            try:
                                v_tts = generate_tts(v_text, v_voice_id, 'ko', 1.0, 0.0, 0.75)
                                if not v_tts:
                                    continue
                                v_path = v_tts if isinstance(v_tts, str) else v_tts.path
                                v_effect = ve.get('webaudio_effect', '')
                                if v_effect and v_effect != 'normal':
                                    v_path = apply_webaudio_effect(v_path, v_effect) or v_path
                                duet_paths.append(v_path)
                            except Exception as e:
                                print(f"⚠️ 듀엣 TTS 오류: {e}")
                        if duet_paths:
                            try:
                                duet_mp3 = merge_duet_audio(duet_paths, mode=page.get('mode', 'alternate'))
                                if duet_mp3:
                                    audio_files.append(duet_mp3)
                                    combined_text = '\n'.join(v.get('text', '') for v in voices if v.get('text'))
                                    successful_texts.append(combined_text)
                                    page_infos.append({'page_type': 'duet', 'text': combined_text, 'voice_id': '', 'speed_value': 1.0, 'style_value': 0.0, 'similarity_value': 0.75, 'webaudio_effect': 'normal', 'audio_path': duet_mp3})
                                    print(f"🎭 듀엣 페이지 생성 완료 ({page.get('mode','alternate')} 모드)")
                            except Exception as e:
                                print(f"⚠️ 듀엣 병합 오류 (페이지 {page_idx+1}): {e}")
                        continue

                    text = page.get('text', '')
                    voice_id = page.get('voice_id', '')

                    if not text or not voice_id:
                        continue

                    self.update_state(state='PROGRESS', meta={
                        'status': f'TTS 생성 중: {page_idx + 1}/{len(pages)} 페이지',
                        'progress': progress + int((page_idx / len(pages)) * (100 / total_steps)),
                        'current_step': step_idx + 1,
                        'total_steps': total_steps
                    })

                    try:
                        tts_file = generate_tts(text, voice_id, 'ko', 1.0, 0.0, 0.75)
                        
                        # 🔥 파일 유효성 검사 추가
                        if not tts_file:
                            print(f"⚠️ TTS 생성 실패: {page_idx + 1}번 페이지")
                            continue
                            
                        tts_path = tts_file if isinstance(tts_file, str) else tts_file.path
                        
                        # 🔥 파일 존재 및 크기 확인
                        if not os.path.exists(tts_path):
                            print(f"⚠️ TTS 파일 없음: {tts_path}")
                            continue
                            
                        if os.path.getsize(tts_path) < 1000:  # 1KB 미만이면 손상된 파일
                            print(f"⚠️ TTS 파일 손상 (너무 작음): {tts_path}")
                            os.remove(tts_path)
                            continue

                        # WebAudio 효과 적용
                        webaudio_effect = page.get('webaudio_effect', 'normal')
                        if webaudio_effect and webaudio_effect != 'normal':
                            try:
                                processed_path = apply_webaudio_effect(tts_path, webaudio_effect)
                                
                                # 🔥 처리된 파일 검증
                                if processed_path and os.path.exists(processed_path):
                                    if os.path.getsize(processed_path) >= 1000:
                                        if processed_path != tts_path:
                                            os.remove(tts_path)  # 원본 삭제
                                        tts_file = processed_path
                                    else:
                                        print(f"⚠️ WebAudio 처리 파일 손상: {processed_path}")
                                        # 원본 사용
                                else:
                                    print(f"⚠️ WebAudio 처리 실패, 원본 사용")
                            except Exception as e:
                                print(f"⚠️ WebAudio 효과 적용 오류: {e}")
                                # 원본 파일 그대로 사용

                        tts_path_final = tts_file if isinstance(tts_file, str) else getattr(tts_file, 'path', str(tts_file))
                        audio_files.append(tts_file)
                        successful_texts.append(text)
                        page_infos.append({
                            'page_type': 'tts',
                            'text': text,
                            'voice_id': voice_id,
                            'speed_value': page.get('speed_value', 1.0),
                            'style_value': page.get('style_value', 0.85),
                            'similarity_value': page.get('similarity_value', 0.75),
                            'webaudio_effect': page.get('webaudio_effect', 'normal'),
                            'audio_path': tts_path_final,
                        })

                    except Exception as e:
                        print(f"❌ TTS 생성 오류 ({page_idx + 1}번 페이지): {e}")
                        continue

                # 🔥 오디오 파일이 없으면 에러 반환
                if not audio_files:
                    return {'success': False, 'error': 'TTS 생성에 실패했습니다'}

                # 오디오 병합
                self.update_state(state='PROGRESS', meta={
                    'status': '오디오 병합 중...',
                    'progress': progress + int(80 / total_steps),
                    'current_step': step_idx + 1,
                    'total_steps': total_steps
                })

                try:
                    merged_file, timestamps, total_duration = merge_audio_files(audio_files, pages_text=successful_texts)
                    
                    # 🔥 병합 결과 검증
                    if not merged_file or not os.path.exists(merged_file):
                        raise Exception('오디오 병합 실패: 파일이 생성되지 않음')
                        
                    if os.path.getsize(merged_file) < 1000:
                        raise Exception('오디오 병합 실패: 파일이 너무 작음')
                        
                    if not total_duration or total_duration <= 0:
                        # 🔥 duration이 없으면 직접 계산
                        from pydub import AudioSegment
                        audio = AudioSegment.from_file(merged_file)
                        total_duration = len(audio) / 1000.0  # ms → 초
                        print(f"⚠️ duration 자동 계산: {total_duration}초")
                        
                except Exception as e:
                    # 임시 파일 정리
                    for f in audio_files:
                        try:
                            fpath = f if isinstance(f, str) else getattr(f, 'path', None)
                            if fpath and os.path.exists(fpath):
                                os.remove(fpath)
                        except:
                            pass
                    return {'success': False, 'error': f'오디오 병합 실패: {str(e)}'}

                # DB 저장 (절대 경로 → FileField로 올바르게 저장)
                try:
                    content = Content(
                        book=book,
                        title=ep_title,
                        number=ep_number,
                        text="\n".join([p.get('text', '') for p in pages]),
                        audio_timestamps=timestamps,
                        duration_seconds=int(total_duration)
                    )
                    with open(merged_file, 'rb') as f:
                        content.audio_file.save(os.path.basename(merged_file), File(f), save=True)
                except Exception as e:
                    # 병합 파일 삭제
                    if merged_file and os.path.exists(merged_file):
                        os.remove(merged_file)
                    # 임시 파일 정리
                    for f in audio_files:
                        try:
                            fpath = f if isinstance(f, str) else getattr(f, 'path', None)
                            if fpath and os.path.exists(fpath):
                                os.remove(fpath)
                        except:
                            pass
                    return {'success': False, 'error': f'DB 저장 실패: {str(e)}'}

                created_episode_info = {
                    'content_uuid': str(content.public_uuid),
                    'title': ep_title,
                    'number': ep_number,
                    'duration': total_duration,
                    'page_count': len(pages)
                }

                # ── PageAudio 개별 저장 ──────────────────────────────────
                try:
                    from book.models import PageAudio
                    for pg_idx, (audio_file, info) in enumerate(zip(audio_files, page_infos)):
                        fpath = audio_file if isinstance(audio_file, str) else getattr(audio_file, 'path', None)
                        if not fpath or not os.path.exists(fpath):
                            continue
                        try:
                            pa = PageAudio(
                                content=content,
                                page_number=pg_idx + 1,
                                text=info.get('text', ''),
                                voice_id=info.get('voice_id', ''),
                                language_code='ko',
                                speed_value=info.get('speed_value', 1.0),
                                style_value=info.get('style_value', 0.85),
                                similarity_value=info.get('similarity_value', 0.75),
                                webaudio_effect=info.get('webaudio_effect', 'normal'),
                                page_type=info.get('page_type', 'tts'),
                            )
                            with open(fpath, 'rb') as pf:
                                pa.audio_file.save(os.path.basename(fpath), File(pf), save=True)
                        except Exception as e:
                            print(f"⚠️ PageAudio 저장 실패 (페이지 {pg_idx + 1}): {e}")
                    print(f"💾 PageAudio {len(page_infos)}개 저장 완료")
                except Exception as e:
                    print(f"⚠️ PageAudio 전체 저장 오류: {e}")
                # ────────────────────────────────────────────────────────

                # 임시 병합 파일 정리 (이미 FileField로 복사됨)
                if merged_file and os.path.exists(merged_file):
                    os.remove(merged_file)

                # 임시 TTS 파일 정리
                for f in audio_files:
                    try:
                        fpath = f if isinstance(f, str) else getattr(f, 'path', None)
                        if fpath and os.path.exists(fpath):
                            os.remove(fpath)
                    except:
                        pass

            # ==================== BGM 믹싱 ====================
            elif action == 'mix_bgm':
                if not book:
                    return {'success': False, 'error': 'book_uuid가 필요합니다'}

                ep_number = step.get('episode_number', 1)
                # 같은 에피소드 번호로 여러 번 생성시 가장 최신 에피소드를 사용
                content = Content.objects.filter(book=book, number=ep_number).order_by('-pk').first()
                if not content:
                    print(f"⚠️ 에피소드 {ep_number}를 찾을 수 없습니다")
                    continue

                self.update_state(state='PROGRESS', meta={
                    'status': '배경음 믹싱 중...',
                    'progress': progress,
                    'current_step': step_idx + 1,
                    'total_steps': total_steps
                })

                bg_tracks = step.get('background_tracks', [])

                # 변수 치환
                print(f"[mix_bgm] results keys: {list(results.keys())}")
                for track in bg_tracks:
                    music_id = track.get('music_id', '')
                    if music_id.startswith('$'):
                        if music_id in results:
                            track['music_id'] = results[music_id]
                            print(f"[mix_bgm] BGM 변수 치환: {music_id} → {track['music_id']}")
                        else:
                            print(f"[mix_bgm] ⚠️ BGM 변수 미해결: {music_id} (results에 없음)")

                # 타임스탬프 (각 항목에 pageIndex, endTime(ms)만 있음)
                timestamps = content.audio_timestamps
                if isinstance(timestamps, str):
                    timestamps = json.loads(timestamps)

                def page_start_ms(page_idx):
                    """페이지 시작 시간(ms): 이전 페이지의 endTime, 첫 페이지는 0"""
                    if not timestamps or page_idx <= 0:
                        return 0
                    prev_idx = min(page_idx - 1, len(timestamps) - 1)
                    return int(timestamps[prev_idx].get('endTime', 0))

                def page_end_ms(page_idx):
                    """페이지 끝 시간(ms) - timestamps 없으면 전체 duration 사용"""
                    if not timestamps:
                        # fallback: 전체 에피소드 길이 사용
                        return int(content.duration_seconds * 1000) if content.duration_seconds else 0
                    idx = min(page_idx, len(timestamps) - 1)
                    return int(timestamps[idx].get('endTime', 0))

                # bg_tracks → mix_audio_with_background 형식으로 변환
                converted_tracks = []
                for track in bg_tracks:
                    mid = track.get('music_id', '')
                    bgm_obj = BackgroundMusicLibrary.objects.filter(id=mid).first()
                    if not bgm_obj or not bgm_obj.audio_file:
                        print(f"⚠️ BGM ID={mid} 없음, 건너뜀")
                        continue

                    start_page = track.get('start_page', 0)
                    end_page = track.get('end_page', len(timestamps) - 1 if timestamps else -1)
                    volume = track.get('volume', 0.25)
                    volume_db = 20 * math.log10(max(volume, 0.01))

                    start_time = page_start_ms(start_page)
                    end_time = page_end_ms(end_page)

                    if content.duration_seconds:
                        max_ms = int(content.duration_seconds * 1000)
                        end_time = min(end_time, max_ms)

                    if start_time >= end_time:
                        print(f"⚠️ 잘못된 시간 범위: {start_time}ms ~ {end_time}ms, 건너뜀")
                        continue

                    print(f"✅ 배경음 구간: {start_time}ms ~ {end_time}ms ({(end_time - start_time) / 1000:.1f}초)")

                    converted_tracks.append({
                        'audioPath': bgm_obj.audio_file.path,
                        'startTime': start_time,
                        'endTime': end_time,
                        'volume': volume_db
                    })

                # SFX 트랙 — overlay 대신 삽입 방식으로 처리 (대사 직전 순차 재생)
                sfx_tracks = step.get('sound_effects', [])
                sfx_inserts = []  # [(insert_at_ms, sfx_segment)]
                page_ts = [t for t in (timestamps or []) if t.get('type') != 'sfx']

                for sfx_track in sfx_tracks:
                    eid = sfx_track.get('effect_id', '')
                    if eid.startswith('$'):
                        if eid in results:
                            sfx_track['effect_id'] = results[eid]
                            print(f"[mix_bgm] SFX 변수 치환: {eid} → {sfx_track['effect_id']}")
                        else:
                            print(f"[mix_bgm] ⚠️ SFX 변수 미해결: {eid} (results에 없음)")

                    sfx_obj = SoundEffectLibrary.objects.filter(id=sfx_track.get('effect_id', '')).first()
                    if not sfx_obj or not sfx_obj.audio_file:
                        continue

                    sfx_page = sfx_track.get('page_number') or sfx_track.get('page') or 1
                    if page_ts and 0 <= sfx_page - 1 < len(page_ts):
                        insert_at = int(page_ts[sfx_page - 1].get('startTime', 0))
                    else:
                        insert_at = 0

                    sfx_volume = sfx_track.get('volume', 0.7)
                    sfx_volume_db = 20 * math.log10(max(sfx_volume, 0.01))

                    from pydub import AudioSegment as PydubSegment
                    sfx_seg = PydubSegment.from_file(sfx_obj.audio_file.path)
                    sfx_seg = sfx_seg + sfx_volume_db

                    print(f"✅ 효과음 삽입 위치: {insert_at}ms ({len(sfx_seg)}ms 길이)")
                    sfx_inserts.append((insert_at, sfx_seg))

                # 1단계: SFX 삽입 (BGM 전에 — BGM이 SFX 구간도 끊김 없이 커버하도록)
                current_path = content.audio_file.path
                if sfx_inserts:
                    try:
                        from pydub import AudioSegment as PydubSegment
                        import uuid as _uuid
                        audio = PydubSegment.from_file(current_path)
                        sfx_inserts.sort(key=lambda x: x[0])
                        for insert_at, sfx_seg in reversed(sfx_inserts):
                            before = audio[:insert_at]
                            after  = audio[insert_at:]
                            audio  = before + sfx_seg + after

                        # 타임스탬프 보정
                        if timestamps:
                            updated_ts = list(timestamps)
                            for insert_at, sfx_seg in sfx_inserts:  # 오름차순
                                shift = len(sfx_seg)
                                for ts in updated_ts:
                                    if ts.get('type') == 'sfx':
                                        continue
                                    if ts.get('startTime', 0) >= insert_at:
                                        ts['startTime'] = ts['startTime'] + shift
                                    if ts.get('endTime', 0) >= insert_at:
                                        ts['endTime'] = ts['endTime'] + shift
                            content.audio_timestamps = updated_ts
                            content.save(update_fields=['audio_timestamps'])

                        # BGM startTime/endTime도 SFX 삽입량만큼 보정
                        for track in converted_tracks:
                            for insert_at, sfx_seg in sfx_inserts:
                                shift = len(sfx_seg)
                                if track.get('startTime', 0) >= insert_at:
                                    track['startTime'] += shift
                                if track.get('endTime', 0) >= insert_at:
                                    track['endTime'] += shift

                        out_path = os.path.join(settings.MEDIA_ROOT, 'audio', f'sfx_insert_{_uuid.uuid4().hex}.mp3')
                        audio.export(out_path, format='mp3', bitrate='128k')
                        current_path = out_path
                    except Exception as e:
                        print(f"❌ SFX 삽입 오류: {e}")

                # 2단계: BGM overlay (SFX 삽입 후 전체 오디오에 덮어씌워 끊김 없이 재생)
                if converted_tracks:
                    try:
                        mixed_file = mix_audio_with_background(current_path, converted_tracks)
                        if mixed_file and os.path.exists(mixed_file):
                            if current_path != content.audio_file.path and os.path.exists(current_path):
                                os.remove(current_path)
                            current_path = mixed_file
                    except Exception as e:
                        print(f"❌ BGM 믹싱 오류: {e}")

                # mix_config 저장 (에디터에서 SFX/BGM 재생성 가능하도록)
                try:
                    mix_config_bgm = []
                    for track in bg_tracks:
                        mid = track.get('music_id', '')
                        bgm_obj2 = BackgroundMusicLibrary.objects.filter(id=mid).first()
                        if bgm_obj2:
                            mix_config_bgm.append({
                                'id': bgm_obj2.id,
                                'name': bgm_obj2.music_name,
                                'desc': bgm_obj2.music_description,
                                'duration': bgm_obj2.duration_seconds,
                                'volume': track.get('volume', 0.25),
                                'start_page': track.get('start_page', 0),
                                'end_page': track.get('end_page', -1),
                            })
                    mix_config_sfx = []
                    for sfx_track in sfx_tracks:
                        sfx_obj2 = SoundEffectLibrary.objects.filter(id=sfx_track.get('effect_id', '')).first()
                        if sfx_obj2:
                            mix_config_sfx.append({
                                'id': sfx_obj2.id,
                                'name': sfx_obj2.effect_name,
                                'desc': sfx_obj2.effect_description,
                                'volume': sfx_track.get('volume', 0.7),
                                'page_number': sfx_track.get('page_number') or sfx_track.get('page') or 1,
                            })
                    content.mix_config = {'bgm': mix_config_bgm, 'sfx': mix_config_sfx}
                    content.save(update_fields=['mix_config'])
                except Exception as e:
                    print(f"⚠️ mix_config 저장 오류: {e}")

                # 최종 파일 저장
                if current_path != content.audio_file.path and os.path.exists(current_path):
                    try:
                        old_path = content.audio_file.path
                        with open(current_path, 'rb') as f:
                            content.audio_file.save(os.path.basename(current_path), File(f), save=True)
                        if old_path and os.path.exists(old_path):
                            os.remove(old_path)
                        if os.path.exists(current_path):
                            os.remove(current_path)
                        print(f"✅ 배경음/효과음 처리 완료")
                    except Exception as e:
                        print(f"❌ 파일 저장 오류: {e}")

        except Exception as e:
            error_msg = f'Step {step_idx + 1} ({action}) 실패: {str(e)}'
            print(f'❌ {error_msg}')
            traceback.print_exc()
            return {
                'success': False,
                'error': error_msg,
                'failed_step': step_idx + 1,
                'failed_action': action
            }

    # 완료
    response = {
        'success': True,
        'steps_completed': total_steps,
    }

    if created_episode_info:
        response['episode'] = created_episode_info
        response['redirect_url'] = f'/book/detail/{book_uuid}/'

    if warnings:
        response['warnings'] = warnings
        print(f"⚠️ 완료 (경고 {len(warnings)}개): {warnings}")

    return response