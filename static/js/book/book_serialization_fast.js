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

    // 저장된 소설 텍스트 + 에피소드 제목 복원
    if (typeof savedDraftText !== 'undefined' && savedDraftText) {
        const novelTextEl = document.getElementById('novelText');
        if (novelTextEl) { novelTextEl.value = savedDraftText; updateCharCount(); }
    }
    if (typeof savedDraftTitle !== 'undefined' && savedDraftTitle) {
        const titleInputEl = document.getElementById('episodeTitle');
        if (titleInputEl) titleInputEl.value = savedDraftTitle;
    }

    // 저장된 보이스 설정 복원
    if (typeof savedVoiceConfig !== 'undefined' && savedVoiceConfig && Object.keys(savedVoiceConfig).length > 0) {
        restoreVoiceConfig(savedVoiceConfig);
    }

    // 소설 텍스트/제목 변경 시 debounce 자동 저장 (3초)
    let draftSaveTimer = null;
    function scheduleDraftSave() {
        clearTimeout(draftSaveTimer);
        draftSaveTimer = setTimeout(() => saveDraft(), 3000);
    }
    const _novelTextEl = document.getElementById('novelText');
    const _titleInputEl = document.getElementById('episodeTitle');
    if (_novelTextEl) _novelTextEl.addEventListener('input', scheduleDraftSave);
    if (_titleInputEl) _titleInputEl.addEventListener('input', scheduleDraftSave);

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

// ==================== 텍스트 파싱 (N: 또는 N,M: 형식) ====================
function parseNovelText(text, charMap) {
    const lines = text.split('\n').filter(l => l.trim());
    const rawPages = [];
    const errors = [];

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        // N,M,O,...: 형식 (동시 대화) - 예: "1,2: ...", "1,2,3: ...", "1,2,3,4: ..."
        const duetMatch = line.match(/^(\d+(?:\s*,\s*\d+)+)\s*:\s*(.+)$/);
        if (duetMatch) {
            const charNums = duetMatch[1].split(',').map(n => parseInt(n.trim()));
            const content = duetMatch[2].trim();

            // 미등록 캐릭터도 빈 voice_id로 포함 (블록 에디터에서 나중에 선택 가능)
            charNums.forEach(cn => {
                if (!charMap[cn]) {
                    errors.push(`${i + 1}번째 줄: ${cn}번 캐릭터 미등록 → 빈 목소리로 추가됨`);
                }
            });

            rawPages.push({
                isDuet: true,
                voices: charNums.map(cn => ({ voice_id: charMap[cn]?.voice_id || '', text: content })),
                mode: 'overlap'
            });
            continue;
        }

        // N: 형식 (일반 대사)
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
    let current = null;

    for (let i = 0; i < rawPages.length; i++) {
        const page = rawPages[i];

        // duet 블록은 합치지 않고 그대로 추가
        if (page.isDuet) {
            if (current) { grouped.push({ ...current }); current = null; }
            grouped.push({ voices: page.voices, mode: page.mode });
            continue;
        }

        if (!current) {
            current = { text: page.text, voice_id: page.voice_id };
            continue;
        }

        if (page.voice_id === current.voice_id &&
            (current.text.length + page.text.length + 1) <= 300) {
            current.text += ' ' + page.text;
        } else {
            grouped.push({ ...current });
            current = { text: page.text, voice_id: page.voice_id };
        }
    }
    if (current) grouped.push({ ...current });

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

    if (rawPages.length === 0) {
        showStatus('유효한 대사가 없습니다', 'error');
        return null;
    }

    if (errors.length > 0) {
        // 경고만 표시하고 계속 진행 (미등록 캐릭터 등 일부 라인 스킵)
        console.warn('파싱 경고:', errors);
        showStatus(`⚠️ 경고 ${errors.length}건 (스킵됨) - 나머지로 계속 진행`, 'warning');
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
                pages: pages.map(p => {
                    if (p.voices) {
                        // duet 블록 (N,M: 형식)
                        return { voices: p.voices, mode: p.mode || 'overlap' };
                    }
                    return { text: p.text, voice_id: p.voice_id };
                })
            }
        ]
    };

    // JSON 에디터에 표시 (편집 가능)
    const editor = document.getElementById('jsonEditor');
    if (editor) {
        editor.value = JSON.stringify(jsonData, null, 2);
    }

    showStatus(`JSON 생성 완료 (${rawPages.length}줄 → ${pages.length}페이지) - 수정 후 실행 가능`, 'success');

    // 보이스 설정 자동 저장
    saveVoiceConfig(charMap);

    // 블록 뷰 자동 업데이트
    renderBlocks(jsonData);

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

        // AI가 반환한 JSON을 에디터에 표시 + 블록 뷰 업데이트
        const editor = document.getElementById('jsonEditor');
        if (editor) {
            editor.value = JSON.stringify(result, null, 2);
        }
        renderBlocks(result);

        showStatus('AI 분석 완료 - 블록에서 BGM/SFX를 확인하고 수정 후 실행하세요', 'success');

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
    // Ctrl+위아래: 선택된 블록 순서 이동
    if (e.ctrlKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
        const tag = (document.activeElement?.tagName || '').toUpperCase();
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return;
        if (_selectedBlockIndex === null) return;
        e.preventDefault();
        moveSelectedBlock(e.key === 'ArrowUp' ? -1 : 1);
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

// ==================== 보이스 설정 저장/복원 ====================

/**
 * 저장된 config에서 캐릭터 & 목소리를 복원
 * config: { "0": {name, voice_id}, "1": {name, voice_id}, ... }
 */
function restoreVoiceConfig(config) {
    const list = document.getElementById('characterList');
    if (!list) return;

    const keys = Object.keys(config).map(Number).sort((a, b) => a - b);
    let maxNum = 1;

    for (const num of keys) {
        const cfg = config[num];
        if (!cfg || !cfg.voice_id) continue;

        let item = list.querySelector(`.character-item[data-number="${num}"]`);

        if (num >= 1 && !item) {
            // 새 캐릭터 항목 생성
            item = document.createElement('div');
            item.className = 'character-item';
            item.dataset.number = num;
            item.innerHTML = `
                <div class="character-number-badge">${num}</div>
                <div class="character-content">
                    <input type="text" class="character-name" placeholder="캐릭터 이름" data-number="${num}">
                    <select class="voice-select" data-number="${num}">
                        <option value="">목소리 선택</option>
                        ${voiceList.map(v => `<option value="${v.id}">${v.name}</option>`).join('')}
                    </select>
                </div>
                <button class="btn-remove-char" onclick="removeCharacter(${num})">삭제</button>
            `;
            list.appendChild(item);
        }

        if (item) {
            const nameInput = item.querySelector('.character-name');
            const voiceSel = item.querySelector('.voice-select');
            if (nameInput && cfg.name) nameInput.value = cfg.name;
            if (voiceSel && cfg.voice_id) voiceSel.value = cfg.voice_id;
        }

        if (num > maxNum) maxNum = num;
    }

    characterCount = maxNum;
    console.log('보이스 설정 복원 완료:', Object.keys(config).length, '개 캐릭터');
}

/**
 * 캐릭터 맵 + 소설 텍스트 + 제목을 DB에 저장
 */
async function saveVoiceConfig(charMap) {
    if (!bookId) return;

    const novelTextEl = document.getElementById('novelText');
    const titleInputEl = document.getElementById('episodeTitle');

    const payload = {};
    if (charMap && Object.keys(charMap).length > 0) payload.voice_config = charMap;
    if (novelTextEl) payload.draft_text = novelTextEl.value;
    if (titleInputEl) payload.draft_episode_title = titleInputEl.value;

    try {
        await fetch(`/book/serialization/fast/${bookId}/voice-config/save/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(payload)
        });
    } catch (e) {
        console.warn('설정 저장 실패:', e);
    }
}

/**
 * 소설 텍스트 + 제목만 저장 (debounce 자동 저장용)
 */
async function saveDraft() {
    if (!bookId) return;

    const novelTextEl = document.getElementById('novelText');
    const titleInputEl = document.getElementById('episodeTitle');

    const payload = {
        draft_text: novelTextEl ? novelTextEl.value : '',
        draft_episode_title: titleInputEl ? titleInputEl.value : ''
    };

    try {
        await fetch(`/book/serialization/fast/${bookId}/voice-config/save/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(payload)
        });
    } catch (e) {
        console.warn('임시저장 실패:', e);
    }
}

