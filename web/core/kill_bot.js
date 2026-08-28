/* Nut "TAT BOT" tren thanh tren cung: dung TOAN BO AI Video Factory (job,
   FFmpeg, model worker, server) tu trinh duyet - file tach rieng, khong
   nhet vao app.js. Xem app/core/api_system.py::shutdown cho co che kill
   thuc su (ha guc toan bo cay tien trinh cua server). */
(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;

  function isLocallyBusy() {
    const busyEl = document.getElementById('busy');
    return !!busyEl && !busyEl.classList.contains('hidden');
  }

  async function isBackendBusy() {
    try {
      const data = await S.jsonRequest('/api/jobs/status');
      return Boolean(data && data.busy);
    } catch (_e) {
      return false; // khong hoi duoc server -> coi nhu khong con gi de dung
    }
  }

  function ensureModal() {
    if ($('killBotModal')) return;
    const modal = document.createElement('div');
    modal.className = 'modal hidden';
    modal.id = 'killBotModal';
    modal.innerHTML = `
      <div class="modal-card">
        <div class="modal-head"><h3>Tắt AI Video Factory?</h3></div>
        <p>Đang có tác vụ xử lý. Tắt bot sẽ dừng toàn bộ.</p>
        <div class="action-grid" style="margin-top:16px">
          <button class="btn" id="killBotCancelBtn">HỦY</button>
          <button class="btn danger" id="killBotConfirmBtn">⏻ TẮT TẤT CẢ</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    $('killBotCancelBtn').addEventListener('click', () => modal.classList.add('hidden'));
    $('killBotConfirmBtn').addEventListener('click', () => { modal.classList.add('hidden'); doShutdown(); });
  }

  function showConfirm() {
    ensureModal();
    $('killBotModal').classList.remove('hidden');
  }

  function showShutdownDone() {
    let overlay = $('killBotDoneOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'killBotDoneOverlay';
      overlay.className = 'modal';
      overlay.innerHTML = `<div class="modal-card" style="text-align:center">
        <div class="modal-head" style="justify-content:center"><h3>⏻ Đã tắt AI Video Factory</h3></div>
        <p>Toàn bộ tác vụ, FFmpeg và model worker đã dừng, server đã đóng cổng.<br>Bạn có thể đóng tab này.</p>
      </div>`;
      document.body.appendChild(overlay);
    }
    overlay.classList.remove('hidden');
  }

  async function doShutdown() {
    const btn = $('killBotBtn');
    if (btn) { btn.disabled = true; btn.textContent = '⏻ ĐANG TẮT…'; }
    try {
      await S.jsonRequest('/api/system/shutdown', { method: 'POST' });
    } catch (_e) {
      // server co the da chet ngay khi dang tra response - van coi la thanh cong
    }
    showShutdownDone();
  }

  async function onKillBotClick() {
    if (isLocallyBusy() || await isBackendBusy()) {
      showConfirm();
    } else {
      doShutdown();
    }
  }

  $('killBotBtn')?.addEventListener('click', onKillBotClick);
})();
