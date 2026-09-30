(()=>{
'use strict';
const $=id=>document.getElementById(id);
const S={awake:false,busy:false,voice:null,enrolling:false,enrollCount:0,draftImage:null,lastImage:null};
const WAKE='gà ơi dậy đi',SLEEP='gà ngủ đi',norm=x=>String(x||'').trim().toLowerCase();

function stage(t){const e=$('gaOwnerProgress');if(e)e.textContent=t||''}
function state(){const e=$('gaOwnerState');if(!e)return;e.textContent=S.awake?'● THỨC':'● NGỦ';e.classList.toggle('awake',S.awake)}
async function api(url,opt={}){const r=await fetch(url,opt);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.detail||d.error||`HTTP ${r.status}`);return d}

function makeMessage(who,text,cls='',file=null){
 const box=$('gaOwnerChat');if(!box)return;
 const d=document.createElement('div');d.className='ga-owner-msg '+cls;
 const head=document.createElement('b');head.textContent=who+': ';d.appendChild(head);
 if(text)d.appendChild(document.createTextNode(String(text)));
 if(file){
   const wrap=document.createElement('div');wrap.className='ga-owner-chat-image-wrap';
   const img=document.createElement('img');img.className='ga-owner-chat-image';
   const u=URL.createObjectURL(file);img.src=u;img.onload=()=>setTimeout(()=>URL.revokeObjectURL(u),1500);
   const cap=document.createElement('small');cap.textContent=file.name||'ảnh';
   wrap.append(img,cap);d.appendChild(wrap);
 }
 box.appendChild(d);box.scrollTop=box.scrollHeight;
}
function msg(who,text,cls=''){makeMessage(who,text,cls,null)}

function wake(text){
 const low=norm(text);
 if(!S.awake){
   if(low===WAKE){S.awake=true;state();msg('Gà','Tao dậy rồi.');return true}
   if(low.includes('gà ơi')){msg('Gà','Mày nói gì tao chưa hiểu.');return true}
   return true;
 }
 if(low===SLEEP){S.awake=false;state();msg('Gà','Ừ, tao ngủ đây.');return true}
 return false;
}

function getBrain(){const b=window.AIVFModuleBrain;return b&&typeof b.executeMessage==='function'?b:null}
async function waitBrain(timeout=7000){const t=Date.now();while(Date.now()-t<timeout){const b=getBrain();if(b)return b;await new Promise(r=>setTimeout(r,60))}return null}

function isImageFile(file){return !!file&&(String(file.type||'').startsWith('image/')||/\.(png|jpe?g|webp)$/i.test(String(file.name||'')))}
function setDraftImage(file){
 if(file&&!isImageFile(file)){msg('Gà','Chỉ nhận PNG/JPG/JPEG/WebP.');return false}
 if(file&&file.size>20*1024*1024){msg('Gà','Ảnh lớn hơn 20 MB.');return false}
 S.draftImage=file||null;
 const label=$('gaOwnerAttach');if(label)label.textContent=file?'📎 '+(file.name||'ảnh đang soạn'):'';
 const fi=$('gaOwnerFile');if(!file&&fi)fi.value='';
 renderDraft();return true;
}
function clearImageContext(){
 S.draftImage=null;S.lastImage=null;
 const b=getBrain();b?.clearAttachment?.();
 const fi=$('gaOwnerFile');if(fi)fi.value='';
 const label=$('gaOwnerAttach');if(label)label.textContent='';
 renderDraft();msg('Gà','Đã bỏ ảnh khỏi ngữ cảnh chat.');
}
function renderDraft(){
 const wrap=$('gaOwnerAttachPreview');if(!wrap)return;wrap.innerHTML='';
 if(!S.draftImage){wrap.classList.add('hidden');return}
 wrap.classList.remove('hidden');
 const card=document.createElement('div');card.className='ga-owner-attach-card';
 const img=document.createElement('img');img.className='ga-owner-attach-thumb';
 const u=URL.createObjectURL(S.draftImage);img.src=u;img.onload=()=>setTimeout(()=>URL.revokeObjectURL(u),1200);
 const meta=document.createElement('div');meta.className='ga-owner-attach-meta';
 const n=document.createElement('b');n.textContent=S.draftImage.name||'clipboard.png';
 const z=document.createElement('small');z.textContent='Ảnh đang soạn · bấm Gửi để đưa vào chat';meta.append(n,z);
 const x=document.createElement('button');x.type='button';x.className='ga-owner-attach-remove';x.textContent='×';x.title='Xóa ảnh nháp';x.onclick=()=>setDraftImage(null);
 card.append(img,meta,x);wrap.appendChild(card);
}

async function send(text){
 text=String(text||'').trim();
 if((!text&&!S.draftImage)||S.busy)return;
 // Explicit, literal approval command for a self-heal patch proposal - deliberately
 // bypasses wake/awake/interact() entirely so approving a code write never goes
 // through natural-language intent understanding, only an exact typed id match.
 const applyMatch=text.match(/^\/apply-patch\s+(\S+)/);
 if(applyMatch){
   makeMessage('Mày',text,'me');
   try{
     const r=await api('/api/ga-maintenance/apply-patch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({patch_id:applyMatch[1]})});
     if(r.fixed)msg('Gà',`Đã ghi bản vá vào ${r.file} và test PASS. Mở lại AI Video Factory một lần để nạp code mới.`);
     else msg('Gà','Không ghi được bản vá: '+(r.reason||'không qua test, đã hoàn tác.'),'err');
   }catch(e){msg('Gà','Lỗi khi áp dụng bản vá: '+e.message,'err')}
   return;
 }
 if(wake(text))return;
 if(!S.awake)return;

 const sentImage=S.draftImage||null;
 if(sentImage){S.lastImage=sentImage;S.draftImage=null;renderDraft();const label=$('gaOwnerAttach');if(label)label.textContent=''}
 if(!text&&sentImage)text='[Tao gửi ảnh này.]';
 makeMessage('Mày',text,'me',sentImage);
 S.busy=true;stage('🧠 Gà AI Core đang hiểu ý...');
 try{
   const brain=await waitBrain();
   if(!brain)throw new Error('Gà AI Core frontend chưa sẵn sàng');
   // Composer is clean after send, but the last sent image remains conversation context.
   if(S.lastImage)brain.attachFile(S.lastImage);else brain.clearAttachment?.();
   const r=await brain.executeMessage(text);
   const lines=Array.isArray(r.messages)&&r.messages.length?r.messages:[r.message||''];
   for(const line of lines)if(line)msg('Gà',line,r.ok===false?'err':'');
   stage(r.target==='chat'?'Sẵn sàng.':(r.ok===false?'Có lỗi/chưa chạy.':'Theo dõi tác vụ trong module.'));
 }catch(e){msg('Gà','Lỗi Brain: '+(e?.message||e),'err');stage('Sẵn sàng.')}finally{S.busy=false}
}

function handlePaste(e){
 const item=[...(e.clipboardData?.items||[])].find(x=>String(x.type||'').startsWith('image/'));if(!item)return;
 const f=item.getAsFile();if(!f)return;e.preventDefault();e.stopPropagation();
 const ext=(String(f.type||'').split('/')[1]||'png').replace('jpeg','jpg');
 setDraftImage(new File([f],`clipboard_${Date.now()}.${ext}`,{type:f.type||'image/png'}));
}
function handleDrop(e){const f=[...(e.dataTransfer?.files||[])].find(isImageFile);if(!f)return;e.preventDefault();e.stopPropagation();setDraftImage(f)}

async function capturePcm(ms=3300){const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});const ctx=new (window.AudioContext||window.webkitAudioContext)(),src=ctx.createMediaStreamSource(stream),proc=ctx.createScriptProcessor(4096,1,1),chunks=[];proc.onaudioprocess=e=>chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));src.connect(proc);proc.connect(ctx.destination);await new Promise(r=>setTimeout(r,ms));proc.disconnect();src.disconnect();stream.getTracks().forEach(t=>t.stop());const rate=ctx.sampleRate;await ctx.close();let len=chunks.reduce((a,x)=>a+x.length,0),all=new Float32Array(len),off=0;chunks.forEach(x=>{all.set(x,off);off+=x.length});const ratio=rate/16000,n=Math.max(1,Math.floor(all.length/ratio)),pcm=new Int16Array(n);for(let i=0;i<n;i++){const x=Math.max(-1,Math.min(1,all[Math.floor(i*ratio)]||0));pcm[i]=x<0?x*32768:x*32767}return pcm.buffer}
async function refreshVoice(){try{const d=await api('/api/ga-owner/status');S.voice=d.voice||{}}catch(_e){}}
async function enroll(){if(S.enrolling)return;S.enrolling=true;try{if(!S.voice?.available)throw new Error('Voiceprint chưa sẵn sàng');if(S.enrollCount===0){await api('/api/ga-owner/voice/enroll/reset',{method:'POST'});msg('Gà','Nói “gà ơi dậy đi” khoảng 3 giây.')}stage(`🎤 Mẫu ${S.enrollCount+1}/5...`);const raw=await capturePcm(3400),d=await api('/api/ga-owner/voice/enroll/sample',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:raw});S.enrollCount=d.done?0:d.count;if(d.done){msg('Gà','Đăng ký giọng xong.');await refreshVoice()}else msg('Gà',`Đã nhận ${d.count}/5 mẫu.`)}catch(e){msg('Gà','Đăng ký giọng lỗi: '+e.message,'err')}finally{S.enrolling=false;stage('Sẵn sàng.')}}
async function voice(){if(S.busy)return;if(!S.voice?.enrolled){msg('Gà','Chưa đăng ký giọng.');return}const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){msg('Gà','Chrome không hỗ trợ nhận dạng giọng.');return}const rec=new SR();rec.lang='vi-VN';rec.interimResults=false;rec.continuous=false;let transcript='',rawPromise=capturePcm(3900);stage('🎤 Đang nghe...');rec.onresult=e=>transcript=(e.results?.[0]?.[0]?.transcript||'').trim();const done=new Promise((resolve,reject)=>{rec.onend=resolve;rec.onerror=e=>reject(new Error(e.error||'mic error'))});rec.start();try{await done;const raw=await rawPromise;if(!transcript)return stage('Không nghe rõ.');const v=await api('/api/ga-owner/voice/verify',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:raw});if(!v.ok)return stage(`🔒 Bỏ qua giọng lạ · ${v.score}`);await send(transcript)}catch(e){msg('Gà','Mic lỗi: '+e.message,'err');stage('Sẵn sàng.')}}