console.log('오디오북 생성기 스크립트 로드 완료');


// ==================== 블록 편집 전역 상태 ====================
let _blockItems = [];       // [{type:'page', pageData} | {type:'sfx', sfxData}]
let _bgmItems = [];         // [{_id, _name, _desc, start_page, end_page, volume}]
let _blockJSON = null;
let _selectedEpStep = 0;
let _selectedBlockIndex = null;

// ==================== 캐릭터 색상 코딩 ====================
const VOICE_COLORS = [
    '#ec4899','#f59e0b','#10b981','#3b82f6',
    '#8b5cf6','#ef4444','#06b6d4','#84cc16',
    '#f97316','#14b8a6','#a855f7','#64748b'
];
let _voiceColorMap = {};
let _voiceColorIdx = 0;

function getVoiceColor(voiceId) {
    if (!voiceId) return '#4b5563';
    if (!_voiceColorMap[voiceId]) {
        _voiceColorMap[voiceId] = VOICE_COLORS[_voiceColorIdx % VOICE_COLORS.length];
        _voiceColorIdx++;
    }
    return _voiceColorMap[voiceId];
}

// ==================== 예상 재생 시간 ====================
function estimatePageDuration(text) {
    const clean = (text || '').replace(/\[[^\]]*\]/g, '').trim();
    return clean.length / 4.0;  // ~4글자/초 (한국어 TTS)
}

function formatDuration(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    return m > 0 ? `${m}분 ${s}초` : `${s}초`;
}

