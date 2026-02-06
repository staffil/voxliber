// =============================================
// 공통 유틸리티
// =============================================
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
    return null;
}

const csrfToken = getCookie('csrftoken');

// =============================================
// 별점 (Star Rating)
// =============================================
let selectedRating = 5;

function updateStars(rating) {
    document.querySelectorAll('#starRating .star').forEach((star, index) => {
        const isActive = index < rating;
        star.textContent = isActive ? '⭐' : '☆';
        star.classList.toggle('active', isActive);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const starRating = document.getElementById('starRating');
    if (!starRating) return;

    // 기존 리뷰가 있으면 data 속성에서 평점 가져오기
    const userRating = parseInt(starRating.dataset.userRating, 10);
    if (!isNaN(userRating)) {
        selectedRating = userRating;
    }

    updateStars(selectedRating);

    starRating.querySelectorAll('.star').forEach(star => {
        star.addEventListener('click', () => {
            selectedRating = parseInt(star.dataset.rating, 10);
            updateStars(selectedRating);
        });

        star.addEventListener('mouseenter', () => {
            updateStars(parseInt(star.dataset.rating, 10));
        });
    });

    starRating.addEventListener('mouseleave', () => {
        updateStars(selectedRating);
    });

    // 오디오 플레이어 초기화
    initIntroAudioPlayer();

    // 드래그 앤 드롭 초기화
    initEpisodeDragAndDrop();
});

// =============================================
// 리뷰 제출
// =============================================
async function submitReview() {
    const textarea = document.getElementById('reviewText');
    if (!textarea) return;

    const reviewText = textarea.value.trim();
    const submitUrl = textarea.dataset.submitUrl;

    if (!reviewText) {
        alert('리뷰 내용을 입력해주세요.');
        return;
    }

    try {
        const res = await fetch(submitUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `rating=${selectedRating}&review_text=${encodeURIComponent(reviewText)}`,
        });

        if (!res.ok) {
            throw new Error(`서버 응답 오류: ${res.status}`);
        }

        const data = await res.json();

        if (data.success) {
            alert(data.message || '리뷰가 등록되었습니다.');
            location.reload(); // 또는 DOM에 직접 추가하는 방식으로 변경 가능
        } else {
            alert(data.error || '리뷰 등록에 실패했습니다.');
        }
    } catch (err) {
        console.error('리뷰 제출 실패:', err);
        alert('리뷰 등록 중 오류가 발생했습니다.');
    }
}

// =============================================
// 댓글 / 답글
// =============================================
async function submitComment() {
    const input = document.getElementById('commentInput');
    if (!input) return;

    const text = input.value.trim();
    const url = input.dataset.submitUrl;

    if (!text) {
        alert('댓글을 입력해주세요.');
        return;
    }

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `comment=${encodeURIComponent(text)}`,
        });

        const data = await res.json();

        if (data.success) {
            addCommentToDOM(data.comment); // DOM에 바로 추가 (아래 함수 참고)
            input.value = '';
        } else {
            alert(data.error || '댓글 등록 실패');
        }
    } catch (err) {
        console.error(err);
        alert('댓글 작성 중 오류 발생');
    }
}

function toggleReplyForm(commentUuid) {
    const form = document.getElementById(`replyForm${commentUuid}`);
    if (form) {
        form.classList.toggle('active');
    }
}

async function submitReply(parentUuid) {
    const input = document.getElementById(`replyInput${parentUuid}`);
    if (!input) return;

    const text = input.value.trim();
    if (!text) {
        alert('답글 내용을 입력해주세요.');
        return;
    }

    const url = document.querySelector('#commentInput')?.dataset.submitUrl || '';

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `comment=${encodeURIComponent(text)}&parent_uuid=${encodeURIComponent(parentUuid)}`,
        });

        if (!res.ok) {
            throw new Error(`서버 오류: ${res.status}`);
        }

        const data = await res.json();

        if (data.success) {
            addReplyToDOM(parentUuid, {
                comment: text,
                nickname: '나', // 실제로는 서버에서 내려오는 값 사용 권장
                created_at: new Date().toLocaleString('ko-KR', {
                    year: 'numeric', month: '2-digit', day: '2-digit',
                    hour: '2-digit', minute: '2-digit'
                })
            });
            input.value = '';
            toggleReplyForm(parentUuid);
        } else {
            alert(data.error || '답글 등록 실패');
        }
    } catch (err) {
        console.error('답글 제출 실패:', err);
        alert('답글 작성 중 오류가 발생했습니다.');
    }
}

// DOM에 댓글 바로 추가 (새로고침 없이)
function addCommentToDOM(commentData) {
    const list = document.getElementById('commentsList');
    if (!list) return;

    const item = document.createElement('div');
    item.className = 'comment-item';
    item.innerHTML = `
        <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
            <span class="comment-author">${commentData.nickname || '나'}</span>
            <span class="comment-date">${commentData.created_at}</span>
        </div>
        <div class="comment-text">${commentData.comment.replace(/\n/g, '<br>')}</div>
        <div class="reply-form" id="replyForm${commentData.public_uuid}" style="display:none;">
            <textarea class="comment-input" id="replyInput${commentData.public_uuid}" placeholder="답글을 입력하세요..."></textarea>
            <button class="submit-comment-btn" onclick="submitReply('${commentData.public_uuid}')">답글 작성</button>
        </div>
    `;

    list.insertBefore(item, list.firstChild);
}

