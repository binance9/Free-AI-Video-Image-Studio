(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;
  let activeJob = null;
  let timer = null;

  function showProgress(on) {
    $('facebookProgress')?.classList.toggle('hidden', !on);
  }
  function setProgress(pct, stage, detail) {
    const value = Math.max(0, Math.min(100, Number(pct) || 0));
    $('facebookProgressPct').textContent = `${Math.round(value)}%`;
    $('facebookProgressBar').style.width = `${value}%`;
    $('facebookProgressStage').textContent = stage || 'Đang tải Facebook';
    $('facebookProgressDetail').textContent = detail || 'Đang xử lý…';
    S.updateBusyProgress?.(value, stage || 'Đang tải Facebook', detail || 'Đang xử lý…', 'real');
  }
  function setButtonBusy(on) {
    const btn = $('facebookDownloadBtn');
    if (!btn) return;
    btn.disabled = on;
    btn.textContent = on ? 'ĐANG TẢI VIDEO FACEBOOK…' : '⬇ TẢI VIDEO TỪ FACEBOOK VÀO EDITOR';
  }

  async function loadStatus() {
    const box = $('facebookStatus');
    if (!box) return;
    try {
      const data = await S.jsonRequest('/api/facebook-video/status');
      box.innerHTML = data.available
        ? '<strong>✓ Bộ tải Facebook đã sẵn sàng</strong><small>yt-dlp + FFmpeg · video công khai</small>'
        : `<strong>Chưa có yt-dlp</strong><small>${S.esc(data.message || 'Mở lại START_VIDEO_FACTORY.bat để tự cài')}</small>`;
    } catch (e) {
      box.innerHTML = `<strong>Không kiểm tra được</strong><small>${S.esc(e.message)}</small>`;
    }
  }

  async function pollJob() {
    if (!activeJob) return;
    try {
      const job = await S.jsonRequest(`/api/facebook-video/jobs/${activeJob}`);
      setProgress(job.progress, job.stage, job.detail);
      if (job.status === 'done') {
        clearInterval(timer); timer = null;
        setButtonBusy(false);
        setProgress(100, 'Hoàn tất', 'Video Facebook đã được đưa thẳng vào editor');
        const result = job.result || {};
        if (result.editor) {
          S.state.layers = [];
          S.state.selected = null;
          S.applyInfo(result.editor, true);
        }
        $('facebookResult').classList.remove('hidden');
        $('facebookResultTitle').textContent = result.title || 'Video Facebook đã tải';
        const mb = result.size_bytes ? `${(result.size_bytes / 1048576).toFixed(1)} MB` : '';
        $('facebookResultMeta').textContent = [result.uploader, mb, 'Đã đưa vào editor'].filter(Boolean).join(' · ');
        $('facebookOriginalDownload').href = result.download_url || '#';
        S.updateBusyProgress?.(100, 'Hoàn tất', 'Video Facebook đã được đưa vào editor', 'real');
        S.setBusy(false);
        S.setStatus('Tải Facebook xong. Video đã nằm trong editor và có thể cắt / ghép / thêm phụ đề ngay.');
        activeJob = null;
      } else if (job.status === 'cancelled') {
        clearInterval(timer); timer=null; setButtonBusy(false);
        S.setBusy(false); S.setStatus('Đã dừng tải Facebook.'); activeJob=null;
      } else if (job.status === 'error') {
        clearInterval(timer); timer = null;
        setButtonBusy(false);
        S.failBusyProgress?.('Lỗi tải Facebook', job.error || job.detail || 'Không tải được');
        S.setStatus(`Lỗi tải Facebook: ${job.error || job.detail || 'Không tải được'}`, true);
        activeJob = null;
      }
    } catch (e) {
      clearInterval(timer); timer = null;
      setButtonBusy(false);
      S.failBusyProgress?.('Lỗi kiểm tra tải Facebook', e.message);
      S.setStatus('Lỗi kiểm tra tải Facebook: ' + e.message, true);
      activeJob = null;
    }
  }

  async function startDownload() {
    const url = ($('facebookUrl')?.value || '').trim();
    if (!url) return S.setStatus('Dán link video Facebook trước.', true);
    if (activeJob) return;
    $('facebookResult')?.classList.add('hidden');
    showProgress(true);
    setProgress(1, 'Chuẩn bị tải Facebook', 'Đang kiểm tra link…');
    setButtonBusy(true);
    S.setBusy(true, 'Tải video từ Facebook', 'Đang kiểm tra link và chuẩn bị yt-dlp…');
    S.setStatus('Đang tải video từ Facebook…');
    try {
      const job = await S.jsonRequest('/api/facebook-video/jobs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url}),
      });
      activeJob = job.job_id;
      window.AIVFJobTerminal?.start({scope:'facebook_video',jobId:job.job_id,title:'ĐANG XỬ LÝ VIDEO FACEBOOK'});
      await pollJob();
      if (activeJob) timer = setInterval(pollJob, 1000);
    } catch (e) {
      setButtonBusy(false);
      $('facebookProgressStage').textContent='Không tải được';
      $('facebookProgressDetail').textContent=e.message;
      S.failBusyProgress?.('Không bắt đầu được tải Facebook', e.message);
      S.setStatus('Không bắt đầu được tải Facebook: ' + e.message, true);
    }
  }

  $('facebookDownloadBtn')?.addEventListener('click', startDownload);
  $('facebookUrl')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); startDownload(); }
  });
  $('facebookQuickBtn')?.addEventListener('click', () => S.switchTool('facebook'));
  loadStatus();
})();
