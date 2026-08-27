(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;
  let sourceImage = null;
  let paintMeshFile = null;
  let lastAssetId = '';
  let pollTimer = null;
  let sourcePreviewObjectUrl = '';

  function showSourcePreview(fileOrBlob){
    const wrap = $('ai3dSourcePreview');
    const img = $('ai3dSourcePreviewImage');
    if(!wrap || !img || !fileOrBlob) return;
    if(sourcePreviewObjectUrl){ try{ URL.revokeObjectURL(sourcePreviewObjectUrl); }catch(_e){} }
    sourcePreviewObjectUrl = URL.createObjectURL(fileOrBlob);
    img.src = sourcePreviewObjectUrl;
    $('empty')?.classList.add('hidden');
    $('videoBox')?.classList.add('hidden');
    $('ai3dStageViewer')?.classList.add('hidden');
    wrap.classList.remove('hidden');
    if($('videoMeta')) $('videoMeta').textContent = 'Ảnh nguồn nhân vật 3D';
  }

  function hideSourcePreview(){ $('ai3dSourcePreview')?.classList.add('hidden'); }

  async function refreshStatus(){
    try{
      const data = await S.jsonRequest('/api/3d/status');
      const cache = data.weights_cached ? ' · weights local ✓' : '';
      $('ai3dStatus').innerHTML = `<strong>${data.installed ? '✓ TripoSR sẵn sàng' : 'Chưa cài TripoSR'}</strong><span>${S.esc((data.message || '') + cache)}</span>`;
      $('ai3dStatus').classList.toggle('ok-card', !!data.installed);
      const hd = data.backends?.character_hd || {};
      $('ai3dHdStatus').innerHTML = `<strong>${hd.installed ? '✓ Nhân vật HD sẵn sàng' : 'Chưa cài Nhân vật HD'}</strong><span>${S.esc(hd.message || data.character_hd_message || '')}</span>`;
      $('ai3dHdStatus').classList.toggle('ok-card', !!hd.installed);
      if ($('ai3dPaintStatus')){
        $('ai3dPaintStatus').innerHTML = `<strong>${hd.texture_ready ? '✓ Paint màu sẵn sàng' : 'Paint màu chưa build native'}</strong><span>${S.esc(hd.texture_message || '')}</span>`;
        $('ai3dPaintStatus').classList.toggle('ok-card', !!hd.texture_ready);
      }
    }catch(e){
      $('ai3dStatus').innerHTML = `<strong>Không kiểm tra được AI 3D</strong><span>${S.esc(e.message)}</span>`;
    }
  }


  let simpleSource = 'image';
  let autoPaintAfterShape = false;
  function setSimpleSource(source){
    simpleSource = source;
    $('ai3dSimpleImage')?.classList.toggle('active', source==='image');
    $('ai3dSimplePrompt')?.classList.toggle('active', source==='prompt');
    $('ai3dSimpleImageBox')?.classList.toggle('hidden', source!=='image');
    $('ai3dSimplePromptBox')?.classList.toggle('hidden', source!=='prompt');
    if(source==='prompt' && $('ai3dSimpleColor')) $('ai3dSimpleColor').checked=false;
  }
  function applySimpleQuality(){
    const q=$('ai3dSimpleQuality')?.value || 'balanced';
    const map={fast:{backend:'quick',resolution:'192',profile:'light'},balanced:{backend:'character_hd',resolution:'256',profile:'medium'},best:{backend:'character_hd',resolution:'256',profile:'hd'}};
    const v=map[q]||map.balanced;
    $('ai3dBackend').value=v.backend; $('ai3dResolution').value=v.resolution; $('ai3dMeshProfile').value=v.profile;
    $('ai3dOptimizeMesh').checked=true; $('ai3dTexture').checked=false;
  }
  $('ai3dSimpleImage')?.addEventListener('click',()=>setSimpleSource('image'));
  $('ai3dSimplePrompt')?.addEventListener('click',()=>setSimpleSource('prompt'));
  $('ai3dSimpleQuality')?.addEventListener('change',()=>{applySimpleQuality();if($('ai3dSimpleQuality').value==='fast' && $('ai3dSimpleColor'))$('ai3dSimpleColor').checked=false;});
  $('ai3dSimpleRun')?.addEventListener('click',()=>{
    applySimpleQuality();
    autoPaintAfterShape = simpleSource==='image' && Boolean($('ai3dSimpleColor')?.checked);
    if(simpleSource==='image') $('ai3dFromImage')?.click(); else $('ai3dFromPrompt')?.click();
  });
  applySimpleQuality(); setSimpleSource('image');

  $('ai3dImageFile').onchange = e => {
    sourceImage = e.target.files[0] || null;
    $('ai3dImageName').textContent = sourceImage ? sourceImage.name : '＋ Chọn ảnh nhân vật / vật thể';
    if(sourceImage) showSourcePreview(sourceImage);
  };

  $('ai3dPaintMeshFile').onchange = e => {
    paintMeshFile = e.target.files[0] || null;
    $('ai3dPaintMeshName').textContent = paintMeshFile ? paintMeshFile.name : 'Dùng model vừa tạo · hoặc chọn GLB khác';
  };

  $('ai3dSetupHint').onclick = () => S.setStatus('Double-click SETUP_FREE_3D.bat nếu runtime TripoSR chưa sẵn sàng.');
  $('ai3dHdSetupHint').onclick = () => S.setStatus('Double-click SETUP_CHARACTER_HD.bat để cài Character HD riêng.');
  $('ai3dPaintSetupHint').onclick = () => S.setStatus('Double-click SETUP_CHARACTER_HD_TEXTURE.bat để build phần Paint native. File này không cài lại shape/model.');

  $('ai3dFromImage').onclick = async () => {
    if (!sourceImage) return S.setStatus('Chọn một ảnh trước.', true);
    const form = new FormData();
    form.append('file', sourceImage);
    form.append('resolution', $('ai3dResolution').value);
    form.append('texture', $('ai3dTexture').checked ? 'true' : 'false');
    form.append('preview', 'false');
    form.append('backend', $('ai3dBackend').value);
    form.append('optimize_mesh', $('ai3dOptimizeMesh').checked ? 'true' : 'false');
    form.append('mesh_profile', $('ai3dMeshProfile').value || 'hd');
    await startJob('/api/3d/jobs/from-image', {method:'POST', body:form}, 'Đang khởi động AI 3D…', false);
  };

  $('ai3dFromPrompt').onclick = async () => {
    const prompt = $('ai3dPrompt').value.trim();
    if (prompt.length < 3) return S.setStatus('Nhập mô tả nhân vật/vật thể trước.', true);
    const body = {
      prompt,
      style: $('ai3dStyle').value,
      resolution: +$('ai3dResolution').value,
      texture: $('ai3dTexture').checked,
      preview: false,
      backend: $('ai3dBackend').value,
      optimize_mesh: $('ai3dOptimizeMesh').checked,
      mesh_profile: $('ai3dMeshProfile').value || 'hd',
    };
    await startJob('/api/3d/jobs/from-prompt', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
    }, 'AI đang tạo concept rồi dựng 3D…', false);
  };

  $('ai3dColorizeCurrent').onclick = async () => {
    if (!sourceImage) return S.setStatus('Chọn lại ảnh tham chiếu gốc trước khi tô màu.', true);
    if (!paintMeshFile && !lastAssetId) return S.setStatus('Chọn GLB trắng hoặc dựng model trước.', true);
    const form = new FormData();
    form.append('image', sourceImage);
    if (paintMeshFile) form.append('model', paintMeshFile);
    else form.append('asset_id', lastAssetId);
    await startJob('/api/3d/jobs/colorize', {method:'POST', body:form}, 'Khởi động tô màu GLB hiện có…', true);
  };

  function setProgress(data){
    const box = $('ai3dProgress');
    box.classList.remove('hidden');
    const p = Math.max(0, Math.min(100, Number(data.progress || 0)));
    $('ai3dProgressPct').textContent = `${p}%`;
    $('ai3dProgressBar').style.width = `${p}%`;
    $('ai3dProgressStage').textContent = data.stage || 'Đang xử lý';
    $('ai3dProgressDetail').textContent = data.detail || 'AI 3D đang chạy…';
    S.updateBusyProgress?.(p, data.stage || 'AI 3D đang chạy', data.detail || 'AI 3D đang chạy…', 'real');
    S.setStatus(`${p}% · ${data.stage || 'AI 3D đang chạy'}`);
  }

  async function startJob(url, options, busyText, isPaint){
    if (pollTimer){ clearTimeout(pollTimer); pollTimer = null; }
    $('ai3dResult').classList.add('hidden');
    let modeText = 'Shape-only ổn định: Paint cùng job đang TẮT; mesh sẽ được lưu trước.';
    if (isPaint) modeText = 'Chỉ tô màu GLB đã có · không dựng lại shape · Low VRAM.';
    else if ($('ai3dBackend').value === 'character_hd' && $('ai3dTexture').checked){
      modeText = 'Legacy Paint cùng job đang BẬT; nếu lỗi vẫn có thể mất kết quả job này.';
    }
    S.setBusy(true, busyText, modeText);
    setProgress({progress:1, stage:busyText, detail:modeText});
    try{
      const started = await S.jsonRequest(url, options);
      await pollJob(started.status_url, isPaint);
    }catch(e){
      $('ai3dProgressStage').textContent='Lỗi';
      $('ai3dProgressDetail').textContent=e.message;
      S.failBusyProgress?.(isPaint ? 'Paint HD lỗi' : 'AI 3D lỗi', e.message);
      S.setStatus((isPaint ? 'Paint HD lỗi: ' : 'AI 3D lỗi: ') + e.message, true);
    }
  }

  async function pollJob(statusUrl, isPaint=false){
    try{
      const data = await S.jsonRequest(statusUrl);
      setProgress(data);

      if (data.status === 'done'){
        const result = data.result || {};
        if (result.asset_id) lastAssetId = result.asset_id;
        $('ai3dResult').classList.remove('hidden');
        $('ai3dResultTitle').textContent = result.texture ? '✓ Model 3D màu đã tạo' : '✓ Model 3D đã tạo';
        const triInfo = result.mesh_optimized && result.faces_before && result.faces_after
          ? ` · ${Math.round(result.faces_before/1000)}k→${Math.round(result.faces_after/1000)}k tris` : '';
        const profileInfo = result.mesh_profile && !['original','existing'].includes(result.mesh_profile) ? ` · ${String(result.mesh_profile).toUpperCase()}` : '';
        const textureInfo = result.texture ? ` · texture màu HD${result.texture_size ? ` ${result.texture_size/1024}K` : ''}` : ' · chưa texture (shading)';
        $('ai3dResultMeta') && ($('ai3dResultMeta').textContent = `${result.backend || 'triposr'} · ${result.device || 'auto'}${profileInfo}${triInfo}${textureInfo}`);
        $('ai3dDownload').href = result.model_url;
        const viewerUrl = result.viewer_url || result.model_url;
        hideSourcePreview();
        if (window.AIVF3DViewer && viewerUrl) window.AIVF3DViewer.show(viewerUrl, result.texture ? 'Model 3D màu vừa tạo' : 'Model 3D vừa tạo');
        const preview = $('ai3dPreview');
        if (result.preview_url){
          preview.src = result.preview_url + '?v=' + Date.now();
          preview.classList.remove('hidden');
          preview.load();
        }else{
          preview.removeAttribute('src');
          preview.classList.add('hidden');
        }
        S.updateBusyProgress?.(100, 'Hoàn tất', result.texture ? 'GLB màu đã tạo xong' : 'GLB đã tạo xong', 'real');
        S.setBusy(false);
        S.setStatus(result.texture ? '100% · GLB màu đã tạo · mesh trắng gốc vẫn còn.' : '100% · GLB đã tạo xong · viewer 3D đã mở.');
        if(!isPaint && autoPaintAfterShape && sourceImage && result.asset_id){
          autoPaintAfterShape=false;
          S.setStatus('Shape xong · đang chuyển sang tô màu tự động…');
          setTimeout(()=>$('ai3dColorizeCurrent')?.click(),250);
        }
        return;
      }

      if (data.status === 'error'){
        const msg = data.error || data.detail || 'không rõ lỗi';
        S.failBusyProgress?.(isPaint ? 'Paint HD lỗi' : 'AI 3D lỗi', msg);
        S.setStatus((isPaint ? 'Paint HD lỗi: ' : 'AI 3D lỗi: ') + msg, true);
        return;
      }

      pollTimer = setTimeout(() => pollJob(statusUrl, isPaint), 700);
    }catch(e){
      S.setStatus('Mất kết nối tiến độ AI 3D, đang thử lại: ' + e.message);
      S.updateBusyProgress?.(undefined,'AI 3D vẫn đang chạy','Mất kết nối trạng thái tạm thời · đang thử lại…','real');
      pollTimer = setTimeout(() => pollJob(statusUrl, isPaint), 1500);
    }
  }


  $('ai3dOpenFolder')?.addEventListener('click',async()=>{try{const d=await S.jsonRequest('/api/system/open-folder?kind=3d',{method:'POST'});S.setStatus('Thư mục model 3D: '+d.path)}catch(e){S.setStatus(e.message,true)}});

  const turntableBtn = $('ai3dTurntableExport');
  if (turntableBtn) turntableBtn.onclick = async () => {
    if (!window.AIVF3DViewer?.currentUrl) return S.setStatus('Mở model trong Viewer 3D trước.', true);
    const ratio = $('ai3dTurntableRatio')?.value || '1:1';
    const duration = Number($('ai3dTurntableDuration')?.value || 8);
    const dl = $('ai3dTurntableDownload');
    dl?.classList.add('hidden');
    S.setBusy(true, 'Đang quay model 3D…', `360° · ${ratio} · ${duration}s · 1080p`);
    S.updateBusyProgress?.(3,'Chuẩn bị Viewer 3D','Đang dựng khung studio…','estimated');
    try{
      const capturePromise = window.AIVF3DViewer.captureTurntable({duration, ratio, fps:30});
      const started = Date.now();
      const timer = setInterval(()=>{
        const elapsed=(Date.now()-started)/1000;
        const p=Math.min(78,5+Math.round((elapsed/duration)*72));
        S.updateBusyProgress?.(p,'Quay model 360°',`${Math.min(duration,elapsed).toFixed(1)} / ${duration}s`,'estimated');
      },250);
      const blob = await capturePromise;
      clearInterval(timer);
      S.updateBusyProgress?.(82,'Đóng gói video','Đang chuyển WebGL capture sang MP4 H.264…','estimated');
      const form = new FormData();
      form.append('video', blob, 'aivf_turntable.webm');
      form.append('ratio', ratio);form.append('duration', String(duration));
      const resp = await fetch('/api/3d/turntable',{method:'POST',body:form});
      if(!resp.ok){let msg='Xuất MP4 thất bại';try{const j=await resp.json();msg=j.detail||msg}catch(_){msg=await resp.text()||msg}throw new Error(msg)}
      const mp4 = await resp.blob();
      const url = URL.createObjectURL(mp4);
      if (dl){ if(dl.dataset.objectUrl)URL.revokeObjectURL(dl.dataset.objectUrl);dl.dataset.objectUrl=url;dl.href=url;dl.download=`AI_Video_Factory_3D_360_${ratio.replace(':','x')}_${duration}s.mp4`;dl.classList.remove('hidden'); }
      S.updateBusyProgress?.(100,'Hoàn tất','MP4 1080p đã sẵn sàng','real');S.setBusy(false);S.setStatus('100% · Video xoay 3D đã xuất xong · bấm LƯU MP4.');
    }catch(e){S.failBusyProgress?.('Xuất video xoay 3D lỗi',e.message);S.setBusy(false);S.setStatus('Xuất video xoay 3D lỗi: '+e.message,true)}
  };

  function useImageBlob(blob, name='AI_Video_Factory_Character2D.png'){
    if (!blob) return false;
    try{
      sourceImage = new File([blob], name, {type: blob.type || 'image/png'});
    }catch(_e){
      sourceImage = blob;
      try{ Object.defineProperty(sourceImage, 'name', {value:name}); }catch(_ignored){}
    }
    showSourcePreview(sourceImage);
    setSimpleSource('image');
    if ($('ai3dImageName')) $('ai3dImageName').textContent = `✓ ${name} · từ Character 2D`;
    if ($('ai3dSimpleQuality')) $('ai3dSimpleQuality').value = 'balanced';
    applySimpleQuality();
    document.body.classList.remove('home-mode');
    S.switchTool('ai3d');
    S.setStatus('Đã nhận ảnh PASS từ Character 2D · chọn chất lượng rồi bấm TẠO MODEL 3D.');
    return true;
  }

  window.AIVF3D = Object.assign(window.AIVF3D || {}, {
    useImageBlob,
    getLastAssetId: () => lastAssetId,
    setLastAssetId: (id) => { lastAssetId = id; },
  });

  refreshStatus();
})();
