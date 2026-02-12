

// 오디오 재생 (텍스트와 분리)
function playAudioWhenReady(audioUrl, messageElement) {
    const audioStatus = messageElement?.querySelector('.message-audio-status');

    if (audioUrl) {
        const audio = new Audio(audioUrl);

        audio.oncanplaythrough = function() {
            if (audioStatus) {
                audioStatus.innerHTML = '<span class="audio-playing">🔊 재생 중</span>';
            }
            audio.play();
        };

        audio.onended = function() {
            if (audioStatus) {
                audioStatus.innerHTML = '<span class="audio-done">✓ 재생 완료</span>';
                setTimeout(() => {
                    audioStatus.style.display = 'none';
                }, 2000);
            }
        };

        audio.onerror = function() {
            if (audioStatus) {
                audioStatus.innerHTML = '<span class="audio-error">⚠️ 음성 로드 실패</span>';
            }
        };
    } else {
        if (audioStatus) {
            audioStatus.style.display = 'none';
        }
    }
}

function sendTextMessage() {
    const input = document.getElementById('text-input');
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, false);
    input.value = '';

    // 타이핑 인디케이터 표시
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message ai typing-message';
    typingDiv.innerHTML = `
        <div class="message-avatar">
            ${aiImage ? `<img src="${aiImage}" alt="${aiName}">` : '<div class="message-avatar-placeholder">🤖</div>'}
        </div>
        <div class="typing-indicator">
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    const area = document.getElementById('message-area');
    area.appendChild(typingDiv);
    area.scrollTop = area.scrollHeight;

    // 1단계: 텍스트 응답 먼저 가져오기
    fetch(`{% url 'character:chat-view' llm.public_uuid %}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': '{{ csrf_token }}',
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        // 타이핑 인디케이터 제거
        const typing = document.querySelector('.typing-message');
        if (typing) typing.remove();

        if (data.success) {
            // 텍스트 먼저 표시 (오디오 인디케이터와 함께)
            const msgElement = addMessage(data.text, true, true, data.message_id);

            // HP 업데이트 (서버에서 전달된 경우)
            if (data.hp !== undefined) {
                updateHp(data.hp);
            }
            // === 리다이렉트 체크 (HP 100 도달 시) ===
            if (data.redirect) {
                setTimeout(() => {
                    console.log('[REDIRECT] 엔딩 페이지로 이동:', data.redirect);
                    window.location.href = data.redirect;
                }, 1500);  // 1.5초 → 마지막 메시지 + HP 애니메이션 여유
            }

            // 2단계: TTS 별도로 요청 (비동기)
            fetchTTS(data.text, msgElement, data.message_id);
        } else {
            addMessage('오류가 발생했습니다: ' + data.error, true);
        }
        
    })
    .catch(error => {
        const typing = document.querySelector('.typing-message');
        if (typing) typing.remove();
        console.error('채팅 오류:', error);
        addMessage('연결 오류가 발생했습니다.', true);
    });
}

// TTS 별도 요청 함수
function fetchTTS(text, messageElement, messageId = null) {
    const audioStatus = messageElement?.querySelector('.message-audio-status');
    const audioControl = messageElement?.querySelector('.message-audio-control');

    fetch(ttsUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': '{{ csrf_token }}',
        },
        body: JSON.stringify({ text: text, message_id: messageId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.audio) {
            playAudioWhenReady(data.audio, messageElement);

            // 저장된 오디오 URL이 있으면 재생 버튼 활성화
            if (data.audio_url && audioControl) {
                audioControl.dataset.audioUrl = data.audio_url;
                audioControl.style.display = 'flex';
                // 이벤트 리스너 다시 바인딩
                attachSingleAudioControl(messageElement);
            }
        } else {
            if (audioStatus) {
                audioStatus.innerHTML = '<span class="audio-error">⚠️ 음성 생성 실패</span>';
            }
        }
    })
    .catch(error => {
        console.error('TTS 오류:', error);
        if (audioStatus) {
            audioStatus.innerHTML = '<span class="audio-error">⚠️ 음성 로드 실패</span>';
        }
    });
}

// 녹음 관련 변수
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

function toggleRecording() {
    const btn = document.getElementById('record-btn');
    const icon = document.getElementById('record-icon');

    if (!isRecording) {
        startRecording();
        btn.classList.add('recording');
        icon.className = 'fas fa-stop';
    } else {
        stopRecording();
        btn.classList.remove('recording');
        icon.className = 'fas fa-microphone';
    }
    isRecording = !isRecording;
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => {
            audioChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            // 여기서 STT 처리
            console.log('Recording stopped', audioBlob);
        };

        mediaRecorder.start();
    } catch (err) {
        console.error('마이크 접근 오류:', err);
        alert('마이크 접근 권한이 필요합니다.');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
}

// 비전 토글
let visionEnabled = false;
document.getElementById('toggle-vision-btn')?.addEventListener('click', function() {
    visionEnabled = !visionEnabled;
    this.classList.toggle('vision-active', visionEnabled);
    const icon = document.getElementById('vision-icon');
    if (icon) {
        icon.className = visionEnabled ? 'fas fa-video-slash' : 'fas fa-video';
    }
});

