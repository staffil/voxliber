// ── 현재 재생 중인 오디오 추적 ──
let _vlActiveAudio = null;
let _vlActiveBtn   = null;

const PLAY_ICON  = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const PAUSE_ICON = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
const PLAY_ICON_SM  = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const PAUSE_ICON_SM = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';

function _vlFmt(s) {
    if (!isFinite(s) || isNaN(s)) return '0:00';
    return Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
}

function _vlStopCurrent() {
    if (!_vlActiveAudio) return;
    _vlActiveAudio.pause();
    _vlActiveAudio.currentTime = 0;
    if (_vlActiveBtn) {
        const isSmall = _vlActiveBtn.classList.contains('vl-play-sm');
        _vlActiveBtn.innerHTML = isSmall ? PLAY_ICON_SM : PLAY_ICON;
        const player = _vlActiveBtn.closest('.vl-card-player, .vl-my-player');
        if (player) {
            const fill = player.querySelector('.vl-card-fill, .vl-fill-sm');
            const time = player.querySelector('.vl-card-time, .vl-time-sm');
            if (fill) fill.style.width = '0%';
            if (time) time.textContent = isSmall ? '0:00' : '0:00 / 0:00';
        }
    }
    _vlActiveAudio = null;
    _vlActiveBtn   = null;
}

// 전체 보이스 목록 카드 플레이어
function toggleVoicePlay(btn) {
    const player = btn.closest('.vl-card-player');
    const audio  = player ? player.querySelector('audio') : null;
    if (!audio) return;

    if (_vlActiveAudio && _vlActiveAudio !== audio) _vlStopCurrent();

    if (audio.paused) {
        audio.play();
        btn.innerHTML = PAUSE_ICON;
        _vlActiveAudio = audio;
        _vlActiveBtn   = btn;
    } else {
        audio.pause();
        btn.innerHTML = PLAY_ICON;
        _vlActiveAudio = null;
        _vlActiveBtn   = null;
    }

    audio.ontimeupdate = function () {
        const pct  = audio.duration ? (audio.currentTime / audio.duration * 100) : 0;
        const fill = player.querySelector('.vl-card-fill');
        const time = player.querySelector('.vl-card-time');
        if (fill) fill.style.width = pct + '%';
        if (time) time.textContent = _vlFmt(audio.currentTime) + ' / ' + _vlFmt(audio.duration);
    };

    audio.onended = function () {
        btn.innerHTML = PLAY_ICON;
        const fill = player.querySelector('.vl-card-fill');
        const time = player.querySelector('.vl-card-time');
        if (fill) fill.style.width = '0%';
        if (time) time.textContent = '0:00 / 0:00';
        _vlActiveAudio = null;
        _vlActiveBtn   = null;
    };
}

// 내 보이스 컬렉션 소형 플레이어
function togglePlaySmall(btn) {
    const player = btn.closest('.vl-my-player');
    const audio  = player ? player.querySelector('audio') : null;
    if (!audio) return;

    if (_vlActiveAudio && _vlActiveAudio !== audio) _vlStopCurrent();

    if (audio.paused) {
        audio.play();
        btn.innerHTML = PAUSE_ICON_SM;
        _vlActiveAudio = audio;
        _vlActiveBtn   = btn;
    } else {
        audio.pause();
        btn.innerHTML = PLAY_ICON_SM;
        _vlActiveAudio = null;
        _vlActiveBtn   = null;
    }

    audio.ontimeupdate = function () {
        const pct  = audio.duration ? (audio.currentTime / audio.duration * 100) : 0;
        const fill = player.querySelector('.vl-fill-sm');
        const time = player.querySelector('.vl-time-sm');
        if (fill) fill.style.width = pct + '%';
        if (time) time.textContent = _vlFmt(audio.currentTime);
    };

    audio.onended = function () {
        btn.innerHTML = PLAY_ICON_SM;
        const fill = player.querySelector('.vl-fill-sm');
        const time = player.querySelector('.vl-time-sm');
        if (fill) fill.style.width = '0%';
        if (time) time.textContent = '0:00';
        _vlActiveAudio = null;
        _vlActiveBtn   = null;
    };
}

// 보이스 선택 → 별칭 입력 후 저장
function selectVoice(voiceId) {
    const alias = prompt('이 보이스의 별칭을 입력하세요 (예: 주인공 목소리)');
    if (alias === null) return; // 취소

    const fd = new FormData();
    fd.append('voice_id', voiceId);
    fd.append('alias_name', alias.trim() || '내 보이스');

    const csrfEl = document.cookie.match('(?:^|; )csrftoken=([^;]*)');
    const csrf   = csrfEl ? decodeURIComponent(csrfEl[1]) : '';

    fetch(window.location.pathname, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf },
        body: fd,
    })
    .then(r => {
        if (r.ok) location.reload();
        else alert('저장에 실패했습니다.');
    })
    .catch(() => alert('네트워크 오류가 발생했습니다.'));
}
