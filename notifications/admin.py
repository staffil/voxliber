from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
from notifications.models import FCMToken, Notification
from notifications.fcm import send_push_multicast
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(FCMToken)
class FCMTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'device', 'token_short', 'created_at']
    search_fields = ['user__email', 'user__username']

    def token_short(self, obj):
        return obj.token[:25] + '...'
    token_short.short_description = '토큰'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'title', 'created_at']
    search_fields = ['user__email', 'title']


class SendPushView(admin.ModelAdmin):

    def get_urls(self):
        return [
            path('', self.admin_site.admin_view(self.push_view), name='send_push'),
        ]

    def push_view(self, request):
        users = User.objects.all().order_by('email')

        if request.method == 'POST':
            target = request.POST.get('target')
            title = request.POST.get('title', '').strip()
            body = request.POST.get('body', '').strip()
            cover_url = request.POST.get('cover_url', '').strip()
            image_file = request.FILES.get('image')

            if not title or not body:
                messages.error(request, '제목과 내용을 입력해주세요.')
                return redirect('/admin/send-push/')

            # 이미지 업로드 처리
            if image_file:
                import os
                from django.conf import settings as django_settings
                upload_dir = os.path.join(django_settings.MEDIA_ROOT, 'uploads', 'push_images')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, image_file.name)
                with open(file_path, 'wb+') as f:
                    for chunk in image_file.chunks():
                        f.write(chunk)
                cover_url = f'https://voxliber.ink/media/uploads/push_images/{image_file.name}'

            # 토큰 조회
            if target == 'all':
                tokens = list(FCMToken.objects.values_list('token', flat=True))
                target_label = f'전체 ({len(tokens)}명)'
            else:
                tokens = list(FCMToken.objects.filter(user_id=target).values_list('token', flat=True))
                try:
                    user = User.objects.get(id=target)
                    target_label = user.email
                except User.DoesNotExist:
                    target_label = '알 수 없음'

            if tokens:
                send_push_multicast(
                    tokens=tokens,
                    title=title,
                    body=body,
                    data={'type': 'admin_push', 'cover_url': cover_url},
                )
                messages.success(request, f'✅ {target_label}에게 푸시 발송 완료! ({len(tokens)}개 기기)')
            else:
                messages.warning(request, '⚠️ 발송할 토큰이 없습니다.')

            return redirect('/admin/send-push/')

        context = {
            'title': '푸시 알림 발송',
            'users': users,
            **self.admin_site.each_context(request),
        }
        return render(request, 'admin/send_push.html', context)