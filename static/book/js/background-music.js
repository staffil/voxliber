/**
 * background-music.js
 * 배경음 관련 기능
 */

// 배경음 트랙을 위한 볼륨 드래그 플래그
let isDraggingVolume = false;

// 배경음 모달 열기
function openBackgroundMusicModal() {
    const modal = document.getElementById('backgroundMusicModal');
    modal.style.display = 'flex';
    document.getElementById('musicName').value = '';
    document.getElementById('musicDescription').value = '';
    document.getElementById('musicDuration').value = '30';
    showMusicTab('new');
}

// 배경음 모달 닫기
function closeBackgroundMusicModal() {
    const modal = document.getElementById('backgroundMusicModal');
    modal.style.display = 'none';
}

// 배경음 탭 전환
function showMusicTab(tab) {
    const newTab = document.getElementById('musicNewTab');
    const libraryTab = document.getElementById('musicLibraryTab');
    const uploadTab = document.getElementById('musicUploadTab');

    const newContent = document.getElementById('musicNewContent');
    const libraryContent = document.getElementById('musicLibraryContent');
    const uploadContent = document.getElementById('musicUploadContent');

    const textSecondary = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim();
    const accentColor = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();

    // 기본 숨김
    newContent.style.display = 'none';
    libraryContent.style.display = 'none';
    uploadContent.style.display = 'none';

    // 탭 기본 색상 초기화
    newTab.style.color = textSecondary;
    newTab.style.borderBottom = '2px solid transparent';
    libraryTab.style.color = textSecondary;
    libraryTab.style.borderBottom = '2px solid transparent';
    uploadTab.style.color = textSecondary;
    uploadTab.style.borderBottom = '2px solid transparent';

    if (tab === 'new') {
        newTab.style.color = accentColor;
        newTab.style.borderBottom = `2px solid ${accentColor}`;
        newContent.style.display = 'block';
    }
    else if (tab === 'library') {
        libraryTab.style.color = accentColor;
        libraryTab.style.borderBottom = `2px solid ${accentColor}`;
        libraryContent.style.display = 'block';
        loadMusicLibrary();
    }
    else if (tab === 'upload') {
        uploadTab.style.color = accentColor;
        uploadTab.style.borderBottom = `2px solid ${accentColor}`;
        uploadContent.style.display = 'block';
        loadUploadMusicList();
    }
}

// 라이브러리에서 배경음 사용
async function useMusicFromLibrary(musicName, audioUrl) {
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
        const audioFile = new File([blob], `${musicName}.mp3`, { type: 'audio/mp3' });
        const objectUrl = URL.createObjectURL(blob);

        // 배경음 트랙에 추가 (현재 대사에만 적용)
        const newTrack = {
            id: Date.now(),
            startPage: currentPageIndex,
            endPage: currentPageIndex,
            audioFile: audioFile,
            audioUrl: objectUrl,
            musicName: musicName,
            volume: 1  // 기본 볼륨 100%
        };
        backgroundTracks.push(newTrack);

        // 모달 닫기
        closeBackgroundMusicModal();

        // 배경음 트랙 렌더링
        renderBackgroundTracks();

        alert(`배경음 "${musicName}"이(가) 대사 ${currentPageIndex + 1}에 추가되었습니다!\n범위를 조정하려면 배경음 카드를 클릭하세요.`);
    } catch (err) {
        console.error('❌ 배경음 사용 오류:', err);
        alert(`배경음 사용에 실패했습니다.\n오류: ${err.message}`);
    }
}

