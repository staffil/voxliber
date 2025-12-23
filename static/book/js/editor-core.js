/**
 * editor-core.js
 * 에피소드 에디터 핵심 기능
 */

function toggleVoicePlay(event, audioUrl) {
    event.stopPropagation(); // voice-item 클릭 이벤트 방지

    const btn = event.currentTarget;
    const playIcon = btn.querySelector('.play-icon');
    const pauseIcon = btn.querySelector('.pause-icon');

    // 다른 버튼이 재생 중이면 멈춤
    if (currentPlayingBtn && currentPlayingBtn !== btn) {
        const otherPlayIcon = currentPlayingBtn.querySelector('.play-icon');
        const otherPauseIcon = currentPlayingBtn.querySelector('.pause-icon');
        otherPlayIcon.style.display = 'block';
        otherPauseIcon.style.display = 'none';
        currentPlayingBtn.classList.remove('playing');
    }

    // 현재 버튼 토글
    if (samplePlayer.paused || samplePlayer.src !== window.location.origin + audioUrl) {
        samplePlayer.src = audioUrl;
        samplePlayer.play();
        playIcon.style.display = 'none';
        pauseIcon.style.display = 'block';
        btn.classList.add('playing');
        currentPlayingBtn = btn;
    } else {
        samplePlayer.pause();
        playIcon.style.display = 'block';
        pauseIcon.style.display = 'none';
        btn.classList.remove('playing');
        currentPlayingBtn = null;
    }
}

// 오디오 종료 시 아이콘 원래대로
if (samplePlayer) {
    samplePlayer.addEventListener('ended', function() {
        if (currentPlayingBtn) {
            const playIcon = currentPlayingBtn.querySelector('.play-icon');
            const pauseIcon = currentPlayingBtn.querySelector('.pause-icon');
            playIcon.style.display = 'block';
            pauseIcon.style.display = 'none';
            currentPlayingBtn.classList.remove('playing');
            currentPlayingBtn = null;
        }
    });
}

// 나레이션 선택
function selectVoice(element) {
    // 모든 voice-item에서 active 제거
    document.querySelectorAll('.voice-item').forEach(item => {
        item.classList.remove('active');
    });

    // 선택된 항목에 active 추가
    element.classList.add('active');
    selectedVoiceId = element.getAttribute('data-voice-id');

    console.log('선택된 목소리 ID:', selectedVoiceId);
}

// 언어 업데이트
function updateLanguage(value) {
    selectedLanguage = value;
    console.log('선택된 언어:', selectedLanguage);
}


// 속도 업데이트
    function updateSpeed(value) {
        // value 0~100 → 0.7 ~ 1.2 매핑
        const speed = (0.7 + (2.0 - 0.7) * (value / 100)).toFixed(2);
        document.getElementById("speedValue").innerText = speed;
    }

    // 초기 표시값 설정
    updateSpeed(50);

// 대사 데이터 구조
function createPage(content = '', audioFile = null, isSoundEffect = false) {
    return {
        id: Date.now() + Math.random(),
        content: content,
        charCount: content.length,
        audioFile: audioFile,
        audioUrl: null,
        isSoundEffect: isSoundEffect,  // 사운드 이팩트 여부
        effectName: '',  // 사운드 이팩트 이름
        novelDraft: ''  // 소설 미리쓰기 내용
    };
}

// 모달 외부 클릭 시 닫기
document.addEventListener('click', function(event) {
    const soundModal = document.getElementById('soundEffectModal');
    const musicModal = document.getElementById('backgroundMusicModal');
    if (event.target === soundModal) {
        closeSoundEffectModal();
    }
    if (event.target === musicModal) {
        closeBackgroundMusicModal();
    }
});



// IndexedDB 초기화
let db = null;


// 초기 대사 4개 생성
async function initPages() {
    // IndexedDB 초기화
    try {
        await initIndexedDB();
    } catch (error) {
        console.error('IndexedDB 초기화 실패:', error);
    }

    if (pages.length === 0) {
        for (let i = 0; i < 4; i++) {
            pages.push(createPage());
        }
    }
    renderPagesList();
    loadPage(0);

    // 임시저장 존재 여부 체크
    await checkDraftExists();
}



// 대사 목록 렌더링
function renderPagesList() {
    const pagesList = document.getElementById('pagesList');
    pagesList.innerHTML = '';

    pages.forEach((page, index) => {
        const pageItem = document.createElement('div');
        pageItem.className = `page-item ${index === currentPageIndex ? 'active' : ''}`;
        pageItem.setAttribute('draggable', 'true');
        pageItem.setAttribute('data-index', index);
        pageItem.onclick = () => loadPage(index);

        // 드래그 이벤트 리스너
        pageItem.addEventListener('dragstart', handleDragStart);
        pageItem.addEventListener('dragover', handleDragOver);
        pageItem.addEventListener('drop', handleDrop);
        pageItem.addEventListener('dragend', handleDragEnd);
        pageItem.addEventListener('dragenter', handleDragEnter);
        pageItem.addEventListener('dragleave', handleDragLeave);

        // 사운드 이팩트 카드인 경우
        if (page.isSoundEffect) {
            pageItem.style.background = '#2d1b4e'; // 보라색 배경
            pageItem.style.borderLeft = '4px solid #8b5cf6';

            pageItem.innerHTML =
                '<div class="page-item-header">' +
                    '<span class="page-number" style="color: #c4b5fd;">🎵 사운드 이팩트</span>' +
                '</div>' +
                '<div class="page-preview" style="color: #c4b5fd; font-weight: 600;">' + page.effectName + '</div>' +
                '<div style="font-size: 11px; color: #a78bfa; margin-top: 4px;">오디오 준비됨</div>';
        } else {
            // 일반 대사 카드
            const preview = page.content.substring(0, 30) || '내용을 작성하세요';
            const previewClass = page.content ? '' : 'empty';
            const hasAudio = page.audioFile || page.audioUrl;

            pageItem.innerHTML =
                '<div class="page-item-header">' +
                    '<span class="page-number">대사 ' + (index + 1) + '</span>' +
                    '<span class="char-count-small">' + page.charCount + '자</span>' +
                '</div>' +
                '<div class="page-preview ' + previewClass + '">' + preview + '</div>' +
                (hasAudio ? '<div style="font-size: 11px; color: #6366f1; margin-top: 4px;">🎵 오디오 있음</div>' : '');
        }

        pagesList.appendChild(pageItem);
    });
}

// 드래그 시작
function handleDragStart(e) {
    draggedIndex = parseInt(e.currentTarget.getAttribute('data-index'));
    e.currentTarget.style.opacity = '0.5';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', e.currentTarget.innerHTML);
}

// 드래그 오버
function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

