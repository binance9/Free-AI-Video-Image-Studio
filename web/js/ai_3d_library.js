(() => {
  'use strict';
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;
  const esc = v => String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const fmtBytes = n => Number(n||0) < 1048576 ? `${Math.max(1,Math.round(Number(n||0)/1024))} KB` : `${(Number(n||0)/1048576).toFixed(1)} MB`;
  const fmtDate = s => { try { return new Date(s).toLocaleString('vi-VN',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}); } catch(_){ return ''; } };

  function installUi(){
    if ($('ai3dLibraryBox')) return;
    const panel = $('panel-ai3d');
    if (!panel) return;
    const style = document.createElement('style');
    style.textContent = `
      .model-library-box{border:1px solid #293b58;border-radius:14px;padding:12px;background:linear-gradient(180deg,rgba(31,45,72,.62),rgba(12,22,38,.72));}
      .model-library-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}.model-library-head>div{display:flex;flex-direction:column;gap:2px}.model-library-head small{color:#8ea6c6;font-size:11px;font-weight:500}
      .ai3d-library-grid{display:grid;grid-template-columns:1fr;gap:8px;margin-top:9px;max-height:390px;overflow:auto}.library-empty{padding:12px;border:1px dashed #304766;border-radius:10px;text-align:center}
      .ai3d-library-card{display:grid;grid-template-columns:58px minmax(0,1fr);gap:9px;padding:8px;border:1px solid #2b3f5c;border-radius:12px;background:#0e192a}.ai3d-library-icon{width:58px;height:58px;border-radius:9px;background:#070d16;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800;color:#879bbb}
      .ai3d-library-info{min-width:0;display:flex;flex-direction:column;justify-content:center;gap:3px}.ai3d-library-info strong,.ai3d-library-info small{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ai3d-library-info strong{color:#eef5ff}.ai3d-library-info small{color:#8fa6c4;font-size:10px}.ai3d-library-actions{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;gap:6px}.ai3d-library-actions .btn{min-height:33px;padding:6px 8px}.ai3d-library-actions .danger{border-color:#6c2b3a;color:#ffb4be;background:#27121a}.ai3d-library-actions .danger:hover{background:#3b1823}
    `;
    document.head.appendChild(style);
    const box = document.createElement('div');
    box.id = 'ai3dLibraryBox';
    box.className = 'model-library-box section-gap';
    box.innerHTML = `
      <div class="model-library-head"><div><strong>📦 THƯ VIỆN 3D</strong><small>Lưu 1 lần · mở test lại không dựng/rig lại</small></div><button class="btn" id="ai3dLibraryRefresh" title="Làm mới">↻</button></div>
      <button class="btn accent wide" id="ai3dLibrarySave">💾 LƯU MODEL ĐANG XEM</button>
      <div class="game-ready-status ok section-gap" id="ai3dLibraryStatus">Đang đọc thư viện 3D…</div>
      <div class="ai3d-library-grid" id="ai3dLibraryGrid"></div>`;
    panel.appendChild(box);
    $('ai3dLibrarySave')?.addEventListener('click', saveCurrent);
    $('ai3dLibraryRefresh')?.addEventListener('click', refresh);
    $('ai3dLibraryGrid')?.addEventListener('click', e => {
      const open = e.target.closest('.library-open');
      if (open) return openItem(open.dataset.id, open.dataset.name || 'Model 3D');
      const del = e.target.closest('.library-delete');
      if (del) return deleteItem(del.dataset.id, del.dataset.name || 'Model 3D');
    });
  }

  function setStatus(text,warn=false){ const el=$('ai3dLibraryStatus'); if(!el)return; el.textContent=text;el.classList.toggle('warn',!!warn);el.classList.toggle('ok',!warn); }
  function assetIdFromViewer(){ const url=window.AIVF3DViewer?.currentUrl||''; const m=url.match(/\/api\/3d\/(?:view|model)\/([^/?#]+)/); return m?decodeURIComponent(m[1]):''; }

  async function refresh(){
    installUi(); const grid=$('ai3dLibraryGrid'); if(!grid)return;
    try{
      const d=await S.jsonRequest('/api/3d/library'); const items=Array.isArray(d.items)?d.items:[];
      if(!items.length){grid.innerHTML='<div class="hint library-empty">Chưa có model đã lưu.</div>';setStatus('0 model · Game Ready xong thì bấm LƯU MODEL ĐANG XEM');return;}
      grid.innerHTML=items.map(x=>{const anim=Array.isArray(x.animations)&&x.animations.length?x.animations.join(' / '):'model tĩnh';const tri=x.triangles?`${Math.round(Number(x.triangles)/1000)}k tris · `:'';return `<article class="ai3d-library-card"><div class="ai3d-library-icon">${x.game_ready?'🦴':'3D'}</div><div class="ai3d-library-info"><strong title="${esc(x.name)}">${esc(x.name)}</strong><small>${tri}${esc(anim)}</small><small>${fmtBytes(x.size_bytes)} · ${fmtDate(x.updated_at||x.saved_at)}</small></div><div class="ai3d-library-actions"><button class="btn library-open" data-id="${esc(x.id)}" data-name="${esc(x.name)}">▶ MỞ TEST</button><button class="btn danger library-delete" data-id="${esc(x.id)}" data-name="${esc(x.name)}">🗑 XÓA</button></div></article>`;}).join('');
      setStatus(`${items.length} model đã lưu · mở lại vài giây, không chạy AI/rig lại`);
    }catch(e){grid.innerHTML='';setStatus('Không đọc được thư viện 3D: '+e.message,true);}
  }

  async function saveCurrent(){
    const assetId=assetIdFromViewer(); if(!assetId)return S.setStatus('Chưa có model trong Viewer 3D để lưu.',true);
    const vm=window.AIVF3DViewer?.meta||{}; const ready=!!(vm.skinned||(Array.isArray(vm.animations)&&vm.animations.length));
    const def=`${ready?'Game Ready':'Model 3D'} ${new Date().toLocaleDateString('vi-VN')}`; const name=window.prompt('Đặt tên model để lần sau dễ tìm:',def); if(name===null)return;
    try{setStatus('Đang lưu model…');const d=await S.jsonRequest('/api/3d/library/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset_id:assetId,name:(name||def).trim()})});S.setStatus(`Đã lưu “${d.item?.name||name}” · lần sau mở test không cần tạo 3D lại.`);await refresh();}
    catch(e){setStatus('Lưu model lỗi: '+e.message,true);S.setStatus('Lưu thư viện 3D lỗi: '+e.message,true);}
  }

  async function openItem(id,name){
    try{setStatus(`Đang mở “${name}”…`);const d=await S.jsonRequest(`/api/3d/library/${encodeURIComponent(id)}/restore`,{method:'POST'});document.body.classList.remove('home-mode');S.switchTool('ai3d');if(window.AIVF3DViewer)await window.AIVF3DViewer.show(d.viewer_url,`Thư viện 3D · ${name}`);const dl=$('ai3dDownload');if(dl){dl.href=d.model_url;dl.download=`${name||'model_3d'}.glb`;}setStatus(`Đã mở “${name}” · không tạo lại AI/rig/animation`);S.setStatus(`Đã mở “${name}” từ thư viện 3D · test ngay.`);}
    catch(e){setStatus('Mở model lỗi: '+e.message,true);S.setStatus('Mở model thư viện lỗi: '+e.message,true);}
  }

  async function deleteItem(id,name){
    if(!window.confirm(`XÓA “${name}” khỏi thư viện 3D?\n\nFile model đã lưu trong thư viện sẽ bị xóa.`))return;
    try{await S.jsonRequest(`/api/3d/library/${encodeURIComponent(id)}`,{method:'DELETE'});S.setStatus(`Đã xóa “${name}” khỏi thư viện 3D.`);await refresh();}
    catch(e){setStatus('Xóa model lỗi: '+e.message,true);S.setStatus('Xóa model thư viện lỗi: '+e.message,true);}
  }

  installUi(); refresh(); window.AIVF3DLibrary={refresh,saveCurrent};
})();
