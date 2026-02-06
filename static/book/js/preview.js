/**
 * preview.js
 * 미리듣기 관련 기능
 */

// 미리듣기 페이지로 이동
async function goToPreview() {
    saveCurrentPage();

    const episodeTitle = document.getElementById('episodeTitle').value.trim();
    if (!episodeTitle) {
        alert('에피소드 제목을 입력해주세요.');
        return;
    }

    // 오디오가 있는 페이지만 필터링
    const hasAudio = pages.some(page => page.audioFile);
    if (!hasAudio) {
        alert('최소 하나의 대사에 오디오를 생성해주세요.');
        return;
    }

    // 임시저장 후 미리듣기 페이지로 이동
    await saveDraft();

    // 미리듣기 페이지로 이동 (쿼리 파라미터로 bookId 전달)
  window.location.href = `/book/preview/?public_uuid=${bookId}`;
}

// CSRF 토큰 가져오기
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