// 드래그 진입
function handleDragEnter(e) {
    const targetIndex = parseInt(e.currentTarget.getAttribute('data-index'));
    if (draggedIndex !== targetIndex) {
        e.currentTarget.style.borderTop = '3px solid #6366f1';
    }
}

// 드래그 이탈
function handleDragLeave(e) {
    e.currentTarget.style.borderTop = '';
}

// 드롭
function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }
    e.preventDefault();

    const targetIndex = parseInt(e.currentTarget.getAttribute('data-index'));

    if (draggedIndex !== null && draggedIndex !== targetIndex) {
        // 배열에서 항목 이동
        const draggedItem = pages[draggedIndex];
        pages.splice(draggedIndex, 1);
        pages.splice(targetIndex, 0, draggedItem);

        // currentPageIndex 업데이트
        if (currentPageIndex === draggedIndex) {
            currentPageIndex = targetIndex;
        } else if (draggedIndex < currentPageIndex && targetIndex >= currentPageIndex) {
            currentPageIndex--;
        } else if (draggedIndex > currentPageIndex && targetIndex <= currentPageIndex) {
            currentPageIndex++;
        }

        // UI 업데이트
        renderPagesList();
        loadPage(currentPageIndex, true); // skipSave = true
    }

    e.currentTarget.style.borderTop = '';
    return false;
}

// 드래그 종료
function handleDragEnd(e) {
    e.currentTarget.style.opacity = '1';
    e.currentTarget.style.borderTop = '';

    // 모든 카드의 스타일 초기화
    document.querySelectorAll('.page-item').forEach(item => {
        item.style.borderTop = '';
    });
}

// 페이지 로드
function loadPage(index, skipSave = false) {
    // 현재 페이지 저장 (skipSave가 true이면 건너뜀)
    if (!skipSave) {
        saveCurrentPage();
    }

    currentPageIndex = index;
    const page = pages[index];

    const editorArea = document.getElementById('editorArea');
    const writeArea = document.getElementById('writeArea');

    writeArea.innerHTML = `
        <div class="write-panel-header">
            📘 소설 미리 작성
            <span id="novelDraftStatus" style="font-size: 11px; color: #888; margin-left: 10px;"></span>
        </div>
        <textarea id="novelDraft" placeholder="여기에 소설 내용을 미리 작성하세요..."></textarea>
    `;

    // 소설 미리쓰기 불러오기 및 자동저장 설정
    setTimeout(() => {
        const novelTextarea = document.getElementById('novelDraft');
        const novelDraftStatus = document.getElementById('novelDraftStatus');

        if (novelTextarea) {
            // 저장된 소설 미리쓰기 불러오기
            const savedNovelDraft = page.novelDraft || localStorage.getItem(`novelDraft_${bookId}_${index}`) || '';
            novelTextarea.value = savedNovelDraft;

            console.log(`📖 소설 미리쓰기 불러오기 (페이지 ${index + 1}):`, {
                'page.novelDraft 있음': !!page.novelDraft,
                'localStorage 있음': !!localStorage.getItem(`novelDraft_${bookId}_${index}`),
                '불러온 길이': savedNovelDraft.length,
                '미리보기': savedNovelDraft.substring(0, 50)
            });

            if (savedNovelDraft) {
                novelDraftStatus.textContent = '✓ 저장된 내용 불러옴';
                novelDraftStatus.style.color = '#10b981';
                setTimeout(() => {
                    novelDraftStatus.textContent = '';
                }, 3000);
            }

            // 자동 저장 (디바운싱)
            let novelDraftTimeout;
            novelTextarea.addEventListener('input', function() {
                clearTimeout(novelDraftTimeout);
                novelDraftStatus.textContent = '입력 중...';
                novelDraftStatus.style.color = '#fbbf24';

                novelDraftTimeout = setTimeout(() => {
                    const draftContent = novelTextarea.value;

                    // pages 배열에 저장
                    if (pages[currentPageIndex]) {
                        pages[currentPageIndex].novelDraft = draftContent;
                    }

                    // localStorage에도 백업 저장
                    localStorage.setItem(`novelDraft_${bookId}_${index}`, draftContent);

                    novelDraftStatus.textContent = '✓ 자동 저장됨';
                    novelDraftStatus.style.color = '#10b981';

                    console.log(`💾 소설 미리쓰기 자동 저장됨 (페이지 ${index + 1}), 길이: ${draftContent.length}자`);

                    // 3초 후 상태 메시지 숨김
                    setTimeout(() => {
                        novelDraftStatus.textContent = '';
                    }, 3000);
                }, 1000); // 1초 대기 후 저장
            });
        } else {
            console.error('❌ novelDraft textarea를 찾을 수 없습니다');
        }
    }, 100);


    // 사운드 이팩트 카드인 경우 - 특별한 UI 표시
    if (page.isSoundEffect) {
        document.getElementById('currentPageTitle').textContent = '🎵 사운드 이팩트 / ' + pages.length;

        editorArea.innerHTML =
            '<div class="editor-toolbar" style="background: #2d1b4e; border-bottom: 1px solid #8b5cf6;">' +
                '<span style="color: #c4b5fd; font-size: 14px;">🎵 사운드 이팩트</span>' +
            '</div>' +
            '<div class="page-editor" style="background: #1a1a2e; text-align: center; padding: 60px 30px;">' +
                '<div style="margin-bottom: 30px;">' +
                    '<div style="width: 80px; height: 80px; margin: 0 auto 20px; background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 40px;">🎵</div>' +
                    '<h3 style="color: #fff; font-size: 24px; margin-bottom: 10px;">' + page.effectName + '</h3>' +
                    '<p style="color: #888; font-size: 14px;">사운드 이팩트 카드</p>' +
                '</div>' +
                '<div style="max-width: 500px; margin: 0 auto; background: #16213e; padding: 20px; border-radius: 12px;">' +
                    '<audio controls style="width: 100%; margin-bottom: 15px;" id="pageAudioPlayer">' +
                        '<source src="' + page.audioUrl + '" type="audio/mp3">' +
                    '</audio>' +
                    '<div style="font-size: 13px; color: #6366f1;">✓ 사운드 이팩트가 준비되었습니다</div>' +
                '</div>' +
            '</div>' +
            '<div class="editor-footer">' +
                '<div class="footer-info" style="color: #888;">' +
                    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
                        '<circle cx="12" cy="12" r="10"/>' +
                        '<path d="M12 6v6l4 2"/>' +
                    '</svg>' +
                    ' 사운드 이팩트는 자동으로 저장됩니다' +
                '</div>' +
                '<div class="pagination-controls">' +
                    '<button class="btn btn-secondary" onclick="prevPage()" ' + (index === 0 ? 'disabled' : '') + '>← 이전</button>' +
                    '<button class="btn btn-secondary" onclick="nextPage()" ' + (index === pages.length - 1 ? 'disabled' : '') + '>다음 →</button>' +
                '</div>' +
            '</div>';
    } else {
        // 일반 대사 카드 UI
        document.getElementById('currentPageTitle').textContent = '대사 ' + (index + 1) + ' / ' + pages.length;

        const hasAudio = page.audioFile || page.audioUrl;

        let audioSection = '';
        if (hasAudio) {
            audioSection = '<div style="background: #1a1a2e; padding: 15px; border-radius: 8px; margin-bottom: 10px;">' +
                '<audio controls style="width: 100%;" id="pageAudioPlayer">' +
                '<source src="' + page.audioUrl + '" type="audio/mp3">' +
                '</audio>' +
                '<div style="font-size: 13px; color: #888; margin-top: 8px;">✓ 오디오가 추가되었습니다</div>' +
                '</div>';
        } else {
            audioSection = '<div style="font-size: 14px; color: #888; margin-bottom: 12px;">이 페이지에 배경음악이나 나레이션을 추가하세요</div>';
        }

        let audioRemoveBtn = hasAudio ? '<button class="btn btn-danger" style="padding: 6px 12px; font-size: 13px;" onclick="removeAudio()">오디오 제거</button>' : '';

        editorArea.innerHTML =
            '<div class="editor-toolbar">' +
                '<span style="color: #888; font-size: 14px;">🎶 대사 ' + (index + 1) + '</span>' +
                '<span class="char-count-display">' +
                    '<span id="currentCharCount">' + page.charCount + '</span> / 200자' +
                    '<span id="charWarning" style="display: none;" class="char-limit-warning">(권장 글자 수 초과)</span>' +
                '</span>' +
            '</div>' +
            '<div class="page-editor">' +
                '<textarea id="pageContent" placeholder="이 페이지의 내용을 작성하세요...&#10;&#10;팁:&#10;- 한 페이지에 한 장면이나 한 단락을 작성하세요&#10;- 200자 이내로 작성하면 읽기 편합니다&#10;- Enter로 문단을 나누세요" oninput="updateCharCount()"></textarea>' +
            '</div>' +
            '<div style="background: #16213e; padding: 20px; border-radius: 12px; margin-top: 20px;">' +
                '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">' +
                    '<h4 style="color: #fff; font-size: 16px; margin: 0;">🎵 페이지 오디오</h4>' +
                    audioRemoveBtn +
                '</div>' +
                '<div style="display: flex; gap: 10px; margin-bottom: 10px;">' +
                    '<input type="file" id="audioFileInput" accept="audio/*" style="display: none;" onchange="handleAudioUpload(event)">' +
                    '<button class="btn btn-secondary" style="flex: 1;" onclick="generatePageTTS(event)">'+
                        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'+
                            '<polygon points="5 3 19 12 5 21 5 3"/>'+
                        '</svg>'+
                        '전체 TTS 생성'+
                    '</button>' +
                '</div>' +
audioSection + getFilter()

                '<div style="font-size: 12px; color: #666; margin-top: 8px; text-align: center;">' +
                    '💡 텍스트를 드래그로 선택한 후 버튼을 클릭하세요' +
                '</div>' +
            '</div>' +
            '<div class="editor-footer">' +
                '<div class="footer-info">' +
                    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
                        '<circle cx="12" cy="12" r="10"/>' +
                        '<path d="M12 6v6l4 2"/>' +
                    '</svg>' +
                    ' 자동 저장됨' +
                '</div>' +
                '<div class="pagination-controls">' +
                    '<button class="btn btn-secondary" onclick="prevPage()" ' + (index === 0 ? 'disabled' : '') + '>← 이전</button>' +
                    '<button class="btn btn-secondary" onclick="nextPage()" ' + (index === pages.length - 1 ? 'disabled' : '') + '>다음 →</button>' +
                '</div>' +
            '</div>';

        // textarea의 value를 JavaScript로 직접 설정 (HTML 이스케이핑 문제 방지)
        setTimeout(() => {
            const textarea = document.getElementById('pageContent');
                initAudioFilters();
            if (textarea) {
                textarea.value = page.content;
                console.log('✅ loadPage() - textarea에 텍스트 설정:', page.content.length, '자');
            }
        }, 50);
    }

    renderPagesList();
}

