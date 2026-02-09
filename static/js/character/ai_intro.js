
    function renderAvatar(user) {
    if (user.user_img) {
        return `<img src="${user.user_img}" alt="${user.username}">`;
    }
    return `<span class="avatar-text">
        ${user.username.charAt(0).toUpperCase()}
    </span>`;
}

document.addEventListener('DOMContentLoaded', function() {
    const llmUuid = '{{ llm.public_uuid }}';
    const csrfToken = '{{ csrf_token }}';

    // 좋아요 토글
    const likeBtn = document.getElementById('like-btn');
    const likeBadge = document.getElementById('like-badge');

    if (likeBtn) {
        likeBtn.addEventListener('click', function() {
            fetch(`/character/api/llm/${llmUuid}/like/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                const likeCount = document.getElementById('like-count');
                const badgeIcon = likeBadge.querySelector('.like-icon');

                if (data.liked) {
                    likeBtn.classList.add('liked');
                    likeBtn.innerHTML = '<span>❤️ 좋아요 취소</span>';
                    badgeIcon.textContent = '❤️';
                } else {
                    likeBtn.classList.remove('liked');
                    likeBtn.innerHTML = '<span>🤍 좋아요</span>';
                    badgeIcon.textContent = '🤍';
                }
                likeCount.textContent = data.like_count;
            })
            .catch(error => console.error('Error:', error));
        });
    }

    // 댓글 작성
    const submitBtn = document.getElementById('submit-comment-btn');
    const commentInput = document.getElementById('comment-input');

    if (submitBtn && commentInput) {
        submitBtn.addEventListener('click', function() {
            const content = commentInput.value.trim();
            if (!content) {
                alert('댓글 내용을 입력해주세요.');
                return;
            }

            fetch(`/character/api/llm/${llmUuid}/comment/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ content: content })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const commentsList = document.getElementById('comments-list');
                    const noComments = document.getElementById('no-comments');
                    if (noComments) noComments.remove();

                    const newComment = createCommentElement(data.comment);
                    commentsList.insertBefore(newComment, commentsList.firstChild);
                    commentInput.value = '';
                } else {
                    alert(data.error || '댓글 작성에 실패했습니다.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('댓글 작성 중 오류가 발생했습니다.');
            });
        });
    }

    // 댓글 삭제
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('delete-btn')) {
            const commentId = e.target.dataset.commentId;
            if (confirm('댓글을 삭제하시겠습니까?')) {
                fetch(`/character/api/llm/comment/${commentId}/delete/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const commentItem = e.target.closest('.comment-item, .reply-item');
                        if (commentItem) commentItem.remove();
                    } else {
                        alert(data.error || '삭제에 실패했습니다.');
                    }
                });
            }
        }
    });

    function createCommentElement(comment) {
        const div = document.createElement('div');
        div.className = 'comment-item';
        div.dataset.commentId = comment.id;
        div.innerHTML = `
            <div class="comment-avatar">
                    {% if user.user_img %}
                    <img src="{{ user.user_img.url }}" alt="{{ user.nickname }}">
                    {% else %}
                        {{ user.username|slice:":1"|upper }}
                        {% endif %}        
                            </div>
            <div class="comment-body">
                <div class="comment-header">
                    <span class="comment-author">${comment.username}</span>
                    <span class="comment-date">${comment.created_at}</span>
                </div>
                <div class="comment-content">${comment.content}</div>
                <div class="comment-actions">
                    <button class="delete-btn" data-comment-id="${comment.id}">삭제</button>
                </div>
            </div>
        `;
        return div;
    }
});