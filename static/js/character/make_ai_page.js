/**
 * AI 캐릭터 생성 페이지 전용 JavaScript
 * make_ai.html에서 사용
 */

document.addEventListener('DOMContentLoaded', function() {
    // ========================================
    // 탭 전환 기능
    // ========================================
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const progressFill = document.querySelector('.progress-fill');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const submitBtn = document.getElementById('submit-btn');

    let currentTab = 0;
    const totalTabs = tabBtns.length;

    function updateTab(index) {
        currentTab = index;

        // 탭 버튼 활성화
        tabBtns.forEach((btn, i) => {
            btn.classList.toggle('active', i === index);
        });

        // 탭 컨텐츠 활성화
        tabContents.forEach((content, i) => {
            content.classList.toggle('active', i === index);
        });

        // 진행 바 업데이트
        if (progressFill) {
            const progress = ((index + 1) / totalTabs) * 100;
            progressFill.style.width = progress + '%';
        }

        // 네비게이션 버튼 업데이트
        if (prevBtn) prevBtn.style.display = index === 0 ? 'none' : 'flex';
        if (nextBtn) nextBtn.style.display = index === totalTabs - 1 ? 'none' : 'flex';
        if (submitBtn) submitBtn.style.display = index === totalTabs - 1 ? 'flex' : 'none';
    }

    // 탭 버튼 클릭
    tabBtns.forEach((btn, index) => {
        btn.addEventListener('click', () => updateTab(index));
    });

    // 이전/다음 버튼
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentTab > 0) updateTab(currentTab - 1);
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (currentTab < totalTabs - 1) updateTab(currentTab + 1);
        });
    }

    // ========================================
    // 목소리 선택 (캐릭터 음성)
    // ========================================
    const voiceCards = document.querySelectorAll('.voice-card:not(.narrator-card)');
    const voiceInput = document.getElementById('voice_id');
    const voiceSearch = document.getElementById('voice-search');
    const selectedDisplay = document.getElementById('selected-voice-display');
    const selectedVoiceImg = document.getElementById('selected-voice-img');
    const selectedVoiceName = document.getElementById('selected-voice-name');
    const clearVoiceBtn = document.getElementById('clear-voice-btn');
    const audioPlayer = document.getElementById('voice-sample-player');
    let currentPlayingBtn = null;

    // 목소리 카드 클릭 - 선택
    voiceCards.forEach(card => {
        card.addEventListener('click', function(e) {
            if (e.target.closest('.btn-play-sample')) return;

            voiceCards.forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');

            const voiceId = this.dataset.voiceId;
            const voiceName = this.dataset.voiceName;
            const voiceTags = this.dataset.voiceTags
            const voiceImage = this.dataset.voiceImage;

            if (voiceInput) voiceInput.value = voiceId;

            if (selectedVoiceName) selectedVoiceName.textContent = voiceName;
            if (selectedVoiceImg) {
                if (voiceImage) {
                    selectedVoiceImg.src = voiceImage;
                    selectedVoiceImg.style.display = 'block';
                } else {
                    selectedVoiceImg.style.display = 'none';
                }
            }
            if (selectedDisplay) selectedDisplay.style.display = 'block';
        });
    });

    // 선택 해제
    if (clearVoiceBtn) {
        clearVoiceBtn.addEventListener('click', function() {
            voiceCards.forEach(c => c.classList.remove('selected'));
            if (voiceInput) voiceInput.value = '';
            if (selectedDisplay) selectedDisplay.style.display = 'none';
        });
    }

    // 목소리 타입 필터
    const voiceTypeBtns = document.querySelectorAll('.voice-type-btn');
    let selectedTypes = new Set();

    // 필터 적용 함수
    function applyVoiceFilters() {
        const searchTerm = voiceSearch ? voiceSearch.value.toLowerCase().trim() : '';

        voiceCards.forEach(card => {
            const voiceName = (card.dataset.voiceName || '').toLowerCase();
            const voiceTypes = (card.dataset.voiceTypes || '').split(',').filter(t => t);

            // 검색어 매칭
            const matchesSearch = searchTerm === '' || voiceName.includes(searchTerm);

            // 타입 매칭 (선택된 타입이 없으면 모두 표시)
            const matchesType = selectedTypes.size === 0 ||
                [...selectedTypes].some(typeId => voiceTypes.includes(typeId));

            card.classList.toggle('hidden', !matchesSearch || !matchesType);
        });
    }

    // 타입 버튼 클릭 (중복 선택 가능)
    voiceTypeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const typeId = this.dataset.typeId;

            if (selectedTypes.has(typeId)) {
                selectedTypes.delete(typeId);
                this.classList.remove('active');
            } else {
                selectedTypes.add(typeId);
                this.classList.add('active');
            }

            applyVoiceFilters();
        });
    });

    // 목소리 검색
    if (voiceSearch) {
        voiceSearch.addEventListener('input', applyVoiceFilters);
    }

    // 샘플 오디오 재생
    document.querySelectorAll('.btn-play-sample').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const audioUrl = this.dataset.audio;

            if (currentPlayingBtn === this && audioPlayer && !audioPlayer.paused) {
                audioPlayer.pause();
                audioPlayer.currentTime = 0;
                this.classList.remove('playing');
                this.querySelector('.play-icon').textContent = '▶';
                currentPlayingBtn = null;
            } else {
                if (currentPlayingBtn) {
                    currentPlayingBtn.classList.remove('playing');
                    currentPlayingBtn.querySelector('.play-icon').textContent = '▶';
                }
                if (audioPlayer) {
                    audioPlayer.src = audioUrl;
                    audioPlayer.play();
                }
                this.classList.add('playing');
                this.querySelector('.play-icon').textContent = '⏸';
                currentPlayingBtn = this;
            }
        });
    });

    if (audioPlayer) {
        audioPlayer.addEventListener('ended', function() {
            if (currentPlayingBtn) {
                currentPlayingBtn.classList.remove('playing');
                currentPlayingBtn.querySelector('.play-icon').textContent = '▶';
                currentPlayingBtn = null;
            }
        });
    }

    // 편집 모드에서 기존 선택된 목소리 표시 초기화
    const initialSelectedCard = document.querySelector('.voice-card:not(.narrator-card).selected');
    if (initialSelectedCard && selectedDisplay) {
        const voiceName = initialSelectedCard.dataset.voiceName;
        const voiceImage = initialSelectedCard.dataset.voiceImage;

        if (selectedVoiceName) selectedVoiceName.textContent = voiceName;
        if (selectedVoiceImg) {
            if (voiceImage) {
                selectedVoiceImg.src = voiceImage;
                selectedVoiceImg.style.display = 'block';
            } else {
                selectedVoiceImg.style.display = 'none';
            }
        }
        selectedDisplay.style.display = 'block';
    }

    // ========================================
    // 나레이터 목소리 선택
    // ========================================
    const narratorCards = document.querySelectorAll('.narrator-card');
    const narratorInput = document.getElementById('narrator_voice_id');
    const narratorDisplay = document.getElementById('selected-narrator-display');
    const narratorImg = document.getElementById('selected-narrator-img');
    const narratorName = document.getElementById('selected-narrator-name');
    const clearNarratorBtn = document.getElementById('clear-narrator-btn');

    // 나레이터 카드 클릭 - 선택
    narratorCards.forEach(card => {
        card.addEventListener('click', function(e) {
            if (e.target.closest('.btn-play-sample')) return;

            narratorCards.forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');

            const voiceId = this.dataset.voiceId;
            const voiceName = this.dataset.voiceName;
            const voiceImage = this.dataset.voiceImage;

            if (narratorInput) narratorInput.value = voiceId;

            if (narratorName) narratorName.textContent = voiceName;
            if (narratorImg) {
                if (voiceImage) {
                    narratorImg.src = voiceImage;
                    narratorImg.style.display = 'block';
                } else {
                    narratorImg.style.display = 'none';
                }
            }
            if (narratorDisplay) narratorDisplay.style.display = 'block';
        });
    });

    // 나레이터 선택 해제
    if (clearNarratorBtn) {
        clearNarratorBtn.addEventListener('click', function() {
            narratorCards.forEach(c => c.classList.remove('selected'));
            if (narratorInput) narratorInput.value = '';
            if (narratorDisplay) narratorDisplay.style.display = 'none';
        });
    }

    // 편집 모드에서 기존 선택된 나레이터 목소리 표시 초기화
    const initialNarratorCard = document.querySelector('.narrator-card.selected');
    if (initialNarratorCard && narratorDisplay) {
        const voiceName = initialNarratorCard.dataset.voiceName;
        const voiceImage = initialNarratorCard.dataset.voiceImage;

        if (narratorName) narratorName.textContent = voiceName;
        if (narratorImg) {
            if (voiceImage) {
                narratorImg.src = voiceImage;
                narratorImg.style.display = 'block';
            } else {
                narratorImg.style.display = 'none';
            }
        }
        narratorDisplay.style.display = 'block';
    }

    // ========================================
    // 프로필 이미지 업로드
    // ========================================
    const profileUpload = document.getElementById('profile-upload-area');
    const profileInput = document.getElementById('user_image');
    const previewImage = document.getElementById('preview-image');
    const uploadPlaceholder = document.getElementById('upload-placeholder');
    const previewAvatar = document.getElementById('preview-avatar');

    if (profileUpload && profileInput) {
        profileUpload.addEventListener('click', () => profileInput.click());

        profileInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    if (previewImage) {
                        previewImage.src = e.target.result;
                        previewImage.style.display = 'block';
                    }
                    if (uploadPlaceholder) uploadPlaceholder.style.display = 'none';

                    // 미니 프로필도 업데이트
                    const miniPreview = document.getElementById('preview-image-mini');
                    const miniPlaceholder = document.getElementById('upload-mini-placeholder');
                    if (miniPreview) {
                        miniPreview.src = e.target.result;
                        miniPreview.style.display = 'block';
                    }
                    if (miniPlaceholder) miniPlaceholder.style.display = 'none';
                };
                reader.readAsDataURL(file);
            }
        });

        // 드래그 앤 드롭
        profileUpload.addEventListener('dragover', (e) => {
            e.preventDefault();
            profileUpload.classList.add('dragover');
        });

        profileUpload.addEventListener('dragleave', () => {
            profileUpload.classList.remove('dragover');
        });

        profileUpload.addEventListener('drop', (e) => {
            e.preventDefault();
            profileUpload.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                profileInput.files = e.dataTransfer.files;
                profileInput.dispatchEvent(new Event('change'));
            }
        });
    }

    // ========================================
    // 기본 정보 탭 - 미니 프로필 이미지 업로드
    // ========================================
    const profileMiniUpload = document.getElementById('profile-upload-mini');
    const llmImageInput = document.getElementById('llm_image');
    const previewImageMini = document.getElementById('preview-image-mini');
    const uploadMiniPlaceholder = document.getElementById('upload-mini-placeholder');

    if (profileMiniUpload && llmImageInput) {
        profileMiniUpload.addEventListener('click', () => llmImageInput.click());

        llmImageInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    if (previewImageMini) {
                        previewImageMini.src = e.target.result;
                        previewImageMini.style.display = 'block';
                    }
                    if (uploadMiniPlaceholder) uploadMiniPlaceholder.style.display = 'none';

                    // 이미지 탭의 큰 미리보기도 업데이트
                    const largePreview = document.getElementById('preview-image');
                    const largePlaceholder = document.getElementById('upload-placeholder');
                    if (largePreview) {
                        largePreview.src = e.target.result;
                        largePreview.style.display = 'block';
                    }
                    if (largePlaceholder) largePlaceholder.style.display = 'none';
                };
                reader.readAsDataURL(file);
            }
        });

        // 드래그 앤 드롭
        profileMiniUpload.addEventListener('dragover', (e) => {
            e.preventDefault();
            profileMiniUpload.classList.add('dragover');
        });

        profileMiniUpload.addEventListener('dragleave', () => {
            profileMiniUpload.classList.remove('dragover');
        });

        profileMiniUpload.addEventListener('drop', (e) => {
            e.preventDefault();
            profileMiniUpload.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                llmImageInput.files = e.dataTransfer.files;
                llmImageInput.dispatchEvent(new Event('change'));
            }
        });
    }

    // ========================================
    // 프롬프트 글자 수 카운터
    // ========================================
    const promptTextarea = document.getElementById('prompt');
    const promptCount = document.getElementById('prompt-count');

    if (promptTextarea && promptCount) {
        promptTextarea.addEventListener('input', function() {
            promptCount.textContent = this.value.length;
        });
    }

    // ========================================
    // 프롬프트 글자 수 카운터 (추가 이벤트)
    // ========================================

    // ========================================
    // 로어북 항목 추가 (최대 10개)
    // ========================================
    const loreContainer = document.getElementById('lore-entries-container');
    const addLoreBtn = document.getElementById('add-lore-entry');
    const MAX_LORE = 10;

    function getLoreCount() {
        return document.querySelectorAll('.lore-entry').length;
    }

    function updateLoreNumbers() {
        document.querySelectorAll('.lore-entry').forEach((entry, index) => {
            const numEl = entry.querySelector('.lore-number');
            if (numEl) numEl.textContent = index + 1;
        });
        if (addLoreBtn) {
            if (getLoreCount() >= MAX_LORE) {
                addLoreBtn.disabled = true;
                addLoreBtn.innerHTML = '<span>⚠️</span> 최대 10개까지만 추가 가능';
            } else {
                addLoreBtn.disabled = false;
                addLoreBtn.innerHTML = '<span>+</span> 로어북 항목 추가';
            }
        }
    }

    if (addLoreBtn && loreContainer) {
        addLoreBtn.addEventListener('click', function() {
            if (getLoreCount() >= MAX_LORE) {
                alert('로어북 항목은 최대 10개까지만 추가할 수 있습니다.');
                return;
            }

            const newNumber = getLoreCount() + 1;
            const entry = document.createElement('div');
            entry.className = 'lore-entry';
            entry.innerHTML = `
                <div class="lore-entry-header">
                    <span class="lore-number">${newNumber}</span>
                    <button type="button" class="remove-lore-entry"><span>✕</span></button>
                </div>
                <div class="form-group">
                    <label class="form-label">활성화 키워드</label>
                    <textarea name="lore_keys[]" class="form-textarea" rows="2" placeholder="쉼표(,) 또는 줄바꿈으로 구분"></textarea>
                    <span class="form-hint">이 키워드가 대화에 나오면 아래 내용이 주입됩니다</span>
                </div>
                <div class="form-group">
                    <label class="form-label">주입될 내용</label>
                    <textarea name="lore_content[]" class="form-textarea" rows="4" placeholder="AI에게 주입할 설명, 사실, 설정 등"></textarea>
                </div>
                <div class="lore-options">
                    <div class="form-group form-group-inline">
                        <label class="form-label">우선순위</label>
                        <input type="number" name="lore_priority[]" class="form-input-small" value="0" min="0">
                    </div>
                    <div class="form-group form-group-inline">
                        <label class="form-label">카테고리</label>
                        <select name="lore_category[]" class="form-select-small">
                            <option value="">선택 안 함</option>
                            <option value="personality">성격</option>
                            <option value="world">세계관</option>
                            <option value="relationship">관계</option>
                        </select>
                    </div>
                    <div class="form-group form-group-checkbox">
                        <label class="checkbox-label">
                            <input type="checkbox" name="lore_always_active[]" value="true">
                            <span class="checkbox-custom"></span>
                            <span>항상 포함</span>
                        </label>
                    </div>
                </div>
            `;
            loreContainer.appendChild(entry);

            entry.querySelector('.remove-lore-entry').addEventListener('click', function() {
                entry.remove();
                updateLoreNumbers();
            });

            updateLoreNumbers();
        });
    }

    // 기존 로어북 삭제 버튼
    document.querySelectorAll('.remove-lore-entry').forEach(btn => {
        btn.addEventListener('click', function() {
            this.closest('.lore-entry').remove();
            updateLoreNumbers();
        });
    });

    updateLoreNumbers();

    // ========================================
    // 서브 이미지 추가 (최대 10개)
    // ========================================
    const subContainer = document.getElementById('sub-images-container');
    const addSubBtn = document.getElementById('add-sub-image-btn');
    const MAX_SUB = 10;

    function getSubCount() {
        return document.querySelectorAll('.sub-image-entry').length;
    }

    function updateSubNumbers() {
        document.querySelectorAll('.sub-image-entry').forEach((entry, index) => {
            const numEl = entry.querySelector('.sub-image-number');
            if (numEl) numEl.textContent = index + 1;
        });
        if (addSubBtn) {
            if (getSubCount() >= MAX_SUB) {
                addSubBtn.disabled = true;
                addSubBtn.innerHTML = '<span>⚠️</span> 최대 10개까지만 추가 가능';
            } else {
                addSubBtn.disabled = false;
                addSubBtn.innerHTML = '<span>+</span> 서브 이미지 추가';
            }
        }
    }

    // 서브 이미지 미리보기 기능
    function setupSubImagePreview(entry) {
        const fileInput = entry.querySelector('.sub-image-file');
        if (!fileInput) return;

        fileInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    // 기존 미리보기 제거
                    let preview = entry.querySelector('.sub-image-preview');
                    if (!preview) {
                        preview = document.createElement('div');
                        preview.className = 'sub-image-preview';
                        const uploadDiv = entry.querySelector('.sub-image-upload');
                        if (uploadDiv) {
                            uploadDiv.appendChild(preview);
                        }
                    }
                    preview.innerHTML = `<img src="${e.target.result}" alt="미리보기"><button type="button" class="remove-preview-btn">✕</button>`;

                    // 미리보기 삭제 버튼
                    preview.querySelector('.remove-preview-btn').addEventListener('click', function(ev) {
                        ev.stopPropagation();
                        preview.remove();
                        fileInput.value = '';
                    });
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // 기존 서브 이미지에 미리보기 설정
    document.querySelectorAll('.sub-image-entry').forEach(entry => {
        setupSubImagePreview(entry);
    });

    if (addSubBtn && subContainer) {
        addSubBtn.addEventListener('click', function() {
            if (getSubCount() >= MAX_SUB) {
                alert('서브 이미지는 최대 10개까지만 추가할 수 있습니다.');
                return;
            }

            const newNumber = getSubCount() + 1;
            const entry = document.createElement('div');
            entry.className = 'sub-image-entry';
            entry.innerHTML = `
                <div class="sub-image-header">
                    <span class="sub-image-number">${newNumber}</span>
                    <button type="button" class="remove-sub-image"><span>✕</span></button>
                </div>
                <div class="sub-image-content">
                    <div class="sub-image-upload">
                        <input type="file" name="sub_images" accept="image/*" class="sub-image-file">
                    </div>
                    <div class="sub-image-options">
                        <div class="hp-range">
                            <label>HP 범위</label>
                            <div class="hp-inputs">
            <input type="number" 
                   name="min_hp[]" 
                   placeholder="최소" 
                   min="0" 
                   max="100" 
                   class="form-input-small" 
                   required 
                   oninput="this.value = Math.max(0, Math.min(100, this.value || 0)); validateHpRange(this)">
            
            <span class="hp-separator">~</span>
            
            <!-- 최대 HP: 0 ~ 100 사이, min보다 커야 함 -->
            <input type="number" 
                   name="max_hp[]" 
                   placeholder="최대" 
                   min="0" 
                   max="100" 
                   class="form-input-small" 
                   required 
                   oninput="this.value = Math.max(0, Math.min(100, this.value || 0)); validateHpRange(this)">
                            </div>
                        </div>
                        <div class="sub-image-title">
                            <label>제목/메모</label>
                            <input type="text" name="sub_image_title[]" placeholder="예: 상처 입은 모습" class="form-input">
                        </div>
                    </div>
                </div>
            `;
            subContainer.appendChild(entry);

            // 새 서브 이미지에 미리보기 설정
            setupSubImagePreview(entry);

            entry.querySelector('.remove-sub-image').addEventListener('click', function() {
                entry.remove();
                updateSubNumbers();
            });

            updateSubNumbers();
        });
    }

    // 기존 서브 이미지 삭제 버튼
    document.querySelectorAll('.remove-sub-image').forEach(btn => {
        btn.addEventListener('click', function() {
            this.closest('.sub-image-entry').remove();
            updateSubNumbers();
            validateHpRanges(); // HP 겹침 재검사
        });
    });

    updateSubNumbers();

    // ========================================
    // HP 범위 겹침 검사
    // ========================================
    function validateHpRanges() {
        const entries = document.querySelectorAll('.sub-image-entry');
        const ranges = [];
        let hasOverlap = false;
        let overlapMessages = [];

        // 모든 기존 경고 제거
        document.querySelectorAll('.hp-overlap-warning').forEach(el => el.remove());
        entries.forEach(entry => entry.classList.remove('hp-error'));

        // HP 범위 수집
        entries.forEach((entry, index) => {
            const minInput = entry.querySelector('input[name="min_hp[]"]');
            const maxInput = entry.querySelector('input[name="max_hp[]"]');
            const minHp = parseInt(minInput?.value) || 0;
            const maxHp = parseInt(maxInput?.value) || 100;

            if (minHp > maxHp) {
                entry.classList.add('hp-error');
                showHpWarning(entry, `HP 범위 오류: 최소(${minHp})가 최대(${maxHp})보다 큽니다`);
                hasOverlap = true;
            }

            ranges.push({
                index: index + 1,
                minHp: minHp,
                maxHp: maxHp,
                entry: entry
            });
        });

        // 겹침 검사
        for (let i = 0; i < ranges.length; i++) {
            for (let j = i + 1; j < ranges.length; j++) {
                const a = ranges[i];
                const b = ranges[j];

                // 두 범위가 겹치는지 확인
                if (a.minHp <= b.maxHp && b.minHp <= a.maxHp) {
                    hasOverlap = true;
                    a.entry.classList.add('hp-error');
                    b.entry.classList.add('hp-error');

                    const msg = `서브 이미지 ${a.index}번(${a.minHp}~${a.maxHp})과 ${b.index}번(${b.minHp}~${b.maxHp})의 HP 범위가 겹칩니다`;
                    overlapMessages.push(msg);
                    showHpWarning(b.entry, msg);
                }
            }
        }

        // 전역 경고 표시
        const globalWarning = document.getElementById('hp-global-warning');
        if (hasOverlap) {
            if (!globalWarning) {
                const warning = document.createElement('div');
                warning.id = 'hp-global-warning';
                warning.className = 'hp-global-warning';
                warning.innerHTML = `
                    <span class="warning-icon">⚠️</span>
                    <span>HP 범위 설정에 문제가 있습니다. 겹치는 범위를 수정해주세요.</span>
                `;
                const subContainer = document.getElementById('sub-images-container');
                subContainer?.parentNode.insertBefore(warning, subContainer);
            }
        } else {
            globalWarning?.remove();
        }

        return !hasOverlap;
    }

    function showHpWarning(entry, message) {
        const existing = entry.querySelector('.hp-overlap-warning');
        if (existing) {
            existing.textContent = message;
        } else {
            const warning = document.createElement('div');
            warning.className = 'hp-overlap-warning';
            warning.textContent = message;
            entry.appendChild(warning);
        }
    }

    // HP 입력값 변경 시 검사
    document.addEventListener('input', function(e) {
        if (e.target.name === 'min_hp[]' || e.target.name === 'max_hp[]') {
            validateHpRanges();
        }
    });

    // 폼 제출 시 검사
    const aiForm = document.querySelector('form');
    if (aiForm) {
        aiForm.addEventListener('submit', function(e) {
            if (!validateHpRanges()) {
                e.preventDefault();
                alert('HP 범위가 겹치는 서브 이미지가 있습니다. 수정 후 다시 시도해주세요.');
                return false;
            }
        });
    }

    // 초기 검사 실행
    validateHpRanges();

});