// 배경음 라이브러리 로드
async function loadMusicLibrary() {
    try {
        const response = await fetch('/book/background-music/library/');
        const data = await response.json();

        const bgTertiary = getComputedStyle(document.documentElement).getPropertyValue('--bg-tertiary');
        const textPrimary = getComputedStyle(document.documentElement).getPropertyValue('--text-primary');
        const textSecondary = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary');
        const textTertiary = getComputedStyle(document.documentElement).getPropertyValue('--text-tertiary');
        const dangerColor = getComputedStyle(document.documentElement).getPropertyValue('--danger');

        const listEl = document.getElementById('musicLibraryList');
        if (data.success && data.music.length > 0) {
            listEl.innerHTML = data.music.map(music => `
                <div style="background: ${bgTertiary}; padding: 15px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex: 1;">
                        <div style="color: ${textPrimary}; font-weight: 600; margin-bottom: 5px;">${music.music_name}</div>
                        <div style="color: ${textSecondary}; font-size: 13px; margin-bottom: 8px;">${music.music_description || '설명 없음'}</div>
                        <div style="font-size: 12px; color: ${textTertiary};">${music.created_at}</div>
                    </div>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        ${music.audio_url ? `<audio controls style="width: 200px; height: 32px;"><source src="${music.audio_url}" type="audio/mp3"></audio>` : `<span style="color: ${dangerColor}; font-size: 12px;">오디오 없음</span>`}
                        <button onclick="useMusicFromLibrary('${music.music_name}', '${music.audio_url}')" class="btn btn-primary" style="padding: 8px 16px;" ${!music.audio_url ? 'disabled' : ''}>사용하기</button>
                    </div>
                </div>
            `).join('');
        } else {
            listEl.innerHTML = `<div style="text-align: center; color: ${textSecondary}; padding: 40px;">저장된 배경음이 없습니다.</div>`;
        }
    } catch (err) {
        console.error(err);
        alert('라이브러리를 불러오는데 실패했습니다.');
    }
}

// 배경음 업로드 목록 로드
function loadUploadMusicList() {
    const container = document.getElementById("uploadMusicContainer");

    container.innerHTML = `
        <div style="
            background: #16213e;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #1f2a44;
        ">
            <h3 style="color: #fff; margin-bottom: 15px;">
                배경음 오디오 업로드
            </h3>

            <input
                type="file"
                id="localMusicFile"
                accept="audio/*"
                style="width: 100%; margin-bottom: 15px;"
            />

            <button
                onclick="uploadLocalMusicFile()"
                class="btn btn-primary"
                style="width: 100%; padding: 10px 16px;"
            >
                업로드
            </button>
        </div>
    `;
}

// 로컬 배경음 파일 업로드
function uploadLocalMusicFile() {
    const fileInput = document.getElementById("localMusicFile");
    const file = fileInput.files[0];

    if (!file) {
        alert("업로드할 오디오 파일을 선택해주세요.");
        return;
    }

    const objectUrl = URL.createObjectURL(file);

    // 배경음 트랙에 추가 (현재 대사에만 적용)
    const newTrack = {
        id: Date.now(),
        startPage: currentPageIndex,
        endPage: currentPageIndex,
        audioFile: file,
        audioUrl: objectUrl,
        musicName: file.name,
        volume: 1  // 기본 볼륨 100%
    };
    backgroundTracks.push(newTrack);

    // 모달 닫기
    closeBackgroundMusicModal();

    // 배경음 트랙 렌더링
    renderBackgroundTracks();

    alert(`배경음 "${file.name}"이(가) 대사 ${currentPageIndex + 1}에 추가되었습니다!\n범위를 조정하려면 배경음 카드를 클릭하세요.`);
}

// 배경음 생성
async function generateBackgroundMusic() {
    const musicName = document.getElementById('musicName').value.trim();
    const musicDescription = document.getElementById('musicDescription').value.trim();
    const duration = parseInt(document.getElementById('musicDuration').value);

    if (!musicName || !musicDescription) {
        alert('배경음 이름과 설명을 모두 입력해주세요.');
        return;
    }

    const generateBtn = event.target;
    generateBtn.disabled = true;
    generateBtn.textContent = '🔄 생성 중...';

    try {
        const response = await fetch('/book/background-music/generate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                music_name: musicName,
                music_description: musicDescription,
                duration_seconds: duration
            })
        });

        if (!response.ok) {
            throw new Error('배경음 생성 실패');
        }

        const blob = await response.blob();
        const audioUrl = URL.createObjectURL(blob);
        const audioFile = new File([blob], `music_${Date.now()}.mp3`, { type: 'audio/mp3' });

        // 배경음 트랙에 추가 (현재 대사에만 적용)
        const newTrack = {
            id: Date.now(),
            startPage: currentPageIndex,
            endPage: currentPageIndex,
            audioFile: audioFile,
            audioUrl: audioUrl,
            musicName: musicName,
            volume: 1  // 기본 볼륨 100%
        };
        backgroundTracks.push(newTrack);

        // 모달 닫기
        closeBackgroundMusicModal();

        // 배경음 트랙 렌더링
        renderBackgroundTracks();

        alert(`배경음 "${musicName}"이(가) 대사 ${currentPageIndex + 1}에 추가되었습니다!\n범위를 조정하려면 배경음 카드를 클릭하세요.`);

    } catch (err) {
        console.error(err);
        alert('배경음 생성에 실패했습니다: ' + err.message);
    } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = '생성하기';
    }
}

