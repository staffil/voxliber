

// ===================== 조회수 증가 (중복 방지) =====================
fetch(`/book/book/snap/${snapId}/view/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCookie('csrftoken') }
})
.then(res => res.json())
.then(data => {
    document.getElementById('viewCount').textContent = data.views;
})
.catch(err => console.error(err));

// ===================== 비디오 컨트롤 =====================
if (video) {
    videoWrapper.addEventListener('click', function(e) {
        if (e.target === video || e.target === playOverlay || e.target.closest('.play-overlay')) {
            if (video.paused) {
                video.play();
                playOverlay.classList.remove('visible');
            } else {
                video.pause();
                playOverlay.classList.add('visible');
            }
        }
    });

    video.addEventListener('play', () => playOverlay.classList.remove('visible'));
    video.addEventListener('pause', () => playOverlay.classList.add('visible'));

    video.play().catch(() => playOverlay.classList.add('visible'));
}

// ===================== 좋아요 토글 =====================
likeBtn.addEventListener('click', function() {
    fetch(`/book/book/snap/${snapId}/like/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') }
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById('likeCount').textContent = data.likes;
        document.getElementById('likeIcon').textContent = data.liked ? '❤️' : '🤍';
    })
    .catch(err => console.error(err));
});

// ===================== 댓글 토글 =====================
document.getElementById('commentBtn').addEventListener('click', function() {
    document.getElementById('commentsPanel').classList.toggle('open');
});

closeCommentsBtn.addEventListener('click', function() {
    commentsPanel.classList.remove('open'); // 닫기
});

// ===================== 댓글 작성 =====================
function toggleComments(event) {
    if (event.key !== 'Enter') return;
    const content = event.target.value.trim();
    if (!content) return;

    fetch(`/book/book/snap/${snapId}/comment/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: `content=${encodeURIComponent(content)}`
    })
    .then(res => res.json())
    .then(data => {
        const commentsList = document.getElementById('commentsList');
        const commentHTML = `
            <div class="comment-item">
                <div class="comment-author">${data.user}</div>
                <div class="comment-text">${data.content}</div>
                <div class="comment-time">방금 전</div>
            </div>
        `;
        commentsList.insertAdjacentHTML('afterbegin', commentHTML);
        event.target.value = '';
    })
    .catch(err => console.error(err));
}

// ===================== 공유 =====================
document.getElementById('shareBtn').addEventListener('click', function() {
    const url = window.location.href;
    if (navigator.share) {
        navigator.share({ title: '{{ snap.snap_title }}', url });
    } else {
        navigator.clipboard.writeText(url);
        alert('링크가 복사되었습니다!');
    }
});

// ===================== 스냅 네비게이션 =====================
function navigateSnap(snapId) {
    window.location.href = `/book/book/snap/${snapId}/`;
}

// ===================== 드래그/스와이프/휠/키보드 =====================
let startY = 0, startX = 0, isDragging = false, startTime = 0;

function startDrag(e) {
    if (e.target.closest('button, a, input, .action-btn')) return;
    startY = e.touches ? e.touches[0].clientY : e.clientY;
    startX = e.touches ? e.touches[0].clientX : e.clientX;
    startTime = Date.now();
    isDragging = true;
}

function endDrag(e, isTouch) {
    if (!isDragging) return;
    const endY = isTouch ? e.changedTouches[0].clientY : e.clientY;
    const endX = isTouch ? e.changedTouches[0].clientX : e.clientX;
    const deltaY = startY - endY;
    const deltaX = Math.abs(startX - endX);
    const deltaTime = Date.now() - startTime;

    if (Math.abs(deltaY) > deltaX && Math.abs(deltaY) > (isTouch ? 50 : 80) && deltaTime < (isTouch ? 500 : 800)) {
        if (deltaY > 0 && nextSnapId) navigateSnap(nextSnapId);
        else if (deltaY < 0 && prevSnapId) navigateSnap(prevSnapId);
    }
    isDragging = false;
}

// 터치 이벤트
document.addEventListener('touchstart', startDrag, { passive: true });
document.addEventListener('touchend', e => endDrag(e, true), { passive: true });

// 마우스 이벤트
document.addEventListener('mousedown', startDrag);
document.addEventListener('mouseup', e => endDrag(e, false));
document.addEventListener('mouseleave', () => isDragging = false);

// 휠 스크롤 네비게이션
let wheelTimeout, lastWheelTime = 0;
document.addEventListener('wheel', function(e) {
    const now = Date.now();
    if (now - lastWheelTime < 500) return;

    clearTimeout(wheelTimeout);
    wheelTimeout = setTimeout(() => {
        if (e.deltaY > 0 && nextSnapId) navigateSnap(nextSnapId);
        else if (e.deltaY < 0 && prevSnapId) navigateSnap(prevSnapId);
        lastWheelTime = Date.now();
    }, 50);
}, { passive: true });

// 키보드
document.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowUp' && prevSnapId) navigateSnap(prevSnapId);
    else if (e.key === 'ArrowDown' && nextSnapId) navigateSnap(nextSnapId);
});


function handleCommentKeyPress(event) {
    if (event.key !== 'Enter') return;
    const content = event.target.value.trim();
    if (!content) return;

    fetch(`/book/book/snap/${snapId}/comment/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: `content=${encodeURIComponent(content)}`
    })
    .then(res => res.json())
    .then(data => {
        const commentsList = document.getElementById('commentsList');
        const commentHTML = `
            <div class="comment-item">
                <div class="comment-author">${data.user}</div>
                <div class="comment-text">${data.content}</div>
                <div class="comment-time">방금 전</div>
            </div>
        `;
        commentsList.insertAdjacentHTML('afterbegin', commentHTML);
        event.target.value = '';
    })
    .catch(err => console.error(err));
}

// ===================== CSRF =====================
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
function formatTime(t) {
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

video.addEventListener("loadedmetadata", () => {
    timeDisplay.textContent = `00:00 / ${formatTime(video.duration)}`;
});

video.addEventListener("timeupdate", () => {
    const progress = (video.currentTime / video.duration) * 100;
    seekBar.value = progress;
    timeDisplay.textContent = `${formatTime(video.currentTime)} / ${formatTime(video.duration)}`;
});

seekBar.addEventListener("input", (e) => {
    e.stopPropagation();
});
seekBar.addEventListener("mousedown", (e) => {
    e.stopPropagation();
});
seekBar.addEventListener("touchstart", (e) => {
    e.stopPropagation();
});