// 현재 페이지 저장
function saveCurrentPage() {
    const textarea = document.getElementById('pageContent');
    if (textarea && pages[currentPageIndex]) {
        const content = textarea.value;
        pages[currentPageIndex].content = content;
        pages[currentPageIndex].charCount = content.length;
        console.log('💾 saveCurrentPage() 호출 - 페이지', currentPageIndex + 1, '저장됨, 텍스트 길이:', content.length, '자');
    } else {
        console.warn('⚠️ saveCurrentPage() - textarea 또는 페이지를 찾을 수 없음');
    }
}

// 글자 수 업데이트
function updateCharCount() {
    const textarea = document.getElementById('pageContent');
    const charCount = textarea.value.length;

    document.getElementById('currentCharCount').textContent = charCount;

    const warning = document.getElementById('charWarning');
    if (charCount > 200) {
        warning.style.display = 'inline';
    } else {
        warning.style.display = 'none';
    }

    // 실시간 저장
    pages[currentPageIndex].content = textarea.value;
    pages[currentPageIndex].charCount = charCount;

    // 사이드바 업데이트
    renderPagesList();
}



// ========= Web Audio 필터 UI (=버튼+필터 설정 모음) =========
function getFilter() {
    return `
        <div id="webaudioUI" style="margin-top:15px; padding:10px; background:#252836; border-radius:8px; color:#fff;">
            <h5 style="margin-bottom:8px;">🎧 목소리 효과</h5>
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:10px;">
                <button class="btn btn-secondary voice-btn" data-voice="normal">기본</button>
                <button class="btn btn-secondary voice-btn" data-voice="phone">전화</button>
                <button class="btn btn-secondary voice-btn" data-voice="cave">동굴</button>
                <button class="btn btn-secondary voice-btn" data-voice="underwater">물속</button>
                <button class="btn btn-secondary voice-btn" data-voice="robot">로봇</button>
                <button class="btn btn-secondary voice-btn" data-voice="ghost">유령</button>
                <button class="btn btn-secondary voice-btn" data-voice="old">노인</button>
                <button class="btn btn-secondary voice-btn" data-voice="echo">메아리</button>
                <button class="btn btn-secondary voice-btn" data-voice="whisper">속삭임</button>
                <button class="btn btn-secondary voice-btn" data-voice="radio">라디오</button>
                <button class="btn btn-secondary voice-btn" data-voice="megaphone">확성기</button>
                <button class="btn btn-secondary voice-btn" data-voice="protoss">신성한 목소리</button>
                <button class="btn btn-secondary voice-btn" data-voice="demon">악마</button>
                <button class="btn btn-secondary voice-btn" data-voice="angel">천사</button>
                <button class="btn btn-secondary voice-btn" data-voice="vader">다스베이더</button>
                <button class="btn btn-secondary voice-btn" data-voice="giant">거인</button>
                <button class="btn btn-secondary voice-btn" data-voice="tiny">꼬마요정</button>
                <button class="btn btn-secondary voice-btn" data-voice="possessed">빙의</button>
                <button class="btn btn-secondary voice-btn" data-voice="horror">호러</button>
                <button class="btn btn-secondary voice-btn" data-voice="helium">헬륨</button>
                <button class="btn btn-secondary voice-btn" data-voice="timewarp">시간왜곡</button>
                <button class="btn  btn-secondary voice-btn" data-voice="glitch">글리치 AI</button>
                <button class="btn  btn-secondary voice-btn" data-voice="choir">성가대</button>
                <button class="btn  btn-secondary    voice-btn" data-voice="hyperpop">Hyperpop</button>
                <button class="btn  btn-secondary voice-btn" data-voice="vaporwave">Vaporwave</button>
                <button class="btn  btn-secondary    voice-btn" data-voice="darksynth">Dark Synth</button>
                <button class="btn  btn-secondary  voice-btn" data-voice="lofi-girl">Lo-Fi Girl</button>
                <button class="btn  btn-secondary   voice-btn" data-voice="bitcrush-voice">Bitcrush</button>
                <button class="btn  btn-secondary  voice-btn" data-voice="portal">Portal</button>
                <button class="btn  btn-secondary   voice-btn" data-voice="neoncity">Neon City</button>
                <button class="btn  btn-secondary   voice-btn" data-voice="ghost-in-machine">Ghost AI</button>
            </div>

            <h5>필터 선택</h5>
            <label>필터:
                <select id="filterType">
                    <option value="allpass">All-pass</option>
                    <option value="lowpass">Low-pass</option>
                    <option value="highpass">High-pass</option>
                    <option value="bandpass">Band-pass</option>
                    <option value="notch">Notch</option>
                </select>
            </label>

            <div style="margin-top:5px;">
                <label>Freq: <input type="number" id="filterFrequency" value="1000"></label>
                <label style="margin-left:10px;">Q: <input type="number" id="filterQ" value="1"></label>
                <label style="margin-left:10px;">Gain: <input type="number" id="filterGain" value="0"></label>
            </div>

            <div style="margin-top:10px;">
                <label style="color:#fff;">🔊 볼륨:
                    <input type="range" id="masterVolume" min="0" max="2" step="0.01" value="1" style="width:200px;">
                </label>
            </div>

            <button onclick="saveFilteredAudio()" class="btn btn-purple" style="margin-top:10px;">
                🎧 현재 효과로 오디오 저장
            </button>
        </div>
    `;
}

