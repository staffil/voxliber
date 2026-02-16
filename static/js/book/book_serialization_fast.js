// ==================== 전역 변수 ====================
let characterCount = 1; // 0은 나레이션, 1부터 시작

// ==================== 초기화 ====================
document.addEventListener('DOMContentLoaded', function() {
    const novelText = document.getElementById('novelText');
    if (novelText) {
        novelText.addEventListener('input', updateCharCount);
    }

    // 에피소드 이미지 업로드 미리보기
    const imageInput = document.getElementById('episodeImageInput');
    if (imageInput) {
        imageInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;

            if (!file.type.startsWith('image/')) {
                alert('이미지 파일만 업로드 가능합니다.');
                imageInput.value = '';
                return;
            }
            if (file.size > 5 * 1024 * 1024) {
                alert('이미지는 5MB 이하만 가능합니다.');
                imageInput.value = '';
                return;
            }

            const preview = document.getElementById('imagePreview');
            const placeholder = document.getElementById('imagePlaceholder');
            const reader = new FileReader();
            reader.onload = function(ev) {
                if (preview) {
                    preview.src = ev.target.result;
                    preview.classList.add('show');
                }
                if (placeholder) placeholder.style.display = 'none';
            };
            reader.readAsDataURL(file);
        });
    }

    console.log('오디오북 생성기 초기화 완료');
});

// 이미지 삭제
function deleteImage(e) {
    e.stopPropagation();
    const input = document.getElementById('episodeImageInput');
    const preview = document.getElementById('imagePreview');
    const placeholder = document.getElementById('imagePlaceholder');
    if (input) input.value = '';
    if (preview) { preview.src = ''; preview.classList.remove('show'); }
    if (placeholder) placeholder.style.display = '';
}

// ==================== 글자 수 카운터 ====================
function updateCharCount() {
    const text = document.getElementById('novelText');
    const countEl = document.getElementById('charCount');
    if (text && countEl) {
        countEl.textContent = text.value.length.toLocaleString();
    }
}

// ==================== 캐릭터 추가/삭제 ====================
function addCharacter() {
    characterCount++;
    const characterList = document.getElementById('characterList');
    if (!characterList) return;

    const characterItem = document.createElement('div');
    characterItem.className = 'character-item';
    characterItem.dataset.number = characterCount;

    characterItem.innerHTML = `
        <div class="character-number-badge">${characterCount}</div>
        <div class="character-content">
            <input type="text" class="character-name" placeholder="캐릭터 이름 (예: 민수, 지영)" data-number="${characterCount}">
            <select class="voice-select" data-number="${characterCount}">
                <option value="">목소리 선택</option>
                ${voiceList.map(voice => `
                    <option value="${voice.id}">${voice.name}</option>
                `).join('')}
            </select>
        </div>
        <button class="btn-remove-char" onclick="removeCharacter(${characterCount})">삭제</button>
    `;

    characterList.appendChild(characterItem);
    showStatus('캐릭터가 추가되었습니다', 'success');
}

function removeCharacter(number) {
    const characterItem = document.querySelector(`.character-item[data-number="${number}"]`);
    if (characterItem) {
        characterItem.remove();
        showStatus('캐릭터가 삭제되었습니다', 'success');
    }
}

// ==================== 캐릭터 맵 수집 ====================
function collectCharacterMap() {
    const charMap = {};
    const characterItems = document.querySelectorAll('.character-item');

    characterItems.forEach(item => {
        const num = parseInt(item.dataset.number);
        const nameInput = item.querySelector('.character-name');
        const voiceSelect = item.querySelector('.voice-select');

        const name = nameInput ? nameInput.value.trim() : (num === 0 ? '나레이션' : '');
        const voiceId = voiceSelect ? voiceSelect.value : '';

        if (voiceId) {
            charMap[num] = {
                name: name || (num === 0 ? '나레이션' : `캐릭터${num}`),
                voice_id: voiceId
            };
        }
    });

    return charMap;
}

// ==================== 텍스트 파싱 (N: 형식) ====================
function parseNovelText(text, charMap) {
    const lines = text.split('\n').filter(l => l.trim());
    const rawPages = [];
    const errors = [];

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        const match = line.match(/^(\d+)\s*:\s*(.+)$/);

        if (!match) {
            errors.push(`${i + 1}번째 줄: 번호가 없습니다 → "${line.substring(0, 30)}..."`);
            continue;
        }

        const charNum = parseInt(match[1]);
        const content = match[2].trim();

        if (!charMap[charNum]) {
            errors.push(`${i + 1}번째 줄: ${charNum}번 캐릭터가 등록되지 않았습니다`);
            continue;
        }

        rawPages.push({
            charNum: charNum,
            text: content,
            voice_id: charMap[charNum].voice_id
        });
    }

    return { rawPages, errors };
}

