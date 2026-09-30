(()=>{
  const API='/api/ai-video-director';
  let plan=null, produceJob=null, pollTimer=null, characterReferenceId=null, characterReferenceUrl='';
  const el=(t,c,txt)=>{const n=document.createElement(t);if(c)n.className=c;if(txt!=null)n.textContent=txt;return n};
  const esc=s=>String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
  const $=id=>document.getElementById(id);

  function ensureUI(){
    const main=document.querySelector('.home-main');
    if(!main || $('aivdPage')) return;

    const homeGrid=document.querySelector('.home-tool-grid');
    if(homeGrid && !$('aivdHomeCard')){
      const hb=el('button','home-tool-card'); hb.id='aivdHomeCard'; hb.type='button'; hb.dataset.aivdOpen='1';
      hb.innerHTML='<b>🎬</b><strong>AI Director</strong><small>Ý tưởng → kịch bản → storyboard → AUTO PRODUCE</small>';
      homeGrid.insertBefore(hb,homeGrid.firstChild);
    }
    const homeNav=document.querySelector('.home-nav');
    if(homeNav && !$('aivdHomeNav')){
      const nb=el('button','home-nav-item'); nb.id='aivdHomeNav'; nb.type='button'; nb.dataset.aivdOpen='1';
      nb.innerHTML='<span>🎬</span>AI Director'; homeNav.appendChild(nb);
    }

    const page=el('section','aivd-page hidden'); page.id='aivdPage';
    page.innerHTML=`
      <div class="aivd-page-head">
        <div>
          <h1>AI Video Director</h1>
          <p>Ý tưởng → kịch bản → storyboard → ảnh → chuyển động → voice → phụ đề → nhạc → MP4.</p>
        </div>
        <div class="aivd-head-actions"><button id="aivdBackHome" class="aivd-ghost">⌂ Home</button></div>
      </div>
      <div class="aivd-workspace">
        <aside class="aivd-left">
          <div class="aivd-field"><label>Bạn muốn làm video gì?</label><textarea id="aivdIdea" placeholder="Ví dụ: Video 30 giây về một nữ cung thủ bước vào thành cổ, phong cách tiên hiệp, đăng TikTok"></textarea></div>
          <div class="aivd-row"><div class="aivd-field"><label>Thời lượng</label><select id="aivdDuration"><option value="15">15 giây</option><option value="30" selected>30 giây</option><option value="45">45 giây</option><option value="60">60 giây</option><option value="90">90 giây</option></select></div><div class="aivd-field"><label>Nền tảng</label><select id="aivdPlatform"><option>TikTok</option><option>Reels</option><option>Shorts</option><option>YouTube</option><option>Facebook</option><option>Khác</option></select></div></div>
          <div class="aivd-field"><label>Phong cách</label><input id="aivdStyle" value="cinematic, polished, modern" /></div>
          <div class="aivd-row"><div class="aivd-field"><label>Tỉ lệ</label><select id="aivdRatio"><option value="9:16">9:16 dọc</option><option value="16:9">16:9 ngang</option><option value="1:1">1:1 vuông</option></select></div><div class="aivd-field"><label>Đối tượng xem</label><input id="aivdAudience" value="người xem phổ thông" /></div></div>
          <div class="aivd-field"><label>Mục tiêu</label><input id="aivdGoal" value="thu hút người xem và truyền tải ý chính rõ ràng" /></div>
          <div class="aivd-reference-box">
            <div class="aivd-reference-head"><div><b>ẢNH NHÂN VẬT THAM CHIẾU</b><small>Có ảnh: ảnh là source of truth cho ngoại hình. Không có ảnh: Director tự tạo Character Anchor.</small></div><label class="aivd-ref-pick">+ Chọn ảnh<input id="aivdCharacterReference" type="file" accept="image/png,image/jpeg,image/webp" hidden></label></div>
            <div id="aivdReferencePreviewWrap" class="aivd-ref-preview hidden"><img id="aivdReferencePreview" alt="Character reference"><div><strong id="aivdReferenceStatus">Đã khóa ảnh tham chiếu</strong><button id="aivdReferenceRemove" type="button" class="aivd-ghost">Bỏ ảnh</button></div></div>
            <div class="aivd-ref-locks"><label><input id="aivdLockFace" type="checkbox" checked> Khóa khuôn mặt</label><label><input id="aivdLockBody" type="checkbox" checked> Khóa tỷ lệ cơ thể</label><label><input id="aivdLockCostume" type="checkbox" checked> Khóa tóc / trang phục / vũ khí</label></div>
          </div>
          <label class="aivd-check"><input id="aivdCharacterLock" type="checkbox" checked /> <span><b>Khóa nhân vật xuyên cảnh</b><small>Nếu có ảnh tham chiếu, dùng ảnh đó cho toàn bộ scene. Nếu không, tự tạo Character Anchor.</small></span></label>
          <button id="aivdCreate" class="aivd-primary">✨ 1. LÊN KỊCH BẢN + STORYBOARD</button>
          <div class="aivd-producebox">
            <div class="aivd-field"><label>Engine video</label><select id="aivdEngine"><option value="wan" selected>Director thường (Wan local, nhanh)</option><option value="framepack">FramePack · đẹp, dài, không cần ảnh (chậm)</option></select></div><div class="aivd-field"><label>Chất lượng AUTO PRODUCE</label><select id="aivdQuality"><option value="draft">Draft nhanh</option><option value="balanced">Balanced</option><option value="high">High 1080p</option><option value="high" selected>FINAL · Quality First 1080p</option></select></div>
            <div class="aivd-produce-actions"><button id="aivdProduce" class="aivd-primary aivd-green" disabled>🚀 2. AUTO PRODUCE VIDEO</button><button id="aivdCancelProduce" class="aivd-danger" disabled>■ DỪNG</button></div>
            <a id="aivdDownload" class="aivd-download hidden" href="#">⬇ TẢI FINAL_VIDEO.MP4</a>
            <div class="aivd-progress"><div id="aivdProgressBar"></div></div>
            <small id="aivdProduceDetail">Chưa chạy.</small>
          </div>
                    <div class="aivd-muted">Director điều phối các module độc lập hiện có. Người dùng chỉ cần mô tả ý tưởng; prompt, shot, voice, subtitle và edit plan được tự xây.</div>
        </aside>
        <main class="aivd-right">
          <section id="aivdLiveMonitor" class="aivd-live hidden">
            <div class="aivd-live-head"><b>LIVE PRODUCTION</b><span id="aivdLiveState">Đang chờ</span></div>
            <div class="aivd-live-grid">
              <div class="aivd-preview-wrap">
                <div id="aivdPreviewEmpty" class="aivd-preview-empty">Preview sẽ xuất hiện ngay khi có Character Anchor / Scene Image / Scene Video.</div>
                <img id="aivdPreviewImage" class="hidden" alt="Production preview"/>
                <video id="aivdPreviewVideo" class="hidden" controls muted autoplay loop playsinline></video>
              </div>
              <div class="aivd-live-info">
                <div><small>TIẾN ĐỘ</small><strong id="aivdLivePercent">0%</strong></div>
                <div><small>ĐÃ CHẠY</small><strong id="aivdElapsed">00:00</strong></div>
                <div><small>CÒN LẠI</small><strong id="aivdEta">--:--</strong></div>
                <div><small>STAGE</small><strong id="aivdLiveStage">Chưa chạy</strong></div>
              </div>
            </div>
          </section>
          <div class="aivd-toolbar"><span id="aivdStatus" class="aivd-status">Sẵn sàng</span><button id="aivdSave" class="aivd-save" disabled>💾 Lưu production package</button></div>
          <div id="aivdOutput" class="aivd-empty">Nhập một ý tưởng ở bên trái để bắt đầu.</div>
          
        </main>
      </div>`;
    main.appendChild(page);

    // FRAMEPACK engine — gan TRUC TIEP vao nut '2. AUTO PRODUCE VIDEO' co san (additive 30/09).
    // Khi engine = FramePack: chan luong Wan cu, dung y tuong + thoi luong + anh tham chieu (neu co)
    // tu CHINH FORM tren cung, ket qua hien trong LIVE PRODUCTION + nut tai cu.
    (() => {
      const $ = id => document.getElementById(id);
      const val = id => ($(id)?.value || '').trim();
      async function docAnhThamChieu() {
        const f = $('aivdCharacterReference')?.files?.[0];
        if (!f) return null;
        return await new Promise(res => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = () => res(null); r.readAsDataURL(f); });
      }
      async function framepackProduce(e) {
        e.stopPropagation(); e.preventDefault();
        const btn = $('aivdProduce'), det = $('aivdProduceDetail'), st = $('aivdStatus');
        const bar = $('aivdProgressBar'), dl = $('aivdDownload');
        const kichban = [val('aivdIdea'), val('aivdStyle') ? ('Phong cách: ' + val('aivdStyle')) : ''].filter(Boolean).join('. ');
        if (kichban.length < 5) { if (st) st.textContent = 'Nhập ý tưởng trước đã.'; return; }
        let so_giay = parseInt(val('aivdDuration') || '30', 10); if (so_giay > 60) so_giay = 60;
        if (so_giay > 10 && !confirm('Video FramePack ' + so_giay + ' giây sẽ render RẤT lâu trên card 16GB (nhiều chục phút). Vẫn chạy?')) return;
        btn.disabled = true; if (dl) dl.classList.add('hidden'); if (bar) bar.style.width = '3%';
        if (st) st.textContent = 'FramePack: đang dịch ý tưởng + chuẩn bị ảnh đầu...';
        if (det) det.textContent = 'Engine FramePack · không cần ảnh (AI tự vẽ nếu chưa chọn ảnh tham chiếu)';
        try {
          const anh = await docAnhThamChieu();
          const r = await fetch('/api/framepack/script', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kichban, so_giay, anh_base64: anh }) });
          const j = await r.json();
          if (!j.ok) { if (st) st.textContent = 'Lỗi: ' + (j.error || 'không rõ'); btn.disabled = false; return; }
          const live = $('aivdLiveMonitor'); if (live) live.classList.remove('hidden');
          if (j.image_url) { const im = $('aivdPreviewImage'); if (im) { im.src = j.image_url; im.classList.remove('hidden'); } $('aivdPreviewEmpty')?.classList.add('hidden'); const vd=$('aivdPreviewVideo'); if(vd) vd.classList.add('hidden'); }
          if (det) det.textContent = 'Prompt video: ' + (j.video_prompt || '').slice(0, 120);
          if (st) st.textContent = 'FramePack đang render ' + so_giay + ' giây...';
          let tick = 4;
          const timer = setInterval(async () => {
            try {
              const ss = await (await fetch('/api/framepack/script-status/' + j.job)).json();
              tick = Math.min(96, tick + 1.2); if (bar) bar.style.width = tick + '%';
              if (ss.done && ss.ok) {
                clearInterval(timer); if (bar) bar.style.width = '100%';
                const im = $('aivdPreviewImage'); if (im) im.classList.add('hidden');
                const vd = $('aivdPreviewVideo');
                if (vd && ss.video_url) { vd.src = ss.video_url; vd.classList.remove('hidden'); vd.play().catch(() => {}); }
                if (dl && ss.video_url) { dl.href = ss.video_url; dl.classList.remove('hidden'); }
                if (st) st.textContent = 'XONG — video FramePack đã sẵn trong khung bên phải.';
                btn.disabled = false;
              } else if (ss.done && !ss.ok) {
                clearInterval(timer); if (bar) bar.style.width = '0%';
                if (st) st.textContent = 'Lỗi render: ' + (ss.error || 'job lỗi'); btn.disabled = false;
              }
            } catch (err) { /* mat ket noi tam — poll lai */ }
          }, 5000);
        } catch (err) { if (st) st.textContent = 'Lỗi mạng: ' + err.message; btn.disabled = false; }
      }
      // capture-phase tren document: chay TRUOC listener goc cua nut — engine FramePack thi chan luong Wan
      document.addEventListener('click', e => {
        if (!(e.target instanceof Element)) return;
        if (!e.target.closest('#aivdProduce')) return;
        if (val('aivdEngine') === 'framepack') framepackProduce(e);
      }, true);
    })();







    document.addEventListener('click',e=>{
      const target=e.target.closest('[data-aivd-open="1"],#aivdHomeCard,#aivdHomeNav');
      if(target){e.preventDefault(); open();}
    });
    $('aivdBackHome').onclick=close;
    $('aivdCreate').onclick=createPlan;
    $('aivdSave').onclick=savePlan;
    $('aivdProduce').onclick=startProduce;
    $('aivdCancelProduce').onclick=cancelProduce;
    $('aivdCharacterReference').onchange=e=>uploadCharacterReference(e.target.files?.[0]);
    $('aivdReferenceRemove').onclick=removeCharacterReference;
    forceLivePlacement();

    ['homeBtn'].forEach(id=>$(id)?.addEventListener('click',close,true));
    document.querySelector('[data-home-action="home"]')?.addEventListener('click',close,true);
    document.querySelectorAll('.home-nav-item:not(#aivdHomeNav)').forEach(n=>n.addEventListener('click',()=>{ if(!n.dataset.aivdOpen) close(); },true));
  }

  function open(){
    document.body.classList.add('home-mode');
    const main=document.querySelector('.home-main'); if(!main)return;
    main.classList.add('aivd-active'); $('aivdPage')?.classList.remove('hidden');
    document.querySelectorAll('.home-nav-item').forEach(n=>n.classList.toggle('active',n.id==='aivdHomeNav'));
    forceLivePlacement();
    window.scrollTo(0,0);
  }
  function close(){
    const main=document.querySelector('.home-main'); main?.classList.remove('aivd-active'); $('aivdPage')?.classList.add('hidden');
    document.querySelectorAll('.home-nav-item').forEach(n=>n.classList.toggle('active',n.dataset.homeAction==='home'));
  }

  async function uploadCharacterReference(file){
    if(!file)return;
    const status=$('aivdStatus'); status.textContent='Đang nạp ảnh nhân vật tham chiếu…';
    try{
      const opts={method:'POST',headers:{'Content-Type':file.type||'image/png','X-File-Name':encodeURIComponent(file.name||'reference')},body:file};
      let r=await fetch(API+'/reference',opts);
      if(r.status===404){ r=await fetch(API+'/character-reference',opts); }
      let j={}; try{j=await r.json();}catch(_){j={};}
      if(!r.ok||!j.ok)throw new Error(j.detail||('Character Reference HTTP '+r.status));
      characterReferenceId=j.reference_id; characterReferenceUrl=j.preview_url+'?t='+Date.now();
      $('aivdReferencePreview').src=characterReferenceUrl; $('aivdReferencePreviewWrap').classList.remove('hidden');
      $('aivdReferenceStatus').textContent=`Đã khóa · ${j.width}×${j.height}`; $('aivdCharacterLock').checked=true;
      syncReferenceIntoPlan(); systemLog(`Character Reference: đã nạp ảnh ${j.width}x${j.height} · khóa cho toàn bộ scene`,'stdout');
      status.textContent='Ảnh tham chiếu sẵn sàng · sẽ bám nhân vật này xuyên mọi cảnh.';
    }catch(e){status.textContent='Lỗi ảnh tham chiếu: '+e.message; systemLog('LỖI Character Reference · '+e.message,'stderr');}
    finally{$('aivdCharacterReference').value='';}
  }
  async function removeCharacterReference(){
    const old=characterReferenceId; characterReferenceId=null; characterReferenceUrl='';
    $('aivdReferencePreviewWrap').classList.add('hidden'); $('aivdReferencePreview').removeAttribute('src'); syncReferenceIntoPlan();
    if(old){fetch(API+'/reference/'+encodeURIComponent(old),{method:'DELETE'}).then(r=>{if(r.status===404)return fetch(API+'/character-reference/'+encodeURIComponent(old),{method:'DELETE'});}).catch(()=>{});}
    systemLog('Character Reference: đã bỏ ảnh; Director sẽ tự tạo Character Anchor nếu cần.','stdout');
  }
  function syncReferenceIntoPlan(){
    if(!plan)return; plan.concept=plan.concept||{};
    plan.concept.character_reference_id=characterReferenceId||null;
    plan.concept.reference_lock_face=!!$('aivdLockFace')?.checked;
    plan.concept.reference_lock_body=!!$('aivdLockBody')?.checked;
    plan.concept.reference_lock_costume=!!$('aivdLockCostume')?.checked;
    if(characterReferenceId)plan.concept.character_lock=true;
  }

  async function createPlan(){
    const idea=$('aivdIdea').value.trim(); if(idea.length<3){alert('Nhập ý tưởng video trước.');return}
    const btn=$('aivdCreate'), st=$('aivdStatus');btn.disabled=true;st.textContent='Director đang xây kịch bản và storyboard…';
    try{
      const body={idea,duration_seconds:+$('aivdDuration').value,platform:$('aivdPlatform').value,aspect_ratio:$('aivdRatio').value,style:$('aivdStyle').value,audience:$('aivdAudience').value,goal:$('aivdGoal').value,captions:true,character_lock:$('aivdCharacterLock').checked,quality_priority:'quality_first'};
      const r=await fetch(API+'/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const j=await r.json(); if(!r.ok||!j.ok)throw new Error(j.detail||'Không tạo được plan'); plan=j.plan; syncReferenceIntoPlan(); render(); st.textContent=`Đã tạo ${plan.scenes?.length||0} cảnh · planner: ${plan.meta?.planner||'unknown'}`;$('aivdSave').disabled=false;$('aivdProduce').disabled=false;
    }catch(e){st.textContent='Lỗi: '+e.message;}finally{btn.disabled=false}
  }

  function render(){
    const out=$('aivdOutput');out.className='';out.innerHTML='';if(!plan)return;
    const c=plan.concept||{};const sum=el('div','aivd-summary');sum.innerHTML=`<strong>${esc(plan.title||c.idea||'Video')}</strong><small>${esc(c.platform||'')} · ${esc(String(c.duration_seconds||''))}s · ${esc(c.aspect_ratio||'')} · ${esc(c.style||'')}</small><div class="aivd-qualityline">${c.character_lock?'🔒 Character Lock ON':'Character Lock OFF'} · ${c.character_reference_id?'🖼 Reference ON · ':''}Quality First</div>`;out.appendChild(sum);
    const scenes=el('div','aivd-scenes');(plan.scenes||[]).forEach(s=>scenes.appendChild(sceneCard(s)));out.appendChild(scenes);
    [['Quality',plan.quality_policy],['Voice',plan.voice_plan],['Phụ đề',plan.caption_plan],['Âm nhạc',plan.music_plan],['Edit/QC',plan.edit_plan]].forEach(([name,obj])=>{const b=el('div','aivd-plan-block');b.innerHTML=`<h4>${name}</h4><p>${esc(JSON.stringify(obj||{},null,2))}</p>`;out.appendChild(b)});
  }
  function sceneCard(s){
    const d=el('div','aivd-scene');const cam=s.camera||{};d.innerHTML=`<div class="aivd-scene-head"><b>Scene ${esc(String(s.id))} · ${esc(s.phase||'')}</b><span class="aivd-badge">${esc(String(s.start))}–${esc(String(s.end))}s</span></div><p>${esc(s.visual||'')}</p><div class="aivd-meta"><span>🎥 ${esc(cam.framing||'')}</span><span>↗ ${esc(cam.angle||'')}</span><span>⇢ ${esc(cam.movement||'')}</span></div><div class="aivd-prompt"><b>VOICE:</b> ${esc(s.voice||'')}\n\n<b>IMAGE:</b> ${esc(s.image_prompt||'')}\n\n<b>VIDEO:</b> ${esc(s.video_prompt||'')}</div><div class="aivd-edit"><input placeholder="Chỉ sửa cảnh này, ví dụ: đổi thành trời mưa"/><button>Áp dụng</button></div>`;
    const input=d.querySelector('input'),btn=d.querySelector('button');btn.onclick=()=>patchScene(s.id,input.value,btn);return d;
  }
  async function patchScene(id,instruction,btn){if(!instruction.trim())return;btn.disabled=true;$('aivdStatus').textContent=`Đang sửa riêng Scene ${id}…`;try{const r=await fetch(API+'/patch-scene',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan,scene_id:id,instruction})});const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.detail||'Patch lỗi');plan=j.plan;render();$('aivdStatus').textContent=`Scene ${id} đã cập nhật, các scene khác được giữ nguyên.`}catch(e){$('aivdStatus').textContent='Lỗi: '+e.message}finally{btn.disabled=false}}
  async function savePlan(){if(!plan)return;const st=$('aivdStatus');st.textContent='Đang lưu production package…';try{const r=await fetch(API+'/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan})});const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.detail||'Save lỗi');st.textContent='Đã lưu: '+j.path}catch(e){st.textContent='Lỗi: '+e.message}}

  let lastSystemLogKey='', lastPreviewStamp='';
  function forceLivePlacement(){
    const box=$('aivdLiveMonitor'), produce=document.querySelector('.aivd-producebox');
    if(!box||!produce)return;
    if(box.parentElement!==produce) produce.appendChild(box);
    box.classList.add('aivd-live-inline');
  }
  function findSystemLogTarget(){
    const explicit=['#systemLog','#systemLogs','#systemOutput','#systemConsole','#logOutput','#logs','.system-log-content','.system-log-output','.system-console','.log-output','.console-output','.system-body','.log-lines'];
    for(const q of explicit){const n=document.querySelector(q);if(n&&n.offsetParent!==null)return n;}
    // The real AI Video Factory console already contains launcher/backend stdout lines.
    // Find the deepest visible node containing those lines instead of guessing a CSS selector.
    const nodes=[...document.querySelectorAll('div,pre,code,section')].filter(n=>n.offsetParent!==null);
    const logNode=nodes.filter(n=>{const t=n.textContent||'';return /stdout\s*[–-]\s*Backend|Đang kết nối system log|Backend: health OK/i.test(t);})
      .sort((a,b)=>a.children.length-b.children.length || a.textContent.length-b.textContent.length)[0];
    if(logNode){
      const inner=[...logNode.querySelectorAll('div,pre,code')].filter(n=>/stdout\s*[–-]\s*Backend|Backend: health OK/i.test(n.textContent||''));
      if(inner.length)return inner.sort((a,b)=>a.children.length-b.children.length)[0];
      return logNode;
    }
    const title=nodes.find(n=>{const own=[...n.childNodes].filter(x=>x.nodeType===3).map(x=>x.textContent).join(' ').trim().toUpperCase();return own==='HỆ THỐNG'||own==='HE THONG'||own==='SYSTEM';});
    if(title){
      let panel=title.parentElement;
      for(let i=0;i<4&&panel;i++,panel=panel.parentElement){
        const c=[...panel.querySelectorAll('div,pre,code')].filter(n=>n.clientHeight>100 && n!==title);
        if(c.length)return c.sort((a,b)=>b.clientHeight-a.clientHeight)[0];
      }
    }
    return null;
  }
  function systemLog(msg,kind='stdout'){
    if(!msg)return;
    const line=`${new Date().toLocaleTimeString('vi-VN',{hour12:false})}  ${kind} – ${msg}`;
    try{
      window.dispatchEvent(new CustomEvent('aivf:system-log',{detail:{message:msg,line,source:'AI Director',kind}}));
      document.dispatchEvent(new CustomEvent('system-log',{detail:{message:msg,line,source:'AI Director',kind}}));
    }catch(_){ }
    for(const name of ['appendSystemLog','addSystemLog','pushSystemLog','appendLogLine']){
      try{if(typeof window[name]==='function'){window[name](line,kind,'AI Director');return;}}catch(_){ }
    }
    const n=findSystemLogTarget();
    if(n){
      const row=document.createElement('div'); row.textContent=line; row.className=`aivd-system-log-line ${kind==='stderr'?'aivd-log-error':''}`;
      n.appendChild(row); n.scrollTop=n.scrollHeight; return;
    }
    console.log('[AI Director]',msg);
  }
  function setLive(j){
    const box=$('aivdLiveMonitor'); if(!box)return; box.classList.remove('hidden');
    $('aivdLivePercent').textContent=`${Math.max(0,Math.min(100,+j.progress||0))}%`;
    $('aivdElapsed').textContent=fmtTime(j.elapsed_seconds||0);
    $('aivdEta').textContent=(+j.eta_seconds>0)?fmtTime(j.eta_seconds):'--';
    $('aivdLiveStage').textContent=j.stage||'Đang chạy';
    $('aivdLiveState').textContent=j.status==='done'?'HOÀN TẤT':j.status==='error'?'LỖI':j.status==='cancelled'?'ĐÃ DỪNG':'ĐANG TẠO';
    document.querySelectorAll('.aivd-scene').forEach(x=>x.classList.remove('aivd-scene-running'));
    const m=String(j.stage||'').match(/Scene\s+(\d+)/i); if(m){const cards=document.querySelectorAll('.aivd-scene'); const i=Math.max(0,+m[1]-1); cards[i]?.classList.add('aivd-scene-running'); cards[i]?.scrollIntoView({block:'nearest',behavior:'smooth'});}
  }
  async function refreshPreview(){
    if(!produceJob)return;
    const url=`${API}/produce/${produceJob}/preview?t=${Date.now()}`;
    try{
      const r=await fetch(url,{cache:'no-store'}); if(!r.ok)return;
      const type=r.headers.get('content-type')||''; const blob=await r.blob(); if(!blob.size)return;
      const stamp=`${type}:${blob.size}`; if(stamp===lastPreviewStamp)return; lastPreviewStamp=stamp;
      const obj=URL.createObjectURL(blob), img=$('aivdPreviewImage'), vid=$('aivdPreviewVideo'), empty=$('aivdPreviewEmpty');
      empty.classList.add('hidden');
      if(type.includes('video')){ if(img.dataset.obj)URL.revokeObjectURL(img.dataset.obj); img.classList.add('hidden'); vid.src=obj; vid.dataset.obj=obj; vid.classList.remove('hidden'); vid.play().catch(()=>{}); }
      else { if(vid.dataset.obj)URL.revokeObjectURL(vid.dataset.obj); vid.pause(); vid.classList.add('hidden'); img.src=obj; img.dataset.obj=obj; img.classList.remove('hidden'); }
    }catch(_){ }
  }

  async function startProduce(){
    if(!plan)return;
    const b=$('aivdProduce'), c=$('aivdCancelProduce');b.disabled=true;c.disabled=false;$('aivdDownload').classList.add('hidden');lastPreviewStamp='';forceLivePlacement();$('aivdLiveMonitor')?.classList.remove('hidden');$('aivdLiveMonitor')?.scrollIntoView({block:'nearest',behavior:'smooth'});setProgress(1,'Đang khởi tạo AUTO PRODUCE… ETA sẽ tự học theo tốc độ máy sau vài phút.');setLive({progress:1,status:'queued',stage:'Khởi tạo',elapsed_seconds:0,eta_seconds:0});systemLog('AI Director: bắt đầu AUTO PRODUCE.','stdout');
    try{syncReferenceIntoPlan(); const selectedQuality=$('aivdQuality').value;const apiQuality=selectedQuality==='final'?'high':selectedQuality;const r=await fetch(API+'/produce',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan,quality:apiQuality})});const j=await r.json(); if(!r.ok||!j.ok)throw new Error(j.detail||'Không khởi động được AUTO PRODUCE'); produceJob=j.job_id; pollProduce();}
    catch(e){setProgress(0,'Lỗi: '+e.message);b.disabled=false;c.disabled=true}
  }
  function fmtTime(sec){
    sec=Math.max(0,Math.round(+sec||0));
    const h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),s=sec%60;
    if(h>0)return `${h}g ${m}p`;
    if(m>0)return `${m}p ${s}s`;
    return `${s}s`;
  }
  function pollProduce(){
    clearTimeout(pollTimer); if(!produceJob)return;
    fetch(API+'/produce/'+produceJob).then(async r=>{const j=await r.json(); if(!r.ok)throw new Error(j.detail||'Status lỗi');setProgress(j.progress||0,`${j.stage||''}${j.detail?' · '+j.detail:''}${j.eta_seconds>0?' · ETA '+fmtTime(j.eta_seconds):''}${j.elapsed_seconds>0?' · đã chạy '+fmtTime(j.elapsed_seconds):''}`);setLive(j);const logKey=`${j.progress}|${j.stage}|${j.detail}`;if(logKey!==lastSystemLogKey){lastSystemLogKey=logKey;systemLog(`${j.progress}% · ${j.stage||''}${j.detail?' · '+j.detail:''}`,(j.status==='error'?'stderr':'stdout'));}refreshPreview();if(j.status==='done'){$('aivdCancelProduce').disabled=true;const a=$('aivdDownload');a.href=API+'/produce/'+produceJob+'/download';a.classList.remove('hidden');$('aivdProduce').disabled=false;$('aivdStatus').textContent='AUTO PRODUCE hoàn tất · FINAL_VIDEO.mp4';systemLog('AI Director: AUTO PRODUCE hoàn tất · FINAL_VIDEO.mp4','stdout');refreshPreview();return}if(j.status==='error'||j.status==='cancelled'){$('aivdCancelProduce').disabled=true;$('aivdProduce').disabled=false;$('aivdStatus').textContent=(j.status==='error'?'Lỗi AUTO PRODUCE: ':'Đã dừng: ')+(j.detail||j.error||'');systemLog(`${j.status==='error'?'LỖI':'ĐÃ DỪNG'} · ${j.detail||j.error||''}`,j.status==='error'?'stderr':'stdout');return}pollTimer=setTimeout(pollProduce,1500)}).catch(e=>{setProgress(0,'Lỗi status: '+e.message);$('aivdProduce').disabled=false;$('aivdCancelProduce').disabled=true});
  }
  async function cancelProduce(){if(!produceJob)return;$('aivdCancelProduce').disabled=true;await fetch(API+'/produce/'+produceJob+'/cancel',{method:'POST'});setProgress(+$('aivdProgressBar').dataset.pct||0,'Đang dừng ở bước an toàn gần nhất…')}
  function setProgress(pct,msg){const p=Math.max(0,Math.min(100,+pct||0));const bar=$('aivdProgressBar');bar.style.width=p+'%';bar.dataset.pct=p;$('aivdProduceDetail').textContent=`${p}% · ${msg}`;}

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ensureUI);else ensureUI();
})();
