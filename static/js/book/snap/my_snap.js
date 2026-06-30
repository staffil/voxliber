function deleteSnap(uuid, title) {
  if (!confirm('"' + title + '" 스냅을 삭제할까요?')) return;
  fetch('/book/snap/' + uuid + '/delete/', {
    method: 'POST',
    headers: {'X-CSRFToken': '{{ csrf_token }}', 'Content-Type': 'application/json'}
  }).then(r => r.json()).then(data => {
    if (data.success) location.reload();
    else alert('삭제에 실패했습니다.');
  });
}