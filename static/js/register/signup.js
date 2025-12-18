// 프로필 이미지 업로드 미리보기
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('user-image');
    const profilePreview = document.getElementById('profile-preview');
    const previewImg = document.getElementById('preview-img');

    // 프로필 이미지 클릭 시 파일 선택
    if (profilePreview) {
        profilePreview.addEventListener('click', function() {
            fileInput.click();
        });
    }

    // 파일 선택 시 미리보기
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(event) {
                    previewImg.src = event.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // 전체 동의 체크박스
    const termsAll = document.getElementById('terms-all');
    const termsRequired = document.querySelectorAll('.terms-required');
    const allCheckboxes = document.querySelectorAll('.checkbox-input:not(#terms-all)');

    if (termsAll) {
        termsAll.addEventListener('change', function() {
            allCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
        });

        // 개별 체크박스 변경 시 전체 동의 상태 업데이트
        allCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                const allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
                termsAll.checked = allChecked;
            });
        });
    }

    // 폼 제출 처리
    const signupForm = document.getElementById('signup-form');
    if (signupForm) {
        signupForm.addEventListener('submit', function(e) {
            // 필수 약관 체크 확인
            const allRequiredChecked = Array.from(termsRequired).every(cb => cb.checked);
            
            if (!allRequiredChecked) {
                e.preventDefault();
                alert('필수 약관에 동의해주세요.');
                return false;
            }

            // 여기에 실제 폼 제출 로직 추가 가능
            // e.preventDefault(); // 테스트 시 주석 해제
        });
    }

    // 입력 필드 애니메이션
    const formInputs = document.querySelectorAll('.form-input');
    formInputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });

        input.addEventListener('blur', function() {
            if (!this.value) {
                this.parentElement.classList.remove('focused');
            }
        });
    });
});