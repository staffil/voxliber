
// Flutter WebView 감지 및 OAuth 리다이렉트
// base.html이 항상 로드하므로 모달/standalone 모두 여기서 정의
function oauthLogin(provider) {
    const ua = navigator.userAgent;
    const isFlutter = ua.includes('VoxLiberApp') ||
                      typeof window.flutter_inappwebview !== 'undefined' ||
                      typeof window.oauthRedirectUri !== 'undefined';

    let url = `/login/oauth/${provider}/`;
    if (isFlutter) {
        const redirectUri = window.oauthRedirectUri || 'voxliber://oauth/callback';
        url += `?redirect_uri=${encodeURIComponent(redirectUri)}`;
    }
    location.href = url;
}

function openLogin() {
    const modalHTML = `
    <div id="login-modal" class="login-modal-context">
        <div class="modal-overlay" onclick="closeLogin()"></div>
        <div class="modal-content">
            <button class="close-btn" onclick="closeLogin()">X</button>
            <div id="login-container"></div>
        </div>
    </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    fetch('/login/')
        .then(res => res.text())
        .then(html => {
            const container = document.getElementById('login-container');
            container.innerHTML = html;

            // innerHTML로 삽입된 <script> 태그는 브라우저가 실행 안 함 → 수동 실행
            container.querySelectorAll('script').forEach(oldScript => {
                const newScript = document.createElement('script');
                if (oldScript.src) {
                    newScript.src = oldScript.src;
                } else {
                    newScript.textContent = oldScript.textContent;
                }
                document.head.appendChild(newScript);
            });
        });
}

function closeLogin() {
    const modal = document.getElementById('login-modal');
    if (modal) modal.remove();
}