// ==================== 페이지 그룹핑 (같은 목소리 합치기) ====================
function groupPages(rawPages) {
    if (rawPages.length === 0) return [];

    const grouped = [];
    let current = {
        text: rawPages[0].text,
        voice_id: rawPages[0].voice_id
    };

    for (let i = 1; i < rawPages.length; i++) {
        const page = rawPages[i];

        if (page.voice_id === current.voice_id &&
            (current.text.length + page.text.length + 1) <= 300) {
            current.text += ' ' + page.text;
        } else {
            grouped.push({ ...current });
            current = {
                text: page.text,
                voice_id: page.voice_id
            };
        }
    }
    grouped.push({ ...current });

    return grouped;
}

// ==================== JSON 미리보기 생성 ====================
function generateJSONPreview() {
    const episodeTitle = document.getElementById('episodeTitle');
    const novelText = document.getElementById('novelText');

    if (!episodeTitle || !novelText) {
        showStatus('페이지 오류가 발생했습니다', 'error');
        return null;
    }

    const title = episodeTitle.value.trim();
    const text = novelText.value.trim();
    const number = nextEpisodeNumber;

    if (!title) {
        showStatus('에피소드 제목을 입력하세요', 'error');
        return null;
    }

    if (!text) {
        showStatus('소설 텍스트를 입력하세요', 'error');
        return null;
    }

    const charMap = collectCharacterMap();
    if (Object.keys(charMap).length === 0) {
        showStatus('최소 1개 이상의 목소리를 선택하세요', 'error');
        return null;
    }

    const { rawPages, errors } = parseNovelText(text, charMap);

    if (errors.length > 0) {
        showStatus(`파싱 오류 ${errors.length}건: ${errors[0]}`, 'error');
        console.warn('파싱 오류:', errors);
        return null;
    }

    if (rawPages.length === 0) {
        showStatus('유효한 대사가 없습니다', 'error');
        return null;
    }

    const pages = groupPages(rawPages);

    const jsonData = {
        action: "batch",
        book_uuid: bookId || "",
        steps: [
            {
                action: "create_episode",
                book_uuid: bookId || "",
                episode_number: number,
                episode_title: title,
                pages: pages.map(p => ({
                    text: p.text,
                    voice_id: p.voice_id
                }))
            }
        ]
    };

    // JSON 에디터에 표시 (편집 가능)
    const editor = document.getElementById('jsonEditor');
    if (editor) {
        editor.value = JSON.stringify(jsonData, null, 2);
    }

    showStatus(`JSON 생성 완료 (${rawPages.length}줄 → ${pages.length}페이지) - 수정 후 실행 가능`, 'success');
    return jsonData;
}

// ==================== AI 화자 분류 (자연어 → N: 형식) ====================
async function aiAssignSpeakers() {
    const novelText = document.getElementById('novelText');
    const text = novelText ? novelText.value.trim() : '';

    if (!text) {
        showStatus('소설 텍스트를 입력하세요', 'error');
        return;
    }

    // 이미 N: 형식인지 간단 체크
    const lines = text.split('\n').filter(l => l.trim());
    const numberedLines = lines.filter(l => /^\d+\s*:/.test(l.trim()));
    if (numberedLines.length > lines.length * 0.5) {
        if (!confirm('이미 번호가 매겨진 텍스트가 포함되어 있습니다.\nAI 화자 분류를 실행하면 텍스트가 덮어쓰기됩니다.\n계속하시겠습니까?')) {
            return;
        }
    }

    // 캐릭터 맵 수집
    const characters = {};
    document.querySelectorAll('.character-item').forEach(item => {
        const num = parseInt(item.dataset.number);
        const nameInput = item.querySelector('.character-name');
        const name = nameInput ? nameInput.value.trim() : '';
        if (name) {
            characters[num] = name;
        } else if (num === 0) {
            characters[0] = '나레이션';
        }
    });

    if (Object.keys(characters).length < 2) {
        showStatus('캐릭터를 최소 1명 이상 등록하세요 (나레이션 + 캐릭터)', 'error');
        return;
    }

    showLoading('AI 화자 분류 중...', 'GPT가 텍스트를 분석하고 있습니다');

    try {
        const response = await fetch('/book/json/ai-speakers/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ text, characters })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'AI 분류 실패');
        }

        const result = await response.json();
        hideLoading();

        if (result.formatted_text) {
            novelText.value = result.formatted_text;
            updateCharCount();
            showStatus(`AI 화자 분류 완료 - 결과를 확인하고 필요시 수정하세요`, 'success');
        } else {
            showStatus('AI 응답이 비어있습니다', 'error');
        }

    } catch (error) {
        hideLoading();
        showStatus('AI 오류: ' + error.message, 'error');
        console.error('AI 화자 분류 오류:', error);
    }
}

