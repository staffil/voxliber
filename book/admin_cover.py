"""
관리자 전용 책 표지 AI 생성 시스템
- FLUX.1-schnell (HF Inference API) 사용
- GPT-4o로 표지 이미지 프롬프트 자동 생성
- staff_member_required로 관리자만 접근 가능
"""
import os
import io
import json
import requests
from django.views import View
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.core.files.base import ContentFile
from book.models import Books


HF_TOKEN = os.environ.get("HF_TOKEN", "") or os.environ.get("HF_TOEKN", "")  # .env typo 허용
HF_API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")


def _make_image_prompt(title: str, description: str, book_type: str) -> str:
    """GPT-4o로 책 표지용 영어 이미지 프롬프트 생성"""
    if not OPENAI_KEY:
        # API 키 없으면 기본 템플릿
        return f"Korean {book_type} book cover art, '{title}', cinematic composition, vibrant colors, professional illustration"

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    system = (
        "You are an expert at writing image generation prompts for book covers. "
        "Generate a concise English prompt (max 120 tokens) for FLUX.1-schnell to create a beautiful Korean webnovel/audiobook cover. "
        "Focus on: art style, mood, main visual elements, color palette. "
        "Output ONLY the prompt, no explanations."
    )
    user = f"Book title: {title}\nDescription: {description[:300]}\nBook type: {book_type}"
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=150,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return f"Korean {book_type} book cover, '{title}', cinematic composition, vibrant colors, professional digital art"


def _generate_image(prompt: str) -> bytes:
    """HF FLUX.1-schnell로 이미지 생성 → bytes 반환"""
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"inputs": prompt}
    r = requests.post(HF_API_URL, headers=headers, json=payload, timeout=120)
    if r.status_code != 200:
        raise Exception(f"HF API 오류: {r.status_code} {r.text[:200]}")
    return r.content


@method_decorator(staff_member_required, name='dispatch')
class CoverGenerateView(View):

    def get(self, request):
        books = Books.objects.filter(is_deleted=False).select_related('user').order_by(
            'book_type', '-created_at'
        )
        # 카테고리 분리
        no_cover = books.filter(cover_img='')
        has_cover = books.exclude(cover_img='')
        return render(request, 'admin/book/cover_generate.html', {
            'no_cover_books': no_cover,
            'has_cover_books': has_cover,
            'hf_configured': bool(HF_TOKEN),
            'openai_configured': bool(OPENAI_KEY),
        })

    def post(self, request):
        book_uuid = request.POST.get('book_uuid', '').strip()
        custom_prompt = request.POST.get('custom_prompt', '').strip()

        if not book_uuid:
            messages.error(request, '책을 선택해주세요.')
            return redirect('cover_generate')

        try:
            book = Books.objects.get(public_uuid=book_uuid, is_deleted=False)
        except Books.DoesNotExist:
            messages.error(request, '책을 찾을 수 없습니다.')
            return redirect('cover_generate')

        if not HF_TOKEN:
            messages.error(request, 'HF_TOKEN 환경변수가 설정되지 않았습니다.')
            return redirect('cover_generate')

        try:
            # 1. 프롬프트 생성
            if custom_prompt:
                prompt = custom_prompt
            else:
                prompt = _make_image_prompt(book.name, book.description or '', book.book_type)

            # 2. 이미지 생성
            img_bytes = _generate_image(prompt)

            # 3. 저장
            safe_name = "".join(c for c in book.name if c.isalnum() or c in (' ', '_', '-'))[:40]
            filename = f"cover_{safe_name}.png"
            book.cover_img.save(filename, ContentFile(img_bytes), save=True)

            messages.success(request, f'✅ [{book.name}] 표지 생성 완료!')

        except Exception as e:
            messages.error(request, f'❌ 생성 실패: {str(e)[:200]}')

        return redirect('cover_generate')