// ========= Web Audio API 연결 =========
function initAudioFilters() {
    const audioEl = document.getElementById("pageAudioPlayer");
    if (!audioEl) return;

    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaElementSource(audioEl);

    // 기본 필터
    const filter = audioCtx.createBiquadFilter();

    // ==== 동굴 효과용 Delay + Feedback ====
    const delayNode = audioCtx.createDelay();
    delayNode.delayTime.value = 0.25;

    const feedback = audioCtx.createGain();
    feedback.gain.value = 0.4;

    delayNode.connect(feedback);
    feedback.connect(delayNode);

    // ==== 로봇 효과용 Tremolo ====
    const tremoloGain = audioCtx.createGain();
    tremoloGain.gain.value = 1;

    const tremoloOsc = audioCtx.createOscillator();
    tremoloOsc.type = "sine";
    tremoloOsc.frequency.value = 10;
    tremoloOsc.connect(tremoloGain.gain);
    tremoloOsc.start();

    // ==== Master Gain (전체 볼륨) ====
    const masterGain = audioCtx.createGain();
    masterGain.gain.value = 1;

    // 기본 연결: source -> filter -> masterGain -> destination
    source.connect(filter);
    filter.connect(masterGain);
    masterGain.connect(audioCtx.destination);

    // UI 요소
    const filterType = document.getElementById("filterType");
    const filterFreq = document.getElementById("filterFrequency");
    const filterQ = document.getElementById("filterQ");
    const filterGain = document.getElementById("filterGain");
    const masterVolumeSlider = document.getElementById("masterVolume");
    const voiceBtns = document.querySelectorAll(".voice-btn");

    // 필터 업데이트
    function updateFilter() {
        filter.type = filterType.value;
        filter.frequency.value = parseFloat(filterFreq.value);
        filter.Q.value = parseFloat(filterQ.value);
        filter.gain.value = parseFloat(filterGain.value);
    }

    filterType.onchange = updateFilter;
    filterFreq.oninput = updateFilter;
    filterQ.oninput = updateFilter;
    filterGain.oninput = updateFilter;

    // Master Gain 슬라이더
    masterVolumeSlider.oninput = () => {
        masterGain.gain.value = parseFloat(masterVolumeSlider.value);
    };

    updateFilter();

// 효과 적용 라우팅
function applyRouting(effect) {
    try {
        source.disconnect();
        filter.disconnect();
        delayNode.disconnect();
        tremoloGain.disconnect();
    } catch (e) {}

    source.connect(filter);

    if (effect === "cave") {
        // 기존 동굴 메아리
        filter.connect(delayNode);
        delayNode.connect(masterGain);
        filter.connect(masterGain); // 원본 + 메아리
    } 
    else if (effect === "robot") {
        // 기존 로봇
        filter.connect(tremoloGain);
        tremoloGain.connect(masterGain);
    }
    else if (effect === "whisper" || effect === "radio" || effect === "telephone" || effect === "megaphone" || effect === "protoss") {
        // 이 효과들도 딜레이/트레몰로 필요하면 cave/protoss랑 같은 라우팅 타면 됨
        filter.connect(delayNode);
        delayNode.connect(feedback);
        feedback.connect(delayNode);
        delayNode.connect(masterGain);
        filter.connect(masterGain);
        if (effect === "radio" || effect === "whisper") {
            filter.connect(tremoloGain);
            tremoloGain.connect(masterGain);
        }
    }
    else if (effect === "echo") {
        // 새로 추가된 echo 효과
        filter.connect(delayNode);
        delayNode.delayTime.value = 0.6;   // 긴 메아리
        feedback.gain.value = 0.75;        // 피드백 강하게
        delayNode.connect(masterGain);
        filter.connect(masterGain);         // 원본 + 메아리
    }
    else if (["demon","angel","vader","giant","tiny","angel","possessed"].includes(effect)) {
    filter.connect(delayNode);
    delayNode.connect(feedback);
    feedback.connect(delayNode);
    delayNode.connect(masterGain);
    filter.connect(masterGain);
    if (effect === "demon" || effect === "vader" || effect === "possessed") {
        filter.connect(tremoloGain);
        tremoloGain.connect(masterGain);
    }
}
else if (["horror","helium"].includes(effect)) {
    filter.connect(delayNode);
    delayNode.connect(feedback);
    feedback.connect(delayNode);
    delayNode.connect(masterGain);
    filter.connect(masterGain);
    if (effect === "horror") {
        filter.connect(tremoloGain);
        tremoloGain.connect(masterGain);
    }
}
else if (["timewarp","glitch","choir"].includes(effect)) {
    filter.connect(delayNode);
    delayNode.connect(feedback);
    feedback.connect(delayNode);
    delayNode.connect(masterGain);
    filter.connect(masterGain);
    filter.connect(tremoloGain);        // 모두 트레몰로 필요
    tremoloGain.connect(masterGain);
}
else if (["hyperpop","vaporwave","darksynth","lofi-girl","bitcrush-voice","portal","neoncity","ghost-in-machine"].includes(effect)) {
    filter.connect(delayNode);
    delayNode.connect(feedback);
    feedback.connect(delayNode);
    delayNode.connect(masterGain);
    filter.connect(masterGain);
    filter.connect(tremoloGain);
    tremoloGain.connect(masterGain);
}
    else {
        // 기본 효과
        filter.connect(masterGain);
    }
}


    // 프리셋 버튼 동작
    voiceBtns.forEach(btn => {
        btn.onclick = () => {
            let v = btn.dataset.voice;

        switch (v) {
            case "normal":
                filterType.value = "allpass";
                filterFreq.value = 1000;
                filterQ.value = 1;
                tremoloGain.gain.value = 0;
                delayNode.delayTime.value = 0;
                feedback.gain.value = 0;
                currentEffect = "normal";
                break;

            case "phone":
                filterType.value = "highpass";
                filterFreq.value = 2000;
                filterQ.value = 8;
                tremoloGain.gain.value = 0;
                delayNode.delayTime.value = 0;
                feedback.gain.value = 0;
                currentEffect = "phone";
                break;

            case "cave":
                filterType.value = "lowpass";
                filterFreq.value = 600;
                filterQ.value = 6;
                delayNode.delayTime.value = 0.45; // 메아리 길게
                feedback.gain.value = 0.7;        // 피드백 강하게
                tremoloGain.gain.value = 0;
                currentEffect = "cave";
                break;

            case "underwater":
                filterType.value = "lowpass";
                filterFreq.value = 400;
                filterQ.value = 2;
                delayNode.delayTime.value = 0.15;
                feedback.gain.value = 0.3;
                tremoloGain.gain.value = 0.2;
                tremoloOsc.frequency.value = 5; // 느린 진동
                currentEffect = "underwater";
                break;

            case "robot":
                filterType.value = "highpass";
                filterFreq.value = 1200;
                filterQ.value = 1;
                tremoloGain.gain.value = 1;
                tremoloOsc.frequency.value = 30; // 빠른 떨림
                delayNode.delayTime.value = 0;
                feedback.gain.value = 0;
                currentEffect = "robot";
                break;

            case "ghost": // 공포/유령 느낌
                filterType.value = "bandpass";
                filterFreq.value = 500;
                filterQ.value = 9;
                delayNode.delayTime.value = 0.5;
                feedback.gain.value = 0.8;
                tremoloGain.gain.value = 0.4;
                tremoloOsc.frequency.value = 3; // 느린 떨림
                currentEffect = "ghost";
                break;

            case "child":
                filterType.value = "allpass";
                filterFreq.value = 1500;
                filterQ.value = 2;
                tremoloGain.gain.value = 0.3;
                tremoloOsc.frequency.value = 15; // 빠른 떨림
                delayNode.delayTime.value = 0;
                feedback.gain.value = 0;
                currentEffect = "child";
                break;

            case "old":
                filterType.value = "lowpass";
                filterFreq.value = 700;
                filterQ.value = 3;
                tremoloGain.gain.value = 0.2;
                tremoloOsc.frequency.value = 2; // 느린 떨림
                delayNode.delayTime.value = 0.2;
                feedback.gain.value = 0.5;
                currentEffect = "old";
                break;

            case "echo":
                filterType.value = "allpass";
                filterFreq.value = 1000;
                filterQ.value = 1;
                delayNode.delayTime.value = 0.6; // 긴 메아리
                feedback.gain.value = 0.7;
                tremoloGain.gain.value = 0;
                currentEffect = "echo";
                break;
            case "protoss":
            filterType.value = "allpass";
            filterFreq.value = 1100;
            filterQ.value = 6;
            delayNode.delayTime.value = 0.09;
            feedback.gain.value = 0.42;
                tremoloGain.gain.value = 0;
                currentEffect = "protoss";
                break;


case "whisper":
    filterType.value = "bandpass";
    filterFreq.value = 1800;
    filterQ.value = 4;
    filter.gain.value = 6;
    delayNode.delayTime.value = 0.03;   // 아주 짧은 울림만
    feedback.gain.value = 0.2;
    tremoloGain.gain.value = 0.15;
    tremoloOsc.frequency.value = 4;
    currentEffect = "whisper";
    break;

case "radio":
    filterType.value = "bandpass";
    filterFreq.value = 1800;      // 중음역만 남김
    filterQ.value = 2;
    filter.gain.value = 8;
    delayNode.delayTime.value = 0;
    tremoloGain.gain.value = 0.4;
    // 라디오 특유 떨림
    tremoloOsc.frequency.value = 6.5;
    currentEffect = "radio";
    break;


case "megaphone":
    filterType.value = "highpass";
    filterFreq.value = 900;
    filterQ.value = 5;
    filter.gain.value = 15;           // 확성기라서 진짜 크게
    delayNode.delayTime.value = 0.05;
    feedback.gain.value = 0.35;
    tremoloGain.gain.value = 0;
    currentEffect = "megaphone";
    break;
case "demon":
    filterType.value = "lowpass";
    filterFreq.value = 800;
    filterQ.value = 3;
    filter.gain.value = 12;
    delayNode.delayTime.value = 0.07;   // 역리버브 느낌
    feedback.gain.value = 0.6;
    tremoloGain.gain.value = 0.5;
    tremoloOsc.frequency.value = 120;   // 메탈릭 링모드
    currentEffect = "demon";
    break;

case "angel":
    filterType.value = "highpass";
    filterFreq.value = 800;
    filterQ.value = 5;
    filter.gain.value = 10;
    delayNode.delayTime.value = 0.35;   // 길고 성스러운 꼬리
    feedback.gain.value = 0.65;
    tremoloGain.gain.value = 0.2;
    tremoloOsc.frequency.value = 1.5;   // 천상의 떨림
    currentEffect = "angel";
    break;

case "vader":
    filterType.value = "bandpass";
    filterFreq.value = 400;
    filterQ.value = 8;
    filter.gain.value = 15;
    delayNode.delayTime.value = 0.04;
    feedback.gain.value = 0.4;
    tremoloGain.gain.value = 0.3;
    tremoloOsc.frequency.value = 80;     // 숨소리 같은 링잉
    currentEffect = "vader";
    break;

case "giant":
    filterType.value = "lowpass";
    filterFreq.value = 300;
    filterQ.value = 4;
    filter.gain.value = 18;             // 진짜 산만하게 크게
    delayNode.delayTime.value = 0.6;
    feedback.gain.value = 0.7;
    currentEffect = "giant";
    break;

case "tiny":
    filterType.value = "highpass";
    filterFreq.value = 2200;
    filterQ.value = 6;
    filter.gain.value = 8;
    delayNode.delayTime.value = 0.02;
    feedback.gain.value = 0.3;
    tremoloGain.gain.value = 0.4;
    tremoloOsc.frequency.value = 8;
    currentEffect = "tiny";
    break;

case "possessed":
    filterType.value = "bandpass";
    filterFreq.value = 600;
    filterQ.value = 5;
    filter.gain.value = 12;
    delayNode.delayTime.value = 0.07;   // 이중 목소리 느낌
    feedback.gain.value = 0.7;
    tremoloGain.gain.value = 0.6;
    tremoloOsc.frequency.value = 100;
    currentEffect = "possessed";
    break;
    case "horror": // 진짜 소름 돋는 공포 목소리
    filterType.value = "bandpass";
    filterFreq.value = 620;
    filterQ.value = 14;                // 극단적 공명
    filter.gain.value = 15;
    delayNode.delayTime.value = 0.38;  // 불길한 메아리
    feedback.gain.value = 0.78;
    tremoloGain.gain.value = 0.6;
    tremoloOsc.frequency.value = 2.8;   // 불안한 떨림
    currentEffect = "horror";
    break;


case "helium": // 헬륨 빨고 말하는 꼬마/웃긴 목소리
    filterType.value = "highpass";
    filterFreq.value = 2900;            // 고음 극대화
    filterQ.value = 7;
    filter.gain.value = 10;
    delayNode.delayTime.value = 0.015;  // 아주 짧은 울림만
    feedback.gain.value = 0.18;
    tremoloGain.gain.value = 0.2;
    tremoloOsc.frequency.value = 12;    // 미세한 떨림으로 더 웃김
    currentEffect = "helium";
    break;
    case "timewarp": // 시간이 느려지는 듯한 몽환·환상 효과
    filterType.value = "lowpass";
    filterFreq.value = 580;
    filterQ.value = 9;
    filter.gain.value = 13;
    delayNode.delayTime.value = 0.42;   // 길게 늘어지는 메아리
    feedback.gain.value = 0.89;         // 거의 무한에 가까운 반복
    tremoloOsc.frequency.value = 0.25;  // 초저속 떨림 → 시간 멈춘 듯
    tremoloGain.gain.value = 0.5;
    currentEffect = "timewarp";
    break;

case "glitch": // 디지털 깨져버린 AI·사이버펑크 목소리
    filterType.value = "bandpass";
    filterFreq.value = 1300;
    filterQ.value = 22;                 // 극단적 공명
    filter.gain.value = 11;
    delayNode.delayTime.value = 0.008;  // 아주 짧고 날카로운 반복
    feedback.gain.value = 0.35;
    tremoloOsc.frequency.value = 280;   // 미친듯이 빠른 떨림
    tremoloGain.gain.value = 0.92;      // 거의 깨진 느낌
    currentEffect = "glitch";
    break;

case "choir": // 천상의 성가대·신성한 합창 효과
    filterType.value = "allpass";
    filterFreq.value = 1600;
    filterQ.value = 5;
    filter.gain.value = 15;
    delayNode.delayTime.value = 0.28;   // 은은하게 퍼지는 울림
    feedback.gain.value = 0.72;
    tremoloOsc.frequency.value = 1.1;   // 천사들의 미세 떨림
    tremoloGain.gain.value = 0.28;
    currentEffect = "choir";
    break;
    case "hyperpop":      // TikTok·Hyperpop 보컬
    filterType.value = "highpass";
    filterFreq.value = 3200;
    filterQ.value = 14;
    filter.gain.value = 19;
    delayNode.delayTime.value = 0.018;
    feedback.gain.value = 0.42;
    tremoloOsc.frequency.value = 220;
    tremoloGain.gain.value = 0.7;
    currentEffect = "hyperpop";
    break;

case "vaporwave":     // 80년대 쇼핑몰 + 슬로우 리버브
    filterType.value = "lowpass";
    filterFreq.value = 3400;
    filterQ.value = 2;
    filter.gain.value = 11;
    delayNode.delayTime.value = 0.38;
    feedback.gain.value = 0.78;
    tremoloOsc.frequency.value = 0.35;
    tremoloGain.gain.value = 0.65;
    currentEffect = "vaporwave";
    break;

case "darksynth":     // Cyberpunk 2077 나이트시티 DJ
    filterType.value = "bandpass";
    filterFreq.value = 950;
    filterQ.value = 11;
    filter.gain.value = 17;
    delayNode.delayTime.value = 0.24;
    feedback.gain.value = 0.70;
    tremoloOsc.frequency.value = 130;
    tremoloGain.gain.value = 0.55;
    currentEffect = "darksynth";
    break;

case "lofi-girl":     // Lo-Fi HipHop 라디오 걸 ASMR 보이스
    filterType.value = "lowpass";
    filterFreq.value = 4200;
    filterQ.value = 1.8;
    filter.gain.value = 9;
    delayNode.delayTime.value = 0.45;
    feedback.gain.value = 0.62;
    tremoloOsc.frequency.value = 0.12;
    tremoloGain.gain.value = 0.35;
    currentEffect = "lofi-girl";
    break;

case "bitcrush-voice": // 8bit 게임 깨져버린 보이스 (2025 트렌드)
    filterType.value = "bandpass";
    filterFreq.value = 2200;
    filterQ.value = 28;
    filter.gain.value = 15;
    delayNode.delayTime.value = 0.004;
    feedback.gain.value = 0.25;
    tremoloOsc.frequency.value = 420;
    tremoloGain.gain.value = 0.96;
    currentEffect = "bitcrush-voice";
    break;

case "portal":        // 차원문 열리는 듯한 공간 왜곡
    filterType.value = "allpass";
    filterFreq.value = 750;
    filterQ.value = 18;
    filter.gain.value = 22;
    delayNode.delayTime.value = 0.65;
    feedback.gain.value = 0.94;
    tremoloOsc.frequency.value = 0.7;
    tremoloGain.gain.value = 0.8;
    currentEffect = "portal";
    break;

case "neoncity":      // Blade Runner 2049 네온 도시 아나운서
    filterType.value = "bandpass";
    filterFreq.value = 1150;
    filterQ.value = 9;
    filter.gain.value = 19;
    delayNode.delayTime.value = 0.52;
    feedback.gain.value = 0.80;
    tremoloOsc.frequency.value = 2.8;
    tremoloGain.gain.value = 0.45;
    currentEffect = "neoncity";
    break;

case "ghost-in-machine": // AI가 귀신 들린 듯한 최신 호러
    filterType.value = "bandpass";
    filterFreq.value = 780;
    filterQ.value = 20;
    filter.gain.value = 16;
    delayNode.delayTime.value = 0.09;
    feedback.gain.value = 0.58;
    tremoloOsc.frequency.value = 190;
    tremoloGain.gain.value = 0.88;
    currentEffect = "ghost-in-machine";
    break;
        }
        

            updateFilter();
            applyRouting(currentEffect);
        };
    });
}



