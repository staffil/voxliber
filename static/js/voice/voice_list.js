function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

let selectedVoiceId = null;

// 전체 목록 오디오 플레이어 제어
function toggleVoicePlay(btn) {
    const player = btn.parentElement.querySelector('audio');
    const allPlayers = document.querySelectorAll('.voice-audio-player audio, .audio-player-small audio');
    const allButtons = document.querySelectorAll('.voice-audio-player .play-btn, .audio-player-small button');

    // 다른 플레이어 모두 정지
    allPlayers.forEach((p, idx) => {
        if (p !== player && !p.paused) {
            p.pause();
            allButtons[idx].innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
        }
    });

    // 현재 플레이어 토글
    if (player.paused) {
        player.play();
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/></svg>';
    } else {
        player.pause();
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
    }

    // 진행률 및 시간 업데이트
    player.ontimeupdate = function() {
        const progressBar = btn.parentElement.querySelector('.audio-progress-bar');
        const percentage = (player.currentTime / player.duration * 100) || 0;
        progressBar.style.width = percentage + '%';

        const timeDisplay = btn.parentElement.querySelector('.audio-time');
        const current = formatAudioTime(player.currentTime);
        const total = formatAudioTime(player.duration);
        timeDisplay.textContent = `${current} / ${total}`;
    };

    // 재생 종료 시
    player.onended = function() {
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
        const progressBar = btn.parentElement.querySelector('.audio-progress-bar');
        progressBar.style.width = '0%';
    };
}

// 내 보이스 오디오 플레이어 제어
function togglePlaySmall(btn) {
    const player = btn.parentElement.querySelector('audio');
    const allPlayers = document.querySelectorAll('.voice-audio-player audio, .audio-player-small audio');
    const allButtons = document.querySelectorAll('.voice-audio-player .play-btn, .audio-player-small button');

    // 다른 플레이어 모두 정지
    allPlayers.forEach((p, idx) => {
        if (p !== player && !p.paused) {
            p.pause();
            allButtons[idx].innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
        }
    });

    // 현재 플레이어 토글
    if (player.paused) {
        player.play();
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/></svg>';
    } else {
        player.pause();
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
    }

    // 진행률 및 시간 업데이트
    player.ontimeupdate = function() {
        const progress = btn.parentElement.querySelector('.progress-small');
        const percentage = (player.currentTime / player.duration * 100) || 0;
        progress.style.width = percentage + '%';

        const time = btn.parentElement.querySelector('.time-small');
        const current = formatAudioTime(player.currentTime);
        const total = formatAudioTime(player.duration);
        time.textContent = `${current} / ${total}`;
    };

    // 재생 종료 시
    player.onended = function() {
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
        const progress = btn.parentElement.querySelector('.progress-small');
        progress.style.width = '0%';
    };
}

function formatAudioTime(seconds) {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function selectVoice(voiceId) {
    selectedVoiceId = voiceId;

    const container = document.getElementById("voice_name");

    container.innerHTML = `
        <div id="voice_overlay" style="
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: rgba(0,0,0,0.6);
            backdrop-filter: blur(4px);
            z-index: 999;
        " onclick="closeAlias()"></div>

        <div id="voice_modal" style="
            position: fixed;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            background:#16213e;
            padding: 25px;
            border-radius: 14px;
            color:#fff;
            width: 350px;
            z-index: 1000;
            box-shadow:0 6px 25px rgba(0,0,0,0.5);
        ">
            <h3 style="text-align:center; margin-bottom:18px;">보이스 별칭 설정</h3>

            <input id="alias_input" type="text" placeholder="별칭 입력" style="
                width:100%;
                padding:12px;
                border-radius:8px;
                border:none;
                background:#0f172a;
                color:white;
                margin-bottom:18px;
            ">

            <button onclick="submitAlias()" style="
                width:100%;
                padding:12px;
                background:#8b5cf6;
                border:none;
                border-radius:8px;
                color:white;
                font-weight:600;
            ">저장</button>

            <button onclick="closeAlias()" style="
                width:100%;
                padding:12px;
                background:#444;
                border:none;
                border-radius:8px;
                color:white;
                margin-top:10px;
            ">취소</button>
        </div>
    `;

    container.style.display = "block";
}

function submitAlias() {
    const aliasInput = document.getElementById("alias_input");
    const aliasName = aliasInput.value.trim();

    if (!aliasName) {
        alert("별칭을 입력해주세요.");
        return;
    }

    const csrfToken = getCookie('csrftoken'); 
    const formData = new FormData();
    formData.append('voice_id', selectedVoiceId);
    formData.append('alias_name', aliasName);

fetch("/voice/voice/list/", {
        method: "POST",
        body: formData,
        headers: {
            "X-CSRFToken": csrfToken
        }
    })
    .then(res => {
        if (res.ok) {
            alert("보이스가 성공적으로 선택되었습니다!");
            location.reload();
        } else {
            alert("보이스 선택 실패!");
        }
    })
    .catch(err => {
        console.error(err);
        alert("오류 발생!");
    });
}

function closeAlias() {
    const container = document.getElementById("voice_name");
    container.innerHTML = "";
    container.style.display = "none";
}

// 스크롤 위치 저장 및 복원
window.addEventListener("beforeunload", () => {
    localStorage.setItem("scrollPos", window.scrollY);
});

window.addEventListener("load", () => {
    const pos = localStorage.getItem("scrollPos");
    if (pos) window.scrollTo(0, pos);
});
