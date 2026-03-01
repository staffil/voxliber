/**
 * draft-manager.js
 * 임시저장 관련 기능 (IndexedDB 사용)
 */

// IndexedDB 초기화
function initIndexedDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('VoxliberDrafts', 1);

        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            db = request.result;
            resolve(db);
        };

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('drafts')) {
                db.createObjectStore('drafts', { keyPath: 'bookId' });
            }
        };
    });
}

// 임시저장 키 생성
function getDraftKey() {
    return bookId;
}

// 오디오 파일을 Blob으로 변환
async function fileToBlob(file) {
    if (!file) return null;
    return new Blob([await file.arrayBuffer()], { type: file.type });
}

// 임시저장 (IndexedDB 사용)
async function saveDraft() {
    saveCurrentPage(); // 현재 페이지 저장

    console.log('📝 임시저장 시작 - 현재 페이지 데이터:', {
        currentPageIndex: currentPageIndex,
        content: pages[currentPageIndex]?.content,
        totalPages: pages.length
    });

    try {
        if (!db) {
            await initIndexedDB();
        }

        // 오디오 파일을 Blob으로 변환
        const pagesWithAudio = await Promise.all(pages.map(async (page, index) => {
            const audioBlob = page.audioFile ? await fileToBlob(page.audioFile) : null;
            console.log(`페이지 ${index + 1} - 텍스트 길이: ${page.content.length}자, 오디오: ${audioBlob ? '있음' : '없음'}, 사운드 이팩트: ${page.isSoundEffect ? '예' : '아니오'}, 소설 미리쓰기: ${page.novelDraft ? '있음' : '없음'}`);
            return {
                content: page.content,
                charCount: page.charCount,
                audioBlob: audioBlob,
                hasAudio: !!audioBlob,
                isSoundEffect: page.isSoundEffect || false,
                effectName: page.effectName || '',
                isSilence: page.isSilence || false,
                silenceDuration: page.silenceDuration || 1.0,
                isDuet: page.isDuet || false,
                duetMode: page.duetMode || 'overlap',
                duetData: page.duetData ? JSON.parse(JSON.stringify(page.duetData)) : null,
                duetText: page.duetText || '',
                novelDraft: page.novelDraft || ''
            };
        }));

        // 배경음 트랙 Blob 변환
        const backgroundTracksWithAudio = await Promise.all(backgroundTracks.map(async (track) => {
            const audioBlob = track.audioFile ? await fileToBlob(track.audioFile) : null;
            return {
                id: track.id,
                startPage: track.startPage,
                endPage: track.endPage,
                audioBlob: audioBlob,
                musicName: track.musicName,
                volume: track.volume ?? 1
            };
        }));

        const draftData = {
            bookId: bookId,
            episodeTitle: document.getElementById('episodeTitle').value,
            pages: pagesWithAudio,
            backgroundTracks: backgroundTracksWithAudio,
            timestamp: new Date().toISOString(),
            selectedVoiceId: selectedVoiceId,
            selectedLanguage: selectedLanguage
        };

        const transaction = db.transaction(['drafts'], 'readwrite');
        const store = transaction.objectStore('drafts');
        store.put(draftData);

        // transaction 완료를 기다림
        await new Promise((resolve, reject) => {
            transaction.oncomplete = () => {
                console.log('✅ 임시저장 완료 (오디오 포함)', {
                    bookId: draftData.bookId,
                    episodeTitle: draftData.episodeTitle,
                    pagesCount: draftData.pages.length,
                    backgroundTracksCount: draftData.backgroundTracks.length
                });
                resolve();
            };
            transaction.onerror = () => {
                console.error('❌ IndexedDB transaction 오류:', transaction.error);
                reject(transaction.error);
            };
        });

        // 임시저장 상태 표시
        const statusEl = document.getElementById('draftStatus');
        statusEl.style.display = 'block';
        statusEl.textContent = '💾 임시저장됨 (' + new Date().toLocaleTimeString() + ')';

        // 3초 후 숨김
        setTimeout(() => {
            statusEl.style.display = 'none';
        }, 3000);
    } catch (error) {
        console.error('❌ 임시저장 오류:', error);
        alert('임시저장 중 오류가 발생했습니다.');
    }
}

