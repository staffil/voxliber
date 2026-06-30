/* === VM-GRID DRAG SCROLL === */
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.vm-grid').forEach(function(el) {
    var isDown = false, startX, scrollLeft;
    el.addEventListener('mousedown', function(e) {
      isDown = true; el.style.cursor = 'grabbing';
      startX = e.pageX - el.offsetLeft; scrollLeft = el.scrollLeft; e.preventDefault();
    });
    document.addEventListener('mouseup', function() { if (isDown) { isDown = false; el.style.cursor = ''; } });
    el.addEventListener('mouseleave', function() { isDown = false; el.style.cursor = ''; });
    el.addEventListener('mousemove', function(e) {
      if (!isDown) return;
      var x = e.pageX - el.offsetLeft;
      el.scrollLeft = scrollLeft - (x - startX) * 1.2;
    });
  });
});

/* === HERO BANNER SLIDER === */
(function() {
  const track = document.getElementById('heroBannerTrack');
  const dots  = document.querySelectorAll('.hero-dot');
  if (!track || !dots.length) return;
  let current = 0;
  const total = dots.length;
  let timer = setInterval(nextSlide, 5000);

  function goTo(idx) {
    current = idx;
    track.style.transform = `translateX(-${idx * 100}%)`;
    dots.forEach((d, i) => d.classList.toggle('active', i === idx));
  }

  function nextSlide() { goTo((current + 1) % total); }

  dots.forEach(function(dot) {
    dot.addEventListener('click', function() {
      clearInterval(timer);
      goTo(parseInt(this.dataset.idx));
      timer = setInterval(nextSlide, 5000);
    });
  });
})();

/* === GENRE TABS === */
document.querySelectorAll('.genre-tab').forEach(function(tab) {
  tab.addEventListener('click', function() {
    document.querySelectorAll('.genre-tab').forEach(t => t.classList.remove('active'));
    this.classList.add('active');
    const idx = this.dataset.genreIdx;
    document.querySelectorAll('.genre-panel').forEach(function(panel) {
      panel.style.display = 'none';
    });
    const target = document.getElementById('genrePanel' + idx);
    if (target) target.style.display = '';
  });
});

/* === SNIPPET PLAYER === */
let activeSnippetAudio = null;
function playSnippet(btn, url) {
  if (activeSnippetAudio) {
    activeSnippetAudio.pause();
    activeSnippetAudio = null;
    document.querySelectorAll('.snippet-play-btn').forEach(function(b) {
      b.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> 재생';
    });
  }
  const audio = new Audio(url);
  audio.play();
  activeSnippetAudio = audio;
  btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> 정지';
  audio.onended = function() {
    btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> 재생';
    activeSnippetAudio = null;
  };
}

/* === DEMO PLAYER === */
var demoAudio = document.getElementById('demoAudio');
var demoPlaying = false;
function toggleDemoPlay() {
  if (!demoAudio) return;
  if (demoPlaying) {
    demoAudio.pause();
    demoPlaying = false;
    document.getElementById('demoPlayIcon').innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
  } else {
    demoAudio.play();
    demoPlaying = true;
    document.getElementById('demoPlayIcon').innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
  }
}
if (demoAudio) {
  demoAudio.addEventListener('timeupdate', function() {
    if (!demoAudio.duration) return;
    const pct = (demoAudio.currentTime / demoAudio.duration) * 100;
    document.getElementById('demoProgressFill').style.width = pct + '%';
  });
  demoAudio.addEventListener('ended', function() {
    demoPlaying = false;
    document.getElementById('demoPlayIcon').innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
    document.getElementById('demoProgressFill').style.width = '0%';
  });
  var track = document.getElementById('demoProgressTrack');
  if (track) {
    track.addEventListener('click', function(e) {
      const rect = this.getBoundingClientRect();
      const pct = (e.clientX - rect.left) / rect.width;
      demoAudio.currentTime = pct * demoAudio.duration;
    });
  }
}