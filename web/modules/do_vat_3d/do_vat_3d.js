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

  let lastJobId = null;

  function showResult(result, status) {
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

    const isPartial = status === 'partial_success';
    $('dovat3dPartialNotice')?.classList.toggle('hidden', !isPartial);
    $('dovat3dRetryTexture')?.classList.toggle('hidden', !isPartial);

    const perf = $('dovat3dPerfInfo');
    if (perf) {
      const t = result.timings || {};
      const poly = result.poly || {};
      const rows = [];
      if (result.engine_label) rows.push(`Engine: ${S.esc(result.engine_label)}`);
      if (result.device) rows.push(`GPU/CPU: ${S.esc(result.device)}`);
      if (typeof t.shape_seconds === 'number') rows.push(`Shape: ${t.shape_seconds}s`);
      if (typeof t.optimize_seconds === 'number') rows.push(`Optimize: ${t.optimize_seconds}s`);
      if (typeof t.texture_seconds === 'number' && t.texture_seconds > 0) rows.push(`Texture: ${t.texture_seconds}s`);
      if (typeof t.total_seconds === 'number') rows.push(`Total: ${t.total_seconds}s`);
      if (poly.original_triangle_count) {
        rows.push(`Poly: ${poly.original_triangle_count.toLocaleString('vi-VN')} → ${(poly.optimized_triangle_count || 0).toLocaleString('vi-VN')}` +
          (poly.poly_target ? ` (target ${poly.poly_target.toLocaleString('vi-VN')}${poly.poly_target_met ? ' ✓' : ''})` : ''));
      }
      if (rows.length) {
        perf.innerHTML = rows.map(r => `<div>${r}</div>`).join('');
        perf.classList.remove('hidden');
      } else {
        perf.classList.add('hidden');
      }
    }
  }

  async function pollJob(statusUrl) {
    try {
      const data = await S.jsonRequest(statusUrl);
      setProgress(data);
      if (data.status === 'done') {
        S.setBusy(false);
        S.setStatus('100% · Đồ vật 3D đã tạo xong.');
        showResult(data.result || {}, data.status);
        return;
      }
      if (data.status === 'partial_success') {
        S.setBusy(false);
        S.setStatus('Shape 3D đã hoàn tất · tô màu chưa hoàn tất.');
        showResult(data.result || {}, data.status);
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
      lastJobId = started.job_id;
      pollJob(started.status_url);
    } catch (e) {
      S.setBusy(false);
      S.setStatus('Không bắt đầu được tạo đồ vật 3D: ' + e.message, true);
    }
  }

  async function retryTexture() {
    if (!lastJobId) return;
    const texture = $('dovat3dTexture').value;
    S.setBusy(true, 'Đang tô màu lại…', 'Dùng lại shape đã tạo, không dựng lại từ đầu');
    setProgress({ progress: 1, stage: 'Bắt đầu tô màu lại', detail: '' });
    try {
      const started = await S.jsonRequest(`/api/do-vat-3d/job/${lastJobId}/retry-texture`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texture_mode: texture === 'none' ? 'lite' : texture }),
      });
      pollJob(started.status_url);
    } catch (e) {
      S.setBusy(false);
      S.setStatus('Không tô màu lại được: ' + e.message, true);
    }
  }

  $('dovat3dRun')?.addEventListener('click', runCreate);
  $('dovat3dAgain')?.addEventListener('click', runCreate);
  $('dovat3dRetryTexture')?.addEventListener('click', retryTexture);

  window.AIVFDoVat3D = Object.assign(window.AIVFDoVat3D || {}, {
    getLastResult: () => lastResult,
  });

  refreshStatus();
})();
