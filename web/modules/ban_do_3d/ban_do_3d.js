(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;

  let job = null;
  let pollTimer = null;
  let manifest = null;
  let viewMode = 'tiles'; // 'tiles' | 'full'
  let zoom = 1, pan = [0, 0];
  let drag = null, lastPointer = [0, 0];

  async function refreshStatus() {
    const box = $('mapHdStatus');
    if (!box) return;
    try {
      const data = await S.jsonRequest('/api/ban-do-3d/status');
      box.innerHTML = `<strong>${data.ok ? '✓ Bản đồ HD sẵn sàng' : 'Chưa sẵn sàng'}</strong><span>Chất lượng: Nhẹ / Trung bình / Đẹp · Deep zoom tile gốc${data.prompt_ai ? '' : ' · AI ảnh local chưa sẵn sàng, cần ảnh mẫu'}</span>`;
      box.classList.toggle('ok-card', !!data.ok);
    } catch (e) {
      box.innerHTML = `<strong>Không kiểm tra được Bản đồ HD</strong><span>${S.esc(e.message)}</span>`;
    }
  }

  // ---------- sidebar wiring ----------

  let quality = 'standard';
  document.querySelectorAll('#panel-bandohd .map-hd-quality button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#panel-bandohd .map-hd-quality button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      quality = btn.dataset.q;
    });
  });

  let refImage = null;
  $('mapHdImageFile') && ($('mapHdImageFile').onchange = (e) => {
    refImage = e.target.files[0] || null;
    $('mapHdImageName').textContent = refImage ? refImage.name : '＋ Ảnh mẫu (khuyên dùng)';
  });

  function setProgress(stage, pct, detail) {
    const box = $('mapHdProgress');
    if (!box) return;
    box.classList.remove('hidden');
    const p = Math.max(0, Math.min(100, Number(pct || 0)));
    $('mapHdStage').textContent = stage || 'Đang xử lý';
    $('mapHdPct').textContent = `${p}%`;
    $('mapHdBar').style.width = `${p}%`;
    $('mapHdDetail').textContent = detail || '';
    S.updateBusyProgress?.(p, stage || 'Đang tạo Bản đồ HD', detail || '', 'real');
  }

  async function createMap() {
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    $('mapHdResult')?.classList.add('hidden');
    const prompt = $('mapHdPrompt').value.trim();
    if (!refImage && !prompt) { return S.setStatus('Cần ảnh mẫu hoặc mô tả map.', true); }
    const tileCount = $('mapHdTiles').value;
    $('mapHdCreate').disabled = true;
    S.setBusy(true, 'Đang tạo Bản đồ HD…', 'Khóa bố cục tổng → chia tile → tinh chỉnh → ghép');
    setProgress('Bắt đầu', 1, '');
    try {
      const form = new FormData();
      form.append('prompt', prompt);
      form.append('quality', quality);
      if (tileCount) form.append('tile_count', tileCount);
      let url = '/api/ban-do-3d/tao-tu-mo-ta';
      if (refImage) { form.append('file', refImage); url = '/api/ban-do-3d/tao-tu-anh'; }
      const started = await S.jsonRequest(url, { method: 'POST', body: form });
      job = started.job_id;
      poll(started.status_url);
    } catch (e) {
      S.setBusy(false);
      $('mapHdCreate').disabled = false;
      S.setStatus('Không tạo được Bản đồ HD: ' + e.message, true);
    }
  }
  $('mapHdCreate')?.addEventListener('click', createMap);

  async function poll(statusUrl) {
    try {
      const data = await S.jsonRequest(statusUrl);
      setProgress(data.stage, data.progress, data.detail || data.error || '');
      if (data.status === 'completed') {
        S.setBusy(false);
        $('mapHdCreate').disabled = false;
        S.setStatus('100% · Bản đồ HD đã tạo xong.');
        await showResult(data);
        return;
      }
      if (data.status === 'failed') {
        throw new Error(data.error || 'Bản đồ HD lỗi không rõ');
      }
      if (data.status === 'cancelled') {
        S.setBusy(false);
        $('mapHdCreate').disabled = false;
        S.setStatus('Đã hủy tạo Bản đồ HD.');
        return;
      }
      pollTimer = setTimeout(() => poll(statusUrl), 900);
    } catch (e) {
      S.setBusy(false);
      $('mapHdCreate').disabled = false;
      S.setStatus('Bản đồ HD lỗi: ' + e.message, true);
      $('mapHdDetail').textContent = 'Lỗi: ' + e.message;
    }
  }

  async function showResult(data) {
    manifest = await (await fetch(data.manifest_url, { cache: 'no-store' })).json();
    $('mapHdResult')?.classList.remove('hidden');
    const v = data.validation || {};
    $('mapHdResultTitle').textContent = v.pass ? '✓ Bản đồ HD đạt chuẩn liền mạch' : '⚠ Bản đồ HD đã tạo (mép nối chưa đạt ngưỡng)';
    $('mapHdResultMeta').textContent =
      `${data.tile_count} tile · ${data.width}×${data.height}px · nét ${Math.round((v.sharpness_score || 0) * 100)}% · mép nối ${Math.round((v.tile_border_score || 0) * 100)}% · ${data.elapsed_seconds}s`;
    viewMode = 'tiles';
    $('mapHdOpenFull').textContent = '🗺 MỞ MAP FULL';
    $('mapHdManifest').href = data.manifest_url;
    openInViewer();
  }

  $('mapHdOpenFull')?.addEventListener('click', () => {
    viewMode = viewMode === 'tiles' ? 'full' : 'tiles';
    $('mapHdOpenFull').textContent = viewMode === 'full' ? '🧩 XEM THEO TILE' : '🗺 MỞ MAP FULL';
    renderCanvas();
  });
  $('mapHdGridToggle')?.addEventListener('change', renderCanvas);

  // ---------- central viewer (shared stage, not a separate frame) ----------

  function hideOtherStageContent() {
    $('empty')?.classList.add('hidden');
    $('videoBox')?.classList.add('hidden');
    $('busy')?.classList.add('hidden');
    $('ai3dSourcePreview')?.classList.add('hidden');
    $('ai3dStageViewer')?.classList.add('hidden');
    document.querySelector('.transport')?.classList.add('viewer-transport-hidden');
  }

  function openInViewer() {
    hideOtherStageContent();
    $('mapHdStageViewer')?.classList.remove('hidden');
    $('mapHdEmpty')?.classList.add('hidden');
    zoom = 1; pan = [0, 0];
    applyTransform();
    renderCanvas();
  }

  function renderCanvas() {
    const canvas = $('mapHdCanvas');
    if (!canvas || !manifest) return;
    canvas.innerHTML = '';
    canvas.classList.toggle('map-hd-canvas-grid', viewMode === 'tiles');
    const showGrid = !!$('mapHdGridToggle')?.checked;
    if (viewMode === 'full') {
      const img = document.createElement('img');
      img.className = 'map-hd-full-img';
      img.alt = 'Bản đồ HD đầy đủ';
      img.src = `/api/ban-do-3d/job/${job}/full?v=${Date.now()}`;
      canvas.appendChild(img);
      $('mapHdState').textContent = `Map full · ${manifest.tiles.length} tile gốc ghép liền mạch`;
      return;
    }
    canvas.style.gridTemplateColumns = `repeat(${manifest.cols}, 220px)`;
    for (const t of manifest.tiles) {
      const cell = document.createElement('div');
      cell.className = 'map-hd-tile-cell';
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.alt = t.tile_id;
      img.src = `/api/ban-do-3d/job/${job}/tile/${t.tile_id}?v=${Date.now()}`;
      cell.appendChild(img);
      if (showGrid) {
        const label = document.createElement('span');
        label.className = 'map-hd-tile-label';
        label.textContent = `${t.tile_id} · (${t.row},${t.col})`;
        cell.appendChild(label);
        cell.classList.add('map-hd-tile-grid-on');
      }
      canvas.appendChild(cell);
    }
    $('mapHdState').textContent = `${manifest.tiles.length} tile · ${manifest.cols}×${manifest.rows} lưới · overlap ${manifest.overlap_px}px`;
  }

  function applyTransform() {
    const canvas = $('mapHdCanvas');
    if (!canvas) return;
    canvas.style.transform = `translate(${pan[0]}px, ${pan[1]}px) scale(${zoom})`;
    $('mapHdZoomText').textContent = `${Math.round(zoom * 100)}%`;
  }

  function setZoom(kind) {
    if (kind === 'in') zoom = Math.min(4, zoom * 1.25);
    else if (kind === 'out') zoom = Math.max(0.2, zoom / 1.25);
    else { zoom = 1; pan = [0, 0]; }
    applyTransform();
  }
  $('mapHdZoomIn')?.addEventListener('click', () => setZoom('in'));
  $('mapHdZoomOut')?.addEventListener('click', () => setZoom('out'));
  $('mapHdZoomReset')?.addEventListener('click', () => setZoom('reset'));

  const viewport = $('mapHdViewport');
  if (viewport) {
    viewport.addEventListener('wheel', (e) => {
      e.preventDefault();
      zoom = Math.max(0.2, Math.min(4, zoom * Math.exp(-e.deltaY * 0.0012)));
      applyTransform();
    }, { passive: false });
    viewport.addEventListener('pointerdown', (e) => {
      drag = true; lastPointer = [e.clientX, e.clientY];
      viewport.setPointerCapture(e.pointerId);
    });
    viewport.addEventListener('pointermove', (e) => {
      if (!drag) return;
      const dx = e.clientX - lastPointer[0], dy = e.clientY - lastPointer[1];
      lastPointer = [e.clientX, e.clientY];
      pan[0] += dx; pan[1] += dy;
      applyTransform();
    });
    const stopDrag = (e) => { drag = false; try { viewport.releasePointerCapture(e.pointerId); } catch (_) {} };
    viewport.addEventListener('pointerup', stopDrag);
    viewport.addEventListener('pointercancel', stopDrag);
  }

  window.AIVFMapHD = { open: openInViewer };
  refreshStatus();
})();
