// Story Detail Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // 카드 호버 효과 강화
    const cards = document.querySelectorAll('.character-card');

    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-4px)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    // 출시 버튼 확인 다이얼로그
    const publishForm = document.querySelector('.publish-ready form');
    if (publishForm) {
        publishForm.addEventListener('submit', function(e) {
            if (!confirm('스토리를 출시하시겠습니까?\n출시 후에는 다른 사용자들이 이 스토리를 볼 수 있습니다.')) {
                e.preventDefault();
            }
        });
    }
});
