(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;
  const state = { runtime: null, rect: null, drawing: false, start: null, activeJob: null };

  function ready() { return Boolean(state.runtime?.ready); }
  function setStatusCard(data) {
    state.runtime = data || {};
    const box = $('cleanupStatus');
    if (!box) return;
    const providers = (data.providers || []).join(', ') || 'chưa có provider';
    box.innerHTML = `<strong>${S.esc(data.ready ? '✓ Video Cleanup AI sẵn sàng' : 'Chưa cài Video Cleanup AI')}</strong><small>${S.esc(data.detail || providers)}</small>`;
  }

  async function refreshStatus() {
    try { setStatusCard(await S.jsonRequest('/api/cleanup/status')); }
    catch (e) { setStatusCard({ready:false, detail:e.message}); }
  }


  function setCleanupMode(mode){
    const erase = mode === 'erase';
    $('cleanupBgSection')?.classList.toggle('hidden', erase);
    $('cleanupEraseSection')?.classList.toggle('hidden', !erase);
    $('cleanupModeBg')?.classList.toggle('active', !erase);
    $('cleanupModeErase')?.classList.toggle('active', erase);
    if(!erase) clearRect();
  }
  $('cleanupModeBg')?.addEventListener('click',()=>setCleanupMode('bg'));
  $('cleanupModeErase')?.addEventListener('click',()=>setCleanupMode('erase'));

  $('cleanupSetupHint')?.addEventListener('click', () => {
    S.setStatus('Đóng app rồi double-click SETUP_VIDEO_CLEANUP_AI.bat. Cài một lần rồi mở Studio lại.');
  });

  $('bgRemoveMode')?.addEventListener('change', () => {
    $('bgColorField')?.classList.toggle('hidden', $('bgRemoveMode').value !== 'solid');
  });

  async function poll(jobId, title) {
    state.activeJob = jobId;
    S.setBusy(true, title, 'Đang khởi động job local…');
    try {
      while (true) {
        const job = await S.jsonRequest(`/api/cleanup/jobs/${jobId}`);
        S.updateBusyProgress?.(Number(job.progress || 0), job.stage || title, job.detail || '', 'real');
        if (job.status === 'done') {
          if (job.result?.editor) S.applyInfo(job.result.editor);
          S.setStatus(job.detail || 'Xử lý video xong.');
          return job;
        }
        if (job.status === 'cancelled') throw Object.assign(new Error(job.detail || 'Đã dừng Video Cleanup'), {cancelled:true});
        if (job.status === 'error') throw new Error(job.error || job.detail || 'Video Cleanup lỗi');
        await new Promise(r => setTimeout(r, 700));
      }
    } finally {
      state.activeJob = null;
      S.setBusy(false);
    }
  }

  $('bgRemoveBtn')?.addEventListener('click', async () => {
    if (!S.hasVideo()) return S.setStatus('Tải video lên trước.', true);
    if (!ready()) return S.setStatus('Chưa cài Video Cleanup AI. Chạy SETUP_VIDEO_CLEANUP_AI.bat trước.', true);
    const payload = {
      mode: $('bgRemoveMode').value,
      color: $('bgRemoveColor').value || '#00ff00',
      model: $('bgRemoveModel').value,
    };
    try {
      const created = await S.jsonRequest(`/api/cleanup/background/${S.state.sessionId}`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
      });
      await poll(created.job_id, 'Xóa nền video AI');
    } catch (e) { if(e.cancelled) S.setStatus('Đã dừng xóa nền.'); else S.setStatus('Lỗi xóa nền: ' + e.message, true); }
  });

  function videoRect() { return $('videoBox').getBoundingClientRect(); }
  function clamp(v) { return Math.max(0, Math.min(1, v)); }
  function point(ev) {
    const r = videoRect();
    return {x:clamp((ev.clientX-r.left)/Math.max(1,r.width)), y:clamp((ev.clientY-r.top)/Math.max(1,r.height))};
  }
  function normalizeRect(a,b) {
    const x1=Math.min(a.x,b.x), y1=Math.min(a.y,b.y), x2=Math.max(a.x,b.x), y2=Math.max(a.y,b.y);
    return {x:x1,y:y1,w:Math.max(.002,x2-x1),h:Math.max(.002,y2-y1)};
  }
  function renderRect() {
    const mask=$('cleanupMask'), info=$('eraseRectInfo'), apply=$('eraseApplyBtn');
    if (!mask) return;
    if (!state.rect) {
      mask.classList.add('hidden');
      if (info) info.innerHTML='<strong>Chưa chọn vùng</strong><small>Kéo một khung quanh chữ / icon cần xóa</small>';
      if (apply) apply.disabled=true;
      return;
    }
    const r=state.rect;
    mask.classList.remove('hidden');
    mask.style.left=(r.x*100)+'%'; mask.style.top=(r.y*100)+'%'; mask.style.width=(r.w*100)+'%'; mask.style.height=(r.h*100)+'%';
    if (info) info.innerHTML=`<strong>Đã chọn vùng xóa</strong><small>x ${(r.x*100).toFixed(1)}% · y ${(r.y*100).toFixed(1)}% · rộng ${(r.w*100).toFixed(1)}% · cao ${(r.h*100).toFixed(1)}%</small>`;
    if (apply) apply.disabled=!S.hasVideo();
  }
  function stopDrawing() {
    state.drawing=false; state.start=null; $('videoBox')?.classList.remove('cleanup-drawing');
    if ($('eraseDrawBtn')) $('eraseDrawBtn').textContent='▧ CHỌN LẠI VÙNG';
  }
  function clearRect() { stopDrawing(); state.rect=null; renderRect(); }

  $('eraseDrawBtn')?.addEventListener('click', () => {
    if (!S.hasVideo()) return S.setStatus('Tải video lên trước.', true);
    state.drawing=true; state.start=null; $('videoBox').classList.add('cleanup-drawing');
    $('eraseDrawBtn').textContent='KÉO CHUỘT TRÊN PREVIEW…';
    S.setStatus('Kéo một khung sát quanh chữ / icon cần xóa.');
  });
  $('eraseClearBtn')?.addEventListener('click', clearRect);
  $('erasePadding')?.addEventListener('input', e => { $('erasePaddingLabel').textContent=e.target.value+' px'; });

  const box=$('videoBox');
  box?.addEventListener('pointerdown', ev => {
    if (!state.drawing) return;
    ev.preventDefault(); ev.stopPropagation();
    state.start=point(ev); state.rect={x:state.start.x,y:state.start.y,w:.002,h:.002}; renderRect();
    try{box.setPointerCapture(ev.pointerId)}catch(_e){}
  }, true);
  box?.addEventListener('pointermove', ev => {
    if (!state.drawing || !state.start) return;
    ev.preventDefault(); state.rect=normalizeRect(state.start,point(ev)); renderRect();
  }, true);
  box?.addEventListener('pointerup', ev => {
    if (!state.drawing || !state.start) return;
    ev.preventDefault(); state.rect=normalizeRect(state.start,point(ev)); renderRect(); stopDrawing();
  }, true);

  $('eraseApplyBtn')?.addEventListener('click', async () => {
    if (!S.hasVideo()) return S.setStatus('Tải video lên trước.', true);
    if (!state.rect) return S.setStatus('Vẽ vùng cần xóa trước.', true);
    const method=$('eraseMethod').value;
    if (method==='inpaint' && !ready()) return S.setStatus('Inpaint cần SETUP_VIDEO_CLEANUP_AI.bat. Hoặc chọn FFmpeg nhanh.', true);
    const payload={...state.rect,padding:Number($('erasePadding').value||4),method};
    try {
      const created=await S.jsonRequest(`/api/cleanup/overlay/${S.state.sessionId}`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
      });
      await poll(created.job_id, method==='inpaint'?'Xóa chữ / icon · Inpaint':'Xóa chữ / icon · FFmpeg');
      clearRect();
    } catch(e) { if(e.cancelled) S.setStatus('Đã dừng xóa chữ/icon.'); else S.setStatus('Lỗi xóa chữ/icon: '+e.message,true); }
  });

  window.AIVFVideoCleanup = { onVideoChanged(){ clearRect(); }, refreshStatus };
  refreshStatus();
})();
