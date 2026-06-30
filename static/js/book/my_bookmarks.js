function removeBookmark(bookUuid) {
  if (!confirm('북마크를 제거할까요?')) return;
  fetch('/book/bookmark/' + bookUuid + '/toggle/', {
    method: 'POST',
    headers: {'X-CSRFToken': '{{ csrf_token }}', 'Content-Type': 'application/json'}
  }).then(r => r.json()).then(data => {
    if (data.success && !data.bookmarked) {
      var card = document.getElementById('bm-' + bookUuid);
      if (card) { card.style.opacity = '0'; card.style.transform = 'scale(.9)'; card.style.transition = 'all .3s'; setTimeout(() => card.remove(), 300); }
    }
  });
}