/* =============================================
   content_detail.js — Voxliber
   config : #cdConfig (application/json)
   bookmarks: #cdBookmarks (application/json)
   ============================================= */

/* ── 유틸 ── */
function formatTime(sec) {
  if (!isFinite(sec)) return "0:00";
  return Math.floor(sec / 60) + ":" + String(Math.floor(sec % 60)).padStart(2, "0");
}
function escapeHtml(t) {
  return String(t || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function convertMd(text) {
  if (!text) return text;
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/__(.+?)__/g, "<u>$1</u>")
    .replace(/~~(.+?)~~/g, "<s>$1</s>")
    .replace(/==(.+?)==/g, '<mark style="background:#ffff00;padding:2px 4px">$1</mark>');
}

/* ── 토스트 ── */
function showToast(icon, msg) {
  const el = document.createElement("div");
  el.style.cssText = "position:fixed;top:88px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:12px 24px;border-radius:50px;font-size:14px;font-weight:600;box-shadow:0 8px 24px rgba(99,102,241,.5);z-index:10000;display:flex;align-items:center;gap:8px;pointer-events:none;transition:opacity .3s;";
  el.innerHTML = (icon || "") + "<span>" + escapeHtml(msg) + "</span>";
  document.body.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 2800);
}

/* ── 사이드 탭 ── */
function cdTab(btn, name) {
  document.querySelectorAll(".cd-side-tab").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".cd-side-panel").forEach(p => { p.style.display = "none"; });
  btn.classList.add("active");
  const panel = document.getElementById("tab-" + name);
  if (panel) panel.style.display = "";
}

