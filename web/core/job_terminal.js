(() => {
  const $ = id => document.getElementById(id);
  const state = { source:null, jobId:null, scope:null, started:0, lines:[] };
  const escapeHtml=value=>{const d=document.createElement('div');d.textContent=String(value??'');return d.innerHTML;};
  const stamp=()=>new Date().toLocaleTimeString('vi-VN',{hour12:false});
  function draw(){const body=$('jobTerminalBody');if(!body)return;body.innerHTML=state.lines.map(x=>`<div class="job-terminal-line ${x.level}"><time>${x.time}</time><span>${escapeHtml(x.message)}</span></div>`).join('');body.scrollTop=body.scrollHeight;}
  function append(message,level='info'){if(!message)return;const last=state.lines.at(-1);if(last?.message===String(message)&&last?.level===level)return;state.lines.push({time:stamp(),message:String(message),level});if(state.lines.length>2000)state.lines.splice(0,state.lines.length-2000);draw();}
  function header(title,pct){if(title)$('jobTerminalTitle').textContent=title;if(pct!==undefined)$('jobTerminalPct').textContent=`${Math.round(Number(pct)||0)}%`;}
  function close(){if(state.source){state.source.close();state.source=null;}}
  function start({scope,jobId,title='ĐANG XỬ LÝ',mode,preserve=false}={}){
    close();
    Object.assign(state,{scope:scope||null,jobId:jobId||null});
    if(!preserve){state.started=performance.now();state.lines=[];}
    $('jobTerminal')?.classList.remove('hidden','collapsed','expanded');
    header(`⚙ ${String(title).toUpperCase()}`,preserve?undefined:0);
    if(!preserve)append('Creating job...');
    if(!scope||!jobId)return;
    const source=new EventSource(`/api/job-logs/${encodeURIComponent(scope)}/${encodeURIComponent(jobId)}/stream?mode=${mode||$('jobTerminalMode')?.value||'normal'}`);state.source=source;
    source.addEventListener('log',event=>{const d=JSON.parse(event.data);header(null,d.progress);append([d.stage,d.message&&d.message!==d.stage?d.message:''].filter(Boolean).join(' — '),d.level||'info');if(d.debug)append(JSON.stringify(d.debug),'debug');});
    source.addEventListener('end',event=>{const d=JSON.parse(event.data);close();const ok=['done','completed'].includes(d.status);header(ok?'✓ HOÀN THÀNH':'✕ LỖI',d.progress);append(d.message||d.stage,ok?'success':'error');append(`Thời gian xử lý: ${d.elapsed_seconds??((performance.now()-state.started)/1000).toFixed(1)}s`,'meta');if(d.output)append(`Output: ${d.output}`,'success');});
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