// 배경음 트랙 렌더링
function renderBackgroundTracks() {
    const tracksList = document.getElementById('backgroundTracksList');

    if (backgroundTracks.length === 0) {
        tracksList.innerHTML = '<div style="color: #666; font-size: 11px; text-align: center; padding: 10px;">배경음이 없습니다</div>';
        return;
    }

tracksList.innerHTML = backgroundTracks.map((track, index) => `
    <div style="
        background: #2d1b4e;
        padding: 6px;
        border-radius: 5px;
        height: 70px;
        margin-bottom: 5px;
        border-left: 3px solid #ec4899;
        cursor: pointer;
        display: flex;
        flex-direction: column;
        justify-content: center;
    "
    onclick="if(isDraggingVolume) return; editBackgroundTrack(${index})">

        <!-- 제목 -->
        <div style="color: #ec4899; font-size: 10px; font-weight: 600; margin-bottom: 1px;">
            ${track.musicName}
        </div>

        <!-- 페이지 -->
        <div style="color: #aaa; font-size: 9px; margin-bottom: 3px;">
            대사 ${track.startPage + 1}${track.startPage !== track.endPage ? ` ~ ${track.endPage + 1}` : ''}
        </div>

        <!-- 버튼 + 볼륨 -->
        <div style="display: flex; align-items: center; gap: 4px;">
            <!-- 재생 버튼 -->
            <button 
                onclick="event.stopPropagation(); playBackgroundTrack(${index})"
                style="
                    padding: 2px 6px; 
                    background: linear-gradient(135deg, #ec4899, #db2777);
                    border: none; 
                    border-radius: 4px; 
                    color: #fff; 
                    font-size: 9px; 
                    cursor: pointer;
                    font-weight: 600;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.25);
                    transition: 0.15s;
                "
                onmouseover="this.style.transform='scale(1.05)'"
                onmouseout="this.style.transform='scale(1)'"
            >
                ▶
            </button>

            <!-- 삭제 버튼 -->
            <button 
                onclick="event.stopPropagation(); deleteBackgroundTrack(${index})"
                style="
                    padding: 2px 6px; 
                    background: linear-gradient(135deg, #dc2626, #b91c1c);
                    border: none; 
                    border-radius: 4px; 
                    color: #fff; 
                    font-size: 9px; 
                    cursor: pointer;
                    font-weight: 600;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.25);
                    transition: 0.15s;
                "
                onmouseover="this.style.transform='scale(1.05)'"
                onmouseout="this.style.transform='scale(1)'"
            >
                🗑
            </button>

            <!-- 볼륨 -->
            <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value="${track.volume ?? 1}"
                style="flex: 1; height: 3px; cursor: pointer; accent-color: #ec4899;"
                onmousedown="isDraggingVolume=true"
                onmouseup="isDraggingVolume=false"
                onclick="event.stopPropagation()"
                oninput="event.stopPropagation(); updateTrackVolume(${index}, this.value);"
            >
        </div>

    </div>
`).join('');
}

// 볼륨 업데이트
function updateTrackVolume(index, value) {
    const track = backgroundTracks[index];
    if (!track) return;

    track.volume = parseFloat(value);

    // 현재 재생 중인 오디오가 해당 트랙이면 볼륨 반영
    if (window.currentBackgroundAudio && window.currentBackgroundAudio.src === track.audioUrl) {
        window.currentBackgroundAudio.volume = track.volume;
    }

    // 슬라이더 옆 표시 업데이트
    renderBackgroundTracks();
}

// 배경음 재생 (토글)
function playBackgroundTrack(index) {
    const track = backgroundTracks[index];
    if (!track || !track.audioUrl) return alert('배경음 파일이 올바르지 않습니다.');

    // 🔄 같은 배경음을 다시 클릭 → 정지
    if (window.currentBackgroundAudio && window.currentPlayingTrackIndex === index) {
        window.currentBackgroundAudio.pause();
        window.currentBackgroundAudio.currentTime = 0;
        window.currentBackgroundAudio = null;
        window.currentPlayingTrackIndex = null;
        return;
    }

    // 🔇 다른 배경음이 재생 중이면 정지
    if (window.currentBackgroundAudio) {
        window.currentBackgroundAudio.pause();
        window.currentBackgroundAudio.currentTime = 0;
        window.currentBackgroundAudio = null;
        window.currentPlayingTrackIndex = null;
    }

    // ▶ 새로운 배경음 재생
    const audio = new Audio(track.audioUrl);
    audio.volume = track.volume ?? 1;

    window.currentBackgroundAudio = audio;
    window.currentPlayingTrackIndex = index;

    audio.play().catch(err => {
        console.error('오디오 재생 오류:', err);
        alert('오디오 재생에 실패했습니다.');
    });

    // 자동으로 끝나면 초기화
    audio.onended = () => {
        window.currentBackgroundAudio = null;
        window.currentPlayingTrackIndex = null;
    };
}


