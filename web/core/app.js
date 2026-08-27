const $ = (id) => document.getElementById(id);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const state = {
  sessionId: null,
  duration: 0,
  width: 0,
  height: 0,
  mergeFile: null,
  mergePosition: 'after',
  selected: null,
  layers: [],
  nextLayer: 1,
  giphyType: 'gifs',
};

const stickers = [
  'star','heart','arrow_right','arrow_left','arrow_up','arrow_down','bolt','check','cross','wow',
  'lol','new','hot','go','sparkles','crown','target','play','pause','game','shield','fire','alert','question',
  '1','2','3','plus','minus','ok'
];

const customStickers = ["ga_haha", "ga_yeu", "ga_wow", "ga_cay", "ga_buon", "ga_ngau", "ga_ngu", "ga_om_tim", "ga_hoi", "ga_vua", "ga_y_tuong", "ga_khoc_lon", "ga_dung", "ga_sai", "ga_sao", "ga_lap_lanh", "ga_vuong_mien", "ga_set", "ga_trai", "ga_phai", "ga_wow_text", "ga_hot", "ga_new", "ga_go"];

const toolMeta = {
  facebook: ['TẢI VIDEO TỪ FACEBOOK','Dán link Facebook công khai, tải xong đưa thẳng vào editor.'],
  bgremove: ['DỌN VIDEO AI','Xóa nền, chữ/logo hoặc vật thể trong một công cụ.'],
  erase: ['DỌN VIDEO AI','Khoanh vùng chữ, logo hoặc icon rồi xóa ngay.'],
  cut: ['CẮT VIDEO','Giữ lại đúng đoạn bạn muốn.'],
  merge: ['GHÉP VIDEO','Thêm clip vào đầu hoặc cuối video.'],
  text: ['CHÈN CHỮ','Chữ, màu, viền và nền theo ý bạn.'],
  image: ['CHÈN HÌNH ẢNH','Tải ảnh hoặc GIF từ máy rồi kéo tới mọi vị trí.'],
  sticker: ['EMOJI & NHÃN DÁN','Emoji kiểu khung chat, sticker local và GIPHY tùy chọn.'],
  caption: ['PHỤ ĐỀ AI LOCAL','Whisper local tạo chú thích và Argos dịch ngay trên máy.'],
  music: ['NHẠC LOCAL','Gợi ý trong kho nhạc trên máy, chọn đoạn ngắn và ghép vào video.'],
  aiimage: ['AI ẢNH LOCAL','Tạo hoặc sửa ảnh bằng model miễn phí trên máy rồi đưa vào video.'],
  character2d: ['NHÂN VẬT 2D','Tạo, giữ form, đổi màu và làm sạch nhân vật 2D từ prompt hoặc ảnh mẫu.'],
  ai3d: ['AI 3D LOCAL','Tạo model GLB từ ảnh hoặc mô tả bằng backend 3D tách riêng.'],
  dovat3d: ['ĐỒ VẬT 3D','Cây, đá, nhà, prop cho game - dùng chung engine 3D local.'],
  bandohd: ['BẢN ĐỒ HD','Khóa bố cục tổng trước, chia tile HD, ghép liền mạch, xuất manifest.'],
};

