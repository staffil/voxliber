function showAppInstallModal(event) {
    // 클릭 이벤트 객체가 넘어오면 기본 동작 막기
    if (event) {
        event.preventDefault(); // a 태그 이동 막기
        event.stopPropagation(); // 혹시 상위 이벤트 전파 막기
    }

    // 이미 모달 존재하면 중복 생성 방지
    let existingModal = document.getElementById('dynamicAppModal');
    if (!existingModal) {
        // 모달 HTML 생성
        const modalHtml = `
            <div id="dynamicAppModal" class="app-modal">
                <div class="app-modal-content">
                    <span class="close-modal">&times;</span>
                    <h3>앱에서 전체 기능을 확인하세요!</h3>
                    <p>앱을 설치하고 더 많은 기능과 콘텐츠를 확인할 수 있습니다.</p>
                    <a href="앱스토어_링크" class="install-app-btn">앱 설치하기</a>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        existingModal = document.getElementById('dynamicAppModal');

        // 닫기 버튼
        const closeBtn = existingModal.querySelector('.close-modal');
        closeBtn.addEventListener('click', function() {
            existingModal.style.display = 'none';
        });

        // 모달 외부 클릭 시 닫기
        window.addEventListener('click', function(event) {
            if (event.target === existingModal) {
                existingModal.style.display = 'none';
            }
        });
    }

    // 모달 표시
    existingModal.style.display = 'block';
}
