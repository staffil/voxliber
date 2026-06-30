function toggleFaq(questionEl) {
  var item = questionEl.closest('.faq-item');
  var answer = item.querySelector('.faq-answer');
  var open = answer.classList.toggle('open');
  item.classList.toggle('open', open);
}
function filterFaq(cat, btn) {
  document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.faq-item').forEach(item => {
    item.style.display = (cat === 'all' || item.dataset.cat === cat) ? '' : 'none';
  });
}
// Remove duplicate category tabs
var seen = new Set();
document.querySelectorAll('.cat-btn[data-cat]').forEach(btn => {
  var cat = btn.dataset.cat;
  if (seen.has(cat)) btn.remove();
  else seen.add(cat);
});