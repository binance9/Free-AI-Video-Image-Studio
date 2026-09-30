(() => {
  const S=window.Studio;if(!S)return;const $=S.$,preview=window.AIVFRealtimePreview;
  const input=new window.AIVFImagePromptInput({fileId:'aiRefFile',promptId:'aiImagePrompt',nameId:'aiRefName',preview,defaultName:'＋ Ảnh tham chiếu (không bắt buộc)'});
  const fileEl=$('aiRefFile'),dropzone=fileEl.closest('.dropzone');
  const region=document.createElement('div');region.className='field hidden';region.innerHTML='<label>Vùng sửa (kéo khung quanh tay / vũ khí)</label><canvas></canvas><button type="button" class="btn" title="Xóa vùng sửa">↺</button>';
  dropzone.after(region);const canvas=region.querySelector('canvas'),ctx=canvas.getContext('2d'),resetRegion=region.querySelector('button');
  Object.assign(canvas.style,{width:'100%',maxHeight:'360px',objectFit:'contain',cursor:'crosshair',border:'1px solid var(--border,#555)',background:'#111'});
  let sourceImage=null,selection=null,dragStart=null;
  function point(event){const box=canvas.getBoundingClientRect();return{x:(event.clientX-box.left)*canvas.width/box.width,y:(event.clientY-box.top)*canvas.height/box.height};}
  function paint(){if(!sourceImage)return;ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(sourceImage,0,0);if(selection){ctx.fillStyle='rgba(255,70,70,.24)';ctx.fillRect(selection.x,selection.y,selection.w,selection.h);ctx.strokeStyle='#ff4646';ctx.lineWidth=Math.max(3,canvas.width/300);ctx.strokeRect(selection.x,selection.y,selection.w,selection.h);}}
  function clearRegion(){selection=null;paint();}
  fileEl.addEventListener('change',()=>{clearRegion();const file=fileEl.files?.[0];region.classList.toggle('hidden',!file);if(!file){sourceImage=null;return;}const url=URL.createObjectURL(file),img=new Image();img.onload=()=>{URL.revokeObjectURL(url);sourceImage=img;canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;paint();};img.src=url;});
  canvas.addEventListener('pointerdown',event=>{if(!sourceImage)return;dragStart=point(event);selection={x:dragStart.x,y:dragStart.y,w:0,h:0};canvas.setPointerCapture(event.pointerId);});
  canvas.addEventListener('pointermove',event=>{if(!dragStart)return;const p=point(event);selection={x:Math.min(dragStart.x,p.x),y:Math.min(dragStart.y,p.y),w:Math.abs(p.x-dragStart.x),h:Math.abs(p.y-dragStart.y)};paint();});
  canvas.addEventListener('pointerup',()=>{dragStart=null;if(selection&&(selection.w<8||selection.h<8))clearRegion();});resetRegion.onclick=clearRegion;
  function maskBlob(){if(!selection)return Promise.resolve(null);const mask=document.createElement('canvas');mask.width=canvas.width;mask.height=canvas.height;const m=mask.getContext('2d');m.fillStyle='#000';m.fillRect(0,0,mask.width,mask.height);m.fillStyle='#fff';m.fillRect(selection.x,selection.y,selection.w,selection.h);return new Promise(resolve=>mask.toBlob(resolve,'image/png'));}
  let result=null,activeJob=null;
  async function run(){
    let value;try{value=input.validate();}catch(error){return S.setStatus(error.message,true);}
    const referenceIntent=/(dựa\s*(theo|trên)|theo\s*ảnh|tham\s*khảo\s*ảnh|based\s+on|use\s+(this|the)\s+(image|photo))/i.test(value.prompt);
    const mode=value.file?(referenceIntent?'IMAGE_REFERENCE':'IMAGE_EDIT'):'TEXT2IMG';
    const pipelineMode=value.file?(selection?'INPAINT':'PRESERVE_IMG2IMG'):'TEXT2IMG';
    S.setStatus(`MODE: ${mode}${value.file?' | input image: '+value.file.name:''}`);
    preview.activate('image',`${mode} | ẢNH AI REALTIME`);
    preview.update({status:'running',progress:1,stage:mode,message:value.file?`${mode} | ${pipelineMode} | input_image_used=true | ${value.file.name}`:'TEXT2IMG | input_image_used=false',preview_type:'image'});
    $('aiImageRun').disabled=true;
    try{
      let created;
      if(value.file){const form=new FormData();form.append('file',value.file);form.append('prompt',value.prompt);form.append('style',$('aiImageStyle').value);form.append('size',$('aiImageSize').value);form.append('quality',$('aiImageQuality').value);const mask=await maskBlob();if(mask)form.append('mask',mask,'edit-mask.png');created=await S.jsonRequest('/api/ai-image/jobs/edit',{method:'POST',body:form});}
      else created=await S.jsonRequest('/api/ai-image/jobs/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:value.prompt,style:$('aiImageStyle').value,size:$('aiImageSize').value,quality:$('aiImageQuality').value})});
      activeJob=created.job_id;const actualMode=created.mode||mode;window.AIVFJobTerminal?.start({scope:'image',jobId:created.job_id,title:`${actualMode} | ĐANG TẠO ẢNH AI`});const job=await window.AIVFRealtimeProgress.poll({url:created.status_url});result=job.result;activeJob=null;$('aiImageResult').classList.remove('hidden');S.setStatus(`${job.mode||actualMode} hoàn tất | input_image_used=${Boolean(value.file)}`);
    }catch(error){activeJob=null;S.setStatus('Lỗi AI ảnh local: '+error.message,true);}finally{$('aiImageRun').disabled=false;}
  }
  $('aiImageRun').onclick=run;$('aiImageAgain').onclick=run;
  $('aiImageToVideo').onclick=async()=>{if(!result)return;if(!S.hasVideo())return S.setStatus('Tải video lên trước rồi mới đưa ảnh vào video.',true);S.setBusy(true,'Đang đưa ảnh AI vào video…');try{const a=await S.jsonRequest(`/api/editor/${S.state.sessionId}/asset-from-ai/${result.image_id}`,{method:'POST'});const l=S.newLayer({type:'image',name:'AI image local',source_kind:'asset',source:a.asset_id,previewUrl:a.url,widthRatio:.32});S.createLayerElement(l);S.selectLayer(l);S.setStatus('Đã đưa ảnh AI vào video.');}catch(e){S.setStatus('Lỗi đưa ảnh vào video: '+e.message,true);}finally{S.setBusy(false);}};
  window.addEventListener('aivf-stop-all',async()=>{if(activeJob)await fetch(`/api/ai-image/jobs/${activeJob}/cancel`,{method:'POST'}).catch(()=>{});});
})();