function init(){
 if(!$('gaOwner'))return;state();refreshVoice();renderDraft();
 $('gaOwnerSend').onclick=()=>{const e=$('gaOwnerInput'),t=e.value;e.value='';send(t)};
 $('gaOwnerInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('gaOwnerSend').click()}});
 $('gaOwnerInput').addEventListener('paste',handlePaste);
 $('gaOwnerAttachBtn').onclick=()=>$('gaOwnerFile').click();
 $('gaOwnerFile').onchange=e=>{setDraftImage(e.target.files?.[0]||null);e.target.value=''};
 const panel=$('gaOwner');panel.addEventListener('paste',handlePaste);panel.addEventListener('dragover',e=>{if([...(e.dataTransfer?.types||[])].includes('Files')){e.preventDefault();panel.classList.add('drag-image')}});panel.addEventListener('dragleave',()=>panel.classList.remove('drag-image'));panel.addEventListener('drop',e=>{panel.classList.remove('drag-image');handleDrop(e)});
 $('gaOwnerVoice').onclick=voice;$('gaOwnerEnroll').onclick=enroll;
 const clear=$('gaOwnerClearAttach');if(clear)clear.onclick=clearImageContext;
 window.addEventListener('ga-brain-message',e=>{const d=e.detail||{};msg('Gà',d.text||'',d.level==='error'?'err':(d.level==='warn'?'warn':''))});
 msg('Gà','Đang ngủ. Gọi đúng “gà ơi dậy đi”.');
}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',init):init();
})();
