/* ===== BOOK DETAIL ===== */

/* ── 북마크 ── */
function toggleBookmark(bookUuid) {
  var token = getCookie('csrftoken');
  fetch('/book/bookmark/' + bookUuid + '/toggle/', {
    method: 'POST',
    headers: { 'X-CSRFToken': token, 'Content-Type': 'application/json' }
  }).then(function(r) { return r.json(); }).then(function(data) {
    if (data.success) {
      var btn  = document.getElementById('bookmarkBtn');
      var txt  = document.getElementById('bookmarkText');
      var icon = document.getElementById('bookmarkIcon');
      if (data.bookmarked) {
        btn && btn.classList.add('bookmarked');
        if (txt) txt.textContent = '저장됨';
        if (icon) icon.setAttribute('fill', 'currentColor');
      } else {
        btn && btn.classList.remove('bookmarked');
        if (txt) txt.textContent = '북마크';
        if (icon) icon.setAttribute('fill', 'none');
      }
    }
  });
}

/* ── 공유 ── */
function shareBook() {
  if (navigator.share) {
    navigator.share({ title: document.title, url: location.href });
  } else {
    navigator.clipboard.writeText(location.href).then(function() {
      alert('링크가 복사되었습니다.');
    });
  }
}

/* ── 공지 폼 토글 ── */
function toggleAnnouncementForm() {
  var form = document.getElementById('announcementForm');
  if (!form) return;
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

/* ── 별점 입력 (hidden input 연동) ── */
document.addEventListener('DOMContentLoaded', function() {
  var container = document.getElementById('starRating');
  if (!container) return;
  var stars = container.querySelectorAll('.star');
  var hidden = document.getElementById('ratingHidden');
  var userRating = parseInt(container.dataset.userRating || '5', 10);

  function paintStars(n) {
    stars.forEach(function(s, i) {
      s.classList.toggle('selected', i < n);
      s.textContent = i < n ? '★' : '☆';
    });
  }

  paintStars(userRating);

  stars.forEach(function(star) {
    star.addEventListener('mouseover', function() { paintStars(parseInt(star.dataset.rating)); });
    star.addEventListener('mouseleave', function() { paintStars(userRating); });
    star.addEventListener('click', function() {
      userRating = parseInt(star.dataset.rating);
      paintStars(userRating);
      container.dataset.userRating = userRating;
      if (hidden) hidden.value = userRating;
    });
  });
});

/* ── 리뷰 제출 (form POST) ── */
function submitReview() {
  var textarea = document.getElementById('reviewText');
  var hidden   = document.getElementById('ratingHidden');
  if (!textarea) return;
  var url = textarea.dataset.submitUrl;
  if (!url) return;
  var form = document.createElement('form');
  form.method = 'POST';
  form.action = url;
  var addHidden = function(n, v) {
    var i = document.createElement('input');
    i.type = 'hidden'; i.name = n; i.value = v;
    form.appendChild(i);
  };
  addHidden('csrfmiddlewaretoken', getCookie('csrftoken'));
  addHidden('rating', hidden ? hidden.value : '5');
  addHidden('review_text', textarea.value);
  document.body.appendChild(form);
  form.submit();
}

/* ── 댓글 제출 (form POST) ── */
function submitComment() {
  var textarea = document.getElementById('commentInput');
  if (!textarea) return;
  var url = textarea.dataset.submitUrl;
  if (!url) return;
  var form = document.createElement('form');
  form.method = 'POST';
  form.action = url;
  var addHidden = function(n, v) {
    var i = document.createElement('input');
    i.type = 'hidden'; i.name = n; i.value = v;
    form.appendChild(i);
  };
  addHidden('csrfmiddlewaretoken', getCookie('csrftoken'));
  addHidden('comment', textarea.value);
  document.body.appendChild(form);
  form.submit();
}

/* ── 답글 폼 토글 ── */
function toggleReplyForm(commentId) {
  var form = document.getElementById('reply-form-' + commentId);
  if (!form) return;
  var isOpen = form.style.display !== 'none';
  form.style.display = isOpen ? 'none' : 'block';
  if (!isOpen) {
    var input = document.getElementById('reply-input-' + commentId);
    if (input) input.focus();
  }
}

/* ── 답글 제출 ── */
function submitReply(commentId, url) {
  var input = document.getElementById('reply-input-' + commentId);
  if (!input || !input.value.trim()) return;
  var realId = commentId.replace(/^bd-/, '').replace(/^cd-/, '');
  var form = document.createElement('form');
  form.method = 'POST';
  form.action = url;
  var addHidden = function(n, v) {
    var i = document.createElement('input');
    i.type = 'hidden'; i.name = n; i.value = v;
    form.appendChild(i);
  };
  addHidden('csrfmiddlewaretoken', getCookie('csrftoken'));
  addHidden('comment', input.value);
  addHidden('parent_id', realId);
  document.body.appendChild(form);
  form.submit();
}

/* ── 섹션 nav 활성화 ── */
document.addEventListener('DOMContentLoaded', function() {
  var navLinks = document.querySelectorAll('.bd-snav-link');
  if (!navLinks.length) return;
  var sections = [];
  navLinks.forEach(function(link) {
    var id = link.getAttribute('href').replace('#', '');
    var el = document.getElementById(id);
    if (el) sections.push({ id: id, el: el, link: link });
  });
  function updateActive() {
    var scrollY = window.scrollY + 80;
    var current = null;
    sections.forEach(function(s) {
      if (s.el.getBoundingClientRect().top + window.scrollY <= scrollY) current = s;
    });
    navLinks.forEach(function(l) { l.classList.remove('active'); });
    if (current) current.link.classList.add('active');
  }
  window.addEventListener('scroll', updateActive, { passive: true });
  updateActive();
});

function getCookie(name) {
  var val = document.cookie.split(';').find(function(c) { return c.trim().startsWith(name + '='); });
  return val ? decodeURIComponent(val.trim().split('=')[1]) : '';
}
