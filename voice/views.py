from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from book.models import VoiceList, MyVoiceList, VoiceType
from django.db.models import Count
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from register.decorator import login_required_to_main
import json, os
from openai import OpenAI

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


@login_required_to_main
@require_POST
def ai_voice_search(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '잘못된 요청입니다.'}, status=400)

    query = data.get('query', '').strip()
    if not query:
        return JsonResponse({'matched_ids': []})

    voices = list(VoiceList.objects.values('id', 'voice_name', 'voice_description', 'language_code'))
    if not voices:
        return JsonResponse({'matched_ids': []})

    voice_lines = '\n'.join(
        f"ID:{v['id']} | 이름:{v['voice_name']} | 언어:{v['language_code']} | 설명:{v['voice_description'] or '없음'}"
        for v in voices
    )

    prompt = (
        f"다음은 목소리 목록입니다:\n{voice_lines}\n\n"
        f"사용자 요청: \"{query}\"\n\n"
        "위 요청에 가장 잘 맞는 목소리의 ID 목록을 JSON 배열로만 반환하세요. 예: [1, 3, 7]\n"
        "맞는 목소리가 없으면 빈 배열 []을 반환하세요.\n"
        "다른 설명 없이 JSON 배열만 반환하세요."
    )

    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        result_text = response.choices[0].message.content.strip()
        matched_ids = json.loads(result_text)
        if not isinstance(matched_ids, list):
            matched_ids = []
    except Exception as e:
        return JsonResponse({'error': f'AI 검색 오류: {str(e)}'}, status=500)

    return JsonResponse({'matched_ids': matched_ids})