// 현재 적용된 효과 저장
async function saveFilteredAudio() {
    const page = pages[currentPageIndex];

    if (!page.audioUrl && !page.audioFile) {
        alert("현재 페이지에 오디오가 없습니다.");
        return;
    }

    // 1) 오디오 로드
    let arrayBuffer;
    if (page.audioFile) {
        arrayBuffer = await page.audioFile.arrayBuffer();
    } else {
        const res = await fetch(page.audioUrl);
        arrayBuffer = await res.arrayBuffer();
    }

    const audioCtx = new AudioContext();
    const originalBuffer = await audioCtx.decodeAudioData(arrayBuffer);

    // 2) OfflineAudioContext 생성
    const offlineCtx = new OfflineAudioContext(
        originalBuffer.numberOfChannels,
        originalBuffer.length,
        originalBuffer.sampleRate
    );

    // 3) 노드 설정 (UI 값 그대로 사용)
    const source = offlineCtx.createBufferSource();
    source.buffer = originalBuffer;

    const filter = offlineCtx.createBiquadFilter();
    filter.type = filterType.value;
    filter.frequency.value = parseFloat(filterFrequency.value);
    filter.Q.value = parseFloat(filterQ.value);
    filter.gain.value = parseFloat(filterGain.value);

    // 4) 오디오 체인 구성 (조건 없음)
    const delayNode = offlineCtx.createDelay();
    delayNode.delayTime.value = 0.05;

    const feedback = offlineCtx.createGain();
    feedback.gain.value = 0.35;

    delayNode.connect(feedback);
    feedback.connect(delayNode);

    const masterGain = offlineCtx.createGain();
    masterGain.gain.value = 1;

    // chain
    source.connect(filter);
    filter.connect(delayNode);
    delayNode.connect(masterGain);
    filter.connect(masterGain); // 원음 섞기
    masterGain.connect(offlineCtx.destination);

    applyOfflineRouting(
        currentEffect,
        source,
        filter,
        delayNode,
        feedback,
        tremoloGain,
        masterGain
    );

    // 5) 렌더링
    source.start();
    const processedBuffer = await offlineCtx.startRendering();

    // 6) WAV 변환
    const wavBlob = bufferToWav(processedBuffer);
    const newFile = new File(
        [wavBlob],
        `page_${currentPageIndex + 1}_filtered.wav`,
        { type: "audio/wav" }
    );

    // 7) 페이지 오디오 교체
    page.audioFile = newFile;
    page.audioUrl = URL.createObjectURL(newFile);

    alert("현재 필터 값으로 오디오가 저장되었습니다!");

    const audioPlayer = document.getElementById("pageAudioPlayer");
    audioPlayer.src = page.audioUrl;
}


