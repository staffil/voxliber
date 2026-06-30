function toggleBookmark(btn, storyUuid) {
  fetch('/character/story/' + storyUuid + '/bookmark/toggle/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token }}' }
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      btn.classList.toggle('active', data.bookmarked);
      const path = btn.querySelector('path');
      if (path) path.setAttribute('fill', data.bookmarked ? 'currentColor' : 'none');
    }
  });
}