(()=>{
'use strict';
let Studio=window.Studio||null;
const $=id=>(window.Studio?.$?window.Studio.$(id):document.getElementById(id));
async function ensureStudio(timeoutMs=10000){
 const t=Date.now();
 while(Date.now()-t<timeoutMs){
   if(window.Studio?.$){
     Studio=window.Studio;
     return Studio;
   }
   await new Promise(r=>setTimeout(r,50));
 }
 throw new Error('Studio frontend chưa sẵn sàng');
}
const B={attachment:null,current:null,busy:false,pendingBrainRun:null,brainPaintUntil:0,jobs:new Map(),lastFailure:null,activeCharacterPlan:null};
const META={
 cut:{title:'Cắt video',run:'cutBtn'},merge:{title:'Ghép video',run:'mergeBtn'},caption:{title:'Phụ đề AI',run:'captionTranscribe'},bgremove:{title:'Dọn video AI',run:'bgRemoveBtn'},aiimage:{title:'AI Ảnh',run:'aiImageRun'},music:{title:'Thêm nhạc',run:'musicSearch'},sticker:{title:'Emoji & Sticker'},facebook:{title:'Tải Facebook',run:'facebookDownloadBtn'},taivideoweb:{title:'Tải Video Web',run:'taiVideoWebDownloadBtn'},text:{title:'Văn bản',run:'addText'},image:{title:'Ảnh / Overlay'},character2d:{title:'Nhân vật 2D',run:'char2dGenerate'},ai3d:{title:'Nhân vật 3D',run:'ai3dSimpleRun'},dovat3d:{title:'Đồ vật 3D',run:'dovat3dRun'},bandohd:{title:'Bản đồ HD',run:'mapHdCreate'},
 // gameready has no panel of its own - its button lives inside the ai3d panel
 // (rig+animation for a character already generated there). No `run` id here:
 // switchTo()/nativeRun() special-case this target to the real ai3d panel.
 gameready:{title:'Game Ready (rig+animation)'}
};
const JOB_RULES={
 character2d:{module:'character2d',scope:'character_2d',label:'Nhân vật 2D',limit:900,stall:180,cancel:null},
 character3d:{module:'ai3d',scope:'character_3d',label:'Nhân vật 3D',limit:900,stall:180,cancel:id=>`/api/3d/jobs/${id}/cancel`},
 object3d:{module:'dovat3d',scope:'object_3d',label:'Đồ vật 3D',limit:600,stall:150,cancel:id=>`/api/do-vat-3d/job/${id}/cancel`},
 map:{module:'bandohd',scope:'map_hd',label:'Bản đồ HD',limit:600,stall:150,cancel:id=>`/api/ban-do-3d/job/${id}/huy`},
 aiimage:{module:'aiimage',scope:'image',label:'AI Ảnh',limit:null,stall:180,cancel:id=>`/api/ai-image/jobs/${id}/cancel`},
 gameReady:{module:'ai3d',scope:'game_ready_3d',label:'Game Ready',limit:900,stall:180,cancel:null}
};
function emit(text,level='info'){window.dispatchEvent(new CustomEvent('ga-brain-message',{detail:{text,level}}))}
function val(id){const e=$(id);if(!e)return null;if(e.type==='checkbox')return !!e.checked;return e.value}
function set(id,v){const e=$(id);if(!e||v===undefined||v===null)return;if(e.type==='checkbox')e.checked=!!v;else e.value=String(v);e.dispatchEvent(new Event('change',{bubbles:true}))}
function click(id){const e=$(id);if(!e)return false;e.click();return true}
function visibleModule(){for(const k of Object.keys(META)){const p=$('panel-'+k);if(p&&!p.classList.contains('hidden'))return k}return null}
function putFile(inputId,file){const input=$(inputId);if(!input||!file)return false;try{const dt=new DataTransfer();dt.items.add(file);input.files=dt.files;input.dispatchEvent(new Event('change',{bubbles:true}));return true}catch(_e){return false}}
function context(){return {current_module:visibleModule(),has_video:!!window.Studio?.hasVideo?.(),merge_file:!!$('mergeFile')?.files?.length,attachment:!!B.attachment,attachment_name:B.attachment?.name||'',attachment_size:B.attachment?.size||0,last_failure:B.lastFailure?{scope:B.lastFailure.job?.rule?.scope||'',label:B.lastFailure.job?.rule?.label||'',stage:B.lastFailure.data?.stage||'',error:B.lastFailure.data?.error||B.lastFailure.data?.detail||B.lastFailure.data?.message||''}:null,forms:{aiimage:{prompt:val('aiImagePrompt'),style:val('aiImageStyle'),quality:val('aiImageQuality'),size:val('aiImageSize')},character2d:{prompt:val('char2dPrompt'),quality:val('char2dQuality'),strength:val('char2dStrength')},ai3d:{prompt:val('ai3dPrompt'),style:val('ai3dStyle'),quality:val('ai3dSimpleQuality'),color:val('ai3dSimpleColor')},dovat3d:{prompt:val('dovat3dPrompt'),category:val('dovat3dCategory'),quality:val('dovat3dQuality'),texture:val('dovat3dTexture')},bandohd:{prompt:val('mapHdPrompt'),tiles:val('mapHdTiles')},cut:{start:val('cutStart'),end:val('cutEnd')},caption:{language:val('captionLanguage'),preset:val('captionPreset')},music:{wish:val('musicWish'),volume:val('musicVolume'),keep_original:val('musicKeepOriginal'),smart:val('musicSmart')},taivideoweb:{url:val('taiVideoWebUrl'),quality:val('taiVideoWebQuality'),mode:val('taiVideoWebMode')},facebook:{url:val('facebookUrl')},text:{text:val('textInput')}}}}
async function api(url,opt={}){
 const r=await fetch(url,opt);
 const d=await r.json().catch(()=>({}));
 if(!r.ok){
   if(r.status===404&&String(url).startsWith('/api/ga-brain/')){
     throw new Error('BACKEND_CU_404: tab này đang nối vào backend cũ. Dùng tab V7 mới mà launcher mở.');
   }
   throw new Error(d.detail||d.error||`HTTP ${r.status}`);
 }
 return d;
}
function mountStrip(target,status){
 const panel=document.getElementById('panel-'+target);
 if(!panel)return null;
 let strip=panel.querySelector('.module-brain-strip');
 if(!strip){
   strip=document.createElement('div');
   strip.className='module-brain-strip';
   strip.innerHTML='<strong>🧠 Gà Brain</strong><span></span><button type="button">Tối ưu</button>';
   panel.insertBefore(strip,panel.firstChild);
   strip.querySelector('button')?.addEventListener('click',()=>optimizeCurrent());
 }
 if(status!==undefined){
   const span=strip.querySelector('span');
   if(span)span.textContent=status;
 }
 return strip;
}
function switchTo(target){if(!META[target])return;const panelTarget=target==='gameready'?'ai3d':target;document.body.classList.remove('home-mode');window.Studio?.switchTool?.(panelTarget);B.current=target;mountStrip(panelTarget)}
function qualityButton(q){document.querySelector(`#panel-bandohd .map-hd-quality button[data-q="${CSS.escape(q)}"]`)?.click()}
function apply(target,f={},useAttachment=true){
 // useAttachment=false means the backend explicitly decided the attached
 // photo no longer matches this request (see service.py's reference-conflict
 // check, e.g. photo shows a bow but this turn asks for a saber) - honor
 // that here too, otherwise this function would silently re-attach B.attachment
 // from its own state regardless of what the backend decided.
 const hasRef=useAttachment&&!!B.attachment;
 if(target==='aiimage'){set('aiImagePrompt',f.prompt);set('aiImageStyle',f.style);set('aiImageQuality',f.quality);set('aiImageSize',f.size);if(hasRef)putFile('aiRefFile',B.attachment)}
 else if(target==='character2d'){set('char2dPrompt',f.prompt);set('char2dQuality',f.quality);set('char2dStrength',f.strength);if(hasRef)putFile('char2dRefFile',B.attachment)}
 else if(target==='ai3d'){B.activeCharacterPlan={requirements:f.requirements||[],unsupported:f.unsupported_requirements||[],needsGameReady:!!f.needs_game_ready};if(hasRef){click('ai3dSimpleImage');putFile('ai3dImageFile',B.attachment)}else{click('ai3dSimplePrompt');set('ai3dPrompt',f.prompt)}set('ai3dStyle',f.style);set('ai3dSimpleQuality',f.quality);set('ai3dSimpleColor',f.color)}
 else if(target==='dovat3d'){if(B.attachment){click('dovat3dSourceImage');putFile('dovat3dImageFile',B.attachment)}else{click('dovat3dSourcePrompt');set('dovat3dPrompt',f.prompt)}set('dovat3dCategory',f.category);set('dovat3dQuality',f.quality);set('dovat3dTexture',f.texture)}
 else if(target==='gameready'){if(f.target_faces)set('ai3dGameReadyFaces',f.target_faces);if(f.weapon_type){const w=String(f.weapon_type).toLowerCase();const isBlade=['sword','blade','katana','dao','kiem','kiếm','đao'].some(x=>w.includes(x));const isStaff=['staff','rod','wand','gay','gậy','truong','trượng'].some(x=>w.includes(x));const isSpear=['spear','lance','polearm','giao','giáo','thuong','thương'].some(x=>w.includes(x));set('ai3dGameReadyWeapon',isBlade?'sword':isStaff?'staff':isSpear?'spear':'bow')}}
 else if(target==='bandohd'){set('mapHdPrompt',f.prompt);set('mapHdTiles',f.tiles);if(f.quality)qualityButton(f.quality);if(B.attachment)putFile('mapHdImageFile',B.attachment)}
 else if(target==='cut'){set('cutStart',f.start);set('cutEnd',f.end)}
 else if(target==='merge'){set('mergeName',f.name)}
 else if(target==='caption'){set('captionLanguage',f.language);set('captionPreset',f.preset)}
 else if(target==='bgremove'){click(f.cleanup_mode==='erase'?'cleanupModeErase':'cleanupModeBg')}
 else if(target==='music'){set('musicWish',f.wish);set('musicVolume',f.volume);set('musicKeepOriginal',f.keep_original);set('musicSmart',f.smart)}
 else if(target==='taivideoweb'){set('taiVideoWebUrl',f.url);set('taiVideoWebQuality',f.quality);set('taiVideoWebMode',f.mode)}
 else if(target==='facebook'){set('facebookUrl',f.url)}
 else if(target==='text'){set('textInput',f.text)}
}
function nativeRun(plan){const t=plan.target,f=plan.fields||{};if(plan.action!=='run')return {started:false,message:plan.needs_user||'Tao đã mở đúng khung và chuẩn bị thông số.'};if(t==='caption'){B.pendingBrainRun='caption';click('captionTranscribe');return {started:true}}if(t==='music'){click('musicSearch');return {started:false,message:'Tao đã tìm nhạc trong đúng khung. Nghe/chọn bài rồi tao sẽ nhớ lựa chọn.'}}if(t==='bgremove'&&f.cleanup_mode==='erase')return {started:false,message:plan.needs_user||'Tao đã vào Dọn video AI. Khoanh vùng cần xóa trên preview trước.'};const id=t==='gameready'?'ai3dMakeGameReady':META[t]?.run;if(id){B.pendingBrainRun=t;setTimeout(()=>{if(B.pendingBrainRun===t)B.pendingBrainRun=null},3500);if(click(id))return {started:true}}return {started:false,message:plan.needs_user||'Đã mở đúng khung; còn thiếu dữ liệu để chạy.'}}
function currentSettings(module){const c=context().forms[module]||{};if(module==='bandohd')c.quality=document.querySelector('#panel-bandohd .map-hd-quality button.active')?.dataset?.q||'standard';return c}
async function remember(module,source='manual'){if(!META[module])return;try{await api('/api/ga-brain/remember',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({module,settings:currentSettings(module),source})})}catch(_e){}}
function watchManualRuns(){for(const [module,m] of Object.entries(META)){if(!m.run)continue;$(m.run)?.addEventListener('click',()=>remember(module,'native-run'),true)}}
async function plan(message,forceTarget=null,optimizeOnly=false){return api('/api/ga-brain/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,context:context(),force_target:forceTarget,optimize_only:optimizeOnly})})}
async function interact(message){
 if(B.attachment){
   const fd=new FormData();
   fd.append('message',message);
   fd.append('context_json',JSON.stringify(context()));
   fd.append('file',B.attachment,B.attachment.name||'reference.png');
   return api('/api/ga-brain/interact-with-image',{method:'POST',body:fd});
 }
 return api('/api/ga-brain/interact',{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({message,context:context()})
 });
}
function classifyStart(url){const u=String(url||'');if(/\/api\/3d\/game-ready\/jobs$/.test(u))return 'gameReady';if(/\/api\/do-vat-3d\/(create|create-from-prompt)$/.test(u))return 'object3d';if(/\/api\/3d\/jobs\/(from-image|from-prompt|colorize)$/.test(u))return 'character3d';if(/\/api\/character-2d\/jobs$/.test(u))return 'character2d';if(/\/api\/ban-do-3d\/(tao-tu-anh|tao-tu-mo-ta)$/.test(u))return 'map';if(/\/api\/ai-image\/jobs\/(generate|edit)$/.test(u))return 'aiimage';return null}
async function waitServerAndReload(){
 emit('Backend đang tự restart để nạp bản sửa đã PASS. Tao chờ server lên lại…','warn');
 for(let i=0;i<80;i++){
  await new Promise(r=>setTimeout(r,1000));
  try{const r=await nativeFetch('/api/health',{cache:'no-store'});if(r.ok){location.reload();return}}catch(_e){}
 }
 emit('Backend chưa lên lại sau 80 giây. Mở lại AI Video Factory bằng launcher để xem log.','error')
}
async function rerunAfterResourceRecovery(job){
 if(job.recoveryRetries>=1||!job.byBrain)return false;
 job.recoveryRetries++;
 if(job.kind==='character3d'&&job.phase==='paint'){
   emit('Nhân vật 3D: đã dọn tài nguyên. Tao retry ĐÚNG bước Paint 1 lần, không dựng lại Shape.','warn');
   B.brainPaintUntil=Date.now()+120000;
   await new Promise(r=>setTimeout(r,700));
   return !!click('ai3dColorizeCurrent');
 }
 emit(`${job.rule.label}: đã dọn tài nguyên an toàn. Tao retry đúng 1 lần bằng chính form hiện tại.`,'warn');
 B.pendingBrainRun=job.rule.module;
 await new Promise(r=>setTimeout(r,500));
 const r=nativeRun({target:job.rule.module,action:'run',fields:context().forms[job.rule.module]||{}});
 return !!r.started;
}
async function selfHealFailure(job,data){
 if(job.healHandled)return;job.healHandled=true;
 emit(`${job.rule.label} báo lỗi. Tao đang đọc đúng stderr/traceback của job trên PowerShell trước khi đụng vào source…`,'warn');
 try{
  const d=await api('/api/ga-brain/heal-job',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope:job.rule.scope,job_id:job.id,job_state:data||{}})});
  for(const m of d.messages||[])emit(m,d.fixed?'warn':(d.manual_review_required?'error':'warn'));
  const summary=repairReport(d,job);
  for(const line of summary)emit(line,d.fixed?'warn':(d.manual_review_required?'error':'warn'));
  if(d.fixed&&d.restart_required){
   emit('Repair source đã PASS toàn bộ smoke/static test. Tao giữ source ở bản PASS. Để tránh vòng launcher Windows, tao không tự restart; mở lại AI Video Factory một lần để nạp code mới.','warn');
   return;
  }
  if(d.resource_recovered&&d.retry_safe){
   const retried=await rerunAfterResourceRecovery(job);
   if(!retried)emit('Tài nguyên đã được dọn nhưng tao không tự retry vì job này không do Gà khởi tạo hoặc đã retry đủ 1 lần.','warn');
   return;
  }
  if(d.manual_review_required&&!d.proposed_patch)emit('Tao chưa có bằng chứng đủ chắc để sửa file. Source được giữ nguyên; không có sửa mò.','error');
  if(d.proposed_patch)emit(`Diff đề xuất:\n${d.proposed_patch.diff||''}`,'warn');
 }catch(e){emit('SELF-HEAL không đọc được log job: '+e.message+'. Tao giữ nguyên source.','error')}
}
async function monitorJob(job){let data={};while(B.jobs.has(job.key)){await new Promise(r=>setTimeout(r,1500));try{const r=await fetch(job.statusUrl,{cache:'no-store',headers:{'X-GA-WATCHDOG':'1'}});data=await r.json().catch(()=>({}));if(!r.ok)continue;const sig=`${data.progress}|${data.stage}|${data.status}|${data.detail||data.message||''}`;if(sig!==job.lastSig){job.lastSig=sig;job.lastChange=Date.now();job.stallNotified=false}updateStrip(job,data);const st=String(data.status||'').toLowerCase();if(job.rule.limit&&Date.now()-job.started>=job.rule.limit*1000)await safeTimeoutAction(job,data);if(!job.stallNotified&&job.rule.stall&&Date.now()-job.lastChange>=job.rule.stall*1000&&!['done','completed','error','failed','cancelled','partial_success'].includes(st)){job.stallNotified=true;emit(`${job.rule.label}: ${diagnose(job,data,'stall')} Tao vẫn theo dõi, chưa chạy đè job khác.`,'warn')}
 if(st==='partial_success'&&job.kind==='gameReady'){emit('Game Ready CHƯA PASS: rig/skin có thể có nhưng animation chưa đạt đủ. Tao không coi nhân vật là final.','error');finishStrip(job,'CHƯA PASS · animation');B.jobs.delete(job.key);break}
 if(st==='partial_success'&&job.kind==='object3d'){if(job.byBrain&&await retryObjectTexture(job))continue;emit('Đồ vật 3D mới đạt shape nhưng texture chưa đạt. Kết quả chưa được coi là final.','error');finishStrip(job,'CHƯA PASS · texture');B.jobs.delete(job.key);break}
 if(st==='done'||st==='completed'){
   if(job.kind==='character3d'&&job.phase==='shape'&&Boolean(val('ai3dSimpleColor'))&&B.attachment){
     emit(`Nhân vật 3D: SHAPE đạt sau ${fmt((Date.now()-job.started)/1000)} · đang chuyển sang Paint. CHƯA FINAL.`,'warn');
     finishStrip(job,'SHAPE PASS · chờ Paint');
   }
   else if(job.kind==='character2d'&&data.result&&data.result.accepted===false){const blockers=data.result.gate_summary?.blockers||[];emit(`Nhân vật 2D CHƯA PASS${blockers.length?': '+blockers.join(', '):''}. Tao không coi đây là bản final.`,'error');finishStrip(job,'CHƯA PASS · quality gate')}
   else if(job.kind==='map'&&data.validation&&data.validation.pass===false){emit(`Map CHƯA PASS quality gate · border ${Math.round((data.validation.border_score||0)*100)}% · nét ${Math.round((data.validation.sharpness_score||0)*100)}%. Tao không coi là bản final.`,'error');finishStrip(job,'CHƯA PASS · map gate')}
   else if(job.kind==='character3d'&&job.phase==='paint'){
     const cp=B.activeCharacterPlan||{};
     if(cp.needsGameReady){
       emit('Nhân vật 3D: Shape + Paint PASS · đang nối GAME READY để tạo rig/run/attack. CHƯA FINAL.','warn');
       finishStrip(job,'SHAPE+PAINT PASS · chờ Game Ready');
       B.pendingBrainRun='ai3d';
       setTimeout(()=>click('ai3dMakeGameReady'),650);
     }else if(cp.unsupported?.length){
       emit(`Nhân vật 3D CHƯA FINAL: còn capability chưa có pipeline thật: ${cp.unsupported.join(', ')}.`,'error');
       finishStrip(job,'CHƯA FINAL · thiếu capability');
     }else{
       emit(`Nhân vật 3D FINAL: Shape + Paint đều PASS · Paint ${fmt((Date.now()-job.started)/1000)}.`);
       finishStrip(job,`FINAL PASS · Paint ${fmt((Date.now()-job.started)/1000)}`);
     }
   }
   else if(job.kind==='gameReady'){
     const cp=B.activeCharacterPlan||{};
     if(cp.unsupported?.length){
       emit(`Game Ready PASS cho rig/run/attack, nhưng yêu cầu vẫn CHƯA FINAL vì chưa có pipeline thật cho: ${cp.unsupported.join(', ')}.`,'error');
       finishStrip(job,'GAME READY PASS · thiếu facial/hair');
     }else{
       emit('NHÂN VẬT FINAL: Shape + Paint + Game Ready đều PASS · rig/run/attack đạt.');
       finishStrip(job,'FINAL PASS · Game Ready');
     }
   }
   else {emit(`${job.rule.label} hoàn tất sau ${fmt((Date.now()-job.started)/1000)} · pipeline/gate hiện có đã đạt.`);finishStrip(job,`PASS · ${fmt((Date.now()-job.started)/1000)}`)}
   B.jobs.delete(job.key);break
 }
 if(['error','failed'].includes(st)){B.lastFailure={job:{...job},data:{...data}};emit(`${job.rule.label} ${st}: ${diagnose(job,data,'error')}`,'error');finishStrip(job,`${st.toUpperCase()} · ${String(data.stage||'')}`);await selfHealFailure(job,data);B.jobs.delete(job.key);break}
 if(st==='cancelled'){emit(`${job.rule.label} đã cancelled: ${diagnose(job,data,'error')}`,'warn');finishStrip(job,`CANCELLED · ${String(data.stage||'')}`);B.jobs.delete(job.key);break}
 }catch(_e){}}
}
function registerJob(kind,data,phase=''){const rule=JOB_RULES[kind];if(!rule||!data?.job_id||!data?.status_url)return;const key=kind+':'+data.job_id;if(B.jobs.has(key))return;const brainOwned=B.pendingBrainRun===rule.module||((phase==='paint')&&Date.now()<(B.brainPaintUntil||0));const job={key,kind,phase,id:data.job_id,statusUrl:data.status_url,rule,started:Date.now(),lastChange:Date.now(),lastSig:'',stallNotified:false,timeoutHandled:false,retries:0,recoveryRetries:0,healHandled:false,byBrain:brainOwned};if(B.pendingBrainRun===rule.module){if(kind==='character3d'&&phase==='shape')B.brainPaintUntil=Date.now()+120000;B.pendingBrainRun=null;}B.jobs.set(key,job);mountStrip(rule.module,'đang chạy');emit(`${rule.label} bắt đầu · giới hạn ${rule.limit?fmt(rule.limit):'theo pipeline'} · theo dõi tiến độ ngay trong khung.`);monitorJob(job)}
const nativeFetch=window.fetch.bind(window);window.fetch=async function(input,init){const res=await nativeFetch(input,init);try{const url=typeof input==='string'?input:(input?.url||'');const kind=classifyStart(url);const phase=phaseFromStart(url);const method=String(init?.method||input?.method||'GET').toUpperCase();if(kind&&method==='POST'&&res.ok&&!String(init?.headers?.['X-GA-WATCHDOG']||'').includes('1')){const d=await res.clone().json();registerJob(kind,d,phase)}}catch(_e){}return res};

