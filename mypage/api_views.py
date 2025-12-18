from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from book.models import APIKey



from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

@api_view(['GET', 'PATCH'])
def api_user_info(request):
    api_key = request.GET.get('api_key')

    if not api_key:
        return Response({"error": "로그인이 필요합니다."}, status=401)

    try:
        api_key_obj = APIKey.objects.select_related('user').get(
            key=api_key,
            is_active=True
        )
        user = api_key_obj.user
    except APIKey.DoesNotExist:
        return Response({"error": "잘못된 API Key입니다."}, status=401)

    # 🔹 조회
    if request.method == 'GET':
        return Response({
            "id": user.user_id,
            "username": user.username,
            "email": user.email,
            "nickname": user.nickname,
            "gender": user.gender,
            "age": user.age,
            "birthdate": user.birthdate,
            "user_img": user.user_img.url if user.user_img else None,
            "cover_img": user.cover_img.url if user.cover_img else None,
            "follow_count": user.follow_count,
            "status": user.status,
            "oauth_provider": user.oauth_provider,
            "created_at": user.created_at.isoformat(),
        })

    # 🔥 수정
    elif request.method == 'PATCH':
        data = request.data

        user.nickname = data.get('nickname', user.nickname)
        user.gender = data.get('gender', user.gender)
        user.birthdate = data.get('birthdate', user.birthdate)
        if 'user_img' in request.FILES:
            user.user_img = request.FILES['user_img']
        user.save()

        return Response({"success": True})
