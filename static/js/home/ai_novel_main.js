let currentSlide = 0;
const slides = document.querySelectorAll('.ad-slide');
const totalSlides = slides.length;

function showSlide(index) {
  slides.forEach((slide, i) => {
    slide.classList.toggle('active', i === index);
  });
}

function nextSlide() {
  currentSlide = (currentSlide + 1) % totalSlides;
  showSlide(currentSlide);
}

function prevSlide() {
  currentSlide = (currentSlide - 1 + totalSlides) % totalSlides;
  showSlide(currentSlide);
}

// 자동 슬라이드 (5초마다)
if (totalSlides > 1) {
  setInterval(nextSlide, 5000);
}

// 초기 슬라이드 표시
showSlide(currentSlide);