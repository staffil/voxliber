function toggleNotice(id) {
  var body = document.getElementById('notice-' + id);
  var arrow = document.getElementById('arrow-' + id);
  var open = body.classList.toggle('open');
  if (arrow) arrow.style.transform = open ? 'rotate(180deg)' : '';
}