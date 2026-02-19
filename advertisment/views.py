from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from .models import Advertisement, AdImpression
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST


# advertisement/views.py 에 추가

from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from advertisment.models import Advertisement, AdImpression, AdRequest
import json



# advertisement/views.py

@login_required
def request_ad_list(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name', '').strip()
        contact_name = request.POST.get('contact_name', '').strip()
        email        = request.POST.get('email', '').strip()
        title        = request.POST.get('title', '').strip()

        if not company_name:
            return JsonResponse({'error': '회사명을 입력해주세요.'}, status=400)
        if not contact_name:
            return JsonResponse({'error': '담당자명을 입력해주세요.'}, status=400)
        if not email:
            return JsonResponse({'error': '이메일을 입력해주세요.'}, status=400)
        if not title:
            return JsonResponse({'error': '광고 제목을 입력해주세요.'}, status=400)

        ad_req = AdRequest.objects.create(
            user         = request.user,
            company_name = company_name,
            contact_name = contact_name,
            email        = email,
            phone        = request.POST.get('phone', '').strip(),
            title        = title,
            description  = request.POST.get('description', '').strip(),
            placement    = request.POST.get('placement', 'chat'),
            ad_type      = request.POST.get('ad_type', 'image'),
            budget       = int(request.POST.get('budget', 0) or 0),
            link_url = request.POST.get('link_url', '').strip(),
        )

        media_file = request.FILES.get('media_file')
        if media_file:
            if ad_req.ad_type == 'image':
                ad_req.image = media_file
            elif ad_req.ad_type == 'video':
                ad_req.video = media_file
            elif ad_req.ad_type == 'audio':
                ad_req.audio = media_file
            ad_req.save()

        return JsonResponse({'success': True, 'message': '광고 신청이 완료됐습니다.'})

    my_requests = AdRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "advertisment/request_advertisment.html", {'my_ads': my_requests})


@login_required
def edit_ad_request(request, req_id):
    """pending 상태인 광고 신청만 수정 가능"""
    ad_req = get_object_or_404(AdRequest, id=req_id, user=request.user)

    if ad_req.status != 'pending':
        return JsonResponse({'error': '검토 중인 신청만 수정할 수 있습니다.'}, status=403)

    if request.method == 'POST':
        ad_req.company_name = request.POST.get('company_name', ad_req.company_name).strip()
        ad_req.contact_name = request.POST.get('contact_name', ad_req.contact_name).strip()
        ad_req.email        = request.POST.get('email', ad_req.email).strip()
        ad_req.phone        = request.POST.get('phone', ad_req.phone or '').strip()
        ad_req.title        = request.POST.get('title', ad_req.title).strip()
        ad_req.description  = request.POST.get('description', ad_req.description or '').strip()
        ad_req.budget       = int(request.POST.get('budget', ad_req.budget) or 0)
        ad_req.link_url = request.POST.get('link_url', ad_req.link_url or '').strip()


        media_file = request.FILES.get('media_file')
        if media_file:
            if ad_req.ad_type == 'image':
                ad_req.image = media_file
            elif ad_req.ad_type == 'video':
                ad_req.video = media_file
            elif ad_req.ad_type == 'audio':
                ad_req.audio = media_file

        ad_req.save()
        return JsonResponse({'success': True, 'message': '수정이 완료됐습니다.'})

    return JsonResponse({'error': '잘못된 요청입니다.'}, status=400)

@login_required
def my_ad_list(request):
    my_requests = AdRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "advertisment/my_ad.html", {'my_ads': my_requests})