const taskProgress = window.AIVFTaskProgress?.create({rootId:'busy',stageId:'busyText',pctId:'busyPct',barId:'busyBar',detailId:'busyDetail',elapsedId:'busyElapsed'});
let stoppingAll=false;
function setStatus(text, error=false){ $('status').textContent=text; $('status').classList.toggle('error',error); if(error) taskProgress?.fail('Lỗi', text); }
function setBusy(on,text='Đang xử lý…',detail=''){
  $('stopAllBtn')?.classList.toggle('hidden', !on);
  if(on){
    taskProgress?.start(text, detail || 'Tiến trình ước tính · tác vụ local đang xử lý…', 'auto');
    if(!taskProgress){ $('busy').classList.remove('hidden'); $('busyText').textContent=text; }
  }else{
    if(taskProgress) taskProgress.finish('Hoàn tất','Tác vụ đã xử lý xong');
    else $('busy').classList.add('hidden');
  }
}
function updateBusyProgress(progress,stage,detail,mode='real'){
  taskProgress?.update(progress,stage,detail,mode);
}
function failBusyProgress(stage,detail){ taskProgress?.fail(stage||'Lỗi', detail||'Không xử lý được'); }
async function stopAllJobs(){
  if(stoppingAll) return;
  stoppingAll=true;
  const top=$('stopAllBtn'), inner=$('busyStopBtn');
  if(top){top.disabled=true;top.textContent='⏹ ĐANG DỪNG…';}
  if(inner){inner.disabled=true;inner.textContent='ĐANG DỪNG…';}
  try{
    const data=await jsonRequest('/api/jobs/cancel-all',{method:'POST'});
    taskProgress?.cancel('Đã dừng', data.cancelled ? `Đã gửi lệnh dừng ${data.cancelled} tác vụ` : 'Không còn job nền nào đang chạy');
    setStatus(data.cancelled ? `Đã dừng ${data.cancelled} tác vụ đang chạy.` : 'Không còn tác vụ nền nào để dừng.');
    window.dispatchEvent(new CustomEvent('aivf-stop-all'));
  }catch(e){
    setStatus('Không dừng được tác vụ: '+e.message,true);
  }finally{
    stoppingAll=false;
    if(top){top.disabled=false;top.textContent='⏹ DỪNG TẤT CẢ';top.classList.add('hidden');}
    if(inner){inner.disabled=false;inner.textContent='⏹ DỪNG';}
  }
}
$('stopAllBtn')?.addEventListener('click',stopAllJobs);
$('busyStopBtn')?.addEventListener('click',stopAllJobs);

function fmt(s){ s=Math.max(0,Number(s)||0); const m=Math.floor(s/60),x=Math.floor(s%60); return `${String(m).padStart(2,'0')}:${String(x).padStart(2,'0')}`; }
function esc(s){ return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }
function hasVideo(){ return Boolean(state.sessionId); }

async function jsonRequest(url,options={}){
  const res=await fetch(url,options); const data=await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.detail||'Không xử lý được'); return data;
}

function switchTool(name){
  if(name==='erase') name='bgremove';
  $$('.tool').forEach(b=>b.classList.toggle('active',b.dataset.tool===name));
  $$('.toolpanel').forEach(p=>p.classList.add('hidden')); $('panel-'+name).classList.remove('hidden');
  $('inspectTitle').textContent=toolMeta[name][0]; $('inspectDesc').textContent=toolMeta[name][1];
}
$$('.tool').forEach(b=>b.onclick=()=>switchTool(b.dataset.tool));

async function uploadVideo(file){
  if(!file)return; setBusy(true,`Đang tải ${file.name}…`);
  const form=new FormData(); form.append('file',file);
  try{
    const info=await jsonRequest('/api/editor/upload',{method:'POST',body:form});
    state.layers=[]; state.selected=null; applyInfo(info,true); setStatus('Video đã sẵn sàng. Sửa trực tiếp trên khung preview.');
  }catch(e){setStatus('Lỗi: '+e.message,true)} finally{setBusy(false); $('videoFile').value='';}
}
$('videoFile').onchange=e=>uploadVideo(e.target.files[0]);

function applyInfo(info,first=false){
  state.sessionId=info.session_id; state.duration=info.duration; state.width=info.width; state.height=info.height;
  $('empty').classList.add('hidden'); $('videoBox').classList.remove('hidden'); $('exportBtn').disabled=false; $('cutBtn').disabled=false;
  $('undoBtn').disabled=!info.can_undo; $('videoMeta').textContent=`${info.original_name} · ${info.width}×${info.height} · ${info.fps} FPS · ${fmt(info.duration)}`;
  $('cutStart').value=0; $('cutEnd').value=info.duration.toFixed(2); $('showTo').value=info.duration.toFixed(1);
  const video=$('video'); video.src=`/api/editor/${state.sessionId}/media?v=${Date.now()}`; video.load();
  video.onloadedmetadata=()=>{ updateTime(); renderTimeline(); updateLayerVisibility(); };
  if(first){ selectLayer(null); }
  try{localStorage.setItem('aivf_recent_video',JSON.stringify({session_id:state.sessionId,name:info.original_name,width:info.width,height:info.height,duration:info.duration,updated:Date.now()}));window.dispatchEvent(new CustomEvent('aivf-recent-updated'));}catch(_e){}
  renderTimeline(); renderLayers();
  window.AIVFVideoCleanup?.onVideoChanged?.();
}