function repairReport(d,job){
 const lines=[];
 const cls=d?.classification||{};
 const ev=d?.evidence||{};
 lines.push(`KẾT QUẢ SỬA LỖI · ${job?.rule?.label||'job'}`);
 if(cls.summary)lines.push(`Nguyên nhân: ${cls.summary}`);
 if(d?.fixed){
   lines.push('Trạng thái: ĐÃ SỬA + TEST PASS.');
   if(d.file)lines.push(`File đã sửa: ${d.file}`);
   if(d.backup)lines.push(`Backup trước khi sửa: ${d.backup}`);
   const tr=d.tests?.results||[];
   if(tr.length){
     const passed=tr.filter(x=>x?.returncode===0||x?.static_audit_ok===true).length;
     lines.push(`Kiểm thử: ${passed}/${tr.length} bước báo PASS/OK.`);
   }else lines.push('Kiểm thử: self-heal xác nhận PASS trước khi giữ file.');
   if(d.restart_required)lines.push('Cần nạp lại code: mở lại AI Video Factory 1 lần. Tao không tự restart Windows.');
 }else if(d?.resource_recovered){
   lines.push('Không sửa source: đây là lỗi tài nguyên.');
   lines.push('Đã khắc phục tài nguyên an toàn (unload AI/GC/CUDA nếu có).');
   lines.push(d.retry_safe?'Có thể retry đúng 1 lần job do Gà tạo.':'Không tự retry.');
 }else{
   lines.push('Trạng thái: CHƯA SỬA SOURCE.');
   if(d?.manual_review_required)lines.push('Lý do: chưa đủ bằng chứng chắc chắn để ghi đè code; tao giữ nguyên file.');
 }
 const frames=ev?.frames||[];
 if(frames.length){
   const f=frames[frames.length-1];
   lines.push(`Traceback gần nhất: ${f.file||'?'}:${f.line||'?'}`);
 }
 return lines;
}

