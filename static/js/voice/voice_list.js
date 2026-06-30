// ── 현재 재생 중인 오디오 추적 ──
let _vlActiveAudio = null;
let _vlActiveBtn   = null;
let _vlPlayPending = false;

const PLAY_ICON  = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const PAUSE_ICON = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
const PLAY_ICON_SM  = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const PAUSE_ICON_SM = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';

function _vlFmt(s) {
    if (!isFinite(s) || isNaN(s)) return '0:00';
    return Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
}

function _vlResetPlayer(btn, player, isSmall) {
    btn.innerHTML = isSmall ? PLAY_ICON_SM : PLAY_ICON;
    const fill = player.querySelector('.vl-card-fill, .vl-fill-sm');
    const time = player.querySelector('.vl-card-time, .vl-time-sm');
    if (fill) fill.style.width = '0%';
    if (time) time.textContent = isSmall ? '0:00' : '0:00 / 0:00';
}

function _vlStopCurrent() {
    if (!_vlActiveAudio) return;
    const audio = _vlActiveAudio;
    const btn   = _vlActiveBtn;
    _vlActiveAudio = null;
    _vlActiveBtn   = null;
    _vlPlayPending = false;

    const isSmall = btn && btn.classList.contains('vl-play-sm');
    const player  = btn && btn.closest('.vl-card-player, .vl-my-player');
    audio.pause();
    audio.currentTime = 0;
    if (btn && player) _vlResetPlayer(btn, player, isSmall);
}

function _vlPlay(audio, btn, player, isSmall) {
    _vlPlayPending = true;
    audio.play().then(function () {
        _vlPlayPending = false;
        btn.innerHTML = isSmall ? PAUSE_ICON_SM : PAUSE_ICON;
        _vlActiveAudio = audio;
        _vlActiveBtn   = btn;
    }).catch(function (err) {
        _vlPlayPending = false;
        if (err.name !== 'AbortError') console.warn(err);
        _vlResetPlayer(btn, player, isSmall);
    });

    audio.ontimeupdate = function () {
        const pct  = audio.duration ? (audio.currentTime / audio.duration * 100) : 0;
        const fill = player.querySelector('.vl-card-fill, .vl-fill-sm');
        const time = player.querySelector('.vl-card-time, .vl-time-sm');
        if (fill) fill.style.width = pct + '%';
        if (time) time.textContent = isSmall
            ? _vlFmt(audio.currentTime)
            : _vlFmt(audio.currentTime) + ' / ' + _vlFmt(audio.duration);
    };

    audio.onended = function () {
        _vlActiveAudio = null;
        _vlActiveBtn   = null;
        _vlResetPlayer(btn, player, isSmall);
    };
}

function _vlToggle(btn, playerSel, isSmall) {
    if (_vlPlayPending) return;
    const player = btn.closest(playerSel);
    const audio  = player ? player.querySelector('audio') : null;
    if (!audio) return;

    if (_vlActiveAudio && _vlActiveAudio !== audio) _vlStopCurrent();

    if (audio.paused) {
        _vlPlay(audio, btn, player, isSmall);
    } else {
        audio.pause();
        btn.innerHTML = isSmall ? PLAY_ICON_SM : PLAY_ICON;
        _vlActiveAudio = null;
        _vlActiveBtn   = null;
    }
}

// 전체 보이스 목록 카드 플레이어
function toggleVoicePlay(btn) {
    _vlToggle(btn, '.vl-card-player', false);
}

// 내 보이스 컬렉션 소형 플레이어
function togglePlaySmall(btn) {
    _vlToggle(btn, '.vl-my-player', true);
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
