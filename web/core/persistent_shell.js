/* Persistent chat column + system/job terminal shell behavior.
   UI-only: resize handles, height persistence (localStorage), and
   auto-connecting the existing job terminal to the new system/startup log
   stream on page load so it shows real backend logs from launcher start,
   not just once a job begins. Does not touch AI/model/job/pipeline logic -
   only wires the already-existing AIVFJobTerminal SSE consumer to an extra
   stream and adds drag-to-resize for two panels. */
(() => {
  const $ = id => document.getElementById(id);
  const root = document.documentElement;
  const LS_CHAT_H = 'aivf_chat_col_h';
  const LS_TERM_H = 'aivf_terminal_h';

  function clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }

  function makeResizable({ handle, cssVar, storageKey, min, max, getBase }) {
    if (!handle) return;
    const stored = Number(localStorage.getItem(storageKey));
    if (stored && stored >= min && stored <= max) {
      root.style.setProperty(cssVar, stored + 'px');
    }
    let dragging = false, startY = 0, startH = 0;
    const onMove = e => {
      if (!dragging) return;
      const y = e.touches ? e.touches[0].clientY : e.clientY;
      const delta = getBase() === 'down' ? (y - startY) : (startY - y);
      const next = clamp(startH + delta, min, max);
      root.style.setProperty(cssVar, next + 'px');
    };
    const onUp = () => {
      if (!dragging) return;
      dragging = false;
      handle.classList.remove('dragging');
      const px = parseFloat(getComputedStyle(root).getPropertyValue(cssVar)) || min;
      localStorage.setItem(storageKey, String(Math.round(px)));
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('touchmove', onMove);
      window.removeEventListener('touchend', onUp);
    };
    const onDown = e => {
      dragging = true;
      handle.classList.add('dragging');
      const box = handle.parentElement.getBoundingClientRect();
      startH = box.height;
      startY = e.touches ? e.touches[0].clientY : e.clientY;
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
      window.addEventListener('touchmove', onMove, { passive: false });
      window.addEventListener('touchend', onUp);
      e.preventDefault();
    };
    handle.addEventListener('mousedown', onDown);
    handle.addEventListener('touchstart', onDown, { passive: false });
  }

  // Chat column: divider sits at its bottom edge, dragging it down makes the
  // panel taller (pulling the boundary further down), dragging up shrinks it.
  makeResizable({
    handle: $('chatColResize'), cssVar: '--chat-h', storageKey: LS_CHAT_H,
    min: 260, max: Math.round(window.innerHeight * 0.96), getBase: () => 'down',
  });

  // Terminal: divider sits at its TOP edge, dragging it up makes the panel
  // taller (matches "kéo divider phía trên terminal lên = cao hơn").
  makeResizable({
    handle: $('jobTerminalResize'), cssVar: '--terminal-h', storageKey: LS_TERM_H,
    min: 120, max: Math.round(window.innerHeight * 0.6), getBase: () => 'up',
  });
  // A manual drag should win over collapsed/expanded button state so the
  // panel actually reflects the height the user just chose.
  $('jobTerminalResize')?.addEventListener('mousedown', () => {
    $('jobTerminal')?.classList.remove('collapsed', 'expanded');
  });

  // Narrow-screen chat collapse toggle (CSS shows a 💬 tab at <=880px).
  $('chatCol')?.addEventListener('click', e => {
    if (window.innerWidth > 880) return;
    if (document.body.classList.contains('chat-col-open')) return;
    if (e.target.closest('.ga-owner,.chat-col-resize')) return;
    document.body.classList.add('chat-col-open');
  });

  // System/startup log: connect the existing job terminal to the new
  // /api/job-logs/system/startup/stream as soon as the page loads, so real
  // backend stdout/stderr is visible from launcher start onward, not just
  // once the first AI job begins. When any module starts a real job later,
  // its own AIVFJobTerminal.start({scope,jobId,...}) call takes over the
  // same terminal exactly as before (unchanged behavior).
  function startSystemLog() {
    if (!window.AIVFJobTerminal) { setTimeout(startSystemLog, 50); return; }
    window.AIVFJobTerminal.start({ scope: 'system', jobId: 'startup', title: 'HỆ THỐNG', mode: 'debug' });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', startSystemLog);
  else startSystemLog();
})();
