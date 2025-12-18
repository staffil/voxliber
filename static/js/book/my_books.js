document.addEventListener('DOMContentLoaded', function() {
    const deleteModal = document.getElementById('deleteModal');
    const deleteBookName = document.getElementById('deleteBookName');
    const confirmDeleteBtn = document.getElementById('confirmDelete');
    const cancelDeleteBtn = document.getElementById('cancelDelete');
    const deleteBtns = document.querySelectorAll('.btn-delete');

    let bookIdToDelete = null;

    // 삭제 버튼 클릭
    deleteBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            bookIdToDelete = this.dataset.bookId;
            const bookName = this.dataset.bookName;

            deleteBookName.textContent = bookName;
            deleteModal.classList.add('active');
        });
    });

    // 취소 버튼
    cancelDeleteBtn.addEventListener('click', function() {
        deleteModal.classList.remove('active');
        bookIdToDelete = null;
    });

    // 모달 배경 클릭
    deleteModal.addEventListener('click', function(e) {
        if (e.target === deleteModal) {
            deleteModal.classList.remove('active');
            bookIdToDelete = null;
        }
    });

    // 삭제 확인 버튼
    confirmDeleteBtn.addEventListener('click', async function() {
        if (!bookIdToDelete) return;

        try {
            const response = await fetch(`/book/delete/${bookIdToDelete}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                }
            });

            if (response.ok) {
                showNotification('작품이 삭제되었습니다', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                showNotification('삭제 중 오류가 발생했습니다', 'error');
            }
        } catch (error) {
            console.error('Delete error:', error);
            showNotification('삭제 중 오류가 발생했습니다', 'error');
        }

        deleteModal.classList.remove('active');
        bookIdToDelete = null;
    });

    // CSRF 토큰 가져오기
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});

// 알림 표시 함수
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        padding: 16px 24px;
        background: ${type === 'success' ? 'rgba(16, 185, 129, 0.9)' : type === 'error' ? 'rgba(239, 68, 68, 0.9)' : 'rgba(99, 102, 241, 0.9)'};
        color: white;
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        z-index: 10000;
        animation: slideInRight 0.3s ease;
        font-size: 14px;
        font-weight: 500;
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// CSS 애니메이션 추가
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