// wav 변환 함수
function bufferToWav(buffer) {
    const numOfChan = buffer.numberOfChannels,
        length = buffer.length * numOfChan * 2 + 44,
        buffer2 = new ArrayBuffer(length),
        view = new DataView(buffer2),
        channels = [],
        sampleRate = buffer.sampleRate;

    let offset = 0;

    writeString(view, offset, "RIFF"); offset += 4;
    view.setUint32(offset, 36 + buffer.length * numOfChan * 2, true); offset += 4;
    writeString(view, offset, "WAVE"); offset += 4;
    writeString(view, offset, "fmt "); offset += 4;
    view.setUint32(offset, 16, true); offset += 4;
    view.setUint16(offset, 1, true); offset += 2;
    view.setUint16(offset, numOfChan, true); offset += 2;
    view.setUint32(offset, sampleRate, true); offset += 4;
    view.setUint32(offset, sampleRate * numOfChan * 2, true); offset += 4;
    view.setUint16(offset, numOfChan * 2, true); offset += 2;
    view.setUint16(offset, 16, true); offset += 2;
    writeString(view, offset, "data"); offset += 4;
    view.setUint32(offset, buffer.length * numOfChan * 2, true); offset += 4;

    for (let i = 0; i < numOfChan; i++)
        channels.push(buffer.getChannelData(i));

    let pos = 0;
    while (pos < buffer.length) {
        for (let i = 0; i < numOfChan; i++) {
            let sample = Math.max(-1, Math.min(1, channels[i][pos]));
            view.setInt16(offset, sample * 0x7fff, true);
            offset += 2;
        }
        pos++;
    }

    return new Blob([buffer2], { type: "audio/wav" });
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}


