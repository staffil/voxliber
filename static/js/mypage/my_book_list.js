const deleteModal = document.getElementById('deleteModal');
const deleteBookName = document.getElementById('deleteBookName');
const confirmDeleteBtn = document.getElementById('confirmDelete');
const cancelDeleteBtn = document.getElementById('cancelDelete');

let bookIdToDelete = null;

document.querySelectorAll('.mbl-act-delete').forEach(btn => {
  btn.addEventListener('click', function() {
    bookIdToDelete = this.dataset.bookId;
    deleteBookName.textContent = this.dataset.bookName;
    deleteModal.style.display = 'flex';
  });
});

cancelDeleteBtn.addEventListener('click', closeModal);
deleteModal.addEventListener('click', e => { if (e.target === deleteModal) closeModal(); });

function closeModal() {
  deleteModal.style.display = 'none';
  bookIdToDelete = null;
}

confirmDeleteBtn.addEventListener('click', async function() {
  if (!bookIdToDelete) return;
  try {
    const res = await fetch(`/book/delete/${bookIdToDelete}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    });
    if (res.ok) {
      closeModal();
      setTimeout(() => location.reload(), 300);
    } else {
      alert('삭제 중 오류가 발생했습니다');
    }
  } catch {
    alert('요청 실패');
  }
});

function getCookie(name) {
  const m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
  return m ? decodeURIComponent(m[1]) : null;
}