$('newBtn').onclick=()=>location.reload();
$('undoBtn').onclick=async()=>{
  if(!hasVideo())return; setBusy(true,'Đang hoàn tác video…');
  try{ const info=await jsonRequest(`/api/editor/${state.sessionId}/undo`,{method:'POST'}); applyInfo(info); setStatus('Đã quay lại phiên bản video trước.'); }
  catch(e){setStatus('Lỗi: '+e.message,true)} finally{setBusy(false)}
};

const video=$('video');
$('playBtn').onclick=()=>{if(!hasVideo())return; video.paused?video.play():video.pause()};
video.onplay=()=>$('playBtn').textContent='❚❚'; video.onpause=()=>$('playBtn').textContent='▶';
video.ontimeupdate=()=>{ updateTime(); $('seek').value=state.duration?Math.round(video.currentTime/state.duration*1000):0; updateLayerVisibility(); updatePlayhead(); };
$('seek').oninput=e=>{if(state.duration)video.currentTime=(+e.target.value/1000)*state.duration};
$('backBtn').onclick=()=>video.currentTime=Math.max(0,video.currentTime-1); $('forwardBtn').onclick=()=>video.currentTime=Math.min(state.duration||0,video.currentTime+1);
function updateTime(){ $('timeText').textContent=`${fmt(video.currentTime)} / ${fmt(state.duration)}`; }

$('markStart').onclick=()=>$('cutStart').value=(video.currentTime||0).toFixed(2); $('markEnd').onclick=()=>$('cutEnd').value=(video.currentTime||0).toFixed(2);
$('cutBtn').onclick=async()=>{
  const start=+$('cutStart').value,end=+$('cutEnd').value; if(!(end>start))return setStatus('Điểm cuối phải lớn hơn điểm đầu.',true);
  setBusy(true,'Đang cắt video…');
  try{const info=await jsonRequest(`/api/editor/${state.sessionId}/cut`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start,end})});applyInfo(info);setStatus('Cắt xong. Xem lại ngay trên preview.');}
  catch(e){setStatus('Lỗi: '+e.message,true)}finally{setBusy(false)}
};

$('mergeFile').onchange=e=>{state.mergeFile=e.target.files[0]||null;$('mergeName').textContent=state.mergeFile?state.mergeFile.name:'＋ Chọn video để ghép';$('mergeBtn').disabled=!state.mergeFile||!hasVideo()};
$('mergeBefore').onclick=()=>setMergePos('before'); $('mergeAfter').onclick=()=>setMergePos('after');
function setMergePos(pos){state.mergePosition=pos;$('mergeBefore').classList.toggle('active',pos==='before');$('mergeAfter').classList.toggle('active',pos==='after')}
$('mergeBtn').onclick=async()=>{
  if(!state.mergeFile)return; const form=new FormData();form.append('file',state.mergeFile);form.append('position',state.mergePosition);setBusy(true,'Đang ghép video…');
  try{const info=await jsonRequest(`/api/editor/${state.sessionId}/append`,{method:'POST',body:form});applyInfo(info);state.mergeFile=null;$('mergeFile').value='';$('mergeName').textContent='＋ Chọn video để ghép';$('mergeBtn').disabled=true;setStatus('Ghép xong. Xem lại video rồi sửa tiếp nếu cần.');}
  catch(e){setStatus('Lỗi: '+e.message,true)}finally{setBusy(false)}
};

$('backgroundOpacity').oninput=e=>$('bgOpacityLabel').textContent=e.target.value+'%';
$('addText').onclick=()=>{
  if(!hasVideo())return setStatus('Tải video lên trước.',true);
  const text=$('textInput').value.trim()||'Chữ mẫu';
  const layer=newLayer({type:'text',name:text,text,source_kind:null,source:null,widthRatio:.28,
    color:$('textColor').value,outlineColor:$('outlineColor').value,outlineWidth:+$('outlineWidth').value||0,
    background:$('backgroundColor').value,backgroundOpacity:+$('backgroundOpacity').value/100,
    fontFamily:$('fontFamily')?.value||'segoe',fontSizeRatio:+($('fontSizeRatio')?.value||0.05),
    shadowColor:$('shadowColor')?.value||'#000000',shadowOpacity:+($('shadowOpacity')?.value||0)/100,shadowBlur:+($('shadowBlur')?.value||0)});
  createLayerElement(layer); selectLayer(layer); setStatus('Đã chèn chữ. Kéo trực tiếp để đặt vị trí.');
};

