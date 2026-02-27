from django.views import View
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncHour, TruncDate
from register.models import UserVisitLog
import calendar
import json

@method_decorator(staff_member_required, name='dispatch')
class VisitStatsView(View):
    def get(self, request):
        from register.models import Users
        today = timezone.now().date()
        selected_user_ids = request.GET.getlist('users')

        # 캘린더 월 선택
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))

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

        # 캘린더 데이터 - 해당 월 일별 방문자 수
        from datetime import date
        import calendar as cal
        first_day = date(year, month, 1)
        last_day = date(year, month, cal.monthrange(year, month)[1])

        monthly_visits = (
            UserVisitLog.objects
            .filter(visited_at__date__gte=first_day, visited_at__date__lte=last_day)
            .annotate(date=TruncDate('visited_at'))
            .values('date')
            .annotate(
                total=Count('id'),
                unique=Count('ip_address', distinct=True)
            )
            .order_by('date')
        )
        calendar_data = {str(item['date']): {'total': item['total'], 'unique': item['unique']} for item in monthly_visits}

        # 이전/다음 달 계산
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1

        # 캘린더 주 단위 구성
        cal_matrix = cal.monthcalendar(year, month)

        all_users = Users.objects.filter(is_active=True).order_by('nickname')
        cal_weeks = []
        for week in cal_matrix:
            week_days = []
            for day in week:
                if day == 0:
                    week_days.append(None)
                else:
                    from datetime import date as date_cls
                    d = date_cls(year, month, day)
                    key = str(d)
                    data = calendar_data.get(key, {'total': 0, 'unique': 0})
                    week_days.append({
                        'day': day,
                        'date': key,
                        'total': data['total'],
                        'unique': data['unique'],
                        'is_today': (d == today),
                    })
            cal_weeks.append(week_days)
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
            # 캘린더
            'year': year,
            'month': month,
            'cal_weeks': cal_weeks ,
            'month_name': f"{year}년 {month}월",
            'cal_matrix': cal_matrix,
            'calendar_data': calendar_data,
            'prev_year': prev_year,
            'prev_month': prev_month,
            'next_year': next_year,
            'next_month': next_month,
        })