// ==================== AI 생성 (텍스트 분석 → BGM/SFX/효과 자동 추가) ====================
async function aiGenerate() {
    // 먼저 기본 JSON 생성
    const baseJSON = generateJSONPreview();
    if (!baseJSON) return;

    showLoading('AI 분석 중...', '텍스트를 분석하고 BGM/SFX를 추가하고 있습니다');

    try {
        const response = await fetch('/book/json/ai-generate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(baseJSON)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'AI 분석 실패');
        }

        const result = await response.json();
        hideLoading();

        // AI가 반환한 JSON을 에디터에 표시
        const editor = document.getElementById('jsonEditor');
        if (editor) {
            editor.value = JSON.stringify(result, null, 2);
        }

        showStatus('AI 분석 완료 - JSON을 확인하고 수정 후 실행하세요', 'success');

    } catch (error) {
        hideLoading();

        // AI 엔드포인트가 없으면 기본 JSON만 표시
        if (error.message.includes('404') || error.message.includes('Not Found')) {
            showStatus('AI 엔드포인트 준비 중 - 기본 JSON이 생성되었습니다. 수동으로 BGM/SFX를 추가하세요', 'info');
        } else {
            showStatus('AI 오류: ' + error.message, 'error');
        }
    }
}

// ==================== JSON 실행 (Celery 비동기) ====================
let pollingInterval = null;

async function executeJSON() {
    const editor = document.getElementById('jsonEditor');
    if (!editor || !editor.value.trim()) {
        showStatus('먼저 미리보기를 생성하세요', 'error');
        return;
    }

    // JSON 파싱 검증
    let jsonData;
    try {
        jsonData = JSON.parse(editor.value);
    } catch (e) {
        showStatus('JSON 형식 오류: ' + e.message, 'error');
        return;
    }

    // 페이지 수 확인
    const episodeStep = jsonData.steps ? jsonData.steps.find(s => s.action === 'create_episode') : null;
    const pageCount = episodeStep ? (episodeStep.pages ? episodeStep.pages.length : 0) : 0;
    const stepCount = jsonData.steps ? jsonData.steps.length : 0;

    if (!confirm(`오디오북을 생성하시겠습니까?\n\n${stepCount}단계, ${pageCount}페이지 처리가 시작됩니다.`)) {
        return;
    }

    showLoading('오디오북 생성 요청 중...', '서버에 작업을 전송하고 있습니다');

    try {
        const response = await fetch('/book/json/generate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(jsonData)
        });
const text = await response.text();

if (!response.ok) {
    console.error("서버 원본 응답:", text);
    throw new Error("서버가 JSON이 아닌 응답을 반환했습니다");
}

let result;
try {
    result = JSON.parse(text);
} catch (e) {
    console.error("JSON 파싱 실패. 서버 응답:", text);
    throw new Error("서버 응답이 JSON 형식이 아닙니다");
}

        if (result.task_id) {
            // Celery 태스크 시작됨 → 폴링 시작
            showLoading('오디오북 생성 중...', '백그라운드에서 처리 중입니다');
            startPolling(result.task_id);
        } else {
            hideLoading();
            showStatus('태스크 ID를 받지 못했습니다', 'error');
        }

    } catch (error) {
        hideLoading();
        console.error('오디오북 생성 오류:', error);
        showStatus('오류: ' + error.message, 'error');
    }
}

// 폴링 중 페이지 이탈 경고
window.addEventListener('beforeunload', function(e) {
    if (pollingInterval) {
        e.preventDefault();
        e.returnValue = '오디오북 생성이 진행 중입니다. 페이지를 떠나시겠습니까?';
        return e.returnValue;
    }
});

