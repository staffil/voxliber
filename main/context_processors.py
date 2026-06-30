from book.models import ListeningHistory


def sidebar_context(request):
    if not request.user.is_authenticated:
        return {}

    try:
        qs = ListeningHistory.objects.filter(
            user=request.user,
            last_position__gt=0,
        ).select_related('book').order_by('-last_listened_at')

        seen, resume_books = set(), []
        for lh in qs:
            if lh.book_id not in seen:
                resume_books.append(lh)
                seen.add(lh.book_id)
            if len(resume_books) >= 5:
                break
    except Exception:
        resume_books = []

    return {
        'sidebar_resume_books': resume_books,
    }
