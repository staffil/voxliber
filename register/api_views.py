from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from book.models import APIKey
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, date
from book.api_utils import require_api_key, paginate, api_response




def calc_age(birthdate_str):
    birth = datetime.strptime(birthdate_str, "%Y-%m-%d").date()
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

def convert_gender(g):
    if g.lower() == "male": return "M"
    if g.lower() == "female": return "F"
    return "O"

@csrf_exempt
@require_api_key
def api_signup(request):
    """
    OAuth 로그인 후 신규 유저 프로필 완료 API
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST 요청만 허용됩니다"}, status=405)

    user = request.api_key_obj.user

    nickname = request.POST.get("nickname")
    birthdate = request.POST.get("birthdate")
    gender = request.POST.get("gender")
    user_img = request.FILES.get("user-image")

    if not nickname or not birthdate or not gender:
        return JsonResponse({"error": "필수 항목 누락"}, status=400)

    user.nickname = nickname
    user.birthdate = birthdate
    user.age = calc_age(birthdate)
    user.gender = convert_gender(gender)
    user.is_profile_completed = True

    if user_img:
        user.user_img = user_img

    user.save()

    return JsonResponse({"success": True, "message": "회원가입 완료"})
