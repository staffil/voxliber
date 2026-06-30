var currentSnip = null;
function playSnippet(id) {
  var audio = document.getElementById('snip-audio-' + id);
  if (!audio) return;
  if (currentSnip && currentSnip !== id) {
    var prev = document.getElementById('snip-audio-' + currentSnip);
    if (prev) { prev.pause(); prev.currentTime = 0; setPlayIcon(currentSnip, false); }
  }
  if (audio.paused) { audio.play(); currentSnip = id; setPlayIcon(id, true); }
  else { audio.pause(); setPlayIcon(id, false); }

  audio.addEventListener('timeupdate', function() {
    var t = document.getElementById('sptime-' + id);
    if (t) { var s = Math.floor(audio.currentTime); t.textContent = Math.floor(s/60) + ':' + String(s%60).padStart(2,'0'); }
  });
  audio.addEventListener('ended', function() { setPlayIcon(id, false); });
}

function setPlayIcon(id, playing) {
  var btn = document.getElementById('spbtn-' + id);
  if (!btn) return;
  btn.innerHTML = playing
    ? '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>'
    : '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
}