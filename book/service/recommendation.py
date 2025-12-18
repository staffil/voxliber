from book.models import Books, ReadingProgress
from django.db.models import Count, Q

def get_user_preference(user):
    genre_score = {}
    tag_score = {}

    progresses = ReadingProgress.objects.filter(user=user)

    for p in progresses:
        book = p.book
        progress_ratio = p.get_progress_percentage() / 100

        for g in book.genres.all():
            genre_score[g.id] = genre_score.get(g.id, 0) + progress_ratio * 0.3

        for t in book.tags.all():
            tag_score[t.id] = tag_score.get(t.id, 0) + progress_ratio * 0.7

    return genre_score, tag_score

# ai 가 추천하는 책
def recommend_books(user, limit=10):
    genre_score, tag_score = get_user_preference(user)

    if not genre_score and not tag_score:
        return Books.objects.none()

    top_genres = sorted(genre_score, key=genre_score.get, reverse=True)[:3]
    top_tags = sorted(tag_score, key=tag_score.get, reverse=True)[:5]

    qs = Books.objects.annotate(
        genre_match=Count("genres", filter=Q(genres__in=top_genres)),
        tag_match=Count("tags", filter=Q(tags__in=top_tags)),
    ).order_by("-tag_match", "-genre_match", "-book_score")

    return qs[:limit]



import random
def generate_ai_reason(book):
    reasons = []

    if book.tag_match > 0:
        reasons.append(f"관심 키워드 {book.tag_match}개가 일치해요")

    if book.genre_match > 0:
        reasons.append(f"선호 장르 {book.genre_match}개와 맞아요")

    if book.book_score >= 4.5:
        reasons.append(f"평점 {book.book_score}점으로 호평을 받고 있어요")

    if not reasons:
        return "종합적으로 취향에 잘 맞는 책이에요"

    return " · ".join(reasons)



import requests
import json
import logging
from typing import Optional

# 로거 설정
logger = logging.getLogger(__name__)

def ollama_summarize_episode(text: str, model: str = "llama3", max_length: int = 3000, timeout: int = 60) -> Optional[str]:
    """
    Ollama API를 사용하여 에피소드 텍스트를 요약합니다.

    Args:
        text: 요약할 텍스트
        model: 사용할 Ollama 모델 (기본값: llama3)
        max_length: 텍스트 최대 길이 (기본값: 3000자)
        timeout: 요청 타임아웃 (기본값: 60초)

    Returns:
        요약된 텍스트 또는 실패 시 None
    """
    url = "http://localhost:11434/api/generate"

    # 1. 텍스트 길이 제한 (토큰 제한 고려)
    if len(text) > max_length:
        logger.warning(f"텍스트가 너무 깁니다 ({len(text)}자). {max_length}자로 자릅니다.")
        text = text[:max_length] + "..."

    # 2. 빈 텍스트 체크
    if not text or not text.strip():
        logger.error("요약할 텍스트가 비어있습니다.")
        return None

    try:
        logger.info(f"📝 Ollama 요약 시작 - 모델: {model}, 텍스트 길이: {len(text)}자")

        # 3. API 요청 (타임아웃 설정)
        response = requests.post(
            url,
            json={
                "model": model,
                "prompt": f"다음 내용을 7~10문장으로 요약해줘. 핵심 사건, 등장인물 변화, 갈등 포인트 중심으로 정리해줘.\n\n{text}",
                "stream": True
            },
            timeout=timeout,
            stream=True
        )

        # 4. HTTP 응답 상태 코드 확인
        if response.status_code != 200:
            logger.error(f"❌ Ollama API 오류: HTTP {response.status_code}")
            return None

        # 5. 스트리밍 응답 파싱 (JSON 사용)
        result = ""
        line_count = 0

        for line in response.iter_lines():
            if line:
                line_count += 1
                try:
                    # JSON 파싱
                    decoded = line.decode("utf-8")
                    data = json.loads(decoded)

                    # response 필드 추출
                    if "response" in data:
                        result += data["response"]

                    # 완료 확인
                    if data.get("done", False):
                        logger.info(f"✅ 요약 완료 - 총 {line_count}줄 처리됨")
                        break

                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ JSON 파싱 오류 (라인 {line_count}): {e}")
                    continue

        # 6. 빈 결과 처리
        if not result or not result.strip():
            logger.error("❌ 요약 결과가 비어있습니다.")
            return None

        # 7. 결과 정리
        result = result.strip()
        logger.info(f"✅ 요약 성공 - 결과 길이: {len(result)}자")

        return result

    except requests.exceptions.Timeout:
        logger.error(f"❌ Ollama API 타임아웃 ({timeout}초 초과)")
        return None

    except requests.exceptions.ConnectionError:
        logger.error("❌ Ollama 서버에 연결할 수 없습니다. Ollama가 실행 중인지 확인하세요.")
        return None

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 요청 오류: {e}")
        return None

    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
        return None
