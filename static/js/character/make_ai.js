/**
 * AI 캐릭터 생성 페이지 JavaScript
 * 이 파일은 다른 페이지와의 호환성을 위한 기본 기능만 포함
 * 로어북/서브이미지 기능은 make_ai.html 인라인 스크립트에서 처리
 */

document.addEventListener('DOMContentLoaded', function() {

    // ========================================
    // 목소리 선택 (이전 페이지 호환용 - .voice-list span)
    // ========================================
    const voiceSpans = document.querySelectorAll('.voice-list span');
    voiceSpans.forEach(span => {
        span.style.cursor = 'pointer';
        span.addEventListener('click', function() {
            const voiceId = this.textContent.trim().split('/')[0];
            const voiceInput = document.getElementById('voice_id');
            if (voiceInput) {
                voiceInput.value = voiceId;
            }
            voiceSpans.forEach(s => s.style.backgroundColor = '');
            this.style.backgroundColor = 'rgba(0, 212, 255, 0.2)';
        });
    });

    // ========================================
    // 프로필 이미지 미리보기 (이전 페이지 호환용)
    // ========================================
    const fileInput = document.getElementById('user_image');
    const previewImage = document.getElementById('preview-image');
    const fileText = document.getElementById('file-text');

    if (fileInput && previewImage && fileText) {
        fileInput.addEventListener('change', function() {
            const file = this.files[0];
            if (!file) return;

            fileText.textContent = file.name;

            const reader = new FileReader();
            reader.onload = function(e) {
                previewImage.src = e.target.result;
                previewImage.style.display = 'block';
            };
            reader.readAsDataURL(file);
        });
    }

    // ========================================
    // 실시간 미리보기 업데이트 (이전 페이지 호환용)
    // ========================================
    const nameInput = document.getElementById('ai_name');
    const firstInput = document.getElementById('first_sentence');
    const descInput = document.getElementById('distribute') || document.getElementById('description');
    const previewName = document.getElementById('preview-name');
    const previewFirst = document.getElementById('preview-first');
    const previewDesc = document.getElementById('preview-desc');
    const previewAvatar = document.getElementById('preview-avatar');

    if (nameInput && previewName) {
        nameInput.addEventListener('input', () => {
            previewName.textContent = nameInput.value || 'AI 이름';
        });
    }

    if (firstInput && previewFirst) {
        firstInput.addEventListener('input', () => {
            previewFirst.textContent = firstInput.value || '첫 마디 미리보기...';
        });
    }

    if (descInput && previewDesc) {
        descInput.addEventListener('input', () => {
            previewDesc.textContent = descInput.value || '설명이 여기에 표시됩니다';
        });
    }

    // 이미지 업로드 시 미리보기 아바타 업데이트
    if (fileInput && previewAvatar) {
        fileInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewAvatar.src = e.target.result;
                };
                reader.readAsDataURL(file);
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
});



document.addEventListener('DOMContentLoaded', () => {

    const form = document.querySelector('#ai-create-form'); // 실제 폼 id로 변경
    const addSubImageBtn = document.querySelector('#add-sub-image-btn');

    form.addEventListener('submit', (e) => {
        const minInputs = document.querySelectorAll('input[name="min_hp[]"]');
        const maxInputs = document.querySelectorAll('input[name="max_hp[]"]');

        let valid = true;
        let messages = [];

        if (minInputs.length > 0) {
        const firstMin = Number(minInputs[0].value);
            if (firstMin !== 0) {
                valid = false;
                messages.push("첫 서브 이미지의 최소 HP는 0부터 시작해야 합니다.");
            }
        }


        minInputs.forEach((minInput, index) => {
            const maxInput = maxInputs[index];
            const minVal = Number(minInput.value);
            const maxVal = Number(maxInput.value);

            // 값이 비어 있거나 범위 이상/이하
            if (isNaN(minVal) || isNaN(maxVal)) {
                valid = false;
                messages.push(`서브 이미지 ${index+1}의 HP 범위를 모두 입력해주세요.`);
            } else if (minVal < 0 || maxVal > 100 || minVal > maxVal) {
                valid = false;
                messages.push(`서브 이미지 ${index+1}의 HP 범위가 잘못되었습니다 (0~100).`);
            }
        });

        if (!valid) {
            e.preventDefault();
            alert(messages.join('\n'));
            return false;
        }

    });

    // 서브 이미지 추가 시 자동 번호 갱신 (선택)
    addSubImageBtn?.addEventListener('click', () => {
        const entries = document.querySelectorAll('.sub-image-entry');
        entries.forEach((entry, idx) => {
            entry.querySelector('.sub-image-number').textContent = idx + 1;
        });
    });

});