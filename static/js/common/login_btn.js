
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

