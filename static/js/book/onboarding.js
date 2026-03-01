/**
 * VoxTour — Spotlight Guide System
 * Supports sequential tour (next / close) across all guide pages.
 */
(function () {
    'use strict';

    var _overlay   = null;
    var _spotlight = null;
    var _tooltip   = null;
    var _steps     = [];
    var _idx       = 0;

    /* Remove DOM elements only (keep step state) */
    function _closeUI() {
        if (_overlay)   { _overlay.remove();   _overlay   = null; }
        if (_spotlight) { _spotlight.remove(); _spotlight = null; }
        if (_tooltip)   { _tooltip.remove();   _tooltip   = null; }
    }

    /* Full close — removes DOM + resets tour state */
    function close() {
        _closeUI();
        _steps = [];
        _idx   = 0;
    }

    /**
     * Start a tour from a given step index.
     * @param {Array}  stepsArr  Array of {sel, title, desc} objects
     * @param {number} startIdx  0-based index to start from
     */
    function startTour(stepsArr, startIdx) {
        /* Close any open guide panels */
        var gm = document.getElementById('guideModal');
        if (gm) gm.classList.remove('active');

        var gv = document.getElementById('audioBookGuideView');
        if (gv) gv.style.display = 'none';

        var gp = document.getElementById('voxGuidePanelOverlay');
        if (gp) gp.style.display = 'none';

        _steps = stepsArr || [];
        _idx   = startIdx  || 0;
        _closeUI();
        _showCurrent();
    }

    function _showCurrent() {
        var step = _steps[_idx];
        if (!step) { close(); return; }
        _render(step.sel, step.title, step.desc);
    }

    function _render(selector, title, descHTML) {
        var el = document.querySelector(selector);
        if (!el) {
            /* Skip missing elements */
            if (_idx < _steps.length - 1) { _idx++; _showCurrent(); }
            else close();
            return;
        }

        el.scrollIntoView({ block: 'center', behavior: 'smooth' });

        setTimeout(function () {
            var rect    = el.getBoundingClientRect();
            var pad     = 10;
            var stepNum = _idx + 1;
            var total   = _steps.length;
            var isLast  = stepNum >= total;

            /* --- Overlay (click outside to close) --- */
            _overlay = document.createElement('div');
            _overlay.className = 'vox-tour-overlay';
            _overlay.addEventListener('click', close);
            document.body.appendChild(_overlay);

            /* --- Spotlight --- */
            _spotlight = document.createElement('div');
            _spotlight.className = 'vox-tour-spotlight';
            _spotlight.style.left   = (rect.left   - pad) + 'px';
            _spotlight.style.top    = (rect.top    - pad) + 'px';
            _spotlight.style.width  = (rect.width  + pad * 2) + 'px';
            _spotlight.style.height = (rect.height + pad * 2) + 'px';
            document.body.appendChild(_spotlight);

            /* --- Tooltip --- */
            var isFirst = _idx === 0;
            _tooltip = document.createElement('div');
            _tooltip.className = 'vox-tour-tooltip';
            _tooltip.innerHTML =
                '<div class="vox-tour-tooltip-title">' +
                    '<span class="vox-tour-step-badge">' + stepNum + '</span>' +
                    _esc(title) +
                    '<span class="vox-tour-progress">' + stepNum + ' / ' + total + '</span>' +
                '</div>' +
                '<div class="vox-tour-tooltip-desc">' + descHTML + '</div>' +
                '<div class="vox-tour-tooltip-footer">' +
                    '<button class="vox-tour-btn-close" id="_vClose">닫기</button>' +
                    (!isFirst ? '<button class="vox-tour-btn-prev" id="_vPrev">← 이전</button>' : '') +
                    (isLast
                        ? '<button class="vox-tour-btn-finish" id="_vFinish">완료 ✓</button>'
                        : '<button class="vox-tour-btn-next"  id="_vNext">다음 →</button>'
                    ) +
                '</div>';
            document.body.appendChild(_tooltip);

            /* Button events */
            document.getElementById('_vClose').addEventListener('click', close);
            if (!isFirst) {
                document.getElementById('_vPrev').addEventListener('click', function () {
                    _closeUI();
                    _idx--;
                    _showCurrent();
                });
            }
            if (isLast) {
                document.getElementById('_vFinish').addEventListener('click', close);
            } else {
                document.getElementById('_vNext').addEventListener('click', function () {
                    _closeUI();
                    _idx++;
                    _showCurrent();
                });
            }

            /* Position (mobile handled by CSS bottom-sheet) */
            if (window.innerWidth > 640) {
                _positionTooltip(_tooltip, rect, pad);
            }
        }, 380);
    }

    function _positionTooltip(tooltip, targetRect, pad) {
        var vw     = window.innerWidth;
        var vh     = window.innerHeight;
        var tw     = tooltip.offsetWidth  || 340;
        var th     = tooltip.offsetHeight || 200;
        var gap    = 14;
        var margin = 12;
        var top, left;

        if (targetRect.bottom + pad + gap + th < vh) {
            top = targetRect.bottom + pad + gap;
        } else if (targetRect.top - pad - gap - th > 0) {
            top = targetRect.top - pad - gap - th;
        } else {
            top = Math.max(margin, (vh - th) / 2);
        }

        left = targetRect.left + targetRect.width / 2 - tw / 2;
        left = Math.max(margin, Math.min(vw - tw - margin, left));

        tooltip.style.top  = top  + 'px';
        tooltip.style.left = left + 'px';
    }

    function _esc(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    window.VoxTour = {
        startTour: startTour,
        close:     close
    };

})();