function addReplyToDOM(parentUuid, replyData) {
    const replyForm = document.getElementById(`replyForm${parentUuid}`);
    if (!replyForm) return;

    const container = document.createElement('div');
    container.className = 'comment-reply';
    container.innerHTML = `
        <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
            <span style="font-weight:700; color:#667eea;">${replyData.nickname}</span>
            <span class="comment-date">${replyData.created_at}</span>
        </div>
        <div class="comment-text">${replyData.comment.replace(/\n/g, '<br>')}</div>
    `;

    replyForm.parentElement.appendChild(container);
}

// =============================================
// 오디오 플레이어 (미리듣기)
// =============================================
function initIntroAudioPlayer() {
    const audio = document.getElementById('introAudio');
    if (!audio) return;

    const playBtn     = document.getElementById('introPlayBtn');
    const progressBar = document.getElementById('introProgressBar');
    const progressCon = document.getElementById('introProgressContainer');
    const currentTime = document.getElementById('introCurrentTime');
    const durationEl  = document.getElementById('introDuration');
    const volumeBtn   = document.getElementById('introVolumeBtn');
    const volumeSlider= document.getElementById('introVolumeSlider');

    function formatTime(sec) {
        if (!sec || isNaN(sec)) return '0:00';
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return `${m}:${s.toString().padStart(2,'0')}`;
    }

    audio.addEventListener('loadedmetadata', () => {
        durationEl.textContent = formatTime(audio.duration);
    });

    audio.addEventListener('timeupdate', () => {
        if (!audio.duration) return;
        const pct = (audio.currentTime / audio.duration) * 100;
        progressBar.style.width = `${pct}%`;
        currentTime.textContent = formatTime(audio.currentTime);
    });

    window.toggleIntroAudio = () => {
        if (audio.paused) {
            audio.play().catch(e => console.warn("재생 실패:", e));
            playBtn.textContent = '⏸';
        } else {
            audio.pause();
            playBtn.textContent = '▶';
        }
    };

    window.toggleIntroMute = () => {
        audio.muted = !audio.muted;
        volumeBtn.textContent = audio.muted ? '🔇' : '🔊';
        volumeSlider.value = audio.muted ? 0 : audio.volume * 100;
    };

    progressCon.addEventListener('click', e => {
        const rect = progressCon.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        audio.currentTime = pct * audio.duration;
    });

    volumeSlider.addEventListener('input', () => {
        audio.volume = volumeSlider.value / 100;
        audio.muted = false;
        volumeBtn.textContent = volumeSlider.value == 0 ? '🔇' : '🔊';
    });

    audio.addEventListener('ended', () => {
        playBtn.textContent = '▶';
        progressBar.style.width = '0%';
    });
}

// =============================================
// 에피소드 드래그 앤 드롭 재정렬
// =============================================
function initEpisodeDragAndDrop() {
    const grid = document.getElementById('episodesGrid');
    if (!grid) return;

    let dragged = null;
    let placeholder = null;

    grid.addEventListener('dragstart', e => {
        const wrapper = e.target.closest('.episode-wrapper');
        if (!wrapper?.draggable) return;

        dragged = wrapper;
        wrapper.classList.add('dragging');
        wrapper.style.opacity = '0.6';

        placeholder = document.createElement('div');
        placeholder.className = 'episode-placeholder';
        placeholder.style.height = `${wrapper.offsetHeight}px`;
    });

    grid.addEventListener('dragover', e => {
        e.preventDefault();
        if (!dragged) return;

        const after = getDragAfterElement(grid, e.clientY);
        if (after) {
            grid.insertBefore(placeholder, after);
        } else {
            grid.appendChild(placeholder);
        }
    });

    grid.addEventListener('dragend', () => {
        if (!dragged) return;

        dragged.classList.remove('dragging');
        dragged.style.opacity = '1';

        if (placeholder?.parentNode) {
            placeholder.parentNode.insertBefore(dragged, placeholder);
            placeholder.remove();
            saveEpisodeOrder();
        }

        dragged = null;
        placeholder = null;
    });

    function getDragAfterElement(container, y) {
        const draggableEls = [...container.querySelectorAll('.episode-wrapper:not(.dragging)')];

        return draggableEls.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            if (offset < 0 && offset > closest.offset) {
                return { offset, element: child };
            }
            return closest;
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    function saveEpisodeOrder() {
        const wrappers = grid.querySelectorAll('.episode-wrapper');
        const ids = Array.from(wrappers).map(w => w.dataset.contentId);

        fetch(`${window.location.pathname}reorder/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ content_ids: ids }),
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                location.reload(); // 필요 시 주석 처리하고 순서만 UI 반영 가능
            } else {
                alert('순서 저장 실패: ' + (data.error || '알 수 없는 오류'));
            }
        })
        .catch(err => {
            console.error('순서 저장 오류', err);
            alert('순서 변경 중 오류가 발생했습니다.');
        });
    }
}

// =============================================
// 파일 선택 시 파일명 표시 (필요 시 사용)
// =============================================
window.showFileName = function(input) {
    const info = document.getElementById('fileSelectedInfo');
    const nameEl = document.getElementById('selectedFileName');
    if (!info || !nameEl) return;

    if (input.files?.[0]) {
        nameEl.textContent = input.files[0].name;
        info.classList.add('active');
    } else {
        info.classList.remove('active');
    }
};