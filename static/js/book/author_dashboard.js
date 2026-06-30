function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.querySelectorAll('.status-buttons').forEach(container => {
    const bookId = container.dataset.bookId;
    container.querySelectorAll('.adb-status-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const newStatus = btn.dataset.status;
            fetch(`/book/${bookId}/toggle_status/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status: newStatus })
            })
            .then(res => res.json())
            .then(() => {
                container.querySelectorAll('.adb-status-btn').forEach(b => {
                    b.disabled = false;
                    b.classList.remove('is-active', 'is-ongoing', 'is-paused', 'is-ended');
                });
                btn.disabled = true;
                btn.classList.add('is-active', `is-${newStatus}`);
            })
            .catch(err => console.error(err));
        });
    });
});