// 임시저장 불러오기
async function loadDraft() {
    if (!confirm('임시저장된 내용을 불러오시겠습니까?\n현재 작성 중인 내용은 사라집니다.')) {
        return;
    }

    try {
        if (!db) {
            await initIndexedDB();
        }

        const transaction = db.transaction(['drafts'], 'readonly');
        const store = transaction.objectStore('drafts');
        const request = store.get(getDraftKey());

        request.onsuccess = async () => {
            let draftData = request.result;

            // IndexedDB에 없으면 localStorage 백업 확인
            if (!draftData) {
                try {
                    const backupKey = 'draft_backup_' + bookId;
                    const backupStr = localStorage.getItem(backupKey);
                    if (backupStr) {
                        const backup = JSON.parse(backupStr);
                        // localStorage 백업으로 draftData 구성 (오디오 없음)
                        draftData = {
                            bookId: backup.bookId,
                            episodeTitle: backup.episodeTitle || '',
                            pages: (backup.pagesSimple || []).map(p => ({
                                content: p.content || '',
                                charCount: (p.content || '').length,
                                hasAudio: false,
                                audioBlob: null,
                                isDuet: p.isDuet || false,
                                duetMode: p.duetMode || 'overlap',
                                duetData: p.duetData || null,
                                duetText: p.duetText || '',
                                isSilence: p.isSilence || false,
                                silenceDuration: p.silenceDuration || 1.0,
                                isSoundEffect: p.isSoundEffect || false,
                                effectName: p.effectName || '',
                                novelDraft: ''
                            })),
                            backgroundTracks: [],
                            timestamp: backup.timestamp
                        };
                        console.log('📂 localStorage 백업으로 복원 (오디오 제외)');
                    }
                } catch(ex) {}
            }

            if (!draftData) {
                alert('임시저장된 내용이 없습니다.');
                return;
            }

            console.log('📂 임시저장 불러오기 - 저장된 데이터:', draftData);

            // 에피소드 제목 복원
            document.getElementById('episodeTitle').value = draftData.episodeTitle || '';

            // 대사들 복원 (오디오 포함)
            pages = await Promise.all(draftData.pages.map(async (pageData, index) => {
                const page = createPage(pageData.content, null, pageData.isSoundEffect || false);
                console.log(`📄 페이지 ${index + 1} 복원 - 텍스트: ${pageData.content.length}자, 오디오: ${pageData.audioBlob ? '있음' : '없음'}, 사운드 이팩트: ${pageData.isSoundEffect ? '예' : '아니오'}, 소설 미리쓰기: ${pageData.novelDraft ? '있음' : '없음'}`);

                // 사운드 이팩트 정보 복원
                if (pageData.isSoundEffect) {
                    page.effectName = pageData.effectName || '';
                }

                // 무음 정보 복원
                if (pageData.isSilence) {
                    page.isSilence = true;
                    page.silenceDuration = pageData.silenceDuration || 1.0;
                    // 무음 오디오 재생성 (Blob은 저장 불가)
                    if (typeof generateSilenceAudioForPage === 'function') {
                        setTimeout(() => generateSilenceAudioForPage(index), 100);
                    }
                }

                // 2인 대화 정보 복원
                if (pageData.isDuet) {
                    page.isDuet = true;
                    page.duetMode = pageData.duetMode || 'overlap';
                    page.duetData = pageData.duetData || [{voice_id:'',text:''},{voice_id:'',text:''}];
                    if (pageData.duetText) page.duetText = pageData.duetText;
                }

                // 소설 미리쓰기 복원
                if (pageData.novelDraft) {
                    page.novelDraft = pageData.novelDraft;
                }

                // 오디오 복원
                if (pageData.audioBlob) {
                    const audioFile = new File([pageData.audioBlob], `restored_audio_${index}.mp3`, { type: 'audio/mp3' });
                    const audioUrl = URL.createObjectURL(pageData.audioBlob);
                    page.audioFile = audioFile;
                    page.audioUrl = audioUrl;
                }

                return page;
            }));

            // 배경음 트랙 복원
            if (draftData.backgroundTracks && draftData.backgroundTracks.length > 0) {
                backgroundTracks = await Promise.all(draftData.backgroundTracks.map(async (trackData) => {
                    const track = {
                        id: trackData.id,
                        startPage: trackData.startPage,
                        endPage: trackData.endPage,
                        musicName: trackData.musicName,
                        audioFile: null,
                        audioUrl: null,
                        volume: trackData.volume ?? 1
                    };

                    // 오디오 복원
                    if (trackData.audioBlob) {
                        const audioFile = new File([trackData.audioBlob], `${trackData.musicName}.mp3`, { type: 'audio/mp3' });
                        const audioUrl = URL.createObjectURL(trackData.audioBlob);
                        track.audioFile = audioFile;
                        track.audioUrl = audioUrl;
                    }

                    return track;
                }));
                console.log(`🎼 배경음 트랙 ${backgroundTracks.length}개 복원됨`);
            } else {
                backgroundTracks = [];
            }

            // 음성 설정 복원
            if (draftData.selectedVoiceId) {
                selectedVoiceId = draftData.selectedVoiceId;
            }
            if (draftData.selectedLanguage) {
                selectedLanguage = draftData.selectedLanguage;
                document.getElementById('languageSelect').value = selectedLanguage;
            }

            // UI 업데이트
            renderPagesList();
            renderBackgroundTracks();
            loadPage(0, true); // skipSave = true로 설정하여 빈 textarea 저장 방지

            const audioCount = draftData.pages.filter(p => p.hasAudio).length;
            const textCount = draftData.pages.filter(p => p.content && p.content.trim() !== '').length;
            const bgMusicCount = backgroundTracks.length;
            alert(`임시저장된 내용을 불러왔습니다.\n저장 시각: ${new Date(draftData.timestamp).toLocaleString()}\n텍스트가 있는 대사: ${textCount}개\n오디오 파일: ${audioCount}개\n배경음: ${bgMusicCount}개`);

            // 불러오기 버튼 숨김
            document.getElementById('loadDraftBtn').style.display = 'none';
        };

        request.onerror = () => {
            console.error('❌ 임시저장 불러오기 오류:', request.error);
            alert('임시저장 불러오기 중 오류가 발생했습니다.');
        };
    } catch (error) {
        console.error('❌ 임시저장 불러오기 오류:', error);
        alert('임시저장 불러오기 중 오류가 발생했습니다.');
    }
}