async function uploadAsset(file,type='image'){
  if(!hasVideo())return setStatus('Tải video lên trước.',true); if(!file)return;
  setBusy(true,'Đang thêm '+file.name+'…'); const form=new FormData();form.append('file',file);
  try{const asset=await jsonRequest(`/api/editor/${state.sessionId}/asset`,{method:'POST',body:form});const layer=newLayer({type,name:file.name,source_kind:'asset',source:asset.asset_id,previewUrl:asset.url,widthRatio:.24});createLayerElement(layer);selectLayer(layer);setStatus('Đã chèn '+file.name+'.');}
  catch(e){setStatus('Lỗi: '+e.message,true)}finally{setBusy(false)}
}
$('imageFile').onchange=e=>{uploadAsset(e.target.files[0],'image');e.target.value=''}; $('stickerFile').onchange=e=>{uploadAsset(e.target.files[0],'sticker');e.target.value=''};

function newLayer(data){
  const layer={id:'layer_'+state.nextLayer++,type:data.type,name:data.name||data.type,source_kind:data.source_kind??null,source:data.source??null,previewUrl:data.previewUrl||null,text:data.text||null,
    x:.5,y:.5,widthRatio:data.widthRatio||.22,baseWidthRatio:data.widthRatio||.22,opacity:1,rotation:0,start:0,end:state.duration||10,scale:100,
    color:data.color||'#ffffff',outlineColor:data.outlineColor||'#000000',outlineWidth:data.outlineWidth??3,background:data.background||'#000000',backgroundOpacity:data.backgroundOpacity||0,
    fontFamily:data.fontFamily||'segoe',fontSizeRatio:data.fontSizeRatio||.05,shadowColor:data.shadowColor||'#000000',shadowOpacity:data.shadowOpacity||0,shadowBlur:data.shadowBlur||0};
  state.layers.push(layer); return layer;
}

