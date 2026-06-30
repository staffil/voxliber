from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json

from .models import FCMToken, Notification
from book.api_utils import require_api_key_secure


@csrf_exempt
@require_api_key_secure
def register_fcm_token(request):
    """앱에서 FCM 토큰 등록/갱신"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        device = data.get('device', 'android')
    except Exception:
        return JsonResponse({'success': False, 'error': '잘못된 요청'}, status=400)

    if not token:
        return JsonResponse({'success': False, 'error': '토큰 없음'}, status=400)

    # 같은 토큰이 있으면 내 유저로 업데이트, 없으면 새로 생성
    FCMToken.objects.filter(token=token).delete()
    FCMToken.objects.create(user=request.api_user, token=token, device=device)

    return JsonResponse({'success': True})


@login_required
def get_notifications(request):
    """내 알림 목록"""
    qs = Notification.objects.filter(user=request.user)
    unread_count = qs.filter(is_read=False).count()
    notifications = qs.order_by('-created_at')[:50]

    data = [
        {
            'id': n.id,
            'type': n.type,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'link': n.link,
            'created_at': n.created_at.isoformat(),
        }
        for n in notifications
    ]
    return JsonResponse({'notifications': data, 'unread_count': unread_count})


@csrf_exempt
@login_required
def mark_read(request, notification_id):
    """알림 읽음 처리"""
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)
    Notification.objects.filter(id=notification_id, user=request.user).update(is_read=True)
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
def mark_all_read(request):
    """전체 읽음 처리"""
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@login_required
def notification_page(request):
    """알림 전체 목록 페이지"""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timezone.timedelta(days=7)

    qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = qs.filter(is_read=False).count()
    all_notifs = list(qs[:100])

    today_list = [n for n in all_notifs if n.created_at >= today_start]
    week_list  = [n for n in all_notifs if week_start <= n.created_at < today_start]
    older_list = [n for n in all_notifs if n.created_at < week_start]

    return render(request, 'notifications/notification_list.html', {
        'today_list': today_list,
        'week_list': week_list,
        'older_list': older_list,
        'unread_count': unread_count,
    })
