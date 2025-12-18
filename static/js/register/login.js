// Social button click handlers (예시)
document.querySelectorAll('.social-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const provider = this.querySelector('span').textContent;
        console.log(`${provider} 로그인 시도`);
        // 실제 로그인 로직은 여기에 구현
    });
});