function createLayerElement(layer){
  const el=document.createElement('div');el.className='overlay '+(layer.type==='text'?'text':'');el.dataset.id=layer.id;
  if(layer.type==='text'){el.textContent=layer.text;el.style.color=layer.color;el.style.fontFamily=fontStack(layer.fontFamily);el.style.webkitTextStroke=`${Math.max(0,layer.outlineWidth/2)}px ${layer.outlineColor}`;el.style.textShadow=layer.shadowOpacity>0?`0 3px ${Math.max(1,layer.shadowBlur)}px ${hexAlpha(layer.shadowColor,layer.shadowOpacity)}`:'none';if(layer.backgroundOpacity>0)el.style.background=hexAlpha(layer.background,layer.backgroundOpacity);}
  else{const img=document.createElement('img');img.src=layer.previewUrl||sourceUrl(layer);el.appendChild(img)}
  $('overlaySurface').appendChild(el);layer.el=el;applyLayerStyle(layer);bindDrag(layer);renderLayers();renderTimeline();
}
function sourceUrl(layer){if(layer.source_kind==='builtin')return `/static/stickers/${layer.source}.png`;if(layer.source_kind==='asset')return `/api/editor/${state.sessionId}/asset/${layer.source}`;return layer.previewUrl||layer.source||''}
function hexAlpha(hex,a){const h=(hex||'#000000').replace('#','');const r=parseInt(h.slice(0,2),16)||0,g=parseInt(h.slice(2,4),16)||0,b=parseInt(h.slice(4,6),16)||0;return `rgba(${r},${g},${b},${a})`}
function fontStack(name){return {segoe:'Segoe UI,Arial,sans-serif',arial:'Arial,sans-serif',impact:'Impact,Arial Black,sans-serif',georgia:'Georgia,serif'}[name]||'Segoe UI,Arial,sans-serif'}
function applyLayerStyle(layer){if(!layer.el)return;layer.el.style.left=(layer.x*100)+'%';layer.el.style.top=(layer.y*100)+'%';layer.el.style.opacity=layer.opacity;layer.el.style.transform=`translate(-50%,-50%) rotate(${layer.rotation}deg) scale(${layer.scale/100})`;if(layer.type==='text'){layer.el.style.fontSize=Math.max(18,(layer.fontSizeRatio||.05)*$('overlaySurface').clientWidth)+'px'}else{layer.el.querySelector('img').style.width=Math.max(30,layer.baseWidthRatio*$('overlaySurface').clientWidth)+'px'}}
function bindDrag(layer){
  const el=layer.el; let sx=0,sy=0,startX=0,startY=0;
  el.onpointerdown=e=>{e.preventDefault();selectLayer(layer);el.setPointerCapture(e.pointerId);sx=e.clientX;sy=e.clientY;startX=layer.x;startY=layer.y;const rect=$('overlaySurface').getBoundingClientRect();
    el.onpointermove=ev=>{layer.x=Math.max(-.2,Math.min(1.2,startX+(ev.clientX-sx)/rect.width));layer.y=Math.max(-.2,Math.min(1.2,startY+(ev.clientY-sy)/rect.height));applyLayerStyle(layer)};
    el.onpointerup=()=>{el.onpointermove=null;el.onpointerup=null;};
  };
}
function updateLayerVisibility(){const t=video.currentTime||0;state.layers.forEach(l=>{if(l.el)l.el.style.visibility=(t>=l.start&&t<=l.end)?'visible':'hidden'})}
function selectLayer(layer){state.selected=layer;state.layers.forEach(l=>l.el&&l.el.classList.toggle('selected',l===layer));$('noSelection').classList.toggle('hidden',!!layer);$('selectionControls').classList.toggle('hidden',!layer);if(layer){$('sizeRange').value=layer.scale;$('opacityRange').value=Math.round(layer.opacity*100);$('rotationRange').value=layer.rotation;$('showFrom').value=layer.start.toFixed(1);$('showTo').value=layer.end.toFixed(1);updateControlLabels()}renderLayers()}
function updateControlLabels(){$('sizeLabel').textContent=$('sizeRange').value+'%';$('opacityLabel').textContent=$('opacityRange').value+'%';$('rotationLabel').textContent=$('rotationRange').value+'°'}
$('sizeRange').oninput=e=>{if(!state.selected)return;state.selected.scale=+e.target.value;applyLayerStyle(state.selected);updateControlLabels()};
$('opacityRange').oninput=e=>{if(!state.selected)return;state.selected.opacity=+e.target.value/100;applyLayerStyle(state.selected);updateControlLabels()};
$('rotationRange').oninput=e=>{if(!state.selected)return;state.selected.rotation=+e.target.value;applyLayerStyle(state.selected);updateControlLabels()};
$('showFrom').oninput=e=>{if(state.selected){state.selected.start=Math.max(0,+e.target.value||0);renderTimeline();updateLayerVisibility()}};
$('showTo').oninput=e=>{if(state.selected){state.selected.end=Math.max(state.selected.start,+e.target.value||state.duration);renderTimeline();updateLayerVisibility()}};
$('deleteBtn').onclick=()=>{if(!state.selected)return;state.selected.el?.remove();state.layers=state.layers.filter(l=>l!==state.selected);selectLayer(null);renderTimeline()};
$('duplicateBtn').onclick=()=>{const src=state.selected;if(!src)return;const copy={...src,id:undefined,el:undefined,name:src.name+' copy'};const l=newLayer(copy);Object.assign(l,copy,{id:l.id,el:null,x:Math.min(1,src.x+.04),y:Math.min(1,src.y+.04)});createLayerElement(l);selectLayer(l)};
$('layerUp').onclick=()=>moveLayer(1);$('layerDown').onclick=()=>moveLayer(-1);
function moveLayer(dir){const l=state.selected;if(!l)return;const i=state.layers.indexOf(l),j=Math.max(0,Math.min(state.layers.length-1,i+dir));if(i===j)return;state.layers.splice(i,1);state.layers.splice(j,0,l);state.layers.forEach(x=>$('overlaySurface').appendChild(x.el));renderLayers();renderTimeline()}

function renderLayers(){const box=$('layers');box.innerHTML='';[...state.layers].reverse().forEach(l=>{const d=document.createElement('div');d.className='layer'+(l===state.selected?' active':'');const icon=l.type==='text'?'T':l.type==='gif'?'GIF':l.type==='sticker'?'★':'▧';d.innerHTML=`<div class="thumb">${l.type==='text'?icon:`<img src="${esc(l.previewUrl||sourceUrl(l))}">`}</div><div class="meta"><b>${esc(l.name)}</b><small>${l.start.toFixed(1)}s → ${l.end.toFixed(1)}s</small></div>`;d.onclick=()=>selectLayer(l);box.appendChild(d)});if(!state.layers.length)box.innerHTML='<div class="hint">Chưa có layer chữ / ảnh / sticker.</div>'}

