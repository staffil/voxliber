// =====================================================
// 기본 기능
// =====================================================
document.getElementById('avatarInput').addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        if (file.size > 5 * 1024 * 1024) { alert('파일 크기는 5MB 이하여야 합니다.'); this.value = ''; return; }
        const reader = new FileReader();
        reader.onload = function(e) { document.getElementById('avatarPreview').src = e.target.result; };
        reader.readAsDataURL(file);
        document.getElementById('removeAvatarInput').value = 'false';
    }
});

document.getElementById('nickname').addEventListener('input', function() {
    const count = this.value.length;
    document.getElementById('nicknameCount').textContent = count;
    if (count > 20) { this.value = this.value.substring(0, 20); document.getElementById('nicknameCount').textContent = 20; }
});

document.getElementById('profileForm').addEventListener('submit', function(e) {
    const nickname = document.getElementById('nickname').value.trim();
    if (!nickname) { e.preventDefault(); alert('닉네임을 입력해주세요.'); document.getElementById('nickname').focus(); return false; }
});

const deleteModal = document.getElementById('deleteModal');
const deleteBookName = document.getElementById('deleteBookName');
const confirmDeleteBtn = document.getElementById('confirmDelete');
const cancelDeleteBtn = document.getElementById('cancelDelete');
let bookIdToDelete = null;

document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', function() {
        bookIdToDelete = this.dataset.bookId;
        deleteBookName.textContent = this.dataset.bookName;
        deleteModal.classList.add('active');
    });
});
cancelDeleteBtn.addEventListener('click', function() { deleteModal.classList.remove('active'); bookIdToDelete = null; });
deleteModal.addEventListener('click', function(e) { if (e.target === deleteModal) { deleteModal.classList.remove('active'); bookIdToDelete = null; } });
confirmDeleteBtn.addEventListener('click', async function() {
    if (!bookIdToDelete) return;
    try {
        const response = await fetch(`/book/delete/${bookIdToDelete}/`, { method: 'POST', headers: { 'X-CSRFToken': getCookie('csrftoken') } });
        if (response.ok) { showNotification('작품이 삭제되었습니다', 'success'); setTimeout(() => window.location.reload(), 1000); }
        else showNotification('삭제 중 오류가 발생했습니다', 'error');
    } catch (error) { showNotification('삭제 중 오류가 발생했습니다', 'error'); }
    deleteModal.classList.remove('active'); bookIdToDelete = null;
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) { cookieValue = decodeURIComponent(cookie.substring(name.length + 1)); break; }
        }
    }
    return cookieValue;
}

function showNotification(message, type = 'info') {
    const n = document.createElement('div');
    n.style.cssText = `position:fixed;top:100px;right:20px;padding:16px 24px;
        background:${type==='success'?'rgba(16,185,129,0.9)':type==='error'?'rgba(239,68,68,0.9)':'rgba(99,102,241,0.9)'};
        color:white;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.3);z-index:10000;
        animation:slideInRight 0.3s ease;font-size:14px;font-weight:500;`;
    n.textContent = message;
    document.body.appendChild(n);
    setTimeout(() => { n.style.animation = 'slideOutRight 0.3s ease'; setTimeout(() => n.remove(), 300); }, 3000);
}

const animStyle = document.createElement('style');
animStyle.textContent = `
    @keyframes slideInRight { from { transform:translateX(400px); opacity:0; } to { transform:translateX(0); opacity:1; } }
    @keyframes slideOutRight { from { transform:translateX(0); opacity:1; } to { transform:translateX(400px); opacity:0; } }
`;
document.head.appendChild(animStyle);


// =====================================================
// 활동 통계 차트 (일/월/연도 탭)
// =====================================================
const ALL_DATA = window.VOXLIBER_CHART_DATA || {};

const PERIOD_META = {
    daily:   { label: '최근 30일', ttsUnit: '분',  listeningUnit: '분' },
    monthly: { label: '최근 12개월', ttsUnit: '분', listeningUnit: '시간' },
    yearly:  { label: '전체 연도별', ttsUnit: '시간', listeningUnit: '시간' },
};

const scaleOpts = {
    x: { grid: { color: 'rgba(0,0,0,0.06)' }, ticks: { color: '#999', maxRotation: 45, minRotation: 0 } },
    y: { grid: { color: 'rgba(0,0,0,0.06)' }, ticks: { color: '#999' } }
};

// 차트 인스턴스 생성
const ttsChart = new Chart(document.getElementById('ttsChart'), {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'TTS', data: [], backgroundColor: 'rgba(99,102,241,0.7)', borderRadius: 6 }] },
    options: { plugins: { legend: { display: false } }, scales: scaleOpts, animation: { duration: 300 } }
});

const listeningChart = new Chart(document.getElementById('listeningChart'), {
    type: 'bar',
    data: { labels: [], datasets: [{ label: '청취', data: [], backgroundColor: 'rgba(139,92,246,0.7)', borderRadius: 6 }] },
    options: { plugins: { legend: { display: false } }, scales: scaleOpts, animation: { duration: 300 } }
});

function updateCharts(period) {
    const d = ALL_DATA[period];
    const meta = PERIOD_META[period];

    // TTS
    ttsChart.data.labels = d.tts.labels;
    ttsChart.data.datasets[0].data = d.tts.data;
    ttsChart.update();
    document.getElementById('ttsLabel').textContent = `📝 TTS 생성 (${meta.ttsUnit})`;

    // 청취
    listeningChart.data.labels = d.listening.labels;
    listeningChart.data.datasets[0].data = d.listening.data;
    listeningChart.update();
    document.getElementById('listeningLabel').textContent = `🎧 청취 시간 (${meta.listeningUnit})`;

    // 기간 설명
    document.getElementById('chartPeriodLabel').textContent = meta.label;
}

// 탭 클릭 이벤트
document.querySelectorAll('.chart-tab').forEach(btn => {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.chart-tab').forEach(b => {
            b.style.background = 'transparent';
            b.style.color = '#888';
            b.style.borderColor = '#ddd';
            b.classList.remove('active');
        });
        this.style.background = 'rgba(99,102,241,0.8)';
        this.style.color = '#fff';
        this.style.borderColor = 'rgba(99,102,241,0.6)';
        this.classList.add('active');
        updateCharts(this.dataset.period);
    });
});

// 초기 렌더 (일별)
updateCharts('daily');