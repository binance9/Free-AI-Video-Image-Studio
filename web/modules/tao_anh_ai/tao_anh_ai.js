(() => {
  const S=window.Studio;if(!S)return;const $=S.$,preview=window.AIVFRealtimePreview;
  const input=new window.AIVFImagePromptInput({fileId:'aiRefFile',promptId:'aiImagePrompt',nameId:'aiRefName',preview});
  let result=null,activeJob=null;
  async function run(){
    let value;try{value=input.validate();}catch(error){return S.setStatus(error.message,true);}
    preview.activate('image','ẢNH AI REALTIME');
    preview.update({status:'running',progress:1,stage:value.file?'Ảnh nguồn':'Chuẩn bị tạo ảnh',message:value.file?'Bot sẽ kết hợp ảnh với mô tả nếu có.':'Đang tạo từ mô tả.',preview_type:'image'});
    $('aiImageRun').disabled=true;
    try{
      let created;
      if(value.file){const form=new FormData();form.append('file',value.file);form.append('prompt',value.prompt);form.append('style',$('aiImageStyle').value);form.append('size',$('aiImageSize').value);form.append('quality',$('aiImageQuality').value);created=await S.jsonRequest('/api/ai-image/jobs/edit',{method:'POST',body:form});}
      else created=await S.jsonRequest('/api/ai-image/jobs/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:value.prompt,style:$('aiImageStyle').value,size:$('aiImageSize').value,quality:$('aiImageQuality').value})});
      activeJob=created.job_id;window.AIVFJobTerminal?.start({scope:'image',jobId:created.job_id,title:'ĐANG TẠO ẢNH AI'});const job=await window.AIVFRealtimeProgress.poll({url:created.status_url});result=job.result;activeJob=null;$('aiImageResult').classList.remove('hidden');S.setStatus('Ảnh final đã hiện trong khung lớn.');
    }catch(error){activeJob=null;S.setStatus('Lỗi AI ảnh local: '+error.message,true);}finally{$('aiImageRun').disabled=false;}
  }
  $('aiImageRun').onclick=run;$('aiImageAgain').onclick=run;
  $('aiImageToVideo').onclick=async()=>{if(!result)return;if(!S.hasVideo())return S.setStatus('Tải video lên trước rồi mới đưa ảnh vào video.',true);S.setBusy(true,'Đang đưa ảnh AI vào video…');try{const a=await S.jsonRequest(`/api/editor/${S.state.sessionId}/asset-from-ai/${result.image_id}`,{method:'POST'});const l=S.newLayer({type:'image',name:'AI image local',source_kind:'asset',source:a.asset_id,previewUrl:a.url,widthRatio:.32});S.createLayerElement(l);S.selectLayer(l);S.setStatus('Đã đưa ảnh AI vào video.');}catch(e){S.setStatus('Lỗi đưa ảnh vào video: '+e.message,true);}finally{S.setBusy(false);}};
  window.addEventListener('aivf-stop-all',async()=>{if(activeJob)await fetch(`/api/ai-image/jobs/${activeJob}/cancel`,{method:'POST'}).catch(()=>{});});
})();
