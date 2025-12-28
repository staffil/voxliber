/* -----------------------------
   문단 분할 / 타임스탬프 매핑 함수
----------------------------- */
function splitParagraphsForTimestamps(originalText, audioTimestamps) {
    const timestampCount = audioTimestamps.length;

    // 문단 기준 분할
    let paragraphs = originalText
        .split(/\n\s*\n+/)
        .map(p => p.trim())
        .filter(Boolean);

    const paragraphCount = paragraphs.length;

    // 문단 수 == 타임스탬프 수 → 그대로
    if (paragraphCount === timestampCount) return paragraphs;

    // 균등 병합
    const chunks = [];
    const perChunk = Math.ceil(paragraphCount / timestampCount);

    for (let i = 0; i < paragraphCount; i += perChunk) {
        chunks.push(paragraphs.slice(i, i + perChunk).join("\n\n"));
    }

    while (chunks.length < timestampCount) chunks.push("");
    while (chunks.length > timestampCount) {
        chunks[chunks.length - 2] += "\n\n" + chunks.pop();
    }

    return chunks;
}

/* -----------------------------
   HTML escape
----------------------------- */
function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

/* -----------------------------
   메인 실행
----------------------------- */
document.addEventListener("DOMContentLoaded", function () {
    const audioPlayer = document.getElementById("audioPlayer");
    if (!audioPlayer) return;

    /* -----------------------------
       오디오 UI 컨트롤
    ----------------------------- */
    const playPauseBtn = document.getElementById("playPauseBtn");
    const playIcon = document.getElementById("playIcon");
    const pauseIcon = document.getElementById("pauseIcon");
    const progressSlider = document.getElementById("progressSlider");
    const progressFill = document.getElementById("progressFill");
    const currentTimeDisplay = document.getElementById("currentTime");
    const totalTimeDisplay = document.getElementById("totalTime");
    const volumeBtn = document.getElementById("volumeBtn");
    const volumeSlider = document.getElementById("volumeSlider");

    function formatTime(sec) {
        if (!isFinite(sec)) return "0:00";
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return `${m}:${String(s).padStart(2, "0")}`;
    }

    // 이어듣기 알림 표시
    function showResumeNotification(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        const timeText = `${mins}:${String(secs).padStart(2, "0")}`;

        const notification = document.createElement("div");
        notification.style.cssText = `
            position: fixed;
            top: 100px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 28px;
            border-radius: 50px;
            font-size: 15px;
            font-weight: 600;
            box-shadow: 0 8px 24px rgba(99, 102, 241, 0.5);
            z-index: 10000;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: slideDown 0.3s ease;
        `;
        notification.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
            </svg>
            <span>이어듣기: ${timeText}부터 재생</span>
        `;

        document.body.appendChild(notification);

        // 3초 후 제거
        setTimeout(() => {
            notification.style.animation = "slideUp 0.3s ease";
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    playPauseBtn.addEventListener("click", function () {
        if (audioPlayer.paused) {
            audioPlayer.play();
            playIcon.style.display = "none";
            pauseIcon.style.display = "block";
        } else {
            audioPlayer.pause();
            playIcon.style.display = "block";
            pauseIcon.style.display = "none";
        }
    });

    // 재생 시작 시 청취 시작 시간 기록
    audioPlayer.addEventListener("play", function () {
        if (!listeningStartTime) {
            listeningStartTime = Date.now();
            console.log("🎧 청취 시작:", new Date(listeningStartTime).toLocaleTimeString());
        }
    });

    // 일시정지 시 청취 시간 누적
    audioPlayer.addEventListener("pause", function () {
        if (listeningStartTime) {
            const elapsed = (Date.now() - listeningStartTime) / 1000;
            totalListenedSeconds += elapsed;
            listeningStartTime = null;
            console.log(`⏸️ 청취 일시정지: ${elapsed.toFixed(1)}초 경과, 총 ${totalListenedSeconds.toFixed(1)}초`);
        }
    });

    // 오디오 재생 완료 시 저장
    audioPlayer.addEventListener("ended", function () {
        if (listeningStartTime) {
            totalListenedSeconds += (Date.now() - listeningStartTime) / 1000;
            listeningStartTime = null;
        }

        // 끝까지 들었으므로 저장
        console.log("✅ 오디오 재생 완료 - 저장");
        saveListeningHistory(totalListenedSeconds);
    });

    // 이어듣기 위치 확인 (페이지 로드 시)
    const resumePosition = sessionStorage.getItem("resumePosition");
    let shouldResume = false;
    let resumeTime = 0;

    if (resumePosition) {
        const position = parseFloat(resumePosition);
        if (!isNaN(position) && position > 0) {
            shouldResume = true;
            resumeTime = position;
            console.log(`🎧 이어듣기 모드: ${position}초 위치로 이동 예정`);
        }
        // 세션 스토리지에서 제거
        sessionStorage.removeItem("resumePosition");
    }

    audioPlayer.addEventListener("loadedmetadata", function () {
        totalTimeDisplay.textContent = formatTime(audioPlayer.duration);
        progressSlider.max = audioPlayer.duration;
    });

    // canplay 이벤트에서 재생 위치 설정 (더 안정적)
    audioPlayer.addEventListener("canplay", function () {
        if (shouldResume && resumeTime > 0) {
            audioPlayer.currentTime = resumeTime;
            progressSlider.value = resumeTime;
            progressFill.style.width = (resumeTime / audioPlayer.duration) * 100 + "%";
            currentTimeDisplay.textContent = formatTime(resumeTime);

            // 알림 표시
            showResumeNotification(resumeTime);

            shouldResume = false; // 한 번만 실행
            console.log(`✅ 이어듣기: ${resumeTime}초 위치에서 재생 시작`);
        }
    }, { once: true }); // 한 번만 실행

    audioPlayer.addEventListener("timeupdate", function () {
        const cur = audioPlayer.currentTime;
        const dur = audioPlayer.duration;

        currentTimeDisplay.textContent = formatTime(cur);
        progressSlider.value = cur;
        progressFill.style.width = (cur / dur) * 100 + "%";
    });

    progressSlider.addEventListener("input", function () {
        audioPlayer.currentTime = progressSlider.value;
    });

    volumeSlider.addEventListener("input", function () {
        audioPlayer.volume = volumeSlider.value / 100;
    });

    volumeBtn.addEventListener("click", function () {
        if (audioPlayer.volume > 0) {
            audioPlayer.volume = 0;
            volumeSlider.value = 0;
        } else {
            audioPlayer.volume = 1;
            volumeSlider.value = 100;
        }
    });

    /* -----------------------------
       재생 속도 조절
    ----------------------------- */
    const playbackSpeedBtn = document.getElementById("playbackSpeedBtn");
    const speedOptions = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0];
    let currentSpeedIndex = 2; // 기본값 1.0x (인덱스 2)

    playbackSpeedBtn.addEventListener("click", function () {
        // 다음 속도로 변경
        currentSpeedIndex = (currentSpeedIndex + 1) % speedOptions.length;
        const newSpeed = speedOptions[currentSpeedIndex];

        audioPlayer.playbackRate = newSpeed;
        playbackSpeedBtn.textContent = newSpeed.toFixed(2) + "x";

        console.log(`⚡ 재생 속도 변경: ${newSpeed}x`);
    });

    /* -----------------------------
       청취시간 기록
    ----------------------------- */
    let listeningStartTime = null;
    let totalListenedSeconds = 0;
    let isSending = false;

    // Get save URL from data attribute
    const saveUrl = audioPlayer.dataset.saveUrl;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                      document.querySelector('meta[name="csrf-token"]')?.content || '';

    async function saveListeningHistory(seconds) {
        if (isSending || !saveUrl) return;
        isSending = true;

        try {
            const res = await fetch(saveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({
                    listened_seconds: Math.floor(seconds),
                    last_position: audioPlayer.currentTime || 0
                })
            });

            const data = await res.json();
            if (data.success) totalListenedSeconds = 0;
        } finally {
            isSending = false;
        }
    }

    audioPlayer.addEventListener("play", () => {
        listeningStartTime = Date.now();
    });

    audioPlayer.addEventListener("pause", () => {
        if (!listeningStartTime) return;
        totalListenedSeconds += (Date.now() - listeningStartTime) / 1000;
        listeningStartTime = null;
    });

    audioPlayer.addEventListener("ended", () => {
        if (listeningStartTime)
            totalListenedSeconds += (Date.now() - listeningStartTime) / 1000;
        listeningStartTime = null;

        saveListeningHistory(totalListenedSeconds);
    });

    setInterval(() => {
        if (!listeningStartTime) return;

        const elapsed = (Date.now() - listeningStartTime) / 1000;
        const total = totalListenedSeconds + elapsed;

        if (total >= 30) {
            totalListenedSeconds = total;
            listeningStartTime = Date.now();
            saveListeningHistory(totalListenedSeconds);
        }
    }, 30000);

    // 페이지 벗어날 때 무조건 저장 (beforeunload)
    function saveOnExit() {
        // 청취 중이면 시간 누적
        if (listeningStartTime) {
            totalListenedSeconds += (Date.now() - listeningStartTime) / 1000;
        }

        const currentPos = audioPlayer.currentTime || 0;

        // 재생 위치가 1초 이상이면 무조건 저장
        if (currentPos >= 1 && saveUrl) {
            console.log(`💾 페이지 종료 - 위치 저장: ${currentPos.toFixed(1)}초, 청취 시간: ${totalListenedSeconds.toFixed(1)}초`);

            const xhr = new XMLHttpRequest();
            xhr.open("POST", saveUrl, false);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.setRequestHeader("X-CSRFToken", csrfToken);
            xhr.send(
                JSON.stringify({
                    listened_seconds: Math.floor(totalListenedSeconds),
                    last_position: currentPos
                })
            );
        }
    }

    // beforeunload: PC 브라우저용
    window.addEventListener("beforeunload", saveOnExit);

    // pagehide: 모바일 브라우저용 (더 안정적)
    window.addEventListener("pagehide", saveOnExit);

    /* -----------------------------
       대사 하이라이트 기능 (사운드 이팩트 제외)
    ----------------------------- */
    const timestampsData = document.getElementById('audio-timestamps-data');
    if (timestampsData) {
        const audioTimestamps = JSON.parse(timestampsData.textContent || '[]');

        // 텍스트가 있는 대사만 필터링 (사운드 이팩트 제외)
        const dialogues = audioTimestamps.filter(ts => ts.text && ts.text.trim());

        if (dialogues.length > 0) {
            const dialogueList = document.getElementById('dialogueList');
            const prevDialogueBtn = document.getElementById('prevDialogueBtn');
            const nextDialogueBtn = document.getElementById('nextDialogueBtn');
            const dialogueCounter = document.getElementById('dialogueCounter');

            let currentDialogueIndex = -1;

            // 대사 목록 렌더링
            function renderDialogues() {
                dialogueList.innerHTML = '';
                dialogues.forEach((dialogue, index) => {
                    const dialogueItem = document.createElement('div');
                    dialogueItem.className = 'dialogue-item';
                    dialogueItem.dataset.index = index;

                    dialogueItem.innerHTML = `
                        <div class="dialogue-number">대사 ${index + 1}</div>
                        <div class="dialogue-text">${escapeHtml(dialogue.text)}</div>
                    `;

                    // 클릭 시 해당 대사 위치로 이동
                    dialogueItem.addEventListener('click', () => {
                        jumpToDialogue(index);
                    });

                    dialogueList.appendChild(dialogueItem);
                });
            }

            // 대사로 이동
            function jumpToDialogue(index) {
                if (index < 0 || index >= dialogues.length) return;

                const dialogue = dialogues[index];
                audioPlayer.currentTime = dialogue.startTime / 1000;

                if (audioPlayer.paused) {
                    audioPlayer.play();
                    playIcon.style.display = "none";
                    pauseIcon.style.display = "block";
                }

                highlightDialogue(index);
            }

            // 대사 하이라이트
            function highlightDialogue(index) {
                currentDialogueIndex = index;

                // 모든 대사 항목에서 active 제거
                document.querySelectorAll('.dialogue-item').forEach(item => {
                    item.classList.remove('active');
                });

                // 현재 대사 하이라이트
                const currentItem = document.querySelector(`.dialogue-item[data-index="${index}"]`);
                if (currentItem) {
                    currentItem.classList.add('active');

                    // 스크롤하여 현재 대사가 보이도록
                    currentItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }

                // 카운터 업데이트
                dialogueCounter.textContent = `${index + 1}/${dialogues.length}`;

                // 버튼 상태 업데이트
                prevDialogueBtn.disabled = (index === 0);
                nextDialogueBtn.disabled = (index === dialogues.length - 1);
            }

            // 오디오 재생 중 현재 대사 자동 하이라이트
            audioPlayer.addEventListener('timeupdate', () => {
                const currentTimeMs = audioPlayer.currentTime * 1000;

                // 현재 재생 중인 대사 찾기
                for (let i = 0; i < dialogues.length; i++) {
                    const dialogue = dialogues[i];
                    if (currentTimeMs >= dialogue.startTime && currentTimeMs < dialogue.endTime) {
                        if (currentDialogueIndex !== i) {
                            highlightDialogue(i);
                        }
                        break;
                    }
                }
            });

            // 이전/다음 버튼 이벤트
            prevDialogueBtn.addEventListener('click', () => {
                if (currentDialogueIndex > 0) {
                    jumpToDialogue(currentDialogueIndex - 1);
                }
            });

            nextDialogueBtn.addEventListener('click', () => {
                if (currentDialogueIndex < dialogues.length - 1) {
                    jumpToDialogue(currentDialogueIndex + 1);
                }
            });

            // 초기 렌더링
            renderDialogues();

            // 초기 상태 설정
            if (dialogues.length > 0) {
                highlightDialogue(0);
            }
        } else {
            // 대사가 없으면 섹션 숨기기
            const highlightSection = document.querySelector('.dialogue-highlight-section');
            if (highlightSection) {
                highlightSection.style.display = 'none';
            }
        }
    }
});