function startPolling(taskId) {
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`/book/json/task-status/${taskId}/`);
            const data = await response.json();

            if (data.state === 'PROGRESS') {
                const loadingText = document.getElementById('loadingText');
                const loadingDetail = document.getElementById('loadingDetail');
                if (loadingText) loadingText.textContent = data.status || '처리 중...';
                if (loadingDetail) {
                    const stepInfo = data.current_step && data.total_steps
                        ? `(${data.current_step}/${data.total_steps} 단계)`
                        : '';
                    loadingDetail.textContent = `${data.progress || 0}% 완료 ${stepInfo}`;
                }
            }
            else if (data.state === 'SUCCESS') {
                clearInterval(pollingInterval);
                pollingInterval = null;

                if (data.success) {
                    const ep = data.episode || {};

                    // 에피소드 이미지 업로드 (파일이 선택된 경우)
                    const imageInput = document.getElementById('episodeImageInput');
                    if (imageInput && imageInput.files[0] && ep.number) {
                        const loadingText = document.getElementById('loadingText');
                        if (loadingText) loadingText.textContent = '에피소드 이미지 업로드 중...';

                        const formData = new FormData();
                        formData.append('episode_image', imageInput.files[0]);
                        formData.append('episode_number', ep.number);

                        try {
                            await fetch(window.location.pathname, {
                                method: 'POST',
                                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                                body: formData
                            });
                        } catch (imgErr) {
                            console.error('이미지 업로드 실패:', imgErr);
                        }
                    }

                    hideLoading();
                    alert(`오디오북이 성공적으로 생성되었습니다!\n\n에피소드: ${ep.title || ''}\n페이지: ${ep.page_count || '?'}개`);

                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else if (bookId) {
                        window.location.href = `/book/detail/${bookId}/`;
                    }
                } else {
                    hideLoading();
                    showStatus('생성 실패: ' + (data.error || '알 수 없는 오류'), 'error');
                    alert('오디오북 생성 실패:\n' + (data.error || '알 수 없는 오류'));
                }
            }
            else if (data.state === 'FAILURE') {
                clearInterval(pollingInterval);
                pollingInterval = null;
                hideLoading();
                showStatus('태스크 실패: ' + (data.error || ''), 'error');
                alert('오디오북 생성 실패:\n' + (data.error || '알 수 없는 오류'));
            }
            // PENDING → 계속 폴링

        } catch (e) {
            console.error('폴링 오류:', e);
        }
    }, 3000); // 3초마다 폴링
}

// ==================== JSON 다운로드 ====================
function downloadJSON() {
    const editor = document.getElementById('jsonEditor');
    if (!editor || !editor.value.trim()) {
        showStatus('먼저 미리보기를 생성하세요', 'error');
        return;
    }

    let jsonData;
    try {
        jsonData = JSON.parse(editor.value);
    } catch (e) {
        showStatus('JSON 형식 오류: ' + e.message, 'error');
        return;
    }

    const blob = new Blob([editor.value], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const episodeStep = jsonData.steps ? jsonData.steps.find(s => s.action === 'create_episode') : null;
    const title = episodeStep ? episodeStep.episode_title : 'audiobook';
    const num = episodeStep ? episodeStep.episode_number : 1;
    a.href = url;
    a.download = `${title}_ep${num}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showStatus('JSON 다운로드 완료', 'success');
}

// ==================== 모바일 JSON 토글 ====================
function toggleMobileJSON() {
    const rightPanel = document.getElementById('rightPanel');
    const overlay = document.getElementById('mobileJsonOverlay');

    if (rightPanel && overlay) {
        rightPanel.classList.toggle('active');
        overlay.classList.toggle('active');

        if (rightPanel.classList.contains('active')) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
    }
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const rightPanel = document.getElementById('rightPanel');
        if (rightPanel && rightPanel.classList.contains('active')) {
            toggleMobileJSON();
        }
    }
});

window.addEventListener('resize', function() {
    if (window.innerWidth > 1024) {
        const rightPanel = document.getElementById('rightPanel');
        const overlay = document.getElementById('mobileJsonOverlay');
        if (rightPanel) rightPanel.classList.remove('active');
        if (overlay) overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// ==================== 상태 메시지 ====================
function showStatus(message, type = 'info') {
    const statusEl = document.getElementById('statusMessage');
    if (!statusEl) return;

    statusEl.textContent = message;
    statusEl.className = `status-message ${type}`;
    statusEl.style.display = 'block';

    setTimeout(() => {
        statusEl.style.display = 'none';
    }, 5000);
}

// ==================== 로딩 표시 ====================
function showLoading(text, detail) {
    const overlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    const loadingDetail = document.getElementById('loadingDetail');

    if (loadingText) loadingText.textContent = text;
    if (loadingDetail) loadingDetail.textContent = detail;
    if (overlay) overlay.classList.add('active');
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('active');
}

// ==================== 쿠키 ====================
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

console.log('오디오북 생성기 스크립트 로드 완료');



