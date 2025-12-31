from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from book.models import APIKey
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from datetime import datetime, date
from book.api_utils import require_api_key, require_api_key_secure, paginate, api_response
from voxliber.security import validate_image_file




def calc_age(birthdate_str):
    birth = datetime.strptime(birthdate_str, "%Y-%m-%d").date()
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

def convert_gender(g):
    g_lower = g.lower()
    # 앱에서 보내는 단일 문자 형식 (M, F, O) 처리
    if g_lower == "m" or g_lower == "male": return "M"
    if g_lower == "f" or g_lower == "female": return "F"
    return "O"

@require_api_key_secure
def api_signup(request):
    """
    OAuth 로그인 후 신규 유저 프로필 완료 API
    """
    try:
        print("🔵 [API Signup] 시작")
        print(f"   Method: {request.method}")
        print(f"   Headers: {dict(request.headers)}")
        print(f"   POST data: {dict(request.POST)}")
        print(f"   FILES: {list(request.FILES.keys())}")

        if request.method != "POST":
            return JsonResponse({"error": "POST 요청만 허용됩니다"}, status=405)

        print(f"   API Key Obj: {hasattr(request, 'api_key_obj')}")
        if not hasattr(request, 'api_key_obj'):
            print("❌ [API Signup] request.api_key_obj가 없습니다!")
            return JsonResponse({"error": "API Key 인증 실패"}, status=401)

        user = request.api_key_obj.user
        print(f"   User ID: {user.user_id}")
        print(f"   Username: {user.username}")

        nickname = request.POST.get("nickname")
        birthdate = request.POST.get("birthdate")
        gender = request.POST.get("gender")
        user_img = request.FILES.get("user-image")

        print(f"   Nickname: {nickname}")
        print(f"   Birthdate: {birthdate}")
        print(f"   Gender: {gender}")
        print(f"   Has Image: {user_img is not None}")

        if not nickname or not birthdate or not gender:
            print("❌ [API Signup] 필수 항목 누락")
            return JsonResponse({"error": "필수 항목 누락"}, status=400)

        user.nickname = nickname
        user.birthdate = birthdate
        user.age = calc_age(birthdate)
        user.gender = convert_gender(gender)
        user.is_profile_completed = True

        if user_img:
            try:
                validate_image_file(user_img)
                user.user_img = user_img
                print(f"   프로필 이미지 설정 완료")
            except ValidationError as e:
                print(f"❌ [API Signup] 이미지 검증 실패: {e}")
                return JsonResponse({"error": str(e)}, status=400)

        user.save()
        print(f"✅ [API Signup] 사용자 저장 완료")

        return JsonResponse({"success": True, "message": "회원가입 완료"})

    except Exception as e:
        print(f"❌ [API Signup] 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": f"서버 오류: {str(e)}"}, status=500)
