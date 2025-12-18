// Star rating selection
let selectedRating = 5;

document.addEventListener('DOMContentLoaded', function() {
    // Star rating initialization
    const starRating = document.getElementById('starRating');
    if (starRating) {
        // Check if user has existing review
        const reviewText = document.getElementById('reviewText');
        if (reviewText && reviewText.value.trim()) {
            // If there's existing review text, we need to get the rating from data attribute
            const userRating = starRating.dataset.userRating;
            if (userRating) {
                selectedRating = parseInt(userRating);
            }
        }

        const stars = starRating.querySelectorAll('.star');
        updateStars(selectedRating);

        stars.forEach(star => {
            star.addEventListener('click', function() {
                selectedRating = parseInt(this.dataset.rating);
                updateStars(selectedRating);
            });
            star.addEventListener('mouseenter', function() {
                updateStars(parseInt(this.dataset.rating));
            });
        });

        starRating.addEventListener('mouseleave', function() {
            updateStars(selectedRating);
        });
    }

    // Initialize intro audio player if exists
    initIntroAudioPlayer();
});

function updateStars(rating) {
    const stars = document.querySelectorAll('#starRating .star');
    stars.forEach((star, index) => {
        star.textContent = index < rating ? '⭐' : '☆';
        star.classList.toggle('active', index < rating);
    });
}

async function submitReview() {
    const reviewText = document.getElementById('reviewText').value.trim();
    const submitUrl = document.getElementById('reviewText').dataset.submitUrl;

    console.log('리뷰 제출:', { rating: selectedRating, text: reviewText });

    try {
        const response = await fetch(submitUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `rating=${selectedRating}&review_text=${encodeURIComponent(reviewText)}`
        });

        console.log('응답 상태:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('서버 오류:', errorText);
            alert(`리뷰 등록 실패: ${response.status}`);
            return;
        }

        const data = await response.json();
        console.log('서버 응답:', data);

        if (data.success) {
            alert(data.message);
            location.reload();
        } else if (data.error) {
            alert(data.error);
        }
    } catch (error) {
        console.error('리뷰 제출 오류:', error);
        alert('리뷰 등록 중 오류가 발생했습니다: ' + error.message);
    }
}

async function submitComment() {
    const commentText = document.getElementById('commentInput').value.trim();
    const submitUrl = document.getElementById('commentInput').dataset.submitUrl;

    if (!commentText) {
        alert('댓글 내용을 입력해주세요.');
        return;
    }

    try {
        const response = await fetch(submitUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `comment=${encodeURIComponent(commentText)}`
        });

        const data = await response.json();
        if (data.success) {
            location.reload();
        }
    } catch (error) {
        alert('댓글 작성 중 오류가 발생했습니다.');
    }
}

function toggleReplyForm(commentId) {
    const replyForm = document.getElementById(`replyForm${commentId}`);
    if (replyForm) {
        replyForm.classList.toggle('active');
    }
}

async function submitReply(parentId) {
    const replyText = document.getElementById(`replyInput${parentId}`).value.trim();
    const commentInput = document.getElementById('commentInput');
    const submitUrl = commentInput ? commentInput.dataset.submitUrl : '';

    if (!replyText) {
        alert('답글 내용을 입력해주세요.');
        return;
    }

    try {
        const response = await fetch(submitUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `comment=${encodeURIComponent(replyText)}&parent_id=${parentId}`
        });

        const data = await response.json();
        if (data.success) {
            location.reload();
        }
    } catch (error) {
        alert('답글 작성 중 오류가 발생했습니다.');
    }
}

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

function toggleAnnouncementForm() {
    const form = document.getElementById('announcementForm');
    if (form) {
        if (form.style.display === 'none') {
            form.style.display = 'block';
        } else {
            form.style.display = 'none';
        }
    }
}

