(() => {
  const S=window.Studio;if(!S)return;const $=S.$;
  let refFile=null,result=null,activeJob=null,stopped=false;
  $('aiImageRef').onchange=e=>{refFile=e.target.files[0]||null;$('aiImageRefName').textContent=refFile?refFile.name:'＋ Ảnh tham chiếu (tùy chọn)'};

  async function poll(jobId){
    activeJob=jobId;stopped=false;
    try{
      while(activeJob===jobId){
        const job=await S.jsonRequest(`/api/ai-image/jobs/${jobId}`);
        S.updateBusyProgress?.(Number(job.progress||0),job.stage||'AI ảnh local',job.detail||'','real');
        if(job.status==='done') return job.result;
        if(job.status==='cancelled') throw Object.assign(new Error(job.detail||'Đã dừng AI ảnh'),{cancelled:true});
        if(job.status==='error') throw new Error(job.error||job.detail||'AI ảnh local lỗi');
        await new Promise(r=>setTimeout(r,700));
      }
      throw Object.assign(new Error('Đã dừng AI ảnh'),{cancelled:true});
    }finally{if(activeJob===jobId)activeJob=null;}
  }

  async function run(){
    const prompt=$('aiImagePrompt').value.trim();if(!prompt)return S.setStatus('Nhập mô tả ảnh trước.',true);
    S.setBusy(true,refFile?'AI local đang sửa ảnh tham chiếu…':'AI local đang tạo ảnh…','Có thể bấm DỪNG bất cứ lúc nào');
    try{
      let created;
      if(refFile){
        const form=new FormData();form.append('file',refFile);form.append('prompt',prompt);form.append('style',$('aiImageStyle').value);form.append('size',$('aiImageSize').value);form.append('quality',$('aiImageQuality').value);
        created=await S.jsonRequest('/api/ai-image/jobs/edit',{method:'POST',body:form});
      }else{
        created=await S.jsonRequest('/api/ai-image/jobs/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,style:$('aiImageStyle').value,size:$('aiImageSize').value,quality:$('aiImageQuality').value})});
      }
      result=await poll(created.job_id);
      if(!result)return;
      $('aiImagePreview').src=result.url+'?v='+Date.now();$('aiImageResult').classList.remove('hidden');
      S.setStatus('AI ảnh local xong. Xem kết quả rồi đưa vào video nếu ưng.');
    }catch(e){
      if(e.cancelled)S.setStatus('Đã dừng AI ảnh. Ảnh hoàn tất trước đó vẫn được giữ.');
      else S.setStatus('Lỗi AI ảnh local: '+e.message,true);
    }finally{S.setBusy(false)}
  }
  $('aiImageRun').onclick=run;

  $('aiImageToVideo').onclick=async()=>{if(!result)return;if(!S.hasVideo())return S.setStatus('Tải video lên trước rồi mới đưa ảnh vào video.',true);S.setBusy(true,'Đang đưa ảnh AI vào video…');try{const a=await S.jsonRequest(`/api/editor/${S.state.sessionId}/asset-from-ai/${result.image_id}`,{method:'POST'});const l=S.newLayer({type:'image',name:'AI image local',source_kind:'asset',source:a.asset_id,previewUrl:a.url,widthRatio:.32});S.createLayerElement(l);S.selectLayer(l);S.setStatus('Đã đưa AI ảnh lên video. Kéo tới vị trí muốn đặt.')}catch(e){S.setStatus('Lỗi đưa ảnh vào video: '+e.message,true)}finally{S.setBusy(false)}};
  window.addEventListener('aivf-stop-all',()=>{stopped=true;activeJob=null;});
})();
