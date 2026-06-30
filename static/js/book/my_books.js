function deleteBook(uuid, name) {
  document.getElementById('deleteBookName').textContent = '"' + name + '"';
  document.getElementById('deleteForm').action = '/book/delete/' + uuid + '/';
  document.getElementById('deleteModal').style.display = 'flex';
}
function closeDeleteModal() {
  document.getElementById('deleteModal').style.display = 'none';
}