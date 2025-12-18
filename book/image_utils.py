"""
이미지 최적화 유틸리티
- 자동 리사이징
- WebP 변환
- 썸네일 생성
"""
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys


def optimize_image(image_field, max_width=1200, max_height=1200, quality=85):
    """
    이미지 최적화 및 리사이징

    Args:
        image_field: Django ImageField
        max_width: 최대 너비
        max_height: 최대 높이
        quality: JPEG 품질 (1-100)

    Returns:
        최적화된 이미지 파일
    """
    if not image_field:
        return None

    # 이미지 열기
    img = Image.open(image_field)

    # RGBA -> RGB 변환 (JPEG는 투명도 지원 안 함)
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background

    # 비율 유지하며 리사이징
    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

    # 메모리에 저장
    output = BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    output.seek(0)

    # Django 파일로 변환
    optimized_image = InMemoryUploadedFile(
        output,
        'ImageField',
        f"{image_field.name.split('.')[0]}.jpg",
        'image/jpeg',
        sys.getsizeof(output),
        None
    )

    return optimized_image


def create_thumbnail(image_field, size=(300, 300)):
    """
    썸네일 생성

    Args:
        image_field: Django ImageField
        size: 썸네일 크기 (width, height)

    Returns:
        썸네일 이미지 파일
    """
    if not image_field:
        return None

    img = Image.open(image_field)

    # RGBA -> RGB 변환
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background

    # 정사각형 크롭 후 리사이징
    width, height = img.size
    min_dimension = min(width, height)

    left = (width - min_dimension) / 2
    top = (height - min_dimension) / 2
    right = (width + min_dimension) / 2
    bottom = (height + min_dimension) / 2

    img = img.crop((left, top, right, bottom))
    img = img.resize(size, Image.Resampling.LANCZOS)

    # 메모리에 저장
    output = BytesIO()
    img.save(output, format='JPEG', quality=85, optimize=True)
    output.seek(0)

    # Django 파일로 변환
    thumbnail = InMemoryUploadedFile(
        output,
        'ImageField',
        f"{image_field.name.split('.')[0]}_thumb.jpg",
        'image/jpeg',
        sys.getsizeof(output),
        None
    )

    return thumbnail