// ==================== WebAudio 효과 프리셋 ====================
const BLOCK_EFFECTS = [
    {id:'normal',    label:'기본'},    {id:'phone',     label:'전화기'},
    {id:'cave',      label:'동굴'},    {id:'underwater', label:'수중'},
    {id:'robot',     label:'로봇'},    {id:'whisper',   label:'속삭임'},
    {id:'radio',     label:'라디오'},  {id:'deep',      label:'저음'},
    {id:'bright',    label:'밝음'},    {id:'echo',      label:'에코'},
    {id:'demon',     label:'악마'},    {id:'angel',     label:'천사'},
    {id:'horror',    label:'공포'},    {id:'helium',    label:'헬륨'},
    {id:'megaphone', label:'메가폰'},  {id:'choir',     label:'합창'},
    {id:'timewarp',  label:'타임워프'},{id:'lofi-girl', label:'Lo-Fi'},
    {id:'protoss',   label:'프로토스'},{id:'ghost',     label:'유령'},
];

// ==================== 탭 전환 ====================
function switchRightTab(tab) {
    const tabBlocks = document.getElementById('tabBlocks');
    const tabJson = document.getElementById('tabJson');
    const btnBlocks = document.getElementById('tabBtnBlocks');
    const btnJson = document.getElementById('tabBtnJson');
    if (!tabBlocks || !tabJson) return;
    if (tab === 'blocks') {
        tabBlocks.style.display = '';
        tabJson.style.display = 'none';
        if (btnBlocks) btnBlocks.classList.add('active');
        if (btnJson) btnJson.classList.remove('active');
    } else {
        tabBlocks.style.display = 'none';
        tabJson.style.display = '';
        if (btnBlocks) btnBlocks.classList.remove('active');
        if (btnJson) btnJson.classList.add('active');
    }
}

// ==================== JSON 파일 업로드 ====================
function loadJSONFile(input) {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const parsed = JSON.parse(e.target.result);
            const editor = document.getElementById('jsonEditor');
            if (editor) editor.value = JSON.stringify(parsed, null, 2);
            renderBlocks(parsed);
            showStatus('JSON 파일이 로드되었습니다', 'success');
        } catch(err) {
            showStatus('JSON 파싱 오류: ' + err.message, 'error');
        }
    };
    reader.readAsText(file, 'utf-8');
    input.value = '';
}

// ==================== 블록 렌더링 (JSON → _blockItems + _bgmItems) ====================
function renderBlocks(jsonData) {
    if (!jsonData) return;
    _blockJSON = JSON.parse(JSON.stringify(jsonData));

    let epStep = null, epStepIdx = 0;
    if (_blockJSON.action === 'create_episode') {
        epStep = _blockJSON;
    } else if (_blockJSON.steps) {
        for (let i = 0; i < _blockJSON.steps.length; i++) {
            if (_blockJSON.steps[i].action === 'create_episode') {
                epStep = _blockJSON.steps[i]; epStepIdx = i; break;
            }
        }
    }
    _selectedEpStep = epStepIdx;

    const list = document.getElementById('blockList');
    if (!list) return;

    if (!epStep || !epStep.pages || epStep.pages.length === 0) {
        list.innerHTML = "<div class='block-empty'><p>create_episode 데이터가 없습니다</p></div>";
        const bgmSec = document.getElementById('bgmSection');
        if (bgmSec) bgmSec.style.display = 'none';
        return;
    }

    // 페이지 → _blockItems (silence, duet 포함)
    _blockItems = epStep.pages.map(p => {
        if (p.silence_seconds !== undefined) {
            return {type: 'silence', silenceData: {duration: parseFloat(p.silence_seconds) || 1.0}};
        } else if (p.voices) {
            return {
                type: 'duet',
                duetData: {
                    voices: (p.voices || []).map(v => ({
                        voice_id: v.voice_id || '',
                        text: v.text || '',
                        webaudio_effect: v.webaudio_effect || ''
                    })),
                    mode: p.mode || 'alternate'
                }
            };
        } else {
            return {type: 'page', pageData: {text: p.text || '', voice_id: p.voice_id || '', _effect: p.webaudio_effect || ''}};
        }
    });

    // create_bgm / create_sfx 메타 정보 ($bgm_N, $sfx_N → 이름/설명)
    const bgmMeta = {}, sfxMeta = {};
    if (_blockJSON.steps) {
        let bgmCount = 0, sfxCount = 0;
        _blockJSON.steps.forEach(step => {
            if (step.action === 'create_bgm') {
                bgmCount++;
                bgmMeta[`$bgm_${bgmCount}`] = {name: step.music_name || '', desc: step.music_description || ''};
            }
            if (step.action === 'create_sfx') {
                sfxCount++;
                sfxMeta[`$sfx_${sfxCount}`] = {name: step.effect_name || '', desc: step.effect_description || ''};
            }
        });
    }

    // SFX / BGM 파싱
    let mixBgmStep = null;
    if (_blockJSON.steps) mixBgmStep = _blockJSON.steps.find(s => s.action === 'mix_bgm');

    if (mixBgmStep) {
        const sfxSorted = (mixBgmStep.sound_effects || []).slice()
            .sort((a, b) => (b.page_number || b.page || 1) - (a.page_number || a.page || 1));

        sfxSorted.forEach(sfx => {
            const targetPage = Math.max(1, sfx.page_number || sfx.page || 1);
            let pageCount = 0, insertIdx = _blockItems.length;
            for (let i = 0; i < _blockItems.length; i++) {
                const t = _blockItems[i].type;
                if (t === 'page' || t === 'duet' || t === 'silence') {
                    pageCount++;
                    if (pageCount === targetPage) { insertIdx = i; break; }
                }
            }
            const meta = sfxMeta[sfx.effect_id] || {};
            _blockItems.splice(insertIdx, 0, {
                type: 'sfx',
                sfxData: {
                    _id: sfx.effect_id || '',
                    _name: meta.name || '',
                    _desc: meta.desc || '',
                    volume: sfx.volume !== undefined ? sfx.volume : 1.0
                }
            });
        });

        _bgmItems = (mixBgmStep.background_tracks || []).map(t => {
            const meta = bgmMeta[t.music_id] || {};
            return {
                _id: t.music_id || '',
                _name: meta.name || '',
                _desc: meta.desc || '',
                start_page: t.start_page || 1,
                end_page: t.end_page || epStep.pages.length,
                volume: t.volume !== undefined ? t.volume : 0.2
            };
        });
    } else {
        _bgmItems = [];
    }

    _selectedBlockIndex = null;
    _voiceColorMap = {};
    _voiceColorIdx = 0;
    const wp = document.getElementById('webAudioPanel');
    if (wp) wp.style.display = 'none';
    switchRightTab('blocks');
    renderBlockList();
    renderBgmSection();
}

