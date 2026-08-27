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

  function setGameReadyProgress(d){
    const el=$('ai3dGameReadyProgress'); if(!el) return;
    el.classList.remove('hidden'); const p=Math.max(0,Math.min(100,Number(d.progress||0)));
    $('ai3dGameReadyPct').textContent=`${Math.round(p)}%`; $('ai3dGameReadyBar').style.width=`${p}%`;
    $('ai3dGameReadyStage').textContent=d.stage||'Đang xử lý'; $('ai3dGameReadyDetail').textContent=d.detail||'Optimize → Rig → Skin → Animation…';
  }

  async function pollGameReady(url){
    try{
      const d=await S.jsonRequest(url); setGameReadyProgress(d);
      if(d.status==='done'){
        const r=d.result||{}; if(r.asset_id) window.AIVF3D?.setLastAssetId(r.asset_id);
        const dl=$('ai3dGameReadyDownload'); if(dl){dl.href=r.model_url;dl.download=`AI_Video_Factory_${String(r.asset_id||'game_ready').slice(0,8)}_game_ready.glb`;dl.classList.remove('hidden');}
        if(r.viewer_url && window.AIVF3DViewer) window.AIVF3DViewer.show(r.viewer_url,'Game-Ready GLB · Rig + Animation');
        const poly=(r.faces_before&&r.faces_after)?` · ${Math.round(r.faces_before/1000)}k→${Math.round(r.faces_after/1000)}k tris`:'';
        $('ai3dGameReadyStatus').textContent=`✓ GAME READY · ${r.bones||'?'} bones · ${(r.animations||['idle','run','attack_01']).join(' / ')}${poly}`;
        $('ai3dGameReadyStatus').classList.add('ok'); S.setBusy(false); S.setStatus('100% · Game-Ready GLB đã có skeleton + idle/run/attack_01.'); return;
      }
      if(d.status==='error'){ throw new Error(d.error||d.detail||'Game Ready lỗi'); }
      setTimeout(()=>pollGameReady(url),900);
    }catch(e){ S.setBusy(false); $('ai3dGameReadyStatus').textContent='Game Ready lỗi: '+e.message; $('ai3dGameReadyStatus').classList.add('warn'); S.setStatus('Game Ready lỗi: '+e.message,true); }
  }

  $('ai3dGameReadySetup')?.addEventListener('click',()=>S.setStatus('Double-click SETUP_GAME_READY_3D.bat trong thư mục ai_video_factory. Cài xong mở lại bot.'));

  $('ai3dMakeGameReady')?.addEventListener('click',async()=>{
    const lastAssetId = window.AIVF3D?.getLastAssetId();
    if(!lastAssetId) return S.setStatus('Tạo HD Final hoặc mở model vừa tạo trước rồi mới Game Ready.',true);
    $('ai3dGameReadyDownload')?.classList.add('hidden');
    const target=Number($('ai3dGameReadyFaces')?.value||45000);
    S.setBusy(true,'Đang tạo Game Ready…','Optimize → Rig → Skin → Idle / Run / Attack');
    setGameReadyProgress({progress:2,stage:'Chuẩn bị',detail:'Đang gửi model sang Blender local…'});
    try{
      const d=await S.jsonRequest('/api/3d/game-ready/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset_id:lastAssetId,target_faces:target})});
      pollGameReady(d.status_url);
    }catch(e){S.setBusy(false);S.setStatus('Không bắt đầu được Game Ready: '+e.message,true);$('ai3dGameReadyStatus').textContent='Không bắt đầu được: '+e.message;$('ai3dGameReadyStatus').classList.add('warn');}
  });

  window.AIVFGameReady = Object.assign(window.AIVFGameReady || {}, {refreshStatus: refreshGameReadyStatus});

  refreshGameReadyStatus();
})();