// HTML에서 텍스트 추출 (br 태그를 개행으로 변환)
function extractTextFromHtml(html) {
    // <br> 태그를 줄바꿈으로 변환
    let text = html.replace(/<br\s*\/?>/gi, '\n');
    // 나머지 HTML 태그 제거
    text = text.replace(/<[^>]+>/g, '');
    // HTML 엔티티 디코딩
    const textarea = document.createElement('textarea');
    textarea.innerHTML = text;
    return textarea.value.trim();
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    // 이전 AI 메시지들에 나레이션/대사 포맷팅 적용
    const aiMessages = document.querySelectorAll('.message.ai .message-content[data-needs-format]');
    aiMessages.forEach(msgContent => {
        // HTML에서 원본 텍스트 추출
        const originalText = extractTextFromHtml(msgContent.innerHTML);
        if (originalText) {
            msgContent.innerHTML = formatAIResponse(originalText);
        }
    });

    // HP 바 초기화 및 배경 이미지 적용
    updateHp(currentHp);

    // 이전 메시지들의 오디오 컨트롤 바인딩
    attachAudioControls();

    // 스크롤을 맨 아래로
    const area = document.getElementById('message-area');
    if (area) {
        area.scrollTop = area.scrollHeight;
    }

    // 채팅 숨기기/보이기 토글
    const toggleBtn = document.getElementById('toggle-chat-btn');
    const chatFrame = document.getElementById('chat-frame');
    let chatHidden = false;

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function() {
            chatHidden = !chatHidden;
            chatFrame.classList.toggle('chat-hidden', chatHidden);

            // 아이콘 변경
            const icon = this.querySelector('i');
            if (chatHidden) {
                icon.className = 'fas fa-eye-slash';
            } else {
                icon.className = 'fas fa-eye';
            }
        });
    }
});

const audioPlayers = {}; // msgId -> Audio 객체 저장

// 단일 메시지에 오디오 컨트롤 바인딩
function attachSingleAudioControl(msg) {
    const msgId = msg.dataset.msgId || 'msg_' + Date.now();
    const audioControl = msg.querySelector('.message-audio-control');
    const playBtn = audioControl?.querySelector('.audio-play-btn');

    if (!playBtn || playBtn.dataset.bound) return;
    playBtn.dataset.bound = 'true';

    playBtn.addEventListener('click', () => {
        const audioUrl = audioControl.dataset.audioUrl;

        if (!audioUrl) {
            console.warn('오디오 URL 없음:', msgId);
            return;
        }

        let audio = audioPlayers[msgId];

        if (!audio) {
            audio = new Audio(audioUrl);
            audioPlayers[msgId] = audio;

            audio.onplay = () => {
                playBtn.innerHTML = '<i class="fas fa-pause"></i>';
                playBtn.classList.add('playing');
            };

            audio.onpause = audio.onended = () => {
                playBtn.innerHTML = '<i class="fas fa-play"></i>';
                playBtn.classList.remove('playing');
            };
        }
        
        playBtn.addEventListener('click', () => {
            if (audio.paused){
        audio.play().catch(e => console.log('사용자 클릭 전 재생 시도 막힘', e));
            } else {
                audio.pe
            }

        });


    });
}

function attachAudioControls() {
    document.querySelectorAll('.message.ai').forEach(msg => {
        const audioControl = msg.querySelector('.message-audio-control');

        // 서버에서 받은 오디오 URL이 있으면 버튼 보이게
        if (audioControl && audioControl.dataset.audioUrl) {
            audioControl.style.display = 'flex';
        }

        attachSingleAudioControl(msg);
    });
}






// ====================================
// 메시지 전송
// ====================================
async function sendTextMessage() {
    const input = document.getElementById('text-input');
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, false);
    input.value = '';

    showTypingIndicator();

    try {
        const response = await fetch(chatUrl, {  // ← chatUrl 써야 함 (chat-logic URL)
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ message: message })
        });

        hideTypingIndicator();
        const data = await response.json();

        if (data.success) {
            const msgElement = addMessage(data.text, true, data.message_id);

            if (data.hp !== undefined) {
                updateHp(data.hp);
            }

            // 리다이렉트 처리
            if (data.redirect) {
                console.log('[REDIRECT] 엔딩 페이지로 이동 시도:', data.redirect);
                setTimeout(() => {
                    window.location.href = data.redirect;
                }, 1800);  // 1.8초로 조금 늘려서 여유 주기
            }

        } else {
            addMessage('오류: ' + (data.error || '알 수 없는 오류'), true);
        }
    } catch (error) {
        hideTypingIndicator();
        console.error('채팅 요청 실패:', error);
        addMessage('연결 오류가 발생했습니다.', true);
    }
}
// ====================================
// TTS 생성 (버튼 클릭 시만)
// ====================================
async function generateTTS(btn, msgId) {
    const msgDiv = btn.closest('.message');
    const bubble = msgDiv.querySelector('.message-bubble');
    const text = bubble ? bubble.innerText.trim() : '';

    if (!text) return;

    // 버튼 상태 변경
    btn.disabled = true;
    btn.classList.add('loading');
    btn.innerHTML = `
        <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
        </svg>
        <span>생성 중...</span>
    `;

    try {
        const response = await fetch(ttsUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ text: text, message_id: msgId })
        });

        const data = await response.json();

        if (data.success && (data.audio || data.audio_url)) {
            const audioUrl = data.audio_url || data.audio;

            // TTS 버튼을 오디오 버튼으로 교체
            btn.classList.remove('loading', 'tts-btn');
            btn.classList.add('audio-btn', 'has-audio');
            btn.disabled = false;
            btn.dataset.audioUrl = audioUrl;
            btn.innerHTML = `
                <svg class="icon-play" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8 5v14l11-7z"/>
                </svg>
                <svg class="icon-pause" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="display:none;">
                    <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
                </svg>
            `;

            // 자동 재생
            playAudio(audioUrl, btn);
        } else {
            btn.disabled = false;
            btn.classList.remove('loading');
            btn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 5L6 9H2v6h4l5 4V5z"/>
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
                </svg>
                <span>재시도</span>
            `;
        }
    } catch (error) {
        console.error('TTS 오류:', error);
        btn.disabled = false;
        btn.classList.remove('loading');
        btn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
            </svg>
            <span>실패</span>
        `;
    }
}
