(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;
  let sourceMode = 'image';
  let sourceImage = null;
  let pollTimer = null;
  let lastResult = null;

  function setSourceMode(mode) {
    sourceMode = mode;
    $('dovat3dSourceImage')?.classList.toggle('active', mode === 'image');
    $('dovat3dSourcePrompt')?.classList.toggle('active', mode === 'prompt');
    $('dovat3dImageBox')?.classList.toggle('hidden', mode !== 'image');
    $('dovat3dPromptBox')?.classList.toggle('hidden', mode !== 'prompt');
  }
  $('dovat3dSourceImage')?.addEventListener('click', () => setSourceMode('image'));
  $('dovat3dSourcePrompt')?.addEventListener('click', () => setSourceMode('prompt'));

  $('dovat3dImageFile') && ($('dovat3dImageFile').onchange = (e) => {
    sourceImage = e.target.files[0] || null;
    $('dovat3dImageName').textContent = sourceImage ? sourceImage.name : '＋ Upload ảnh đồ vật';
  });

  async function refreshStatus() {
    const box = $('dovat3dStatus');
    if (!box) return;
    try {
      const data = await S.jsonRequest('/api/do-vat-3d/status');
      box.innerHTML = `<strong>${data.installed ? '✓ Engine 3D sẵn sàng' : 'Chưa cài engine 3D'}</strong><span>${S.esc(data.message || '')}</span>`;
      box.classList.toggle('ok-card', !!data.installed);
    } catch (e) {
      box.innerHTML = `<strong>Không kiểm tra được engine 3D</strong><span>${S.esc(e.message)}</span>`;
    }
  }

  function setProgress(d) {
    const box = $('dovat3dProgress');
    if (!box) return;
    box.classList.remove('hidden');
    const p = Math.max(0, Math.min(100, Number(d.progress || 0)));
    $('dovat3dProgressPct').textContent = `${p}%`;
    $('dovat3dProgressBar').style.width = `${p}%`;
    $('dovat3dProgressStage').textContent = d.stage || 'Đang xử lý';
    $('dovat3dProgressDetail').textContent = d.detail || '';
    S.updateBusyProgress?.(p, d.stage || 'Đang tạo đồ vật 3D', d.detail || '', 'real');
  }

  function showResult(result) {
    lastResult = result;
    $('dovat3dResult')?.classList.remove('hidden');
    $('dovat3dResultTitle').textContent = result.has_texture ? '✓ Đồ vật 3D (có màu) đã tạo' : '✓ Đồ vật 3D đã tạo';
    const dims = result.dimensions ? ` · ${result.dimensions.x?.toFixed(2)}×${result.dimensions.y?.toFixed(2)}×${result.dimensions.z?.toFixed(2)}` : '';
    $('dovat3dResultMeta').textContent =
      `${result.category_label || result.category} · ${result.engine_label || result.engine} · ` +
      `${(result.triangle_count || 0).toLocaleString('vi-VN')} tam giác${dims}` +
      (result.texture_error ? ' · tô màu lỗi, giữ shape gốc' : '');
    if (result.model_url) $('dovat3dDownload').href = result.model_url;
    if (result.viewer_url && window.AIVF3DViewer) {
      window.AIVF3DViewer.show(result.viewer_url, 'Đồ vật 3D vừa tạo');
    }
  }

  async function pollJob(statusUrl) {
    try {
      const data = await S.jsonRequest(statusUrl);
      setProgress(data);
      if (data.status === 'done') {
        S.setBusy(false);
        S.setStatus('100% · Đồ vật 3D đã tạo xong.');
        showResult(data.result || {});
        return;
      }
      if (data.status === 'error') {
        throw new Error(data.error || data.detail || 'Lỗi không rõ');
      }
      if (data.status === 'cancelled') {
        S.setBusy(false);
        S.setStatus('Đã dừng tạo đồ vật 3D.');
        return;
      }
      pollTimer = setTimeout(() => pollJob(statusUrl), 800);
    } catch (e) {
      S.setBusy(false);
      S.setStatus('Tạo đồ vật 3D lỗi: ' + e.message, true);
      $('dovat3dProgressDetail').textContent = 'Lỗi: ' + e.message;
    }
  }

  async function runCreate() {
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    $('dovat3dResult')?.classList.add('hidden');
    const category = $('dovat3dCategory').value;
    const quality = $('dovat3dQuality').value;
    const texture = $('dovat3dTexture').value;
    S.setBusy(true, 'Đang tạo đồ vật 3D…', 'Chuẩn hoá ảnh → dựng hình → tô màu → tối ưu → kiểm tra');
    setProgress({ progress: 1, stage: 'Bắt đầu', detail: '' });
    try {
      let started;
      if (sourceMode === 'prompt') {
        const prompt = $('dovat3dPrompt').value.trim();
        if (prompt.length < 3) { S.setBusy(false); return S.setStatus('Nhập mô tả đồ vật trước.', true); }
        started = await S.jsonRequest('/api/do-vat-3d/create-from-prompt', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, category, quality, texture }),
        });
      } else {
        if (!sourceImage) { S.setBusy(false); return S.setStatus('Chọn một ảnh trước.', true); }
        const form = new FormData();
        form.append('file', sourceImage);
        form.append('category', category);
        form.append('quality', quality);
        form.append('texture', texture);
        started = await S.jsonRequest('/api/do-vat-3d/create', { method: 'POST', body: form });
      }
      pollJob(started.status_url);
    } catch (e) {
      S.setBusy(false);
      S.setStatus('Không bắt đầu được tạo đồ vật 3D: ' + e.message, true);
    }
  }

  $('dovat3dRun')?.addEventListener('click', runCreate);
  $('dovat3dAgain')?.addEventListener('click', runCreate);

  window.AIVFDoVat3D = Object.assign(window.AIVFDoVat3D || {}, {
    getLastResult: () => lastResult,
  });

  refreshStatus();
})();