// 임시저장 삭제
async function clearDraft() {
    try {
        if (!db) {
            await initIndexedDB();
        }

        const transaction = db.transaction(['drafts'], 'readwrite');
        const store = transaction.objectStore('drafts');
        await store.delete(getDraftKey());

        document.getElementById('loadDraftBtn').style.display = 'none';
        console.log('🗑️ 임시저장 삭제됨');
    } catch (error) {
        console.error('❌ 임시저장 삭제 오류:', error);
    }
}

// 임시저장 존재 여부 체크
async function checkDraftExists() {
    // localStorage 백업 먼저 확인 (빠른 동기 체크)
    try {
        const backupKey = 'draft_backup_' + bookId;
        if (localStorage.getItem(backupKey)) {
            document.getElementById('loadDraftBtn').style.display = 'block';
            console.log('📂 localStorage 백업 발견');
        }
    } catch(ex) {}

    try {
        if (!db) {
            await initIndexedDB();
        }

        const transaction = db.transaction(['drafts'], 'readonly');
        const store = transaction.objectStore('drafts');
        const request = store.get(getDraftKey());

        request.onsuccess = () => {
            if (request.result) {
                document.getElementById('loadDraftBtn').style.display = 'block';
                console.log('📂 임시저장된 데이터 발견 (오디오 포함)');
            }
        };
    } catch (error) {
        console.error('❌ 임시저장 체크 오류:', error);
    }
}

// 자동 임시저장 시작
function startAutoSave() {
    // 기존 인터벌 제거
    if (autoSaveInterval) {
        clearInterval(autoSaveInterval);
    }

    // 30초마다 자동 저장
    autoSaveInterval = setInterval(() => {
        const hasContent = pages.some(page =>
                              page.content.trim() !== '' ||
                              page.isDuet && (page.duetData || []).some(v => (v.text || '').trim())
                          ) || document.getElementById('episodeTitle').value.trim() !== '';

        if (hasContent) {
            saveDraft();
            console.log('🔄 자동 임시저장 실행');
        }
    }, 10000); // 10초
}
