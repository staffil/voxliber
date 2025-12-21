/**
 * sound-effects.js
 * 사운드 이팩트 관련 기능
 */

// 사운드 이팩트 모달 열기
function openSoundEffectModal() {
    const modal = document.getElementById('soundEffectModal');
    modal.style.display = 'flex';
    document.getElementById('effectName').value = '';
    document.getElementById('effectDescription').value = '';
}

// 사운드 이팩트 모달 닫기
function closeSoundEffectModal() {
    const modal = document.getElementById('soundEffectModal');
    modal.style.display = 'none';
}

// 사운드 이팩트 생성
async function generateSoundEffect() {
    const effectName = document.getElementById('effectName').value.trim();
    const effectDescription = document.getElementById('effectDescription').value.trim();
    const duration = parseInt(document.getElementById('effectDuration').value);

    if (!effectName || !effectDescription) {
        alert('이팩트 이름과 설명을 모두 입력해주세요.');
        return;
    }

    const generateBtn = event.target;
    generateBtn.disabled = true;
    generateBtn.textContent = '🔄 생성 중...';

    try {
        const response = await fetch('/book/sound-effect/generate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                effect_name: effectName,
                effect_description: effectDescription,
                duration_seconds: duration
            })
        });

        if (!response.ok) {
            throw new Error('사운드 이팩트 생성 실패');
        }

        const blob = await response.blob();
        const audioUrl = URL.createObjectURL(blob);
        const audioFile = new File([blob], `sound_effect_${Date.now()}.mp3`, { type: 'audio/mp3' });

        // 사운드 이팩트 카드 생성 (대사가 아닌 사운드 이팩트)
        const soundEffectPage = createPage('', audioFile, true);
        soundEffectPage.effectName = effectName;
        soundEffectPage.audioUrl = audioUrl;

        // 현재 선택된 대사 뒤에 삽입
        saveCurrentPage(); // 현재 페이지 저장
        pages.splice(currentPageIndex + 1, 0, soundEffectPage);

        // 모달 닫기
        closeSoundEffectModal();

        // 목록 다시 렌더링
        renderPagesList();

        // 새로 생성된 사운드 이팩트 카드로 이동
        loadPage(currentPageIndex + 1);

        alert(`사운드 이팩트 "${effectName}"이(가) 생성되어 대사 ${currentPageIndex + 1} 뒤에 추가되었습니다!`);

    } catch (err) {
        console.error(err);
        alert('사운드 이팩트 생성에 실패했습니다: ' + err.message);
    } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = '생성하기';
    }
}

// 사운드 이팩트 탭 전환
function showEffectTab(tab) {
    const newTab = document.getElementById('effectNewTab');
    const libraryTab = document.getElementById('effectLibraryTab');
    const uploadTab = document.getElementById('uploadLibraryTab');

    const newContent = document.getElementById('effectNewContent');
    const libraryContent = document.getElementById('effectLibraryContent');
    const uploadContent = document.getElementById('uploadLibraryContent');

    const textSecondary = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim();
    const secondaryColor = getComputedStyle(document.documentElement).getPropertyValue('--secondary').trim();

    // 모든 콘텐츠 숨기기
    newContent.style.display = 'none';
    libraryContent.style.display = 'none';
    uploadContent.style.display = 'none';

    // 모든 탭 색 초기화
    newTab.style.color = textSecondary;
    newTab.style.borderBottom = '2px solid transparent';
    libraryTab.style.color = textSecondary;
    libraryTab.style.borderBottom = '2px solid transparent';
    uploadTab.style.color = textSecondary;
    uploadTab.style.borderBottom = '2px solid transparent';

    // 선택된 탭 활성화
    if (tab === 'new') {
        newTab.style.color = secondaryColor;
        newTab.style.borderBottom = `2px solid ${secondaryColor}`;
        newContent.style.display = 'block';

    } else if (tab === 'library') {
        libraryTab.style.color = secondaryColor;
        libraryTab.style.borderBottom = `2px solid ${secondaryColor}`;
        libraryContent.style.display = 'block';
        loadEffectLibrary();

    } else if (tab === 'upload') {
        uploadTab.style.color = secondaryColor;
        uploadTab.style.borderBottom = `2px solid ${secondaryColor}`;
        uploadContent.style.display = 'block';
        loadUploadEffectList();
    }
}

