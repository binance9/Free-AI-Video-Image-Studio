(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;

  async function refreshGameReadyStatus(){
    const box=$('ai3dGameReadyStatus'); if(!box) return;
    try{
      const d=await S.jsonRequest('/api/3d/game-ready/status');
      box.textContent=d.installed ? `✓ Blender local sẵn sàng · ${d.pipeline?.join(' → ') || 'Game Ready'}` : (d.message || 'Chưa có Blender');
      box.classList.toggle('ok',!!d.installed); box.classList.toggle('warn',!d.installed);
    }catch(e){ box.textContent='Không kiểm tra được Game Ready: '+e.message; box.classList.add('warn'); }
  }

  // Section 33: named stages so the user always knows exactly which step
  // failed/is running, instead of one generic "processing" message.
  const STAGE_LABELS = [
    'Tối ưu mesh', 'Tạo xương', 'Gắn skin', 'Tạo Idle', 'Tạo Run',
    'Tạo Attack', 'Validate', 'Export game_ready.glb',
  ];

  function setGameReadyProgress(d){
    const el=$('ai3dGameReadyProgress'); if(!el) return;
    el.classList.remove('hidden'); const p=Math.max(0,Math.min(100,Number(d.progress||0)));
    $('ai3dGameReadyPct').textContent=`${Math.round(p)}%`; $('ai3dGameReadyBar').style.width=`${p}%`;
    $('ai3dGameReadyStage').textContent=d.stage||'Đang xử lý'; $('ai3dGameReadyDetail').textContent=d.detail||STAGE_LABELS.join(' → ');
  }

  function renderValidationDebug(validation){
    const el=$('ai3dGameReadyDebug'); if(!el) return;
    if(!validation){ el.classList.add('hidden'); return; }
    el.classList.remove('hidden');
    const clips = validation.required_clips_animated || {};
    const clipText = Object.keys(clips).map(k=>`${k}:${clips[k]?'✓':'✗'}`).join(' ');
    el.textContent =
      `Skin: ${validation.skins_count>0?'YES':'NO'} (${validation.weight_coverage!=null?Math.round(validation.weight_coverage*100)+'% vertex có weight':''})  |  ` +
      `Joints: ${validation.joints_count||0}  |  Animations: ${clipText || '(không có)'}`;
  }

  function showGameReadyResult(status, result){
    const r=result||{};
    if(r.asset_id) window.AIVF3D?.setLastAssetId(r.asset_id);
    const dl=$('ai3dGameReadyDownload');
    if(dl){dl.href=r.model_url;dl.download='game_ready.glb';dl.classList.remove('hidden');}
    const openBtn=$('ai3dGameReadyOpenViewer'); if(openBtn) openBtn.classList.remove('hidden');
    if(r.viewer_url){
      lastViewerUrl = r.viewer_url;
      if(window.AIVF3DViewer) window.AIVF3DViewer.show(r.viewer_url,{label:'Game-Ready GLB · Rig + Animation', type:'character'});
    }
    $('ai3dGameReadyFilename')?.classList.remove('hidden');
    if ($('ai3dGameReadyFilenameValue')) $('ai3dGameReadyFilenameValue').textContent = 'game_ready.glb';
    renderValidationDebug(r.validation);
    const poly=(r.faces_before&&r.faces_after)?` · ${Math.round(r.faces_before/1000)}k→${Math.round(r.faces_after/1000)}k tris`:'';
    const box=$('ai3dGameReadyStatus');
    if(status==='partial_success'){
      box.textContent=`⚠ GAME READY MỘT PHẦN · ${r.bones||'?'} bones${poly} · animation chưa đạt đủ (xem debug bên dưới)`;
      box.classList.remove('ok'); box.classList.add('warn');
      S.setBusy(false); S.setStatus('Shape + skin đã xong nhưng animation chưa đạt - chưa phải Game Ready PASS đầy đủ.', true);
    } else {
      box.textContent=`✓ GAME READY · ${r.bones||'?'} bones · ${(r.animations||['idle','run','attack_01']).join(' / ')}${poly}`;
      box.classList.add('ok'); box.classList.remove('warn');
      S.setBusy(false); S.setStatus('100% · Game-Ready GLB đã có skeleton + skin thật + idle/run/attack_01.');
    }
  }

  async function pollGameReady(url){
    try{
      const d=await S.jsonRequest(url); setGameReadyProgress(d);
      if(d.status==='done' || d.status==='partial_success'){ showGameReadyResult(d.status, d.result); return; }
      if(d.status==='error'){ throw new Error(d.error||d.detail||'Game Ready lỗi'); }
      setTimeout(()=>pollGameReady(url),900);
    }catch(e){ S.setBusy(false); $('ai3dGameReadyStatus').textContent='Game Ready lỗi: '+e.message; $('ai3dGameReadyStatus').classList.add('warn'); S.setStatus('Game Ready lỗi: '+e.message,true); }
  }

  $('ai3dGameReadySetup')?.addEventListener('click',()=>S.setStatus('Double-click SETUP_GAME_READY_3D.bat trong thư mục ai_video_factory. Cài xong mở lại bot.'));

  let lastViewerUrl = null;
  $('ai3dGameReadyOpenViewer')?.addEventListener('click',()=>{
    if(lastViewerUrl && window.AIVF3DViewer) window.AIVF3DViewer.show(lastViewerUrl,{label:'Game-Ready GLB · Rig + Animation', type:'character'});
  });

  $('ai3dMakeGameReady')?.addEventListener('click',async()=>{
    const lastAssetId = window.AIVF3D?.getLastAssetId();
    if(!lastAssetId) return S.setStatus('Tạo HD Final hoặc mở model vừa tạo trước rồi mới Game Ready.',true);
    $('ai3dGameReadyDownload')?.classList.add('hidden');
    $('ai3dGameReadyOpenViewer')?.classList.add('hidden');
    $('ai3dGameReadyFilename')?.classList.add('hidden');
    $('ai3dGameReadyDebug')?.classList.add('hidden');
    $('ai3dGameReadyStatus').classList.remove('warn','ok');
    const target=Number($('ai3dGameReadyFaces')?.value||45000);
    S.setBusy(true,'Đang tạo Game Ready…',STAGE_LABELS.join(' → '));
    setGameReadyProgress({progress:2,stage:'Chuẩn bị',detail:'Đang gửi model sang Blender local…'});
    try{
      const d=await S.jsonRequest('/api/3d/game-ready/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset_id:lastAssetId,target_faces:target})});
      pollGameReady(d.status_url);
    }catch(e){S.setBusy(false);S.setStatus('Không bắt đầu được Game Ready: '+e.message,true);$('ai3dGameReadyStatus').textContent='Không bắt đầu được: '+e.message;$('ai3dGameReadyStatus').classList.add('warn');}
  });

  window.AIVFGameReady = Object.assign(window.AIVFGameReady || {}, {refreshStatus: refreshGameReadyStatus});

  refreshGameReadyStatus();
})();