// 배경음 트랙 편집 (범위 조정)
function editBackgroundTrack(index) {
    const track = backgroundTracks[index];

    // 모달 생성
    const modalHtml = `
        <div id="editTrackModal" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 10000;">
            <div style="background: #0f1419; border: 1px solid #2d3748; border-radius: 12px; width: 90%; max-width: 500px; padding: 25px; box-shadow: 0 20px 50px rgba(0,0,0,0.5);">
                <h3 style="color: #ec4899; margin: 0 0 20px 0; font-size: 18px;">🎼 배경음 범위 설정</h3>

                <div style="margin-bottom: 15px;">
                    <label style="color: #888; font-size: 13px; display: block; margin-bottom: 5px;">배경음 이름</label>
                    <div style="color: #fff; font-size: 14px; font-weight: 600;">${track.musicName}</div>
                </div>

                <div style="margin-bottom: 15px;">
                    <label style="color: #888; font-size: 13px; display: block; margin-bottom: 5px;">시작 대사</label>
                    <select id="startPageSelect" style="width: 100%; padding: 10px; background: #16213e; border: 1px solid #2d3748; border-radius: 6px; color: #fff; font-size: 14px;">
                        ${pages.map((p, i) => !p.isSoundEffect ? `<option value="${i}" ${i === track.startPage ? 'selected' : ''}>대사 ${i + 1}</option>` : '').join('')}
                    </select>
                </div>

                <div style="margin-bottom: 20px;">
                    <label style="color: #888; font-size: 13px; display: block; margin-bottom: 5px;">종료 대사</label>
                    <select id="endPageSelect" style="width: 100%; padding: 10px; background: #16213e; border: 1px solid #2d3748; border-radius: 6px; color: #fff; font-size: 14px;">
                        ${pages.map((p, i) => !p.isSoundEffect ? `<option value="${i}" ${i === track.endPage ? 'selected' : ''}>대사 ${i + 1}</option>` : '').join('')}
                    </select>
                </div>

                <div style="display: flex; gap: 10px; justify-content: flex-end;">
                    <button onclick="closeEditTrackModal()" style="padding: 10px 20px; background: #2d3748; border: none; border-radius: 6px; color: #fff; cursor: pointer; font-size: 14px;">취소</button>
                    <button onclick="saveTrackRange(${index})" style="padding: 10px 20px; background: #ec4899; border: none; border-radius: 6px; color: #fff; cursor: pointer; font-size: 14px; font-weight: 600;">저장</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

// 배경음 범위 저장
function saveTrackRange(index) {
    const startPage = parseInt(document.getElementById('startPageSelect').value);
    const endPage = parseInt(document.getElementById('endPageSelect').value);

    if (startPage > endPage) {
        alert('시작 대사는 종료 대사보다 앞서야 합니다.');
        return;
    }

    backgroundTracks[index].startPage = startPage;
    backgroundTracks[index].endPage = endPage;

    closeEditTrackModal();
    renderBackgroundTracks();

    alert(`배경음 범위가 업데이트되었습니다!\n대사 ${startPage + 1} ~ ${endPage + 1}`);
}

// 배경음 편집 모달 닫기
function closeEditTrackModal() {
    const modal = document.getElementById('editTrackModal');
    if (modal) {
        modal.remove();
    }
}

// 배경음 삭제
function deleteBackgroundTrack(index) {
    const track = backgroundTracks[index];

    if (confirm(`"${track.musicName}" 배경음을 삭제하시겠습니까?`)) {
        // 배경음 삭제
        backgroundTracks.splice(index, 1);

        // UI 업데이트
        renderBackgroundTracks();

        console.log(`🗑️ 배경음 삭제됨: ${track.musicName}`);
    }
}
