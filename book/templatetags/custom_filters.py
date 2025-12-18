from django import template
import re

register = template.Library()

@register.filter(name='remove_brackets')
def remove_brackets(text):
    """
    대괄호 [] 와 그 안의 내용을 모두 제거하는 필터
    예: "안녕하세요 [whispers] 반갑습니다" -> "안녕하세요  반갑습니다"
    """
    if not text:
        return ''
    # [내용] 패턴을 모두 제거
    cleaned_text = re.sub(r'\[([^\]]+)\]', '', text)
    return cleaned_text.strip()