// 사운드 이팩트 라이브러리 로드
async function loadEffectLibrary() {
    try {
        const response = await fetch('/book/sound-effect/library/');
        const data = await response.json();

        const bgTertiary = getComputedStyle(document.documentElement).getPropertyValue('--bg-tertiary');
        const textPrimary = getComputedStyle(document.documentElement).getPropertyValue('--text-primary');
        const textSecondary = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary');
        const textTertiary = getComputedStyle(document.documentElement).getPropertyValue('--text-tertiary');
        const dangerColor = getComputedStyle(document.documentElement).getPropertyValue('--danger');

        const listEl = document.getElementById('effectLibraryList');
        if (data.success && data.effects.length > 0) {
            listEl.innerHTML = data.effects.map(effect => `
                <div style="background: ${bgTertiary}; padding: 15px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex: 1;">
                        <div style="color: ${textPrimary}; font-weight: 600; margin-bottom: 5px;">${effect.effect_name}</div>
                        <div style="color: ${textSecondary}; font-size: 13px; margin-bottom: 8px;">${effect.effect_description || '설명 없음'}</div>
                        <div style="font-size: 12px; color: ${textTertiary};">${effect.created_at}</div>
                    </div>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        ${effect.audio_url ? `<audio controls style="width: 200px; height: 32px;"><source src="${effect.audio_url}" type="audio/mp3"></audio>` : `<span style="color: ${dangerColor}; font-size: 12px;">오디오 없음</span>`}
                        <button onclick="useEffectFromLibrary('${effect.effect_name}', '${effect.audio_url}')" class="btn btn-primary" style="padding: 8px 16px;" ${!effect.audio_url ? 'disabled' : ''}>사용하기</button>
                    </div>
                </div>
            `).join('');
        } else {
            listEl.innerHTML = `<div style="text-align: center; color: ${textSecondary}; padding: 40px;">저장된 사운드 이팩트가 없습니다.</div>`;
        }
    } catch (err) {
        console.error(err);
        alert('라이브러리를 불러오는데 실패했습니다.');
    }
}

// 파일 업로드
function loadUploadEffectList() {
    const container = document.getElementById("uploadEffectContainer");

    const bgTertiary = getComputedStyle(document.documentElement).getPropertyValue('--bg-tertiary');
    const borderColor = getComputedStyle(document.documentElement).getPropertyValue('--border-color');
    const textPrimary = getComputedStyle(document.documentElement).getPropertyValue('--text-primary');

    container.innerHTML = `
        <div style="
            background: ${bgTertiary};
            padding: 20px;
            border-radius: 10px;
            border: 1px solid ${borderColor};
        ">
            <h3 style="color: ${textPrimary}; margin-bottom: 15px;">
                오디오 파일 업로드
            </h3>

            <input
                type="file"
                id="localAudioFile"
                accept="audio/*"
                style="width: 100%; margin-bottom: 15px;"
            />

            <button
                onclick="uploadLocalAudioFile()"
                class="btn btn-primary"
                style="width: 100%; padding: 10px 16px;"
            >
                업로드
                
            </button>
        </div>
    `;
}

function uploadLocalAudioFile() {
    const fileInput = document.getElementById("localAudioFile");
    const file = fileInput.files[0];

    if (!file) {
        alert("업로드할 오디오 파일을 선택해주세요.");
        return;
    }

    const objectUrl = URL.createObjectURL(file);

    // 사운드 이팩트 카드 생성
    const soundEffectPage = createPage('', file, true);
    soundEffectPage.effectName = file.name;
    soundEffectPage.audioUrl = objectUrl;

    // 현재 선택된 대사 뒤에 삽입
    saveCurrentPage();
    pages.splice(currentPageIndex + 1, 0, soundEffectPage);

    // 모달 닫기
    closeSoundEffectModal();

    // 목록 다시 렌더링
    renderPagesList();
    loadPage(currentPageIndex + 1);

    alert(`오디오 파일 "${file.name}"이(가) 추가되었습니다!`);
}

// 라이브러리에서 사운드 이팩트 사용
async function useEffectFromLibrary(effectName, audioUrl) {
    // audioUrl 유효성 검사
    if (!audioUrl || audioUrl === 'undefined' || audioUrl === 'null') {
        alert('유효하지 않은 오디오 파일입니다.');
        console.error('❌ 유효하지 않은 audioUrl:', audioUrl);
        return;
    }

    try {
        const response = await fetch(audioUrl);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const blob = await response.blob();
        const audioFile = new File([blob], `${effectName}.mp3`, { type: 'audio/mp3' });
        const objectUrl = URL.createObjectURL(blob);

        // 사운드 이팩트 카드 생성
        const soundEffectPage = createPage('', audioFile, true);
        soundEffectPage.effectName = effectName;
        soundEffectPage.audioUrl = objectUrl;

        // 현재 선택된 대사 뒤에 삽입
        saveCurrentPage();
        pages.splice(currentPageIndex + 1, 0, soundEffectPage);

        // 모달 닫기
        closeSoundEffectModal();

        // 목록 다시 렌더링
        renderPagesList();
        loadPage(currentPageIndex + 1);

        alert(`사운드 이팩트 "${effectName}"이(가) 대사 ${currentPageIndex + 1} 뒤에 추가되었습니다!`);
    } catch (err) {
        console.error('❌ 사운드 이팩트 사용 오류:', err);
        alert(`사운드 이팩트 사용에 실패했습니다.\n오류: ${err.message}`);
    }
}
