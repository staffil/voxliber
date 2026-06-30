/* VoxTour — lightweight UI tour helper */
const VoxTour = (() => {
    let _steps = [];
    let _idx   = 0;
    let _overlay, _box, _title, _desc, _counter, _prevBtn, _nextBtn;

    function _build() {
        if (document.getElementById('vox-tour-box')) return;

        // 투명 클릭 차단 오버레이 (dim은 highlight box-shadow가 담당)
        _overlay = document.createElement('div');
        _overlay.id = 'vox-tour-overlay';
        _overlay.addEventListener('click', e => { if (e.target === _overlay) VoxTour.end(); });
        document.body.appendChild(_overlay);

        // 툴팁 박스 (오버레이와 별도 element → z-index 자유)
        _box = document.createElement('div');
        _box.id = 'vox-tour-box';
        _box.innerHTML = `
<button id="vox-tour-close" aria-label="닫기">&times;</button>
<div id="vox-tour-counter"></div>
<div id="vox-tour-title"></div>
<div id="vox-tour-desc"></div>
<div id="vox-tour-nav">
  <button id="vox-tour-prev">‹ 이전</button>
  <button id="vox-tour-next">다음 ›</button>
</div>`;
        document.body.appendChild(_box);

        _title    = document.getElementById('vox-tour-title');
        _desc     = document.getElementById('vox-tour-desc');
        _counter  = document.getElementById('vox-tour-counter');
        _prevBtn  = document.getElementById('vox-tour-prev');
        _nextBtn  = document.getElementById('vox-tour-next');

        document.getElementById('vox-tour-close').onclick = () => VoxTour.end();
        _prevBtn.onclick = () => VoxTour.go(_idx - 1);
        _nextBtn.onclick = () => VoxTour.go(_idx + 1);
        document.addEventListener('keydown', _onKey);
    }

    function _onKey(e) {
        if (!_overlay || !_overlay.classList.contains('active')) return;
        if (e.key === 'Escape')     VoxTour.end();
        if (e.key === 'ArrowRight') VoxTour.go(_idx + 1);
        if (e.key === 'ArrowLeft')  VoxTour.go(_idx - 1);
    }

    function _clearHighlight() {
        document.querySelectorAll('.vox-tour-highlight').forEach(el => el.classList.remove('vox-tour-highlight'));
    }

    function _show(idx) {
        _idx = Math.max(0, Math.min(idx, _steps.length - 1));
        const step = _steps[_idx];

        _title.textContent   = step.title || '';
        _desc.innerHTML      = step.desc  || '';
        _counter.textContent = `${_idx + 1} / ${_steps.length}`;
        _prevBtn.disabled    = _idx === 0;
        _nextBtn.textContent = _idx === _steps.length - 1 ? '닫기' : '다음 ›';

        _clearHighlight();

        const target = step.sel ? document.querySelector(step.sel) : null;
        _overlay.classList.add('active');
        _box.classList.add('active');

        if (target) {
            target.classList.add('vox-tour-highlight');
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
            // scroll이 끝난 후 위치 계산 (smooth scroll ~300ms)
            setTimeout(() => _positionBox(target), 350);
        } else {
            // target 없으면 중앙에
            _box.style.top    = '50%';
            _box.style.left   = '50%';
            _box.style.transform = 'translate(-50%, -50%)';
        }
    }

    function _positionBox(target) {
        _box.style.transform = '';
        const tr = target.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const bw = _box.offsetWidth  || 300;
        const bh = _box.offsetHeight || 200;
        const gap = 16;

        // 아래에 충분한 공간이 있으면 아래, 없으면 위
        let top = tr.bottom + gap < vh - bh - 8
            ? tr.bottom + gap
            : tr.top   - bh - gap;
        if (top < 8) top = 8;

        let left = tr.left + tr.width / 2 - bw / 2;
        left = Math.max(12, Math.min(left, vw - bw - 12));

        _box.style.top  = top  + 'px';
        _box.style.left = left + 'px';
    }

    return {
        startTour(steps, startIdx) {
            _steps = steps || [];
            if (!_steps.length) return;
            // 열려있는 가이드 모달/패널 모두 닫기
            const views = ['audioBookGuideView'];
            views.forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
            ['guideModal'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.remove('active'); });
            ['voxGuidePanelOverlay'].forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
            _build();
            _show(startIdx || 0);
        },
        go(idx) {
            if (idx >= _steps.length) { VoxTour.end(); return; }
            if (idx < 0) return;
            _show(idx);
        },
        end() {
            if (_overlay) _overlay.classList.remove('active');
            if (_box)     _box.classList.remove('active');
            _clearHighlight();
        }
    };
})();

/* toggleGuideDetail — collapsible DB guide items */
function toggleGuideDetail(el) {
    const detail  = el.querySelector('.guide-detail');
    const chevron = el.querySelector('.guide-chevron');
    if (!detail) return;
    const isOpen = el.classList.toggle('open');
    detail.style.display = isOpen ? 'block' : 'none';
    if (chevron) chevron.style.transform = isOpen ? 'rotate(180deg)' : '';
}
