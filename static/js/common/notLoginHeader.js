        // Mobile Menu Toggle
        function toggleMobile() {
            const menu = document.getElementById('mobileMenu');
            menu.classList.toggle('active');
        }

        // // Close mobile menu when clicking outside
        // document.addEventListener('click', function(e) {
        //     const menu = document.getElementById('mobileMenu');
        //     const toggle = document.querySelector('.mobile-toggle');
        //     const header = document.getElementById('header');
            
        //     if (!header.contains(e.target)) {
        //         menu.classList.remove('active');
        //     }
        // });

        // Theme Toggle - base.html의 전역 함수 사용
        const themeToggle = document.getElementById('themeToggle');

        if (themeToggle) {
            // 현재 테마에 맞게 아이콘 설정
            const savedTheme = localStorage.getItem('theme');
            themeToggle.textContent = savedTheme === 'light' ? '☀️' : '🌙';

            // 클릭 시 전역 toggleTheme 함수 호출
            themeToggle.addEventListener('click', () => {
                if (window.toggleTheme) {
                    window.toggleTheme();
                }
            });
        }

        // Header scroll effect
        window.addEventListener('scroll', () => {
            const header = document.getElementById('header');
            if (window.scrollY > 50) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
        });

        // Search input focus effect
        const searchInput = document.querySelector('.search-input');
        searchInput.addEventListener('focus', () => {
            searchInput.parentElement.style.transform = 'scale(1.02)';
        });
        searchInput.addEventListener('blur', () => {
            searchInput.parentElement.style.transform = 'scale(1)';
        });

        // Smooth scroll
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            });
        });


// 로그인 카드

function openLogin() {
    const modalHTML = `
    <div id="login-modal">
        <div class="modal-overlay" onclick="closeLogin()"></div>
        <div class="modal-content">
            <button class="close-btn" onclick="closeLogin()">X</button>
            <div id="login-container"></div>
        </div>
    </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    fetch('/login/')  // URL 패턴에 맞게 수정
        .then(res => res.text())
        .then(html => {
            document.getElementById('login-container').innerHTML = html;
        });
}

function closeLogin() {
    const modal = document.getElementById('login-modal');
    if (modal) modal.remove();
}



document.getElementById("searchBtn").addEventListener("click", () => {
    const q = document.getElementById("searchInput").value.trim();
    if (q) window.location.href = `/search/?q=${encodeURIComponent(q)}`;
});

document.getElementById("searchInput").addEventListener("keyup", (e) => {
    if (e.key === "Enter") {
        const q = e.target.value.trim();
        if (q) window.location.href = `/search/?q=${encodeURIComponent(q)}`;
    }
});


