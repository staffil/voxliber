document.addEventListener("DOMContentLoaded", () => {

  /* ============================================================
     🎯 1. 플레이어 요소를 가져오고 언제든 다시 갱신 가능하게 만드는 함수
  ============================================================ */
  function getPlayerElements() {
    return {
      player: document.getElementById("bottom-audio-player"),
      audio: document.getElementById("miniAudio"),
      bookNameElem: document.getElementById("player-book-name"),
      coverImg: document.getElementById("player-cover-img"),
      coverPlaceholder: document.querySelector(".player-cover-placeholder"),
      closeBtn: document.getElementById("closePlayerBtn"),
      playPauseBtn: document.getElementById("playPauseBtn"),
      playIcon: document.getElementById("playIcon"),
      pauseIcon: document.getElementById("pauseIcon"),
      progressBar: document.getElementById("progressBar"),
      progressHandle: document.getElementById("progressHandle"),
      currentTimeElem: document.getElementById("currentTime"),
      totalTimeElem: document.getElementById("totalTime"),
      progressContainer: document.querySelector(".progress-bar-bg"),
      volumeControl: document.getElementById("volumeControl"),
      nextBtn: document.getElementById("nextBtn"),
      prevBtn: document.getElementById("prevBtn"),
    };
  }

  let $ = getPlayerElements(); // 초기 캐싱

  /* ============================================================
     🎯 2. 플레이어 UI 업데이트 함수 (버튼, 진행바 등)
  ============================================================ */

  function attachPlayerEvents() {
    $ = getPlayerElements(); // 최신 요소 다시 가져오기 (AJAX 이후 대비)

    if (!$ || !$.audio) return;

    /* 🔹 재생 / 일시정지 버튼 */
    if ($.playPauseBtn) {
      $.playPauseBtn.onclick = () => {
        if ($.audio.paused) $.audio.play();
        else $.audio.pause();
      };
    }

    /* 🔹 재생 상태 UI */
    $.audio.onplay = () => {
      $.playIcon.style.display = "none";
      $.pauseIcon.style.display = "block";
    };
    $.audio.onpause = () => {
      $.playIcon.style.display = "block";
      $.pauseIcon.style.display = "none";
    };

    /* 🔹 메타데이터 로드 후 총시간 표시 */
    $.audio.onloadedmetadata = () => {
      $.totalTimeElem.textContent = formatTime($.audio.duration);
    };

    /* 🔹 진행바 업데이트 */
    $.audio.ontimeupdate = () => {
      if (!$.audio.duration) return;
      const percent = ($.audio.currentTime / $.audio.duration) * 100;
      $.progressBar.style.width = percent + "%";
      $.progressHandle.style.left = percent + "%";
      $.currentTimeElem.textContent = formatTime($.audio.currentTime);
    };

    /* 🔹 진행바 클릭 이동 */
    if ($.progressContainer) {
      $.progressContainer.onclick = (e) => {
        const rect = $.progressContainer.getBoundingClientRect();
        const percent = (e.clientX - rect.left) / rect.width;
        $.audio.currentTime = percent * $.audio.duration;
      };
    }

    /* 🔹 10초 뒤로, 10초 앞으로 */
    if ($.nextBtn) {
      $.nextBtn.onclick = () => {
        $.audio.currentTime = Math.min($.audio.currentTime + 10, $.audio.duration);
      };
    }
    if ($.prevBtn) {
      $.prevBtn.onclick = () => {
        $.audio.currentTime = Math.max($.audio.currentTime - 10, 0);
      };
    }

    /* 🔹 볼륨 조절 */
    if ($.volumeControl) {
      $.volumeControl.oninput = () => {
        $.audio.volume = $.volumeControl.value / 100;
      };
    }

    /* 🔹 플레이어 닫기 */
    if ($.closeBtn) {
      $.closeBtn.onclick = () => {
        $.audio.pause();
        $.audio.currentTime = 0;
        $.player.classList.add("hidden");
      };
    }
  }

  // 즉시 적용
  attachPlayerEvents();


  /* ============================================================
     🎯 3. 프리뷰 버튼 (동적 요소 포함) - Event delegation
  ============================================================ */
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".preview-audio-btn");
    if (!btn) return;

    e.preventDefault();

    $ = getPlayerElements();

    $.audio.src = btn.dataset.audio;
    $.bookNameElem.textContent = btn.dataset.title;

    if (btn.dataset.cover) {
      $.coverImg.src = btn.dataset.cover;
      $.coverImg.style.display = "block";
      $.coverPlaceholder.style.display = "none";
    } else {
      $.coverImg.style.display = "none";
      $.coverPlaceholder.style.display = "flex";
    }

    $.player.classList.remove("hidden");
    $.audio.play();

    attachPlayerEvents(); // 새 UI 바인딩
  });


  /* ============================================================
     🎯 4. AJAX 장르 필터 → 책 목록 렌더링 (네 코드 유지, 안정화만 함)
  ============================================================ */

  const filterBtns = document.querySelectorAll('.genre-filter-btn');
  const genreBooksContainer = document.getElementById('genreBooks');
  const filterUrl = genreBooksContainer?.dataset.filterUrl || '/filter-books/';

  filterBtns.forEach(btn => {
    btn.addEventListener("click", async function () {

      filterBtns.forEach(b => b.classList.remove("active"));
      this.classList.add("active");

      const genreId = this.dataset.genreId;

      try {
        const url = genreId ? `${filterUrl}?genre_id=${genreId}` : filterUrl;
        const res = await fetch(url);
        const data = await res.json();

        genreBooksContainer.innerHTML = data.books?.length
          ? data.books.map(book => renderBookHTML(book)).join("")
          : `<div class="empty-state">해당 장르의 작품이 없습니다</div>`;

        attachPlayerEvents(); // 🔥 필터 후 다시 플레이어 연결
      } catch (err) {
        console.error("장르 필터 오류:", err);
        genreBooksContainer.innerHTML = `<div class="empty-state">오류가 발생했습니다</div>`;
      }
    });
  });

  function renderBookHTML(book) {
    return `
      <div class="book-item-wrapper">
        <a href="/book/detail/${book.id}/" class="book-item">
          <div class="book-cover-wrapper">
            ${book.cover_img
              ? `<img src="${book.cover_img}" alt="${book.name}">`
              : `<div class="book-placeholder">${book.name.slice(0, 2)}</div>`}
          </div>
          <div class="book-details">
            <h3>${book.name}</h3>
            <p class="book-meta">
              ${book.genres.slice(0, 2).map(g => g.name).join(', ')}
              • ${book.contents_count}화
            </p>
          </div>
        </a>
        ${book.audio_file
          ? `<button class="preview-audio-btn grid-preview"
               data-audio="${book.audio_file}"
               data-title="${book.name}"
               data-cover="${book.cover_img || ''}">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
              </svg>
            </button>`
          : ""}
      </div>`;
  }

  /* ============================================================
     🎯 5. 시간 표시 포맷
  ============================================================ */
  function formatTime(seconds) {
    if (!seconds) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  }

});