function renderTimeline(){const dur=state.duration||30;const r=$('ruler');r.innerHTML=[0,.25,.5,.75,1].map(v=>`<span>${fmt(dur*v)}</span>`).join('');const tracks=$('tracks');tracks.innerHTML=`<div class="track"><div class="track-name">🎬 Video chính</div><div class="trackline"><div class="clip" style="width:100%">video</div><div class="playhead" style="left:${dur?video.currentTime/dur*100:0}%"></div></div></div>`;state.layers.forEach(l=>{const left=Math.max(0,Math.min(100,l.start/dur*100)),width=Math.max(1,Math.min(100-left,(Math.min(l.end,dur)-l.start)/dur*100));const t=document.createElement('div');t.className='track';t.innerHTML=`<div class="track-name">${l.type==='text'?'T':l.type==='sticker'?'★':'▧'} ${esc(l.name)}</div><div class="trackline"><div class="clip overlayclip" style="left:${left}%;width:${width}%">${esc(l.name)}</div></div>`;tracks.appendChild(t)})}
function updatePlayhead(){const p=$('.playhead');if(p)p.style.left=(state.duration?video.currentTime/state.duration*100:0)+'%'}

// AI Video Factory exclusive mascot sticker pack
const customStickerGrid=$('customStickerGrid');
if(customStickerGrid){
  customStickers.forEach(name=>{
    const b=document.createElement('button');
    b.className='sticker-item custom-sticker-item';
    b.title=name.replace(/^ga_/,'').replaceAll('_',' ');
    b.innerHTML=`<img src="/static/stickers/${name}.png" alt="${name}">`;
    b.onclick=()=>{
      if(!hasVideo())return setStatus('Tải video lên trước.',true);
      const l=newLayer({type:'sticker',name:'Gà Con · '+b.title,source_kind:'builtin',source:name,previewUrl:`/static/stickers/${name}.png`,widthRatio:.22});
      createLayerElement(l);selectLayer(l);setStatus('Đã chèn sticker Gà Con riêng.');
    };
    customStickerGrid.appendChild(b);
  });
}

// Built-in sticker library
const stickerGrid=$('stickerGrid'); stickers.forEach(name=>{const b=document.createElement('button');b.className='sticker-item';b.title=name;b.innerHTML=`<img src="/static/stickers/${name}.png" alt="${name}">`;b.onclick=()=>{if(!hasVideo())return setStatus('Tải video lên trước.',true);const l=newLayer({type:'sticker',name:name,source_kind:'builtin',source:name,previewUrl:`/static/stickers/${name}.png`,widthRatio:.18});createLayerElement(l);selectLayer(l);setStatus('Đã chèn nhãn dán.');};stickerGrid.appendChild(b)});

const savedKey=localStorage.getItem('avf_giphy_key')||'';$('giphyKey').value=savedKey;
$('saveGiphyKey').onclick=()=>{localStorage.setItem('avf_giphy_key',$('giphyKey').value.trim());setStatus('Đã lưu GIPHY API key trên trình duyệt này.')};
$('giphyGif').onclick=()=>setGiphyType('gifs');$('giphySticker').onclick=()=>setGiphyType('stickers');
function setGiphyType(type){state.giphyType=type;$('giphyGif').classList.toggle('active',type==='gifs');$('giphySticker').classList.toggle('active',type==='stickers')}
$('giphyQuery').onkeydown=e=>{if(e.key==='Enter')searchGiphy()};$('giphySearch').onclick=searchGiphy;
async function searchGiphy(){
  const key=$('giphyKey').value.trim();if(!key)return setStatus('Nhập GIPHY API key trước.',true);localStorage.setItem('avf_giphy_key',key);
  const q=$('giphyQuery').value.trim();const endpoint=q?`https://api.giphy.com/v1/${state.giphyType}/search`:`https://api.giphy.com/v1/${state.giphyType}/trending`;
  const params=new URLSearchParams({api_key:key,limit:'24',rating:'g'});if(q)params.set('q',q);
  $('giphyGrid').innerHTML='<div class="hint">Đang tìm trên GIPHY…</div>';
  setBusy(true,'Đang tìm GIF / sticker','Đang gọi GIPHY và tải danh sách preview…');
  try{const res=await fetch(`${endpoint}?${params}`);const data=await res.json();if(!res.ok)throw new Error(data?.meta?.msg||'GIPHY lỗi');renderGiphy(data.data||[]);setStatus('Đã tải kết quả GIPHY.')}catch(e){$('giphyGrid').innerHTML=`<div class="hint">${esc(e.message)}</div>`;setStatus('Không tìm được GIPHY: '+e.message,true)}finally{setBusy(false)}
}
function renderGiphy(items){const grid=$('giphyGrid');grid.innerHTML='';items.forEach(item=>{const preview=item.images?.fixed_width?.webp||item.images?.fixed_height?.url||item.images?.original?.url;const original=item.images?.original?.url;if(!preview||!original)return;const b=document.createElement('button');b.className='giphy-item';b.title=item.title||'GIPHY';b.innerHTML=`<img src="${esc(preview)}" alt="${esc(item.title||'GIF')}">`;b.onclick=()=>{if(!hasVideo())return setStatus('Tải video lên trước.',true);const l=newLayer({type:state.giphyType==='stickers'?'sticker':'gif',name:item.title||'GIPHY',source_kind:'giphy',source:original,previewUrl:preview,widthRatio:.22});createLayerElement(l);selectLayer(l);setStatus('Đã chèn nội dung GIPHY vào preview.');};grid.appendChild(b)});if(!items.length)grid.innerHTML='<div class="hint">Không có kết quả.</div>'}


