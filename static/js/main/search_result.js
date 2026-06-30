function showTab(id, btn) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.result-tab').forEach(b => b.classList.remove('active'));
  var el = document.getElementById('tab-' + id);
  if (el) el.classList.add('active');
  btn.classList.add('active');
}