/* 미리듣기 오디오 플레이어 기능 */
function initIntroAudioPlayer() {
    const introAudio = document.getElementById('introAudio');
    if (!introAudio) return;

    const introPlayBtn = document.getElementById('introPlayBtn');
    const introProgressBar = document.getElementById('introProgressBar');
    const introProgressContainer = document.getElementById('introProgressContainer');
    const introCurrentTime = document.getElementById('introCurrentTime');
    const introDuration = document.getElementById('introDuration');
    const introVolumeBtn = document.getElementById('introVolumeBtn');
    const introVolumeSlider = document.getElementById('introVolumeSlider');

    // 재생/일시정지 토글
    window.toggleIntroAudio = function() {
        if (introAudio.paused) {
            introAudio.play();
            introPlayBtn.textContent = '⏸';
        } else {
            introAudio.pause();
            introPlayBtn.textContent = '▶';
        }
    };

    // 음소거 토글
    window.toggleIntroMute = function() {
        introAudio.muted = !introAudio.muted;
        introVolumeBtn.textContent = introAudio.muted ? '🔇' : '🔊';
        introVolumeSlider.value = introAudio.muted ? 0 : introAudio.volume * 100;
    };

    // 시간 포맷 함수
    function formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // 메타데이터 로드 시 총 길이 표시
    introAudio.addEventListener('loadedmetadata', function() {
        introDuration.textContent = formatTime(introAudio.duration);
    });

    // 재생 중 진행 상황 업데이트
    introAudio.addEventListener('timeupdate', function() {
        const progress = (introAudio.currentTime / introAudio.duration) * 100;
        introProgressBar.style.width = progress + '%';
        introCurrentTime.textContent = formatTime(introAudio.currentTime);
    });

    // 진행 바 클릭으로 탐색
    introProgressContainer.addEventListener('click', function(e) {
        const rect = this.getBoundingClientRect();
        const percent = (e.clientX - rect.left) / rect.width;
        introAudio.currentTime = percent * introAudio.duration;
    });

    // 볼륨 슬라이더
    introVolumeSlider.addEventListener('input', function() {
        introAudio.volume = this.value / 100;
        introAudio.muted = false;
        introVolumeBtn.textContent = this.value == 0 ? '🔇' : '🔊';
    });

    // 재생 종료 시
    introAudio.addEventListener('ended', function() {
        introPlayBtn.textContent = '▶';
        introProgressBar.style.width = '0%';
    });
}

/* 파일 업로드 - 선택된 파일명 표시 */
window.showFileName = function(input) {
    const fileInfo = document.getElementById('fileSelectedInfo');
    const fileName = document.getElementById('selectedFileName');

    if (input.files && input.files[0]) {
        fileName.textContent = input.files[0].name;
        fileInfo.classList.add('active');
    } else {
        fileInfo.classList.remove('active');
    }
};

/* ==================== 에피소드 드래그 앤 드롭 재정렬 ==================== */
document.addEventListener('DOMContentLoaded', function() {
    const episodesGrid = document.getElementById('episodesGrid');
    if (!episodesGrid) return;

    let draggedElement = null;
    let placeholder = null;

    // 드래그 시작
    episodesGrid.addEventListener('dragstart', function(e) {
        const wrapper = e.target.closest('.episode-wrapper');
        if (!wrapper || !wrapper.draggable) return;

        draggedElement = wrapper;
        wrapper.style.opacity = '0.5';
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/html', wrapper.innerHTML);

        // 플레이스홀더 생성
        placeholder = document.createElement('div');
        placeholder.className = 'episode-placeholder';
        placeholder.style.height = wrapper.offsetHeight + 'px';
        placeholder.style.margin = '8px 0';
        placeholder.style.border = '2px dashed rgba(99, 102, 241, 0.5)';
        placeholder.style.borderRadius = '12px';
        placeholder.style.background = 'rgba(99, 102, 241, 0.1)';
    });

    // 드래그 오버
    episodesGrid.addEventListener('dragover', function(e) {
        e.preventDefault();
        if (!draggedElement) return;

        const afterElement = getDragAfterElement(episodesGrid, e.clientY);
        if (afterElement == null) {
            episodesGrid.appendChild(placeholder);
        } else {
            episodesGrid.insertBefore(placeholder, afterElement);
        }
    });

    // 드래그 엔드
    episodesGrid.addEventListener('dragend', function(e) {
        const wrapper = e.target.closest('.episode-wrapper');
        if (!wrapper) return;

        wrapper.style.opacity = '1';

        if (placeholder && placeholder.parentNode) {
            // 플레이스홀더 위치에 드래그된 요소 삽입
            placeholder.parentNode.insertBefore(draggedElement, placeholder);
            placeholder.remove();

            // 순서 변경 저장
            saveNewOrder();
        }

        draggedElement = null;
    });

    // 마우스 위치 기준으로 삽입 위치 찾기
    function getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll('.episode-wrapper:not(.dragging)')];

        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;

            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    // 새로운 순서 저장
    function saveNewOrder() {
        const wrappers = episodesGrid.querySelectorAll('.episode-wrapper');
        const contentIds = Array.from(wrappers).map(wrapper => wrapper.dataset.contentId);

        // AJAX로 순서 전송
        fetch(window.location.pathname + 'reorder/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ content_ids: contentIds })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // 페이지 새로고침하여 회차 번호 업데이트
                location.reload();
            } else {
                alert('순서 변경 실패: ' + (data.error || '알 수 없는 오류'));
            }
        })
        .catch(err => {
            console.error('순서 변경 오류:', err);
            alert('순서 변경 중 오류가 발생했습니다.');
        });
    }
});