$('openResultsBtn')?.addEventListener('click',async()=>{
  try{const d=await jsonRequest('/api/system/open-folder?kind=editor',{method:'POST'});setStatus('Thư mục kết quả: '+d.path)}catch(e){setStatus(e.message,true)}
});
async function restoreSession(sessionId){
  if(!sessionId)return false;
  try{const info=await jsonRequest(`/api/editor/${sessionId}`);applyInfo(info,true);setStatus('Đã mở lại dự án gần đây.');return true}catch(e){localStorage.removeItem('aivf_recent_video');setStatus('Dự án gần đây không còn tồn tại.',true);return false}
}
$('exportBtn').onclick=async()=>{
  if(!hasVideo())return; setBusy(true,'Đang render video hoàn chỉnh…'); setStatus('Đang xuất MP4…');
  try{
    const layers=state.layers.map(toPayload);const res=await fetch(`/api/editor/${state.sessionId}/render`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({layers})});
    if(!res.ok){const d=await res.json().catch(()=>({}));throw new Error(d.detail||'Render thất bại')}
    const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=fileNameFromDisposition(res.headers.get('content-disposition'))||'video_edited.mp4';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),15000);setStatus('Đã lưu video MP4. Có thể bấm KẾT QUẢ để mở thư mục làm việc.');
  }catch(e){setStatus('Lỗi render: '+e.message,true)}finally{setBusy(false)}
};
function toPayload(l){
  const surface=$('overlaySurface').getBoundingClientRect();let widthRatio=l.baseWidthRatio*(l.scale/100);
  if(l.el&&surface.width>0)widthRatio=l.el.getBoundingClientRect().width/surface.width;
  return {id:l.id,type:l.type,source_kind:l.source_kind,source:l.source,text:l.text,x:l.x,y:l.y,width_ratio:Math.max(.02,Math.min(1.5,widthRatio)),opacity:l.opacity,rotation:l.rotation,start:l.start,end:Math.min(l.end,state.duration),font_size_ratio:l.fontSizeRatio||.05,color:l.color,outline_color:l.outlineColor,outline_width:l.outlineWidth,background:l.background,background_opacity:l.backgroundOpacity,font_family:l.fontFamily||'segoe',shadow_color:l.shadowColor||'#000000',shadow_opacity:l.shadowOpacity||0,shadow_blur:l.shadowBlur||0};
}
function fileNameFromDisposition(v){const m=/filename="?([^";]+)"?/i.exec(v||'');return m?m[1]:null}

window.addEventListener('resize',()=>state.layers.forEach(applyLayerStyle));
renderLayers();renderTimeline();

window.Studio={state,$,$$,setStatus,setBusy,updateBusyProgress,failBusyProgress,stopAllJobs,fmt,esc,hasVideo,jsonRequest,switchTool,uploadAsset,newLayer,createLayerElement,selectLayer,renderLayers,renderTimeline,applyInfo,restoreSession,video};
