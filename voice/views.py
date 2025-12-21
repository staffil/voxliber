from django.shortcuts import render, redirect
from django.http import HttpResponse
from book.models import VoiceList, MyVoiceList, VoiceType

# Create your views here.


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
    selected_type_id = request.GET.getlist('type_id')

    if selected_type_id:
        voice_lists = VoiceList.objects.filter(types__id__in=selected_type_id).distinct()
    else:
        voice_lists = VoiceList.objects.all()

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
        'selected_type_id': int(selected_type_id) if selected_type_id else None,
        'my_voices': my_voices,
        'books': books,
    }

    return render(request, 'voice/voice_list.html', context)