// 페이지 추가
function addPage() {
    if (pages.length >= 100) {
        alert("대사는 100개까지만 가능합니다.");
        return;
    }

    saveCurrentPage();
    const newPage = createPage();

    // 현재 페이지 바로 뒤에 추가
    pages.splice(currentPageIndex + 1, 0, newPage);
    

    // 현재 페이지 인덱스를 새로 추가한 페이지로 이동
    currentPageIndex = currentPageIndex + 1;
    

    renderPagesList();
    loadPage(currentPageIndex);
}

// 페이지 삭제
function deletePage() {
    if (pages.length <= 1) {
        alert('최소 1개의 페이지가 필요합니다.');
        return;
    }

    if (!confirm(`페이지 ${currentPageIndex + 1}을(를) 삭제하시겠습니까?`)) {
        return;
    }

    pages.splice(currentPageIndex, 1);

    if (currentPageIndex >= pages.length) {
        currentPageIndex = pages.length - 1;
    }

    loadPage(currentPageIndex);
}


function applyOfflineRouting(effect, source, filter, delayNode, feedback, tremoloGain, masterGain) {
    source.connect(filter);

    if (effect === "megaphone") {
        filter.connect(delayNode);
        delayNode.connect(feedback);
        feedback.connect(delayNode);
        delayNode.connect(masterGain);
        filter.connect(masterGain);
    } 
    else if (effect === "robot") {
        filter.connect(tremoloGain);
        tremoloGain.connect(masterGain);
    }
    else {
        filter.connect(masterGain);
    }
}


