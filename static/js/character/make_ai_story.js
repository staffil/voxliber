function publishStory() {
  if (confirm('스토리를 출시하시겠습니까?')) {
    fetch("{% url 'character:publish_story' story.id %}", {
      method: 'POST',
      headers: {'X-CSRFToken': '{{ csrf_token }}'},
    }).then(response => {
      if (response.ok) {
        alert('스토리가 출시되었습니다!');
        location.reload();
      }
    });
  }
}