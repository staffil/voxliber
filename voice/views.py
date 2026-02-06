from django.shortcuts import render, redirect
from django.http import HttpResponse
from book.models import VoiceList, MyVoiceList, VoiceType
from django.db.models import Count
from django.db.models import Count, Q
from register.decorator import login_required_to_main

# Create your views here.

@login_required_to_main
def voice_list(request):
    if request.method == 'POST':
        voice_id = request.POST.get('voice_id')
        alias = request.POST.get("alias_name")
        MyVoiceList.objects.create(
            user=request.user,
            voice_id=voice_id,
            alias_name=alias
        )

    

    # 타입 필터링
    selected_type_ids = request.GET.getlist('type_id')

    voice_lists = VoiceList.objects.all()

    if selected_type_ids:
        voice_lists = (
            voice_lists
            .filter(types__id__in=selected_type_ids)
            .annotate(
                match_count=Count(
                    'types',
                    filter=Q(types__id__in=selected_type_ids),
                    distinct=True
                )
            )
            .filter(match_count=len(selected_type_ids))
        )
    # 모든 VoiceType 가져오기
    voice_types = VoiceType.objects.all()

    # 내 보이스 목록 가져오기 (로그인한 경우)
    my_voices = []
    books = []
    if request.user.is_authenticated:
        from book.models import Books
        my_voices = MyVoiceList.objects.filter(user=request.user).select_related('voice')
        books = Books.objects.filter(user=request.user)

    context = {
        'voice_lists': voice_lists,
        'voice_types': voice_types,
        'selected_type_ids': list(map(int, selected_type_ids)),
        'my_voices': my_voices,
        'books': books,
    }

    return render(request, 'voice/voice_list.html', context)

