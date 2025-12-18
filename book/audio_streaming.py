"""
오디오 파일 스트리밍 최적화
- Range Request 지원
- Chunked Transfer
"""
import os
import mimetypes
from django.http import StreamingHttpResponse, HttpResponse
from django.shortcuts import get_object_or_404
from book.models import Contents


def stream_audio(request, content_id):
    """
    오디오 파일을 스트리밍으로 제공
    Range Request를 지원하여 탐색 가능
    """
    content = get_object_or_404(Contents, id=content_id, is_publish=True)

    if not content.audio_file:
        return HttpResponse('Audio file not found', status=404)

    audio_path = content.audio_file.path
    file_size = os.path.getsize(audio_path)
    content_type = mimetypes.guess_type(audio_path)[0] or 'audio/mpeg'

    # Range 헤더 확인
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = None

    if range_header:
        import re
        range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)

    if range_match:
        # Range Request 처리
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        length = end - start + 1

        # 파일 청크로 읽기
        def file_iterator(file_path, offset, chunk_size=8192):
            with open(file_path, 'rb') as f:
                f.seek(offset)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        response = StreamingHttpResponse(
            file_iterator(audio_path, start),
            status=206,
            content_type=content_type
        )
        response['Content-Length'] = str(length)
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    else:
        # 전체 파일 스트리밍
        def file_iterator(file_path, chunk_size=8192):
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        response = StreamingHttpResponse(
            file_iterator(audio_path),
            content_type=content_type
        )
        response['Content-Length'] = str(file_size)

    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'public, max-age=3600'  # 1시간 캐싱

    return response