/* ── 오디오 점프 + 텍스트 스크롤 ── */
function cdJumpTo(sec) {
  const a = document.getElementById("audioPlayer");
  if (a) {
    a.currentTime = sec;
    if (a.paused) a.play().catch(() => {});
  }
  /* 해당 초에 대응하는 page-block 으로 스크롤 */
  const blocks = document.querySelectorAll(".page-block[data-start-sec]");
  let best = null, bestDiff = Infinity;
  blocks.forEach(el => {
    const diff = Math.abs(parseFloat(el.dataset.startSec) - sec);
    if (diff < bestDiff) { bestDiff = diff; best = el; }
  });
  if (best) {
    setTimeout(() => best.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
  }
}

/* ── 북마크 팝업 ── */
let _bmPendingPos = 0;
let _bmPendingPageIdx = -1;

function cdOpenBmPopup(sec, pageIdx) {
  _bmPendingPos = sec;
  _bmPendingPageIdx = pageIdx !== undefined ? pageIdx : -1;
  const popup = document.getElementById("bmPopup");
  const backdrop = document.getElementById("bmBackdrop");
  if (!popup) return;
  const posEl = document.getElementById("bmPopupPos");
  if (posEl) posEl.textContent = formatTime(sec);
  /* 기존 메모 불러오기 */
  const existing = window._bmByPos && window._bmByPos[Math.round(sec)];
  const memoEl = document.getElementById("bmMemoInput");
  if (memoEl) memoEl.value = existing ? (existing.memo || "") : "";
  popup.style.display = "flex";
  if (backdrop) backdrop.style.display = "block";
  setTimeout(() => { if (memoEl) memoEl.focus(); }, 50);
}
function cdCloseBmPopup() {
  const popup   = document.getElementById("bmPopup");
  const backdrop = document.getElementById("bmBackdrop");
  if (popup) popup.style.display = "none";
  if (backdrop) backdrop.style.display = "none";
}
async function cdSaveBookmark() {
  const cfg = window._cd;
  if (!cfg || !cfg.saveBmUrl) return;
  const memo = (document.getElementById("bmMemoInput") || {}).value || "";
  try {
    const res = await fetch(cfg.saveBmUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cfg.csrf },
      body: JSON.stringify({ position: _bmPendingPos, memo })
    });
    const data = await res.json();
    if (data.success) {
      cdCloseBmPopup();
      const id = data.bookmark_id;
      /* 캐시 업데이트 */
      if (!window._bmByPos) window._bmByPos = {};
      window._bmByPos[Math.round(_bmPendingPos)] = { id, pos: _bmPendingPos, memo };
      /* 사이드바 추가/업데이트 */
      cdUpsertBmInSidebar(id, _bmPendingPos, memo);
      /* 페이지 블록 아이콘 업데이트 */
      if (_bmPendingPageIdx >= 0) cdMarkPageBlock(_bmPendingPageIdx, true, memo);
      showToast(
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>',
        "북마크 저장 · " + formatTime(_bmPendingPos)
      );
    }
  } catch(e) { console.warn("북마크 저장 실패", e); }
}
function cdMarkPageBlock(idx, bookmarked, memo) {
  const el = document.querySelector(`.page-block[data-page="${idx}"]`);
  if (!el) return;
  el.classList.toggle("bookmarked", bookmarked);
  const btn = el.querySelector(".page-bm-btn");
  if (!btn) return;
  btn.classList.toggle("active", bookmarked);
  btn.title = bookmarked ? (memo || "북마크됨") : "여기에 북마크";
}
function cdUpsertBmInSidebar(id, pos, memo) {
  const list = document.getElementById("bookmarkList");
  if (!list) return;
  const empty = document.getElementById("bmEmpty");
  if (empty) empty.style.display = "none";
  /* 같은 위치 기존 항목 제거 */
  const existing = list.querySelector(`.cd-bm-item[data-id="${id}"]`) ||
    list.querySelector(`.cd-bm-item[data-pos="${Math.round(pos)}"]`);
  if (existing) existing.remove();
  const div = document.createElement("div");
  div.className = "cd-bm-item";
  div.dataset.id = id;
  div.dataset.pos = pos;
  div.innerHTML =
    `<button class="cd-bm-jump" data-pos="${pos}" onclick="cdJumpTo(+this.dataset.pos)">` +
    `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>` +
    `${formatTime(pos)}</button>` +
    `<div class="cd-bm-memo">${escapeHtml(memo || "메모 없음")}</div>` +
    `<button class="cd-bm-del" data-id="${id}" onclick="cdDeleteBookmark(+this.dataset.id, this)" title="삭제">×</button>`;
  /* 시간 순 정렬 삽입 */
  const items = Array.from(list.querySelectorAll(".cd-bm-item"));
  const after = items.find(it => parseFloat(it.dataset.pos) > pos);
  if (after) list.insertBefore(div, after);
  else list.appendChild(div);
}
async function cdDeleteBookmark(id, btn) {
  const cfg = window._cd;
  if (!cfg) return;
  const url = cfg.delBmBase.replace("/999999/", "/" + id + "/");
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cfg.csrf }
    });
    const data = await res.json();
    if (data.success !== false) {
      const item = btn.closest(".cd-bm-item");
      const pos = item ? parseFloat(item.dataset.pos) : -1;
      if (item) item.remove();
      /* 캐시에서 제거 */
      if (window._bmByPos && pos >= 0) delete window._bmByPos[Math.round(pos)];
      /* page-block 아이콘 제거 */
      if (pos >= 0) {
        const blocks = document.querySelectorAll(".page-block[data-start-sec]");
        blocks.forEach(el => {
          if (Math.abs(parseFloat(el.dataset.startSec) - pos) < 1) cdMarkPageBlock(parseInt(el.dataset.page), false, "");
        });
      }
      const list = document.getElementById("bookmarkList");
      if (list && !list.querySelector(".cd-bm-item")) {
        const empty = document.getElementById("bmEmpty");
        if (empty) empty.style.display = "";
      }
      showToast("", "북마크 삭제됨");
    }
  } catch(e) { console.warn("북마크 삭제 실패", e); }
}