async function manualHealLast(){
 const lf=B.lastFailure;
 if(!lf?.job)return {ok:false,target:'maintenance',message:'Tao chưa có job lỗi gần nhất trong phiên này. Nếu muốn quét source thì nói rõ “kiểm tra file bot”.'};
 const job=lf.job,data=lf.data||{};
 emit(`Tao quay lại ĐÚNG lỗi ${job.rule.label} gần nhất. Tao đọc log/traceback trước; không quét rác thay cho sửa lỗi.`,'warn');
 let d;
 try{
   d=await api('/api/ga-brain/heal-job',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope:job.rule.scope,job_id:job.id,job_state:data})});
 }catch(e){
   const text=`Không đọc/self-heal được job ${job.rule.label}: ${e.message}. Tao chưa sửa file nào.`;
   emit(text,'error');
   return {ok:false,target:'maintenance',message:text};
 }
 for(const x of d.messages||[])emit(x,d.fixed?'warn':(d.manual_review_required?'error':'warn'));
 const report=repairReport(d,job);
 for(const line of report)emit(line,d.fixed?'warn':(d.manual_review_required?'error':'warn'));
 if(d.fixed&&d.restart_required){
   try{localStorage.setItem('ga-last-heal-note',JSON.stringify({at:Date.now(),text:`Đã sửa ${d.file||'source'} · test PASS.`}))}catch(_e){}
 }else if(d.resource_recovered&&d.retry_safe){
   const retried=await rerunAfterResourceRecovery(job);
   report.push(retried?'Đã retry job đúng 1 lần.':'Không tự retry vì job không do Gà tạo hoặc đã hết lượt retry.');
 }else if(d.manual_review_required){
   report.push('Tao dừng ở đây thay vì sửa mò. Nếu cần, mày bảo tao phân tích sâu log này.');
 }
 return {ok:!!d.fixed||!!d.resource_recovered,target:'maintenance',message:report.join('\n'),messages:report,report:d};
}
async function maintenance(planObj){emit('Đang kiểm tra source bot: Python, JavaScript, JSON, link static và rác an toàn...');const d=await api('/api/ga-maintenance/audit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cleanup:planObj?.fields?.cleanup!==false,repair:planObj?.fields?.repair!==false})});const lines=[];lines.push(`Đã kiểm ${d.checked.python} Python · ${d.checked.javascript} JavaScript · ${d.checked.json} JSON · ${d.checked.static_refs} link static trong ${d.elapsed_seconds}s.`);if(d.cleaned_safe?.length)lines.push(`Đã dọn ${d.cleaned_safe.length} mục chắc chắn là rác/cache: ${d.cleaned_safe.slice(0,8).join(', ')}${d.cleaned_safe.length>8?'…':''}`);if(d.issues?.length){lines.push(`Phát hiện ${d.issues.length} lỗi source.`);for(const x of d.issues.slice(0,6))lines.push(`${x.file}: ${x.error}`)}else lines.push('Không phát hiện lỗi cú pháp hoặc link static bị thiếu.');if(d.suspect_not_deleted?.length||d.unreferenced_web_not_deleted?.length)lines.push(`Có ${d.suspect_not_deleted.length+d.unreferenced_web_not_deleted.length} file nghi không dùng nhưng chưa đủ chắc chắn: tao KHÔNG xóa.`);for(const n of d.notes||[])lines.push(n);return {ok:!d.issues?.length,target:'maintenance',message:lines[0],messages:lines,report:d}}
async function executeMessage(message){
 await ensureStudio();
 if(B.busy)return {ok:false,message:'Brain đang xử lý yêu cầu trước.'};
 B.busy=true;
 try{
   const decision=await interact(message);

   if(decision.mode==='chat'||decision.mode==='clarify'){
     return {
       ok:true,
       target:'chat',
       message:decision.message||'Ừ, tao đang nghe.',
       brain_mode:decision.brain_mode,
       intent:decision.intent
     };
   }

   if(decision.mode!=='action'){
     return {ok:true,target:'chat',message:decision.message||'Tao chưa thực hiện hành động nào.',intent:decision.intent};
   }

   if(decision.execution?.authorized!==true){
     return {ok:false,target:'chat',message:decision.message||'AI Core đã chặn hành động vì chưa đủ quyền/target.',intent:decision.intent};
   }

   const p=decision.plan;
   if(!p||!p.target){
     return {ok:false,target:'chat',message:'AI Core chưa xác định target chắc chắn nên tao không chạy tool.'};
   }

   switchTo(p.target);
   await new Promise(r=>setTimeout(r,90));
   apply(p.target,p.fields||{},!!(p.files&&p.files.length));

   if(p.action!=='run'){
     mountStrip(p.target,'V11 · PREPARED');
     return {ok:true,target:p.target,message:decision.message||p.needs_user||'Đã chuẩn bị đúng khung; chưa chạy tool.',plan:p,intent:decision.intent};
   }

   const result=nativeRun(p);
   mountStrip(p.target,'V11 · AUTHORIZED');

   if(result.started){
     remember(p.target,'ga-brain-v11');
     try{api('/api/ga-brain/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({report:{status:'EXECUTING',evidence:[`native click ${META[p.target]?.run||p.target}`]}})});}catch(_e){}
     return {
       ok:true,target:p.target,
       message:`Đã nhận lệnh ACTION và bấm công cụ ${META[p.target]?.title||p.target}. Đây mới là EXECUTING, chưa phải SUCCESS.`,
       plan:p,intent:decision.intent
     };
   }
   return {ok:false,target:p.target,message:result.message||'Không khởi chạy được tool native; tao không báo thành công.',plan:p,intent:decision.intent};
 }finally{B.busy=false}
}
async function optimizeCurrent(){const target=visibleModule();if(!target)return;const strip=document.querySelector(`#panel-${target} .module-brain-strip`);strip?.classList.add('running');try{const c=context().forms[target]||{},seed=(c.prompt||c.wish||c.text||'')+' Tối ưu thông số cho kết quả tốt nhưng không dùng cấu hình nặng quá mức cần thiết.';const p=await plan(seed,target,true);apply(target,p.fields||{});window.Studio?.setStatus?.(`🧠 Gà Brain đã tối ưu ${META[target]?.title||target}. Kiểm tra setting hoặc ra lệnh cho Gà chạy.`)}catch(e){window.Studio?.setStatus?.('Brain tối ưu lỗi: '+e.message,true)}finally{strip?.classList.remove('running')}}
function attachFile(file){B.attachment=file||null;return !!B.attachment}
function getAttachment(){return B.attachment||null}
function clearAttachment(){B.attachment=null;return true}
async function init(){await ensureStudio().catch(()=>null);watchManualRuns();for(const t of Object.keys(META))mountStrip(t);try{const raw=localStorage.getItem('ga-last-heal-note');if(raw){const n=JSON.parse(raw);localStorage.removeItem('ga-last-heal-note');if(Date.now()-(n.at||0)<300000)setTimeout(()=>emit((n.text||'Self-heal đã hoàn tất.')+' Server mới đã lên.','warn'),700)}}catch(_e){}api('/api/ga-brain/status').then(d=>{
 const sub=$('gaOwnerSub');
 if(sub){
   if(d.core_version!=='V12'){
     sub.textContent='BACKEND CŨ · KHÔNG DÙNG';
     sub.classList.remove('native-ready');
     emit('Tab này đang nối backend cũ. Dùng TAB MỚI launcher mở; nếu 8123 bận thì bản mới sẽ tự chạy ở 8124/8125.','error');
   }else{
     sub.textContent=d.interact_ready?(d.ollama?.main_installed?'V11 CORE · 30B READY':(d.ollama?.fast_installed?'V11 CORE · 8B FALLBACK':'V11 CORE · MODEL OFF')):'V11 CORE · OFF';
     sub.classList.add('native-ready');
   }
 }
}).catch(e=>{
 const sub=$('gaOwnerSub');if(sub)sub.textContent='BACKEND CŨ / BRAIN OFF';
 emit('Không thấy Gà AI Core V11 ở tab này: '+e.message,'error');
})}
window.AIVFModuleBrain={
 context,
 plan,
 executeMessage,
 optimizeCurrent,
 attachFile,
 getAttachment,
 clearAttachment,
 mountStrip,
 remember,
 jobs:B.jobs
};
window.dispatchEvent(new CustomEvent('ga-brain-ready'));
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',()=>{init();}):init();
})();
