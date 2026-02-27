from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from advertisment.models import Advertisement, AdImpression, AdRequest
from datetime import timedelta
from decimal import Decimal
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


@login_required
def ad_settlement(request):
    """광고 정산 페이지 (staff 전용)"""
    if not request.user.is_staff:
        return redirect('main:index')

    now = timezone.now()
    period = request.GET.get('period', 'this_month')

    if period == 'last_month':
        first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_of_this - timedelta(seconds=1)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'custom':
        start_str = request.GET.get('start', '')
        end_str = request.GET.get('end', '')
        try:
            from django.utils.dateparse import parse_date
            sd = parse_date(start_str)
            ed = parse_date(end_str)
            start = timezone.make_aware(timezone.datetime(sd.year, sd.month, sd.day, 0, 0, 0))
            end = timezone.make_aware(timezone.datetime(ed.year, ed.month, ed.day, 23, 59, 59))
        except Exception:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
            period = 'this_month'
    else:  # this_month
        period = 'this_month'
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now

    ads = Advertisement.objects.all().order_by('-created_at')
    ad_stats = []
    total_impressions = 0
    total_cpv = 0
    total_clicks = 0
    total_revenue = Decimal('0')

    for ad in ads:
        impressions = AdImpression.objects.filter(ad=ad, created_at__range=(start, end))
        imp_count = impressions.count()

        # CPV: 스킵 안 하고 min_watch_seconds 이상 시청
        if ad.min_watch_seconds > 0:
            cpv_count = impressions.filter(
                is_skipped=False,
                watched_seconds__gte=ad.min_watch_seconds,
            ).count()
        else:
            cpv_count = 0

        click_count = impressions.filter(is_clicked=True).count()
        skip_count = impressions.filter(is_skipped=True).count()

        # 수익 계산
        revenue = Decimal('0')
        if ad.pricing_type == 'cpm':
            revenue = (Decimal(imp_count) / 1000) * ad.unit_price
        elif ad.pricing_type == 'cpv':
            revenue = Decimal(cpv_count) * ad.unit_price
        elif ad.pricing_type == 'cpc':
            revenue = Decimal(click_count) * ad.unit_price
        elif ad.pricing_type == 'flat':
            revenue = ad.unit_price

        # CPC 보너스 (이미지 광고 혼합 방식)
        if ad.enable_cpc_bonus:
            revenue += Decimal(click_count) * ad.cpc_bonus_price

        ad_stats.append({
            'ad': ad,
            'imp_count': imp_count,
            'cpv_count': cpv_count,
            'click_count': click_count,
            'skip_count': skip_count,
            'revenue': revenue,
        })

        total_impressions += imp_count
        total_cpv += cpv_count
        total_clicks += click_count
        total_revenue += revenue

    # 수익 내림차순 정렬
    ad_stats.sort(key=lambda x: x['revenue'], reverse=True)

    return render(request, 'advertisment/settlement.html', {
        'ad_stats': ad_stats,
        'total_impressions': total_impressions,
        'total_cpv': total_cpv,
        'total_clicks': total_clicks,
        'total_revenue': total_revenue,
        'period': period,
        'start': start,
        'end': end,
        'start_str': start.strftime('%Y-%m-%d'),
        'end_str': end.strftime('%Y-%m-%d'),
    })