// ==================== 블록 목록 HTML 렌더링 ====================
function renderBlockList() {
    const list = document.getElementById('blockList');
    if (!list) return;

    if (_blockItems.length === 0) {
        list.innerHTML = "<div class='block-empty'><p>블록이 없습니다</p></div>";
        return;
    }

    // 색상 pre-scan (등장 순서대로 색상 배정)
    _voiceColorMap = {};
    _voiceColorIdx = 0;
    _blockItems.forEach(item => {
        if (item.type === 'page' && item.pageData.voice_id)
            getVoiceColor(item.pageData.voice_id);
    });

    // 총 예상 시간 계산
    let totalSec = 0;
    _blockItems.forEach(item => {
        if (item.type === 'page') totalSec += estimatePageDuration(item.pageData.text);
        else if (item.type === 'silence') totalSec += (item.silenceData.duration || 1.0);
    });

    let html = `<div class="block-time-summary">예상 재생시간 약 <strong>${formatDuration(totalSec)}</strong><span class="block-move-hint">블록을 움직이려면 클릭 후 Ctrl+↑↓ 를 누르세요</span></div>`;
    html += sfxInsertRowHTML(0);
    let pageNum = 0;

    _blockItems.forEach((item, idx) => {
        if (item.type === 'page') {
            pageNum++;
            const eff = item.pageData._effect || '';
            const effLabel = eff ? (BLOCK_EFFECTS.find(e => e.id === eff) || {label: eff}).label : '';
            const effBadge = eff ? `<span class="block-badge badge-effect">${effLabel}</span>` : '';
            const voiceOpts = voiceList.map(v =>
                `<option value="${v.id}"${v.id === item.pageData.voice_id ? ' selected' : ''}>${v.name}</option>`
            ).join('');
            const isSelected = _selectedBlockIndex === idx;
            const color = getVoiceColor(item.pageData.voice_id);
            const dur = estimatePageDuration(item.pageData.text);
            const durLabel = dur > 0 ? `<span class="block-duration-badge">~${formatDuration(dur)}</span>` : '';

            html += `<div class="block-item${isSelected ? ' selected' : ''}" id="block-${idx}"
                style="border-left: 3px solid ${color};"
                onclick="selectBlock(${idx})">
                <div class="block-header">
                    <span class="block-page-badge" style="background:${color};">P${pageNum}</span>
                    <select class="block-voice-select" onchange="updateBlockVoice(${idx}, this.value)" onclick="event.stopPropagation()">
                        <option value="">목소리 선택</option>${voiceOpts}
                    </select>
                    <div class="block-badges">${effBadge}${durLabel}</div>
                    <button class="page-remove-btn" onclick="event.stopPropagation(); removePage(${idx})" title="삭제">×</button>
                </div>
                <textarea class="block-text-edit" rows="3"
                    onchange="updateBlockText(${idx}, this.value)"
                    onclick="event.stopPropagation()"
                    placeholder="텍스트를 입력하세요">${escapeHtml(item.pageData.text)}</textarea>
            </div>`;

        } else if (item.type === 'sfx') {
            html += `<div class="sfx-block" id="block-${idx}" onclick="selectBlock(${idx})">
                <div class="sfx-main-row">
                    <span class="sfx-icon">🔊</span>
                    <span class="sfx-label">SFX</span>
                    <input class="sfx-name-input" type="text" placeholder="이름 (예: 문 닫히는 소리)"
                        value="${escapeAttr(item.sfxData._name)}"
                        onchange="updateSfxName(${idx}, this.value)" onclick="event.stopPropagation()">
                    <input class="sfx-vol-input" type="number" min="0" max="2" step="0.1"
                        value="${item.sfxData.volume}" title="볼륨"
                        onchange="updateSfxVol(${idx}, this.value)" onclick="event.stopPropagation()">
                    <button class="sfx-remove-btn" onclick="removeSfx(${idx})" title="삭제">×</button>
                </div>
                <input class="sfx-desc-input" type="text"
                    placeholder="사운드 이펙트 프롬프트 넣기 (예: wooden door closing sound)"
                    value="${escapeAttr(item.sfxData._desc)}"
                    onchange="updateSfxDesc(${idx}, this.value)" onclick="event.stopPropagation()">
            </div>`;

        } else if (item.type === 'silence') {
            const dur = item.silenceData.duration || 1.0;
            const opts = [0.5,1.0,1.5,2.0,2.5,3.0].map(v =>
                `<option value="${v}"${v === dur ? ' selected' : ''}>${v}초</option>`
            ).join('');
            html += `<div class="silence-block" id="block-${idx}" onclick="selectBlock(${idx})">
                <span class="silence-icon">🔇</span>
                <span class="silence-label">무음</span>
                <select class="silence-dur-select" onchange="updateSilenceDuration(${idx}, parseFloat(this.value))" onclick="event.stopPropagation()">${opts}</select>
                <span class="silence-hint">BGM 계속 재생</span>
                <button class="sfx-remove-btn" onclick="removeSilence(${idx})" title="삭제">×</button>
            </div>`;

        } else if (item.type === 'duet') {
            try {
                pageNum++;
                const d = item.duetData;
                if (!d || !d.voices) throw new Error('duetData.voices 없음: ' + JSON.stringify(item));
                const voiceCount = d.voices.length;

                let voiceRows = '';
                d.voices.forEach((v, vi) => {
                    const vopts = voiceList.map(vl =>
                        `<option value="${vl.id}"${vl.id === v.voice_id ? ' selected' : ''}>${vl.name}</option>`).join('');
                    const color = getVoiceColor(v.voice_id);
                    voiceRows += `<div class="duet-voice-row" style="border-left:3px solid ${color};">
                        <select class="block-voice-select" onchange="updateDuetVoice(${idx},${vi},this.value)">
                            <option value="">목소리 ${vi+1}</option>${vopts}
                        </select>
                        <textarea class="block-text-edit duet-text" rows="2"
                            onchange="updateDuetText(${idx},${vi},this.value)"
                            placeholder="캐릭터 ${vi+1} 대사">${escapeHtml(v.text)}</textarea>
                        ${voiceCount > 2 ? `<button class="sfx-remove-btn" onclick="removeDuetVoice(${idx},${vi})" title="제거">×</button>` : ''}
                    </div>`;
                });

                html += `<div class="duet-block" id="block-${idx}" onclick="selectBlock(${idx})">
                    <div class="duet-header">
                        <span class="duet-badge">🎭 P${pageNum} ${voiceCount}인 동시 대화</span>
                        <button class="sfx-insert-btn" onclick="addDuetVoice(${idx})" style="font-size:11px;padding:2px 6px;margin-left:4px;">+ 목소리</button>
                        <button class="page-remove-btn" onclick="event.stopPropagation(); removeDuet(${idx})">×</button>
                    </div>
                    ${voiceRows}
                </div>`;
            } catch (e) {
                console.error('[renderBlockList] duet 렌더링 오류 (idx=' + idx + '):', e, item);
                html += `<div style="background:#fee2e2;border:2px solid #f87171;border-radius:8px;padding:8px;margin-bottom:4px;color:#dc2626;font-size:12px;">
                    ⚠️ 2인 대화 렌더링 오류 (idx=${idx}): ${e.message}
                    <button onclick="removeDuet(${idx})" style="margin-left:8px;color:#dc2626;border:1px solid #f87171;background:none;cursor:pointer;border-radius:4px;padding:2px 6px;">삭제</button>
                </div>`;
            }
        } else if (item.type !== 'page' && item.type !== 'sfx' && item.type !== 'silence') {
            console.warn('[renderBlockList] 알 수 없는 블록 타입 (idx=' + idx + '):', item.type, item);
        }
        html += sfxInsertRowHTML(idx + 1);
    });

    list.innerHTML = html;
}

