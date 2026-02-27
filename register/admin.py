from django.views import View
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncHour, TruncDate
from register.models import UserVisitLog
from django.db import models

@method_decorator(staff_member_required, name='dispatch')
class VisitStatsView(View):
    def get(self, request):
        from register.models import Users
        today = timezone.now().date()
        selected_user_ids = request.GET.getlist('users')  # 다중 선택

        today_qs = UserVisitLog.objects.filter(visited_at__date=today)
        today_total = today_qs.count()
        today_unique = today_qs.values('ip_address').distinct().count()

        hourly = (
            today_qs
            .annotate(hour=TruncHour('visited_at'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )

        weekly = (
            UserVisitLog.objects
            .annotate(date=TruncDate('visited_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('-date')[:7]
        )

        # 전체 유저 목록 (select용)
        all_users = Users.objects.filter(is_active=True).order_by('nickname')

        # 선택된 유저들 통계
        users_stats = []
        if selected_user_ids:
            selected_users = Users.objects.filter(user_id__in=selected_user_ids)
            for user in selected_users:
                visits = UserVisitLog.objects.filter(user=user).order_by('visited_at')
                total_visits = visits.count()

                daily_visits = (
                    visits
                    .annotate(date=TruncDate('visited_at'))
                    .values('date')
                    .annotate(count=Count('id'))
                    .order_by('-date')
                )

                visit_dates = list(daily_visits)
                total_days = len(visit_dates)
                revisit_days = sum(1 for d in visit_dates if d['count'] >= 2)
                revisit_rate = round((revisit_days / total_days * 100), 1) if total_days > 0 else 0

                first_visit = visits.first()
                last_visit = visits.last()

                users_stats.append({
                    'user': user,
                    'total_visits': total_visits,
                    'total_days': total_days,
                    'revisit_days': revisit_days,
                    'revisit_rate': revisit_rate,
                    'first_visit': first_visit.visited_at if first_visit else None,
                    'last_visit': last_visit.visited_at if last_visit else None,
                    'daily_visits': daily_visits[:14],
                })

        return render(request, 'admin/register/visit_stats.html', {
            'today': today,
            'today_total': today_total,
            'today_unique': today_unique,
            'hourly': hourly,
            'weekly': weekly,
            'all_users': all_users,
            'users_stats': users_stats,
            'selected_user_ids': [str(i) for i in selected_user_ids],
        })