/* ═══════════════════════════════════════════
   메인
═══════════════════════════════════════════ */
document.addEventListener("DOMContentLoaded", function () {

  /* ── config ── */
  const cfgEl = document.getElementById("cdConfig");
  if (!cfgEl) return;
  const cfg = JSON.parse(cfgEl.textContent);
  window._cd = cfg;

  /* ── 북마크 데이터 ── */
  const bmEl = document.getElementById("cdBookmarks");
  const userBookmarks = bmEl ? JSON.parse(bmEl.textContent) : [];
  window._bmByPos = {};
  userBookmarks.forEach(bm => { window._bmByPos[Math.round(bm.pos)] = bm; });

  const isAuth = !!cfg.saveBmUrl;

  /* ── 마크다운 변환 ── */
  const textEl = document.getElementById("contentText");
  if (textEl) textEl.innerHTML = convertMd(textEl.innerHTML);

  /* ── 현재 화로 사이드 에피소드 스크롤 ── */
  const curEp = document.querySelector(".cd-ep-item.current");
  if (curEp) setTimeout(() => curEp.scrollIntoView({ block: "center", behavior: "smooth" }), 200);

  /* ════ 오디오 플레이어 ════ */
  const audio = document.getElementById("audioPlayer");
  if (!audio) return;

  const playPauseBtn   = document.getElementById("playPauseBtn");
  const playIcon       = document.getElementById("playIcon");
  const pauseIcon      = document.getElementById("pauseIcon");
  const progressSlider = document.getElementById("progressSlider");
  const progressFill   = document.getElementById("progressFill");
  const curTimeEl      = document.getElementById("currentTime");
  const totTimeEl      = document.getElementById("totalTime");
  const volumeBtn      = document.getElementById("volumeBtn");
  const volumeSlider   = document.getElementById("volumeSlider");
  const speedBtn       = document.getElementById("playbackSpeedBtn");
  const skipBack       = document.getElementById("cdSkipBack");
  const skipFwd        = document.getElementById("cdSkipFwd");

  const speeds = [0.75, 1.0, 1.25, 1.5, 2.0];
  let speedIdx = 1;

  function setSpeed(idx) {
    audio.playbackRate = speeds[idx];
    const label = speeds[idx] + "×";
    if (speedBtn) speedBtn.textContent = label;
    const lmSpeed = document.getElementById("lmSpeedBtn");
    if (lmSpeed) lmSpeed.textContent = label;
  }
  if (speedBtn) speedBtn.addEventListener("click", () => { speedIdx = (speedIdx + 1) % speeds.length; setSpeed(speedIdx); });
  if (skipBack) skipBack.addEventListener("click", () => { audio.currentTime = Math.max(0, audio.currentTime - 10); });
  if (skipFwd)  skipFwd.addEventListener("click",  () => { audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 10); });
  if (playPauseBtn) playPauseBtn.addEventListener("click", () => { if (audio.paused) audio.play(); else audio.pause(); });

  /* 청취 기록 */
  let listenStart = null, listenTotal = 0, isSending = false;
  async function saveListen(secs) {
    if (isSending || !cfg.saveUrl) return;
    isSending = true;
    try {
      const r = await fetch(cfg.saveUrl, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": cfg.csrf },
        body: JSON.stringify({ listened_seconds: Math.floor(secs), last_position: audio.currentTime || 0 })
      });
      const d = await r.json();
      if (d.success) listenTotal = 0;
    } finally { isSending = false; }
  }
  function saveOnExit() {
    if (listenStart) listenTotal += (Date.now() - listenStart) / 1000;
    const pos = audio.currentTime || 0;
    if (pos >= 1 && cfg.saveUrl) {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", cfg.saveUrl, false);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.setRequestHeader("X-CSRFToken", cfg.csrf);
      xhr.send(JSON.stringify({ listened_seconds: Math.floor(listenTotal), last_position: pos }));
    }
  }
  window.addEventListener("beforeunload", saveOnExit);
  window.addEventListener("pagehide", saveOnExit);

  audio.addEventListener("play", () => {
    if (playIcon) playIcon.style.display = "none";
    if (pauseIcon) pauseIcon.style.display = "block";
    if (!listenStart) listenStart = Date.now();
  });
  audio.addEventListener("pause", () => {
    if (playIcon) playIcon.style.display = "block";
    if (pauseIcon) pauseIcon.style.display = "none";
    if (listenStart) { listenTotal += (Date.now() - listenStart) / 1000; listenStart = null; }
  });
  audio.addEventListener("ended", () => {
    if (playIcon) playIcon.style.display = "block";
    if (pauseIcon) pauseIcon.style.display = "none";
    if (listenStart) { listenTotal += (Date.now() - listenStart) / 1000; listenStart = null; }
    saveListen(listenTotal);
    if (cfg.nextUrl) {
      let count = 3;
      const toast = document.createElement("div");
      toast.style.cssText = "position:fixed;bottom:88px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:12px 24px;border-radius:50px;font-size:14px;font-weight:600;z-index:10000;display:flex;align-items:center;gap:12px;cursor:pointer;box-shadow:0 8px 24px rgba(99,102,241,.5);";
      const txt = document.createElement("span"); txt.textContent = count + "초 후 다음 화로 이동합니다";
      const cancel = document.createElement("span"); cancel.textContent = "취소"; cancel.style.cssText = "opacity:.7;font-size:11px;border:1px solid rgba(255,255,255,.4);padding:2px 8px;border-radius:20px;";
      toast.appendChild(txt); toast.appendChild(cancel);
      document.body.appendChild(toast);
      const timer = setInterval(() => { count--; txt.textContent = count + "초 후 다음 화로 이동합니다"; if (count <= 0) { clearInterval(timer); window.location.href = cfg.nextUrl; } }, 1000);
      toast.addEventListener("click", () => { clearInterval(timer); toast.remove(); });
    }
  });
  setInterval(() => {
    if (!listenStart) return;
    const el = (Date.now() - listenStart) / 1000, tot = listenTotal + el;
    if (tot >= 30) { listenTotal = tot; listenStart = Date.now(); saveListen(listenTotal); }
  }, 30000);

  audio.addEventListener("loadedmetadata", () => {
    if (totTimeEl) totTimeEl.textContent = formatTime(audio.duration);
    if (progressSlider) progressSlider.max = audio.duration;
  });
  let isSeeking = false;
  audio.addEventListener("timeupdate", () => {
    const cur = audio.currentTime, dur = audio.duration || 1;
    if (curTimeEl) curTimeEl.textContent = formatTime(cur);
    if (!isSeeking) {
      if (progressSlider) progressSlider.value = cur;
      if (progressFill) progressFill.style.width = (cur / dur) * 100 + "%";
    }
  });
  if (progressSlider) {
    progressSlider.addEventListener("pointerdown", () => { isSeeking = true; window._clipEnd = null; });
    progressSlider.addEventListener("pointerup",   () => { audio.currentTime = progressSlider.value; isSeeking = false; });
    progressSlider.addEventListener("input", () => {
      const dur = audio.duration || 1;
      if (curTimeEl) curTimeEl.textContent = formatTime(+progressSlider.value);
      if (progressFill) progressFill.style.width = (progressSlider.value / dur) * 100 + "%";
    });
  }
  if (volumeSlider)   volumeSlider.addEventListener("input",   () => { audio.volume = volumeSlider.value / 100; });
  if (volumeBtn) volumeBtn.addEventListener("click", () => {
    if (audio.volume > 0) { audio.volume = 0; if (volumeSlider) volumeSlider.value = 0; }
    else { audio.volume = 1; if (volumeSlider) volumeSlider.value = 100; }
  });

  /* 이어듣기 */
  audio.addEventListener("canplay", function () {
    const pos = cfg.lastPos || 0;
    if (pos > 5) {
      audio.currentTime = pos;
      showToast('<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>', "이어듣기: " + formatTime(pos) + "부터");
    }
    audio.play().catch(() => {});
  }, { once: true });

  /* ════ 타임스탬프 / 텍스트 하이라이트 ════ */
  const tsData = document.getElementById("audio-timestamps-data");
  if (!tsData) return;

  let timestamps;
  try { timestamps = JSON.parse(tsData.textContent || "[]"); } catch(e) { timestamps = []; }
  const pages = timestamps.filter(ts => ts.startTime !== undefined);
  if (!pages.length) return;

  const fullTextEl = document.getElementById("content-full-text-data");
  const fullText   = fullTextEl ? JSON.parse(fullTextEl.textContent || '""') : "";
  const textParagraphs = fullText.split("\n\n---\n\n");

  const cleanTag = t => t.replace(/\[[^\]]*\]/g, "").trim();
  const BM_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>`;

  function fmtPage(raw) {
    const t = cleanTag(raw || "");
    if (!t) return "";
    const parts = t.split(/ \/ |\n/).map(p => p.trim()).filter(Boolean);
    if (parts.length <= 1) return escapeHtml(t);
    return parts.map((p, i) => i === 0 ? escapeHtml(p) : '<br><span style="padding-left:1.2em;color:#a78bfa;font-size:.92em;">' + escapeHtml(p) + "</span>").join("");
  }

  if (textEl) {
    textEl.innerHTML = pages.map((pg, i) => {
      let raw = pg.text || "";
      if (!cleanTag(raw).trim() && i < textParagraphs.length) raw = textParagraphs[i];
      const startSec = pg.startTime / 1000;
      const isBm = !!window._bmByPos[Math.round(startSec)];
      const existingMemo = isBm ? (window._bmByPos[Math.round(startSec)].memo || "") : "";
      const bmBtn = isAuth
        ? `<button class="page-bm-btn${isBm ? " active" : ""}" data-sec="${startSec}" data-page="${i}" title="${isBm ? (existingMemo || "북마크됨") : "여기에 북마크"}" onclick="cdOpenBmPopup(+this.dataset.sec, +this.dataset.page)">${BM_ICON}</button>`
        : "";
      return `<span class="page-block${isBm ? " bookmarked" : ""}" data-page="${i}" data-start-sec="${startSec}">${bmBtn}${fmtPage(raw)}</span>`;
    }).join("");

    /* 텍스트 블록 클릭 → 해당 위치로 이동 (버튼 클릭 제외) */
    document.querySelectorAll(".page-block").forEach((el, i) => {
      el.addEventListener("click", e => {
        if (e.target.closest(".page-bm-btn")) return;
        audio.currentTime = pages[i].startTime / 1000;
        if (audio.paused) audio.play().catch(() => {});
      });
    });
  }

  /* 오디오 재생 위치 → 텍스트 하이라이트 */
  let curPage = -1;
  const lmSentenceEl = document.getElementById("lmSentence");
  function hlPage(idx) {
    if (idx === curPage) return;
    curPage = idx;
    document.querySelectorAll(".page-block").forEach((el, i) => el.classList.toggle("page-active", i === idx));
    const active = document.querySelector(".page-block.page-active");
    if (active) {
      const overlay = document.getElementById("listenModeOverlay");
      const inListenMode = overlay && overlay.classList.contains("open");
      if (!inListenMode) active.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    if (lmSentenceEl && pages[idx]) lmSentenceEl.textContent = pages[idx].text || "";
  }
  audio.addEventListener("timeupdate", () => {
    const ms = audio.currentTime * 1000;
    for (let i = 0; i < pages.length; i++) {
      if (ms >= pages[i].startTime && ms < pages[i].endTime) { hlPage(i); break; }
    }
  });

  /* ════ 대화 하이라이트 패널 ════ */
  const dialogues = timestamps.filter(ts => ts.text && ts.text.trim());
  const sectionEl    = document.getElementById("dialogueSection");
  const dialogueList = document.getElementById("dialogueList");
  const prevBtn      = document.getElementById("prevDialogueBtn");
  const nextBtn      = document.getElementById("nextDialogueBtn");
  const counter      = document.getElementById("dialogueCounter");

  if (sectionEl && dialogueList && dialogues.length > 0) {
    sectionEl.style.display = "";
    let curDlg = -1;
    dialogueList.innerHTML = "";
    dialogues.forEach((d, i) => {
      const el = document.createElement("div");
      el.className = "cd-dialogue-item";
      el.dataset.index = i;
      el.innerHTML = `<span class="cd-dialogue-num">${i + 1}</span><span class="cd-dialogue-text">${escapeHtml(d.text)}</span>`;
      el.addEventListener("click", () => jumpDlg(i));
      dialogueList.appendChild(el);
    });
    function hlDlg(idx) {
      curDlg = idx;
      document.querySelectorAll(".cd-dialogue-item").forEach((el, i) => el.classList.toggle("active", i === idx));
      const a = document.querySelector(`.cd-dialogue-item[data-index="${idx}"]`);
      if (a) a.scrollIntoView({ behavior: "smooth", block: "nearest" });
      if (counter) counter.textContent = `${idx + 1}/${dialogues.length}`;
      if (prevBtn) prevBtn.disabled = idx === 0;
      if (nextBtn) nextBtn.disabled = idx === dialogues.length - 1;
    }
    function jumpDlg(idx) {
      if (idx < 0 || idx >= dialogues.length) return;
      audio.currentTime = dialogues[idx].startTime / 1000;
      if (audio.paused) audio.play().catch(() => {});
      hlDlg(idx);
    }
    audio.addEventListener("timeupdate", () => {
      const ms = audio.currentTime * 1000;
      for (let i = 0; i < dialogues.length; i++) {
        if (ms >= dialogues[i].startTime && ms < dialogues[i].endTime) { if (curDlg !== i) hlDlg(i); break; }
      }
    });
    if (prevBtn) prevBtn.addEventListener("click", () => { if (curDlg > 0) jumpDlg(curDlg - 1); });
    if (nextBtn) nextBtn.addEventListener("click", () => { if (curDlg < dialogues.length - 1) jumpDlg(curDlg + 1); });
    hlDlg(0);
  }

  /* ════ 듣기 모드 오버레이 ════ */
  const overlay    = document.getElementById("listenModeOverlay");
  const openBtn    = document.getElementById("openListenMode");
  const openBarBtn = document.getElementById("openListenModeBar");
  const closeBtn   = document.getElementById("listenModeClose");
  const bgEl       = document.getElementById("listenModeBg");
  const lmCover    = document.getElementById("lmCover");
  if (!overlay) return;

  const coverSrc = lmCover && (lmCover.dataset.src || lmCover.src || null);
  if (coverSrc && bgEl) bgEl.style.backgroundImage = "url('" + coverSrc + "')";

  function syncLm() {
    const playing = !audio.paused;
    const li = document.getElementById("lmPlayIcon"), lp = document.getElementById("lmPauseIcon");
    if (li) li.style.display = playing ? "none" : "block";
    if (lp) lp.style.display = playing ? "block" : "none";
    if (lmCover && lmCover.tagName === "IMG") lmCover.classList.toggle("playing", playing);
  }
  function openLm() { overlay.classList.add("open"); document.body.style.overflow = "hidden"; if (!audioCtx) initAudioCtx(); syncLm(); }
  function closeLm() { overlay.classList.remove("open"); document.body.style.overflow = ""; if (rafId) { cancelAnimationFrame(rafId); rafId = null; } }

  if (openBtn)    openBtn.addEventListener("click",    openLm);
  if (openBarBtn) openBarBtn.addEventListener("click", openLm);
  if (closeBtn)   closeBtn.addEventListener("click",   closeLm);
  overlay.addEventListener("click", e => { if (e.target === overlay) closeLm(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && overlay.classList.contains("open")) closeLm(); });
  audio.addEventListener("play",  syncLm);
  audio.addEventListener("pause", syncLm);
  audio.addEventListener("ended", syncLm);

  const lmPlay   = document.getElementById("lmPlayBtn");
  const lmBack   = document.getElementById("lmSeekBack");
  const lmFwd    = document.getElementById("lmSeekFwd");
  const lmSpeed  = document.getElementById("lmSpeedBtn");
  const lmPFill  = document.getElementById("lmProgressFill");
  const lmSlider = document.getElementById("lmProgressSlider");
  const lmCurT   = document.getElementById("lmCurrentTime");
  const lmTotT   = document.getElementById("lmTotalTime");

  if (lmPlay)  lmPlay.addEventListener("click",  () => { if (audio.paused) audio.play(); else audio.pause(); });
  if (lmBack)  lmBack.addEventListener("click",  () => { audio.currentTime = Math.max(0, audio.currentTime - 10); });
  if (lmFwd)   lmFwd.addEventListener("click",   () => { audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 10); });
  if (lmSpeed) lmSpeed.addEventListener("click", () => { speedIdx = (speedIdx + 1) % speeds.length; setSpeed(speedIdx); });
  if (lmSlider) lmSlider.addEventListener("input", () => { audio.currentTime = (lmSlider.value / 100) * (audio.duration || 0); });

  audio.addEventListener("timeupdate", () => {
    if (!overlay.classList.contains("open")) return;
    const cur = audio.currentTime, dur = audio.duration || 1;
    if (lmCurT)  lmCurT.textContent = formatTime(cur);
    if (lmPFill) lmPFill.style.width = (cur / dur) * 100 + "%";
    if (lmSlider) lmSlider.value = (cur / dur) * 100;
  });
  audio.addEventListener("loadedmetadata", () => { if (lmTotT) lmTotT.textContent = formatTime(audio.duration); });
  if (audio.duration && lmTotT) lmTotT.textContent = formatTime(audio.duration);

  /* Web Audio 시각화 */
  let audioCtx = null, analyser = null, rafId = null;
  function initAudioCtx() {
    if (audioCtx) return;
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser(); analyser.fftSize = 512; analyser.smoothingTimeConstant = 0.82;
      const src = audioCtx.createMediaElementSource(audio);
      src.connect(analyser); analyser.connect(audioCtx.destination);
      startViz();
    } catch(e) { console.warn("Web Audio 초기화 실패", e); }
  }
  function startViz() {
    const canvas = document.getElementById("listenModeCanvas");
    if (!canvas || !analyser) return;
    const ctx = canvas.getContext("2d");
    const buf = new Uint8Array(analyser.frequencyBinCount);
    function resize() {
      const dpr = devicePixelRatio || 1;
      canvas.width  = canvas.offsetWidth  * dpr;
      canvas.height = canvas.offsetHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize(); window.addEventListener("resize", resize);
    function draw() {
      rafId = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(buf);
      const W = canvas.offsetWidth, H = canvas.offsetHeight;
      ctx.clearRect(0, 0, W, H);
      const N = 80, step = Math.floor(buf.length / N), gap = 2.5, bw = (W - gap * (N - 1)) / N;
      for (let i = 0; i < N; i++) {
        const v = ((buf[i*step]||0) + (buf[i*step+1]||0) + (buf[i*step+2]||0)) / 3 / 255;
        const bh = 3 + v * (H - 6) * 0.95, x = i * (bw + gap), y = (H - bh) / 2;
        const hue = 220 + v * 60, alpha = 0.55 + v * 0.45;
        const g = ctx.createLinearGradient(x, y + bh, x, y);
        g.addColorStop(0, `hsla(${hue},70%,60%,${alpha})`);
        g.addColorStop(1, `hsla(${hue+40},80%,88%,${alpha*.7})`);
        ctx.fillStyle = g;
        const r = Math.min(bw / 2, 3);
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(x, y, bw, bh, r); else ctx.rect(x, y, bw, bh);
        ctx.fill();
      }
    }
    draw();
  }

}); // DOMContentLoaded

/* ── 댓글 작성 ── */
async function cdSubmitComment() {
  const ta  = document.getElementById('cdCommentInput');
  const url = ta?.dataset.submitUrl;
  const text = ta?.value.trim();
  if (!text) { ta?.focus(); return; }

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '',
    },
    body: JSON.stringify({ comment: text }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    showToast('⚠', data.error || '댓글 작성에 실패했습니다.');
    return;
  }

  ta.value = '';
  const list = document.getElementById('cdCommentsList');
  const empty = list?.querySelector('.cd-empty-state');
  if (empty) empty.remove();

  const div = document.createElement('div');
  div.className = 'comment-item';
  div.innerHTML = `
    <div class="comment-hd">
      <span class="comment-author">${escapeHtml(data.nickname || '')}</span>
      <span class="comment-date">${data.created_at || ''}</span>
    </div>
    <div class="comment-text">${escapeHtml(data.comment || text)}</div>`;
  list?.prepend(div);

  const title = document.querySelector('#cd-section-comments .cd-section-title');
  if (title) {
    const m = title.textContent.match(/\d+/);
    const n = m ? parseInt(m[0]) + 1 : 1;
    title.textContent = `댓글 (${n})`;
  }
  showToast('💬', '댓글이 등록되었습니다.');
}

/* ── 답글 작성 ── */
async function cdSubmitReply(commentId, url) {
  const ta   = document.getElementById(`reply-input-cd-${commentId}`);
  const text = ta?.value.trim();
  if (!text) { ta?.focus(); return; }

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '',
    },
    body: JSON.stringify({ comment: text, parent_id: commentId }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    showToast('⚠', data.error || '답글 작성에 실패했습니다.');
    return;
  }

  ta.value = '';
  toggleReplyForm(`cd-${commentId}`);

  const div = document.createElement('div');
  div.className = 'comment-reply';
  div.innerHTML = `
    <div class="reply-hd">
      <span class="comment-reply-author">${escapeHtml(data.nickname || '')}</span>
      <span class="comment-date">${data.created_at || ''}</span>
    </div>
    <div class="comment-text">${escapeHtml(data.comment || text)}</div>`;

  const replyForm = document.getElementById(`reply-form-cd-${commentId}`);
  replyForm?.parentElement?.insertBefore(div, replyForm);
  showToast('💬', '답글이 등록되었습니다.');
}

/* ── 답글 폼 토글 ── */
function toggleReplyForm(id) {
  const form = document.getElementById(`reply-form-${id}`);
  if (!form) return;
  const isOpen = form.style.display === 'block';
  form.style.display = isOpen ? 'none' : 'block';
  if (!isOpen) form.querySelector('textarea')?.focus();
}