/* ============================================================
   🎯 광고 배너 슬라이더 - Enhanced Version
============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  const slider = document.querySelector('.promo-container');
  const indicators = document.querySelectorAll('.promo-indicators .indicator');
  const banners = document.querySelectorAll('.promo-banner');
  const prevBtn = document.getElementById('promoPrev');
  const nextBtn = document.getElementById('promoNext');
  const playPauseBtn = document.getElementById('promoPlayPause');
  const playIcon = document.getElementById('playIcon');
  const pauseIcon = document.getElementById('pauseIcon');
  const currentSlideElem = document.getElementById('currentSlide');
  const totalSlidesElem = document.getElementById('totalSlides');

  if (!slider || banners.length === 0) return;

  let isDown = false;
  let startX;
  let scrollLeft;
  let autoSlideInterval;
  let isPlaying = true;
  let currentIndex = 0;
  let isScrolling = false; // 스크롤 진행 중 플래그

  // 총 슬라이드 개수 설정
  if (totalSlidesElem) {
    totalSlidesElem.textContent = banners.length;
  }

  // 드래그 이벤트
  slider.addEventListener('mousedown', (e) => {
    isDown = true;
    slider.classList.add('active');
    startX = e.pageX - slider.offsetLeft;
    scrollLeft = slider.scrollLeft;
    if (isPlaying) {
      clearInterval(autoSlideInterval);
    }
  });

  slider.addEventListener('mouseleave', () => {
    isDown = false;
    slider.classList.remove('active');
  });

  slider.addEventListener('mouseup', () => {
    isDown = false;
    slider.classList.remove('active');
    if (isPlaying) {
      startAutoSlide();
    }
  });

  slider.addEventListener('mousemove', (e) => {
    if (!isDown) return;
    e.preventDefault();
    const x = e.pageX - slider.offsetLeft;
    const walk = (x - startX);
    slider.scrollLeft = scrollLeft - walk;
    syncIndexFromScroll();
  });

  // 슬라이드 이동 함수
  function goToSlide(index) {
    if (isScrolling) return; // 스크롤 진행 중이면 무시

    isScrolling = true;
    currentIndex = index;
    const bannerWidth = banners[0].offsetWidth;

    // scrollTo 대신 scrollLeft 직접 설정
    slider.scrollLeft = bannerWidth * index;

    updateIndicator();
    updateCounter();

    // 스크롤 완료 후 플래그 해제
    setTimeout(() => {
      isScrolling = false;
    }, 300);
  }

  // 인디케이터 업데이트
  function updateIndicator() {
    indicators.forEach((dot, i) => {
      dot.classList.toggle('active', i === currentIndex);
    });
  }

  // 스크롤 위치에서 현재 인덱스 동기화
  function syncIndexFromScroll() {
    const bannerWidth = banners[0].offsetWidth;
    const index = Math.round(slider.scrollLeft / bannerWidth);
    if (index !== currentIndex && index >= 0 && index < banners.length) {
      currentIndex = index;
      updateIndicator();
      updateCounter();
    }
  }

  // 카운터 업데이트
  function updateCounter() {
    if (currentSlideElem) {
      currentSlideElem.textContent = currentIndex + 1;
    }
  }

  // 다음 슬라이드
  function nextSlide() {
    currentIndex = (currentIndex + 1) % banners.length;
    goToSlide(currentIndex);
  }

  // 이전 슬라이드
  function prevSlide() {
    currentIndex = (currentIndex - 1 + banners.length) % banners.length;
    goToSlide(currentIndex);
  }

  // 자동 슬라이드
  function startAutoSlide() {
    if (autoSlideInterval) clearInterval(autoSlideInterval);
    autoSlideInterval = setInterval(() => {
      nextSlide();
    }, 4000); // 4초마다
  }

  function stopAutoSlide() {
    if (autoSlideInterval) {
      clearInterval(autoSlideInterval);
      autoSlideInterval = null;
    }
  }

  // 이전 버튼
  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      prevSlide();
      if (isPlaying) {
        stopAutoSlide();
        startAutoSlide();
      }
    });
  }

  // 다음 버튼
  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      nextSlide();
      if (isPlaying) {
        stopAutoSlide();
        startAutoSlide();
      }
    });
  }

  // 일시정지/재생 버튼
  if (playPauseBtn) {
    playPauseBtn.addEventListener('click', () => {
      isPlaying = !isPlaying;

      if (isPlaying) {
        playIcon.style.display = 'none';
        pauseIcon.style.display = 'block';
        playPauseBtn.title = '일시정지';
        startAutoSlide();
      } else {
        playIcon.style.display = 'block';
        pauseIcon.style.display = 'none';
        playPauseBtn.title = '재생';
        stopAutoSlide();
      }
    });
  }

  // 인디케이터 클릭
  indicators.forEach((indicator, index) => {
    indicator.addEventListener('click', () => {
      goToSlide(index);
      if (isPlaying) {
        stopAutoSlide();
        startAutoSlide();
      }
    });
  });

  // 초기화
  startAutoSlide();
  updateIndicator();
  updateCounter();
});

/* ============================================================
   🎯 시 응모작 슬라이더 - Poem Slider
============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  const slider = document.querySelector('.poem-slider');
  const indicators = document.querySelectorAll('.poem-indicators .indicator');
  const slides = document.querySelectorAll('.poem-slide');
  const prevBtn = document.getElementById('poemPrev');
  const nextBtn = document.getElementById('poemNext');
  const playPauseBtn = document.getElementById('poemPlayPause');
  const playIcon = document.getElementById('poemPlayIcon');
  const pauseIcon = document.getElementById('poemPauseIcon');
  const currentSlideElem = document.getElementById('poemCurrentSlide');
  const totalSlidesElem = document.getElementById('poemTotalSlides');

  if (!slider || slides.length === 0) return;

  let isDown = false;
  let startX;
  let scrollLeft;
  let autoSlideInterval;
  let isPlaying = true;
  let currentIndex = 0;
  let isScrolling = false; // 스크롤 진행 중 플래그

  // 총 슬라이드 개수 설정
  if (totalSlidesElem) {
    totalSlidesElem.textContent = slides.length;
  }

  // 드래그 이벤트
  slider.addEventListener('mousedown', (e) => {
    isDown = true;
    slider.classList.add('active');
    startX = e.pageX - slider.offsetLeft;
    scrollLeft = slider.scrollLeft;
    if (isPlaying) {
      clearInterval(autoSlideInterval);
    }
  });

  slider.addEventListener('mouseleave', () => {
    isDown = false;
    slider.classList.remove('active');
  });

  slider.addEventListener('mouseup', () => {
    isDown = false;
    slider.classList.remove('active');
    if (isPlaying) {
      startAutoSlide();
    }
  });

  slider.addEventListener('mousemove', (e) => {
    if (!isDown) return;
    e.preventDefault();
    const x = e.pageX - slider.offsetLeft;
    const walk = (x - startX);
    slider.scrollLeft = scrollLeft - walk;
    syncIndexFromScroll();
  });

  // 슬라이드 이동 함수
  function goToSlide(index) {
    if (isScrolling) return; // 스크롤 진행 중이면 무시

    isScrolling = true;
    currentIndex = index;
    const slideWidth = slides[0].offsetWidth;

    // scrollTo 대신 scrollLeft 직접 설정
    slider.scrollLeft = slideWidth * index;

    updateIndicator();
    updateCounter();

    // 스크롤 완료 후 플래그 해제
    setTimeout(() => {
      isScrolling = false;
    }, 300);
  }

  // 인디케이터 업데이트
  function updateIndicator() {
    indicators.forEach((dot, i) => {
      dot.classList.toggle('active', i === currentIndex);
    });
  }

  // 스크롤 위치에서 현재 인덱스 동기화
  function syncIndexFromScroll() {
    const slideWidth = slides[0].offsetWidth;
    const index = Math.round(slider.scrollLeft / slideWidth);
    if (index !== currentIndex && index >= 0 && index < slides.length) {
      currentIndex = index;
      updateIndicator();
      updateCounter();
    }
  }

  // 카운터 업데이트
  function updateCounter() {
    if (currentSlideElem) {
      currentSlideElem.textContent = currentIndex + 1;
    }
  }

  // 다음 슬라이드
  function nextSlide() {
    currentIndex = (currentIndex + 1) % slides.length;
    goToSlide(currentIndex);
  }

  // 이전 슬라이드
  function prevSlide() {
    currentIndex = (currentIndex - 1 + slides.length) % slides.length;
    goToSlide(currentIndex);
  }

  // 자동 슬라이드
  function startAutoSlide() {
    if (autoSlideInterval) clearInterval(autoSlideInterval);
    autoSlideInterval = setInterval(() => {
      nextSlide();
    }, 5000); // 5초마다
  }

  function stopAutoSlide() {
    if (autoSlideInterval) {
      clearInterval(autoSlideInterval);
      autoSlideInterval = null;
    }
  }

  // 이전 버튼
  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      prevSlide();
      if (isPlaying) {
        stopAutoSlide();
        startAutoSlide();
      }
    });
  }

  // 다음 버튼
  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      nextSlide();
      if (isPlaying) {
        stopAutoSlide();
        startAutoSlide();
      }
    });
  }

  // 일시정지/재생 버튼
  if (playPauseBtn) {
    playPauseBtn.addEventListener('click', () => {
      isPlaying = !isPlaying;

      if (isPlaying) {
        if (playIcon) playIcon.style.display = 'none';
        if (pauseIcon) pauseIcon.style.display = 'block';
        playPauseBtn.title = '일시정지';
        startAutoSlide();
      } else {
        if (playIcon) playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
        playPauseBtn.title = '재생';
        stopAutoSlide();
      }
    });
  }

  // 인디케이터 클릭
  indicators.forEach((indicator, index) => {
    indicator.addEventListener('click', () => {
      goToSlide(index);
      if (isPlaying) {
        stopAutoSlide();
        startAutoSlide();
      }
    });
  });

  // 초기화
  startAutoSlide();
  updateIndicator();
  updateCounter();
});

/* ============================================================
   🎯 Poem Audio Player
============================================================ */
function togglePoemAudio(button) {
  const card = button.closest('.poem-card');
  const audio = card.querySelector('audio');
  const playIcon = button.querySelector('svg path');
  const progressFill = card.querySelector('.poem-audio-bar-fill');
  const timeSpans = card.querySelectorAll('.poem-audio-time span');

  // Stop other poem audios
  document.querySelectorAll('.poem-card audio').forEach(a => {
    if (a !== audio && !a.paused) {
      a.pause();
      a.currentTime = 0;
      const btn = a.closest('.poem-card').querySelector('.poem-audio-player button svg path');
      if (btn) btn.setAttribute('d', 'M8 5v14l11-7z');
    }
  });

  if (audio.paused) {
    audio.play();
    playIcon.setAttribute('d', 'M6 4h4v16H6V4zm8 0h4v16h-4V4z');
  } else {
    audio.pause();
    playIcon.setAttribute('d', 'M8 5v14l11-7z');
  }

  // Update progress
  audio.addEventListener('loadedmetadata', () => {
    timeSpans[1].textContent = formatTime(audio.duration);
  });

  audio.addEventListener('timeupdate', () => {
    const percent = (audio.currentTime / audio.duration) * 100;
    progressFill.style.width = percent + '%';
    timeSpans[0].textContent = formatTime(audio.currentTime);
  });

  audio.addEventListener('ended', () => {
    playIcon.setAttribute('d', 'M8 5v14l11-7z');
    progressFill.style.width = '0%';
    audio.currentTime = 0;
  });
}

/* ============================================================
   🎯 Snippet Audio Player
============================================================ */
function toggleSnippetAudio(button) {
  const card = button.closest('.snippet-card');
  const audio = card.querySelector('audio');
  const playIcon = button.querySelector('svg path');

  // Stop other snippet audios
  document.querySelectorAll('.snippet-card audio').forEach(a => {
    if (a !== audio && !a.paused) {
      a.pause();
      a.currentTime = 0;
      const btn = a.closest('.snippet-card').querySelector('.snippet-audio-player button svg path');
      if (btn) btn.setAttribute('d', 'M8 5v14l11-7z');
    }
  });

  if (audio.paused) {
    audio.play();
    playIcon.setAttribute('d', 'M6 4h4v16H6V4zm8 0h4v16h-4V4z');
  } else {
    audio.pause();
    playIcon.setAttribute('d', 'M8 5v14l11-7z');
  }

  audio.addEventListener('ended', () => {
    playIcon.setAttribute('d', 'M8 5v14l11-7z');
    audio.currentTime = 0;
  });
}

function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}
