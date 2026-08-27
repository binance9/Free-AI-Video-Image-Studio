(() => {
  const S=window.Studio,$=S.$;let installTracked=false;
  async function refresh(){
    try{
      const d=await S.jsonRequest('/api/settings/local-ai');
      const p=d.packages||{};
      const rows=[['Whisper phụ đề',p.faster_whisper],['Dịch Argos',p.argostranslate],['PyTorch',p.torch],['Diffusers',p.diffusers],['Transformers',p.transformers]];
      $('localAiStatus').innerHTML=`<strong>${d.ready?'AI local đã sẵn sàng':'Cần cài thêm AI local'}</strong><small>${rows.map(x=>`${x[1]?'✓':'○'} ${x[0]}`).join(' · ')}</small><small>${d.installing?'Đang cài thư viện…':'Không có API trả phí bắt buộc'}</small>`;
      $('installLocalAi').disabled=!!d.installing||!!d.ready;
      if(d.installing){
        installTracked=true;
        const done=rows.filter(x=>x[1]).length;
        const pct=Math.min(94,8+Math.round(done/Math.max(1,rows.length)*82));
        S.updateBusyProgress?.(pct,'Đang cài AI local',`${done}/${rows.length} nhóm thư viện đã sẵn sàng · lần đầu có thể tải model lớn`,'real');
        setTimeout(refresh,3500);
      }else if(installTracked){
        if(d.ready){ S.updateBusyProgress?.(100,'Cài AI local hoàn tất','Whisper, dịch và AI ảnh đã sẵn sàng','real'); S.setBusy(false); }
        else S.failBusyProgress?.('Cài AI local chưa hoàn tất','Một số thư viện vẫn chưa sẵn sàng; có thể chạy SETUP_FREE_AI.bat');
        installTracked=false;
      }
    }catch(e){$('localAiStatus').innerHTML=`<strong>Không đọc được trạng thái</strong><small>${S.esc(e.message)}</small>`}
  }
  $('apiSettingsBtn').onclick=()=>{$('apiModal').classList.remove('hidden');refresh()};
  $('apiModalClose').onclick=()=>$('apiModal').classList.add('hidden');
  $('apiModal').onclick=e=>{if(e.target===$('apiModal'))$('apiModal').classList.add('hidden')};
  $('installLocalAi').onclick=async()=>{
    try{
      $('installLocalAi').disabled=true;installTracked=true;S.setBusy(true,'Đang cài AI local','Chuẩn bị Whisper · Argos · PyTorch · Diffusers…');S.setStatus('Đang bắt đầu cài AI local miễn phí…');
      const d=await S.jsonRequest('/api/settings/install-local-ai',{method:'POST'});
      S.setStatus(d.message+' · Có thể mất vài phút vì PyTorch khá lớn.');refresh();
    }catch(e){S.setStatus('Không cài được AI local: '+e.message,true);$('installLocalAi').disabled=false}
  };
})();
