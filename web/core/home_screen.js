/* AI Video Factory 0.8.9.2 - CapCut-inspired Home UI. UI-only routing; existing editor logic stays untouched. */
(()=>{
  const $=id=>document.getElementById(id);
  const $$=s=>[...document.querySelectorAll(s)];
  const enterEditor=(tool='cut')=>{
    document.body.classList.remove('home-mode');
    if(tool && window.Studio?.switchTool) window.Studio.switchTool(tool);
  };
  const openHome=()=>{document.body.classList.add('home-mode');window.scrollTo(0,0)};
  $('homeBtn')?.addEventListener('click',openHome);
  document.querySelector('[data-home-action="home"]')?.addEventListener('click',openHome);
  $('homeAllToolsBtn')?.addEventListener('click',()=>$('homeAllTools')?.classList.toggle('hidden'));
  ['projects','templates','cloud','publish'].forEach(action=>{
    document.querySelector(`[data-home-action="${action}"]`)?.addEventListener('click',()=>{
      const msg={projects:'Dự án gần đây sẽ hiện ở cột bên trái.',templates:'Mẫu sẽ bổ sung sau; hiện chưa có mẫu giả.',cloud:'Bản local hiện không dùng Cloud.',publish:'Mở video rồi dùng nút XUẤT VIDEO ở editor.'}[action];
      window.alert?.(msg);
    });
  });
  $$('[data-tool-open]').forEach(btn=>btn.addEventListener('click',()=>enterEditor(btn.dataset.toolOpen)));
  $('homePhotoBtn')?.addEventListener('click',()=>{
    enterEditor('aiimage');
    setTimeout(()=>document.getElementById('aiRefFile')?.click(),80);
  });
  ['homeSettingsBtn','homeAiLocalBtn'].forEach(id=>$(id)?.addEventListener('click',()=>{
    enterEditor('cut');setTimeout(()=>$('apiSettingsBtn')?.click(),50);
  }));
  // A video chosen from Home automatically enters the editor while the existing upload handler owns the upload.
  $('videoFile')?.addEventListener('change',e=>{if(e.target.files?.length) enterEditor('cut')});
  const previewExpandBtn=$('previewExpandBtn');
  previewExpandBtn?.addEventListener('click',()=>{
    document.body.classList.toggle('preview-expanded');
    previewExpandBtn.textContent=document.body.classList.contains('preview-expanded')?'↙':'⛶';
  });

  function renderRecent(){
    const box=$('homeRecent'); if(!box)return;
    let item=null;try{item=JSON.parse(localStorage.getItem('aivf_recent_video')||'null')}catch(_e){}
    if(!item?.session_id){box.textContent='Tệp gần đây sẽ hiện ở đây sau khi bạn mở video/ảnh.';return;}
    box.innerHTML=`<button class="home-recent-card" id="homeRecentOpen"><strong>${item.name||'Video gần đây'}</strong><small>${item.width||'?'}×${item.height||'?'} · ${Math.round(item.duration||0)}s</small></button>`;
    $('homeRecentOpen')?.addEventListener('click',async()=>{enterEditor('cut');await window.Studio?.restoreSession?.(item.session_id)});
  }
  window.addEventListener('aivf-recent-updated',renderRecent);renderRecent();

  window.AIVFHome={open:openHome,enterEditor};
})();
