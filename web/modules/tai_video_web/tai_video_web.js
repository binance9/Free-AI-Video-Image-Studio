(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;
  let activeJob = null;
  let timer = null;

  function showProgress(on) {
    $('taiVideoWebProgress')?.classList.toggle('hidden', !on);
  }
  function setProgress(pct, stage, detail) {
    const value = Math.max(0, Math.min(100, Number(pct) || 0));
    $('taiVideoWebProgressPct').textContent = `${Math.round(value)}%`;
    $('taiVideoWebProgressBar').style.width = `${value}%`;
    $('taiVideoWebProgressStage').textContent = stage || 'Đang tải video';
    $('taiVideoWebProgressDetail').textContent = detail || 'Đang xử lý…';
    // Tien trinh realtime hien trong khung VIDEO lon (busy overlay dung
    // chung), khong tao them o preview nho o day.
    S.updateBusyProgress?.(value, stage || 'Đang tải video', detail || 'Đang xử lý…', 'real');
  }
  function setButtonBusy(on) {
    const btn = $('taiVideoWebDownloadBtn');
    if (!btn) return;
    btn.disabled = on;
    btn.textContent = on ? 'ĐANG TẢI VIDEO…' : '⬇ TẢI VIDEO';
  }

  async function loadStatus() {
    const box = $('taiVideoWebStatus');
    if (!box) return;
    try {
      const data = await S.jsonRequest('/api/tai-video-web/status');
      box.innerHTML = data.available
        ? '<strong>✓ Bộ tải video đã sẵn sàng</strong><small>yt-dlp + FFmpeg · 360p/720p/1080p/tốt nhất</small>'
        : `<strong>Chưa có yt-dlp</strong><small>${S.esc(data.message || 'Mở lại START_VIDEO_FACTORY.bat để tự cài')}</small>`;
    } catch (e) {
      box.innerHTML = `<strong>Không kiểm tra được</strong><small>${S.esc(e.message)}</small>`;
    }
  }

  async function pollJob() {
    if (!activeJob) return;
    try {
      const job = await S.jsonRequest(`/api/tai-video-web/jobs/${activeJob}`);
      setProgress(job.progress, job.stage, job.detail);
      if (job.status === 'done') {
        clearInterval(timer); timer = null;
        setButtonBusy(false);
        const result = job.result || {};
        if (result.audio_only) {
          setProgress(100, 'Hoàn tất', 'Audio đã lưu vào thư mục output riêng');
          $('taiVideoWebAudioResult')?.classList.remove('hidden');
          $('taiVideoWebAudioMeta').textContent = result.title || 'Audio đã tải';
          $('taiVideoWebAudioDownload').href = result.download_url || '#';
        } else if (result.editor) {
          S.state.layers = [];
          S.state.selected = null;
          S.applyInfo(result.editor, true);
          setProgress(100, 'Hoàn tất', 'Video đã được đưa thẳng vào editor');
        }
        S.updateBusyProgress?.(100, 'Hoàn tất', 'Tải video xong', 'real');
        S.setBusy(false);
        S.setStatus(result.audio_only ? 'Tải audio xong.' : 'Tải video xong. Video đã nằm trong editor và có thể cắt / ghép / thêm phụ đề ngay.');
        activeJob = null;
      } else if (job.status === 'cancelled') {
        clearInterval(timer); timer = null; setButtonBusy(false);
        S.setBusy(false); S.setStatus('Đã dừng tải video.'); activeJob = null;
      } else if (job.status === 'error') {
        clearInterval(timer); timer = null;
        setButtonBusy(false);
        S.failBusyProgress?.('Lỗi tải video', job.error || job.detail || 'Không tải được');
        S.setStatus(`Lỗi tải video: ${job.error || job.detail || 'Không tải được'}`, true);
        activeJob = null;
      }
    } catch (e) {
      clearInterval(timer); timer = null;
      setButtonBusy(false);
      S.failBusyProgress?.('Lỗi kiểm tra tải video', e.message);
      S.setStatus('Lỗi kiểm tra tải video: ' + e.message, true);
      activeJob = null;
    }
  }

  async function startDownload() {
    const url = ($('taiVideoWebUrl')?.value || '').trim();
    if (!url) return S.setStatus('Dán URL video trước.', true);
    if (activeJob) return;
    const quality = $('taiVideoWebQuality')?.value || '720p';
    const audioOnly = ($('taiVideoWebMode')?.value || 'video') === 'audio';
    $('taiVideoWebAudioResult')?.classList.add('hidden');
    showProgress(true);
    setProgress(1, 'Chuẩn bị tải video', 'Đang kiểm tra URL…');
    setButtonBusy(true);
    S.setBusy(true, 'Tải video từ web', 'Đang kiểm tra URL và chuẩn bị yt-dlp…');
    S.setStatus('Đang tải video…');
    try {
      const job = await S.jsonRequest('/api/tai-video-web/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, quality, audio_only: audioOnly }),
      });
      activeJob = job.job_id;
      window.AIVFJobTerminal?.start({scope:'web_video',jobId:job.job_id,title:'ĐANG TẢI VÀ XỬ LÝ VIDEO'});
      await pollJob();
      if (activeJob) timer = setInterval(pollJob, 1000);
    } catch (e) {
      setButtonBusy(false);
      $('taiVideoWebProgressStage').textContent = 'Không tải được';
      $('taiVideoWebProgressDetail').textContent = e.message;
      S.failBusyProgress?.('Không bắt đầu được tải video', e.message);
      S.setStatus('Không bắt đầu được tải video: ' + e.message, true);
    }
  }

  $('taiVideoWebDownloadBtn')?.addEventListener('click', startDownload);
  $('taiVideoWebUrl')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); startDownload(); }
  });
  loadStatus();
})();
