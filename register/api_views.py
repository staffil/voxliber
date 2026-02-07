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
from register.models import Users



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

def log_to_file(msg):
    """파일에 직접 로그 작성"""
    import datetime
    with open('/home/ubuntu/voxliber/signup_debug.log', 'a') as f:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] {msg}\n")
        f.flush()

@require_api_key_secure
def api_signup(request):
    """
    OAuth 로그인 후 신규 유저 프로필 완료 API
    """
    try:
        log_to_file("🔵 [API Signup] 시작")
        log_to_file(f"   Method: {request.method}")
        log_to_file(f"   Headers: {dict(request.headers)}")
        log_to_file(f"   POST data: {dict(request.POST)}")
        log_to_file(f"   FILES: {list(request.FILES.keys())}")

        if request.method != "POST":
            return JsonResponse({"error": "POST 요청만 허용됩니다"}, status=405)

        log_to_file(f"   API Key Obj: {hasattr(request, 'api_key_obj')}")
        if not hasattr(request, 'api_key_obj'):
            log_to_file("❌ [API Signup] request.api_key_obj가 없습니다!")
            return JsonResponse({"error": "API Key 인증 실패"}, status=401)

        user = request.api_key_obj.user
        log_to_file(f"   User ID: {user.user_id}")
        log_to_file(f"   Username: {user.username}")

        nickname = request.POST.get("nickname")
        birthdate = request.POST.get("birthdate")
        gender = request.POST.get("gender")
        user_img = request.FILES.get("user-image")


        if Users.objects.filter(nickname=nickname).exists():
            return JsonResponse({"error": "이미 존재하는 닉네임입니다."}, status=400)

        log_to_file(f"   Nickname: {nickname}")
        log_to_file(f"   Birthdate: {birthdate}")
        log_to_file(f"   Gender: {gender}")
        log_to_file(f"   Has Image: {user_img is not None}")

        if not nickname or not birthdate or not gender:
            log_to_file("❌ [API Signup] 필수 항목 누락")
            return JsonResponse({"error": "필수 항목 누락"}, status=400)

        user.nickname = nickname
        user.birthdate = birthdate
        user.age = calc_age(birthdate)
        user.gender = convert_gender(gender)
        user.is_profile_completed = True

        if user_img:
            try:
                log_to_file(f"   이미지 검증 시작...")
                validate_image_file(user_img)
                user.user_img = user_img
                log_to_file(f"   프로필 이미지 설정 완료")
            except ValidationError as e:
                log_to_file(f"❌ [API Signup] 이미지 검증 실패: {e}")
                return JsonResponse({"error": str(e)}, status=400)
            except Exception as e:
                log_to_file(f"❌ [API Signup] 이미지 처리 중 예외: {e}")
                import traceback
                log_to_file(traceback.format_exc())
                return JsonResponse({"error": f"이미지 처리 오류: {str(e)}"}, status=500)

        log_to_file(f"   사용자 저장 시작...")
        user.save()
        log_to_file(f"✅ [API Signup] 사용자 저장 완료")

        return JsonResponse({"success": True, "message": "회원가입 완료"})

    except Exception as e:
        log_to_file(f"❌ [API Signup] 예외 발생: {e}")
        import traceback
        log_to_file(traceback.format_exc())
        return JsonResponse({"error": f"서버 오류: {str(e)}"}, status=500)