// 이전/다음 페이지
function prevPage() {
    if (currentPageIndex > 0) {
        loadPage(currentPageIndex - 1);
    }
}

function nextPage() {
    if (currentPageIndex < pages.length - 1) {
        loadPage(currentPageIndex + 1);
    }
}

// 에피소드 저장
async function saveEpisode() {
    console.log("🎬 saveEpisode 함수 호출됨");
    saveCurrentPage();

    const episodeTitle = document.getElementById('episodeTitle').value.trim();
    console.log("📝 에피소드 제목:", episodeTitle);

    if (!episodeTitle) {
        alert('에피소드 제목을 입력해주세요.');
        return;
    }

    // 모든 페이지 내용을 합침
    const fullContent = pages.map(page => page.content).join('\n\n---\n\n');

    if (!fullContent.trim()) {
        alert('최소 하나의 페이지에 내용을 작성해주세요.');
        return;
    }

    // 마지막 에피소드 번호 가져오기
    const contentNumber = {{ latest_episode_number|default:0 }} + 1;

    // 저장 버튼 비활성화
    const saveBtn = document.querySelector('.publish-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = '저장 중...';
    }

    try {
        // FormData로 오디오 파일들과 함께 전송
        const formData = new FormData();
        formData.append('book_id', bookId);
        formData.append('content_number', contentNumber);
        formData.append('content_title', episodeTitle);
        formData.append('content_text', fullContent);
        formData.append('voice_id', selectedVoiceId);
        formData.append('language_code', selectedLanguage);
        formData.append('speed_value', document.getElementById("speedValue").innerText);  


        // 각 대사의 오디오 파일과 텍스트 추가
        pages.forEach((page, index) => {
            if (page.audioFile) {
                formData.append(`audio_${index}`, page.audioFile);
                console.log(`📎 대사 ${index + 1}의 오디오 파일 추가됨`);
            }
            // 페이지 텍스트도 함께 전송 (타임스탬프 매핑용) - 사운드 이팩트는 빈 문자열로 전송
            formData.append(`page_text_${index}`, page.isSoundEffect ? '' : (page.content || ''));
        });

        // 배경음 정보 추가
        if (backgroundTracks && backgroundTracks.length > 0) {
            // 배경음 트랙 개수
            formData.append('background_tracks_count', backgroundTracks.length);

            // 각 배경음 파일과 정보 추가
            backgroundTracks.forEach((track, index) => {
                if (track.audioFile) {
                    formData.append(`background_audio_${index}`, track.audioFile);
                    formData.append(`background_start_${index}`, track.startPage);
                    formData.append(`background_end_${index}`, track.endPage);
                    formData.append(`background_name_${index}`, track.musicName);
                    formData.append(`background_volume_${index}`, track.volume ?? 1);
                    console.log(`🎼 배경음 ${index + 1}: ${track.musicName} (대사 ${track.startPage + 1} ~ ${track.endPage + 1}), 볼륨: ${(track.volume ?? 1) * 100}%`);
                }
            });
        } else {
            formData.append('background_tracks_count', 0);
        }

        const response = await fetch('{% url "book:book_serialization" %}', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            // 발행 성공 시 임시저장 삭제
            clearDraft();

            alert(data.message || '에피소드가 발행되었습니다!');
            if (data.redirect_url) {
                window.location.href = data.redirect_url;
            } else {
                window.location.href = `{% url 'book:book_profile' %}?book_id=${bookId}`;
            }
        } else {
            alert(data.error || '에피소드 발행에 실패했습니다.');
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = '📤 에피소드 발행';
            }
        }
    } catch (error) {
        console.error('저장 오류:', error);
        alert('에피소드 저장 중 오류가 발생했습니다: ' + error.message);
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = '📤 에피소드 발행';
        }
    }
}


// 오디오 파일 업로드 처리
function handleAudioUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('audio/')) {
        alert('오디오 파일만 업로드할 수 있습니다.');
        return;
    }

    // 파일 크기 체크 (10MB 제한)
    if (file.size > 10 * 1024 * 1024) {
        alert('파일 크기는 10MB 이하여야 합니다.');
        return;
    }

    // 파일을 URL로 변환
    const audioUrl = URL.createObjectURL(file);
    pages[currentPageIndex].audioFile = file;
    pages[currentPageIndex].audioUrl = audioUrl;

    // 페이지 다시 로드
    loadPage(currentPageIndex);
}

// 전체 페이지 TTS로 오디오 생성
async function generatePageTTS(event) {
    event.preventDefault(); // 혹시 form 안에 있으면 기본 동작 막기
    const btn = event.target.closest('button'); // 클릭한 버튼 찾기
    const textarea = document.getElementById('pageContent');

    if (!textarea) {
        alert('페이지 내용을 찾을 수 없습니다.');
        return;
    }

    const pageContent = textarea.value.trim();

    if (!pageContent) {
        alert('페이지에 내용을 먼저 작성해주세요.');
        return;
    }

    // 버튼 상태 변경
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '🔄 생성 중...';

    try {
        const response = await fetch('/book/tts/generate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                text: pageContent,
                voice_id: selectedVoiceId,
                language_code: selectedLanguage,
                speed_value: document.getElementById("speedValue").innerText            })
        });

        if (!response.ok) {
            throw new Error('TTS 생성 실패');
        }

        const blob = await response.blob();
        const audioUrl = URL.createObjectURL(blob);
        const audioFile = new File([blob], `page_${currentPageIndex + 1}_tts.mp3`, { type: 'audio/mp3' });

        // 현재 페이지에 저장
        pages[currentPageIndex].audioFile = audioFile;
        pages[currentPageIndex].audioUrl = audioUrl;

        // 페이지 다시 렌더링
        loadPage(currentPageIndex);

    } catch (err) {
        console.error(err);
        alert(err.message);
    } finally {
        // 버튼 원래 상태 복원
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}


// 오디오 제거
function removeAudio() {
    if (!confirm('이 페이지의 오디오를 제거하시겠습니까?')) {
        return;
    }

    if (pages[currentPageIndex].audioUrl) {
        URL.revokeObjectURL(pages[currentPageIndex].audioUrl);
    }

    pages[currentPageIndex].audioFile = null;
    pages[currentPageIndex].audioUrl = null;

    loadPage(currentPageIndex);
}

// 자동 임시저장 (30초마다)
let autoSaveInterval = null;


// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    initPages();
    startAutoSave(); // 자동 저장 시작
});

// 페이지 떠날 때 경고 및 자동 저장
window.addEventListener('beforeunload', function(e) {
    const hasContent = pages.some(page => page.content.trim() !== '');
    if (hasContent) {
        // 떠나기 전 마지막 자동 저장
        saveDraft();

        e.preventDefault();
        e.returnValue = '';
    }
});



