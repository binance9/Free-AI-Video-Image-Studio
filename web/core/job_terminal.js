(() => {
  const $ = id => document.getElementById(id);
  const state = { source:null, jobId:null, scope:null, started:0, lines:[], lastSeq:0, ended:false };
  const escapeHtml=value=>{const d=document.createElement('div');d.textContent=String(value??'');return d.innerHTML;};
  const stamp=()=>new Date().toLocaleTimeString('vi-VN',{hour12:false});
  function draw(){const body=$('jobTerminalBody');if(!body)return;body.innerHTML=state.lines.map(x=>`<div class="job-terminal-line ${x.level}"><time>${x.time}</time><span>${escapeHtml(x.message)}</span></div>`).join('');body.scrollTop=body.scrollHeight;}
  function append(message,level='info'){if(!message)return;const last=state.lines.at(-1);if(last?.message===String(message)&&last?.level===level)return;state.lines.push({time:stamp(),message:String(message),level});if(state.lines.length>2000)state.lines.splice(0,state.lines.length-2000);draw();}
  function header(title,pct){if(title)$('jobTerminalTitle').textContent=title;if(pct!==undefined)$('jobTerminalPct').textContent=`${Math.round(Number(pct)||0)}%`;}
  function close(){if(state.source){state.source.close();state.source=null;}}
  function start({scope,jobId,title='ĐANG XỬ LÝ',mode,preserve=false}={}){
    close();
    Object.assign(state,{scope:scope||null,jobId:jobId||null});
    if(!preserve){state.started=performance.now();state.lines=[];state.lastSeq=0;state.ended=false;}
    $('jobTerminal')?.classList.remove('hidden','collapsed','expanded');
    $('jobTerminalPct')?.classList.toggle('hidden',scope==='system');
    header(`⚙ ${String(title).toUpperCase()}`,preserve?undefined:0);
    if(!preserve)append(scope==='system'?'Đang kết nối system log...':'Creating job...');
    if(!scope||!jobId)return;
    // "since=lastSeq": khi doi NORMAL/DEBUG giua chung 1 job (preserve=true),
    // EventSource cu bi dong va mo lai tu dau - truyen lastSeq de server chi
    // phat cac dong stdout/stderr CHUA tung thay, tranh lap lai toan bo log
    // da hien (bug that da phat hien qua test that: "Creating job...", canh
    // bao CLIP truncate... bi lap 2 lan khi bam doi mode giua luc job chay).
    const source=new EventSource(`/api/job-logs/${encodeURIComponent(scope)}/${encodeURIComponent(jobId)}/stream?mode=${mode||$('jobTerminalMode')?.value||'normal'}&since=${state.lastSeq}`);state.source=source;
    source.addEventListener('log',event=>{const d=JSON.parse(event.data);if(typeof d.seq==='number')state.lastSeq=Math.max(state.lastSeq,d.seq);header(null,d.progress);append([d.stage,d.message&&d.message!==d.stage?d.message:''].filter(Boolean).join(' — '),d.level||'info');if(d.debug)append(JSON.stringify(d.debug),'debug');});
    source.addEventListener('end',event=>{
      close();
      // Doi NORMAL/DEBUG SAU KHI job da xong se mo 1 EventSource moi, va
      // server phat lai 'end' ngay lap tuc (job da o trang thai terminal) -
      // neu da xu ly 'end' 1 lan cho job nay roi thi bo qua, tranh lap lai
      // dong "HOAN THANH"/"Output" (bug that da phat hien qua test that).
      if(state.ended)return;
      state.ended=true;
      const d=JSON.parse(event.data);const ok=['done','completed'].includes(d.status);header(ok?'✓ HOÀN THÀNH':'✕ LỖI',d.progress);append(d.message||d.stage,ok?'success':'error');append(`Thời gian xử lý: ${d.elapsed_seconds??((performance.now()-state.started)/1000).toFixed(1)}s`,'meta');if(d.output)append(`Output: ${d.output}`,'success');
    });
  }
  function update(d={}){header(null,d.progress);append([d.stage,d.detail||d.message].filter(Boolean).join(' — '),d.level||'info');}
  function finish(message='Hoàn thành',output=''){close();header('✓ HOÀN THÀNH',100);append(message,'success');if(output)append(`Output: ${output}`,'success');}
  function fail(stage='Lỗi',message=''){close();header('✕ LỖI');append(`${stage}${message?` — ${message}`:''}`,'error');}
  $('jobTerminalCollapse')?.addEventListener('click',()=>{const panel=$('jobTerminal');panel?.classList.remove('expanded');panel?.classList.toggle('collapsed');});
  $('jobTerminalExpand')?.addEventListener('click',()=>{const panel=$('jobTerminal');panel?.classList.remove('collapsed');panel?.classList.toggle('expanded');});
  $('jobTerminalClear')?.addEventListener('click',()=>{state.lines=[];draw();});
  $('jobTerminalCopy')?.addEventListener('click',()=>navigator.clipboard.writeText(state.lines.map(x=>`[${x.time}] ${x.message}`).join('\n')));
  $('jobTerminalMode')?.addEventListener('change',()=>{if(state.jobId)start({scope:state.scope,jobId:state.jobId,title:$('jobTerminalTitle')?.textContent.replace(/^[⚙✓✕]\s*/,''),mode:$('jobTerminalMode').value,preserve:true});});
  window.AIVFJobTerminal={start,update,finish,fail,append,get state(){return state;}};
})();