// ==================== 블록 Ctrl+방향키 이동 ====================
function moveSelectedBlock(dir) {
    if (_selectedBlockIndex === null) return;
    const idx = _selectedBlockIndex;
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= _blockItems.length) return;
    const moved = _blockItems.splice(idx, 1)[0];
    _blockItems.splice(newIdx, 0, moved);
    _selectedBlockIndex = newIdx;
    renderBlockList();
    syncBlocksToJSON();
    // 이동된 블록으로 스크롤
    const el = document.getElementById('block-' + newIdx);
    if (el) el.scrollIntoView({ block: 'nearest' });
}

function sfxInsertRowHTML(afterIdx) {
    return `<div class="sfx-insert-row">
        <button class="sfx-insert-btn" onclick="insertSfx(${afterIdx})">+ SFX</button>
        <button class="page-insert-btn" onclick="insertPage(${afterIdx})">+ 대사</button>
        <button class="silence-insert-btn" onclick="insertSilence(${afterIdx})">+ 무음</button>
        <button class="duet-insert-btn" onclick="insertDuet(${afterIdx})">+ 2인 대화</button>
    </div>`;
}

function escapeHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeAttr(str) {
    return (str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ==================== BGM 섹션 렌더링 ====================
function renderBgmSection() {
    const section = document.getElementById('bgmSection');
    const trackList = document.getElementById('bgmTrackList');
    if (!section || !trackList) return;
    section.style.display = '';

    if (_bgmItems.length === 0) {
        trackList.innerHTML = "<div class='bgm-empty-msg'>배경음악 없음 — 위 버튼으로 추가하세요</div>";
        return;
    }

    const totalPages = _blockItems.filter(b => b.type === 'page').length;
    trackList.innerHTML = _bgmItems.map((bgm, idx) => `
        <div class="bgm-track-item">
            <div class="bgm-controls-row">
                <input class="bgm-name-input" type="text" placeholder="이름 (예: 긴장감 있는 배경음)"
                    value="${escapeAttr(bgm._name)}"
                    onchange="updateBgmName(${idx}, this.value)">
                <div class="bgm-range-row">
                    <label>P</label>
                    <input class="bgm-page-input" type="number" min="1" max="${totalPages}" value="${bgm.start_page}"
                        onchange="updateBgmField(${idx},'start_page',parseInt(this.value)||1)">
                    <span>~</span>
                    <input class="bgm-page-input" type="number" min="1" max="${totalPages}" value="${bgm.end_page}"
                        onchange="updateBgmField(${idx},'end_page',parseInt(this.value)||${totalPages})">
                    <label>vol</label>
                    <input class="bgm-vol-input" type="number" min="0" max="1" step="0.05" value="${bgm.volume}"
                        onchange="updateBgmField(${idx},'volume',parseFloat(this.value)||0)">
                </div>
                <button class="bgm-remove-btn" onclick="removeBgmTrack(${idx})">×</button>
            </div>
            <input class="bgm-desc-input" type="text"
                placeholder="배경음 프롬프트 넣기 (예: tense orchestral music with strings)"
                value="${escapeAttr(bgm._desc)}"
                onchange="updateBgmDesc(${idx}, this.value)">
        </div>
    `).join('');
}

// ==================== SFX 삽입/삭제/수정 ====================
function insertSfx(atIndex) {
    _blockItems.splice(atIndex, 0, {type: 'sfx', sfxData: {_id: '', _name: '', _desc: '', volume: 1.0}});
    if (_selectedBlockIndex !== null && _selectedBlockIndex >= atIndex) _selectedBlockIndex++;
    renderBlockList();
    syncBlocksToJSON();
}

function removeSfx(idx) {
    _blockItems.splice(idx, 1);
    if (_selectedBlockIndex === idx) {
        _selectedBlockIndex = null;
        const wp = document.getElementById('webAudioPanel');
        if (wp) wp.style.display = 'none';
    } else if (_selectedBlockIndex !== null && _selectedBlockIndex > idx) {
        _selectedBlockIndex--;
    }
    renderBlockList();
    syncBlocksToJSON();
}

function insertPage(atIndex) {
    _blockItems.splice(atIndex, 0, {type: 'page', pageData: {text: '', voice_id: '', _effect: ''}});
    if (_selectedBlockIndex !== null && _selectedBlockIndex >= atIndex) _selectedBlockIndex++;
    renderBlockList();
    syncBlocksToJSON();
}

function removePage(idx) {
    _blockItems.splice(idx, 1);
    if (_selectedBlockIndex === idx) {
        _selectedBlockIndex = null;
        const wp = document.getElementById('webAudioPanel');
        if (wp) wp.style.display = 'none';
    } else if (_selectedBlockIndex !== null && _selectedBlockIndex > idx) {
        _selectedBlockIndex--;
    }
    renderBlockList();
    syncBlocksToJSON();
}

function insertSilence(atIndex) {
    _blockItems.splice(atIndex, 0, {type: 'silence', silenceData: {duration: 1.0}});
    if (_selectedBlockIndex !== null && _selectedBlockIndex >= atIndex) _selectedBlockIndex++;
    renderBlockList();
    syncBlocksToJSON();
}

function removeSilence(idx) {
    _blockItems.splice(idx, 1);
    if (_selectedBlockIndex !== null && _selectedBlockIndex > idx) _selectedBlockIndex--;
    renderBlockList();
    syncBlocksToJSON();
}

function updateSilenceDuration(idx, value) {
    if (_blockItems[idx]) _blockItems[idx].silenceData.duration = value;
    syncBlocksToJSON();
}

// ==================== 2인 대화 ====================
function insertDuet(atIndex) {
    _blockItems.splice(atIndex, 0, {
        type: 'duet',
        duetData: {
            voices: [
                {voice_id: '', text: '', webaudio_effect: ''},
                {voice_id: '', text: '', webaudio_effect: ''}
            ],
            mode: 'overlap'
        }
    });
    if (_selectedBlockIndex !== null && _selectedBlockIndex >= atIndex) _selectedBlockIndex++;
    renderBlockList();
    syncBlocksToJSON();
}

function removeDuet(idx) {
    _blockItems.splice(idx, 1);
    if (_selectedBlockIndex !== null && _selectedBlockIndex > idx) _selectedBlockIndex--;
    renderBlockList();
    syncBlocksToJSON();
}

function addDuetVoice(idx) {
    if (_blockItems[idx] && _blockItems[idx].type === 'duet') {
        _blockItems[idx].duetData.voices.push({voice_id: '', text: '', webaudio_effect: ''});
        renderBlockList();
        syncBlocksToJSON();
    }
}

function removeDuetVoice(idx, voiceNum) {
    if (_blockItems[idx] && _blockItems[idx].type === 'duet') {
        if (_blockItems[idx].duetData.voices.length > 2) {
            _blockItems[idx].duetData.voices.splice(voiceNum, 1);
            renderBlockList();
            syncBlocksToJSON();
        }
    }
}

function updateDuetVoice(idx, voiceNum, voiceId) {
    if (_blockItems[idx]) _blockItems[idx].duetData.voices[voiceNum].voice_id = voiceId;
    renderBlockList();
    syncBlocksToJSON();
}

function updateDuetText(idx, voiceNum, text) {
    if (_blockItems[idx]) _blockItems[idx].duetData.voices[voiceNum].text = text;
    syncBlocksToJSON();
}

function updateDuetMode(idx, mode) {
    if (_blockItems[idx]) _blockItems[idx].duetData.mode = mode;
    syncBlocksToJSON();
}

function updateSfxName(idx, value) {
    if (_blockItems[idx]) _blockItems[idx].sfxData._name = value;
    syncBlocksToJSON();
}

function updateSfxDesc(idx, value) {
    if (_blockItems[idx]) _blockItems[idx].sfxData._desc = value;
    syncBlocksToJSON();
}

function updateSfxVol(idx, value) {
    if (_blockItems[idx]) _blockItems[idx].sfxData.volume = parseFloat(value) || 1.0;
    syncBlocksToJSON();
}

// ==================== BGM 추가/삭제/수정 ====================
function addBgmTrack() {
    const totalPages = _blockItems.filter(b => b.type === 'page').length || 1;
    _bgmItems.push({_id: '', _name: '', _desc: '', start_page: 1, end_page: totalPages, volume: 0.2});
    renderBgmSection();
    syncBlocksToJSON();
}

function removeBgmTrack(idx) {
    _bgmItems.splice(idx, 1);
    renderBgmSection();
    syncBlocksToJSON();
}

function updateBgmName(idx, value) {
    if (_bgmItems[idx]) _bgmItems[idx]._name = value;
    syncBlocksToJSON();
}

function updateBgmDesc(idx, value) {
    if (_bgmItems[idx]) _bgmItems[idx]._desc = value;
    syncBlocksToJSON();
}

function updateBgmField(idx, field, value) {
    if (_bgmItems[idx]) _bgmItems[idx][field] = value;
    syncBlocksToJSON();
}

// ==================== TTS 텍스트 수정 ====================
function updateBlockText(idx, value) {
    if (_blockItems[idx] && _blockItems[idx].type === 'page') {
        _blockItems[idx].pageData.text = value;
    }
    syncBlocksToJSON();
}

// ==================== 블록 선택 (TTS 페이지 → WebAudio) ====================
function selectBlock(idx) {
    if (!_blockItems[idx]) return;

    if (_selectedBlockIndex !== null) {
        const prev = document.getElementById('block-' + _selectedBlockIndex);
        if (prev) prev.classList.remove('selected');
    }
    _selectedBlockIndex = idx;
    const el = document.getElementById('block-' + idx);
    if (el) el.classList.add('selected');

    // page 타입일 때만 WebAudio 패널 표시
    if (_blockItems[idx].type === 'page') {
        let pn = 0;
        for (let i = 0; i <= idx; i++) if (_blockItems[i].type === 'page') pn++;
        const panel = document.getElementById('webAudioPanel');
        const titleEl = document.getElementById('webAudioTitle');
        if (panel) panel.style.display = '';
        if (titleEl) titleEl.textContent = '페이지 ' + pn + ' 효과음';
        renderWebAudioButtons(idx);
    } else {
        const panel = document.getElementById('webAudioPanel');
        if (panel) panel.style.display = 'none';
    }
}

// ==================== WebAudio 버튼 렌더링 ====================
function renderWebAudioButtons(blockIdx) {
    const container = document.getElementById('webAudioEffects');
    if (!container) return;
    const eff = (_blockItems[blockIdx] && _blockItems[blockIdx].pageData && _blockItems[blockIdx].pageData._effect) || '';
    const activeId = eff || 'normal';
    container.innerHTML = BLOCK_EFFECTS.map(e =>
        `<button class="webaudio-btn${e.id === activeId ? ' active' : ''}" onclick="applyBlockEffect('${e.id}')">${e.label}</button>`
    ).join('');
}

// ==================== WebAudio 효과 적용 ====================
function applyBlockEffect(effectId) {
    if (_selectedBlockIndex === null || !_blockItems[_selectedBlockIndex]) return;
    _blockItems[_selectedBlockIndex].pageData._effect = (effectId === 'normal') ? '' : effectId;
    renderBlockList();
    renderWebAudioButtons(_selectedBlockIndex);
    const el = document.getElementById('block-' + _selectedBlockIndex);
    if (el) el.classList.add('selected');
    syncBlocksToJSON();
}

// ==================== 목소리 변경 ====================
function updateBlockVoice(idx, voiceId) {
    if (_blockItems[idx]) _blockItems[idx].pageData.voice_id = voiceId;
    syncBlocksToJSON();
}

// ==================== JSON 에디터 동기화 ====================
function syncBlocksToJSON() {
    if (!_blockJSON) return;

    // 1. pages 재구성 (silence, duet 포함 — BGM은 merged audio 전체에 걸쳐 재생됨)
    const pages = [];
    for (const b of _blockItems) {
        if (b.type === 'page') {
            const p = {text: b.pageData.text, voice_id: b.pageData.voice_id};
            if (b.pageData._effect) p.webaudio_effect = b.pageData._effect;
            pages.push(p);
        } else if (b.type === 'silence') {
            pages.push({silence_seconds: b.silenceData.duration || 1.0});
        } else if (b.type === 'duet') {
            const d = b.duetData;
            const voices = (d.voices || []).map(v => {
                const entry = {voice_id: v.voice_id || '', text: v.text || ''};
                if (v.webaudio_effect && v.webaudio_effect !== 'normal') entry.webaudio_effect = v.webaudio_effect;
                return entry;
            });
            pages.push({voices, mode: 'overlap'});
        }
    }

    // 2. SFX 처리: 프롬프트 있으면 create_sfx step 생성
    let sfxIdx = 0;
    const sfxCreateSteps = [];
    const sfxList = [];
    let pageCount = 0;

    for (let i = 0; i < _blockItems.length; i++) {
        const item = _blockItems[i];
        if (item.type === 'page' || item.type === 'silence' || item.type === 'duet') {
            pageCount++;
        } else if (item.type === 'sfx') {
            const d = item.sfxData;
            let effectId = d._id || '';

            if (d._desc || d._name) {
                // 프롬프트 있음 → create_sfx step 생성
                sfxIdx++;
                sfxCreateSteps.push({
                    action: 'create_sfx',
                    effect_name: d._name || `SFX ${sfxIdx}`,
                    effect_description: d._desc || d._name || ''
                });
                effectId = `$sfx_${sfxIdx}`;
                item.sfxData._id = effectId;
            }

            if (effectId) {
                // page_number 계산
                let nextPageNum = pageCount + 1;
                let hasNext = false;
                for (let j = i + 1; j < _blockItems.length; j++) {
                    if (_blockItems[j].type === 'page' || _blockItems[j].type === 'duet') { hasNext = true; break; }
                }
                if (!hasNext) nextPageNum = Math.max(1, pageCount);
                sfxList.push({
                    effect_id: effectId,
                    page_number: Math.max(1, nextPageNum),
                    volume: d.volume
                });
            }
        }
    }

    // 3. BGM 처리: 프롬프트 있으면 create_bgm step 생성
    let bgmIdx = 0;
    const bgmCreateSteps = [];
    const bgmTracks = [];

    _bgmItems.forEach(b => {
        let musicId = b._id || '';

        if (b._desc || b._name) {
            bgmIdx++;
            bgmCreateSteps.push({
                action: 'create_bgm',
                music_name: b._name || `BGM ${bgmIdx}`,
                music_description: b._desc || b._name || '',
                duration_seconds: 120
            });
            musicId = `$bgm_${bgmIdx}`;
            b._id = musicId;
        }

        if (musicId) {
            bgmTracks.push({
                music_id: musicId,
                start_page: b.start_page,
                end_page: b.end_page,
                volume: b.volume
            });
        }
    });

    // 4. steps 재구성 (순서: create_bgm → create_sfx → create_episode → mix_bgm)
    if (_blockJSON.steps) {
        // 기존 create_bgm, create_sfx, mix_bgm 제거, 나머지 유지
        const otherSteps = _blockJSON.steps.filter(s =>
            s.action !== 'create_bgm' && s.action !== 'create_sfx' && s.action !== 'mix_bgm'
        );

        // create_episode 업데이트
        const epIdx = otherSteps.findIndex(s => s.action === 'create_episode');
        if (epIdx >= 0) otherSteps[epIdx].pages = pages;

        const newSteps = [
            ...bgmCreateSteps,
            ...sfxCreateSteps,
            ...otherSteps
        ];

        if (bgmTracks.length > 0 || sfxList.length > 0) {
            const epStep = otherSteps.find(s => s.action === 'create_episode');
            newSteps.push({
                action: 'mix_bgm',
                book_uuid: (epStep && epStep.book_uuid) || _blockJSON.book_uuid || '',
                episode_number: (epStep && epStep.episode_number) || 1,
                background_tracks: bgmTracks,
                sound_effects: sfxList
            });
        }

        _blockJSON.steps = newSteps;
    } else if (_blockJSON.action === 'create_episode') {
        _blockJSON.pages = pages;
    }

    const editor = document.getElementById('jsonEditor');
    if (editor) editor.value = JSON.stringify(_blockJSON, null, 2);
}

// ==================== WebAudio 패널 닫기 ====================
function closeWebAudio() {
    const panel = document.getElementById('webAudioPanel');
    if (panel) panel.style.display = 'none';
    if (_selectedBlockIndex !== null) {
        const el = document.getElementById('block-' + _selectedBlockIndex);
        if (el) el.classList.remove('selected');
        _selectedBlockIndex = null;
    }
}
