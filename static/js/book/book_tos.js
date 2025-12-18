// 이용약관 페이지 스크립트
document.addEventListener('DOMContentLoaded', function() {
    
    // 부드러운 스크롤 효과
    document.querySelectorAll('.toc-list a').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                const headerOffset = 100;
                const elementPosition = targetElement.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });

                // 활성 링크 표시
                document.querySelectorAll('.toc-list a').forEach(link => {
                    link.style.background = '';
                    link.style.borderLeftColor = 'transparent';
                    link.style.color = 'var(--text-secondary)';
                });

                this.style.background = 'rgba(99, 102, 241, 0.1)';
                this.style.borderLeftColor = 'var(--primary)';
                this.style.color = 'var(--text)';
            }
        });
    });

    // 스크롤 시 현재 섹션 하이라이트
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute('id');
                const correspondingLink = document.querySelector(`.toc-list a[href="#${id}"]`);
                
                if (correspondingLink) {
                    document.querySelectorAll('.toc-list a').forEach(link => {
                        link.style.background = '';
                        link.style.borderLeftColor = 'transparent';
                        link.style.color = 'var(--text-secondary)';
                    });

                    correspondingLink.style.background = 'rgba(99, 102, 241, 0.1)';
                    correspondingLink.style.borderLeftColor = 'var(--primary)';
                    correspondingLink.style.color = 'var(--text)';
                }
            }
        });
    }, {
        rootMargin: '-100px 0px -66% 0px'
    });

    // 모든 article 관찰
    document.querySelectorAll('.terms-article').forEach(article => {
        observer.observe(article);
    });

    // 인쇄 기능 (선택사항)
    const printBtn = document.getElementById('print-terms');
    if (printBtn) {
        printBtn.addEventListener('click', function() {
            window.print();
        });
    }

    // 맨 위로 버튼 (선택사항)
    const scrollToTopBtn = document.getElementById('scroll-to-top');
    if (scrollToTopBtn) {
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) {
                scrollToTopBtn.style.display = 'flex';
            } else {
                scrollToTopBtn.style.display = 'none';
            }
        });

        scrollToTopBtn.addEventListener('click', function() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
});