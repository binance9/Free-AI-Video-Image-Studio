(() => {
  class RealtimePreview {
    constructor() {
      this.root = document.getElementById('realtimePreview');
      this.image = document.getElementById('realtimePreviewImage');
      this.video = document.getElementById('realtimePreviewVideo');
      this.empty = document.getElementById('realtimePreviewEmpty');
      this.mode = null;
      this.objectUrl = null;
    }
    _hideOthers() { ['empty','videoBox','ai3dSourcePreview','ai3dStageViewer','mapHdStageViewer'].forEach(id => document.getElementById(id)?.classList.add('hidden')); }
    activate(mode='image', title='XEM TRƯỚC REALTIME') {
      this.mode=mode; this._hideOthers(); this.root?.classList.remove('hidden');
      const heading=document.querySelector('.preview-head h2'); if(heading)heading.textContent=title;
    }
    deactivate(){this.root?.classList.add('hidden');}
    showFile(file,type='image'){if(!file)return;if(this.objectUrl)URL.revokeObjectURL(this.objectUrl);this.objectUrl=URL.createObjectURL(file);this.show(type,this.objectUrl);}
    show(type,url){
      if(!url)return;this.activate(type,type==='video'?'VIDEO':type==='map'?'BẢN ĐỒ / TILE':'ẢNH REALTIME');this.empty?.classList.add('hidden');
      if(type==='video'){this.image?.classList.add('hidden');this.video.src=url;this.video.classList.remove('hidden');this.video.load();}
      else{this.video?.classList.add('hidden');this.image.src=url;this.image.classList.remove('hidden');}
    }
    update(job={}){
      const type=job.preview_type||this.mode||'image';if(job.preview_url)this.show(type,`${job.preview_url}${job.preview_url.includes('?')?'&':'?'}v=${Date.now()}`);else this.activate(type);
      const p=Math.max(0,Math.min(100,Number(job.progress)||0));
      const set=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};
      set('realtimePreviewStage',job.stage||job.status||'Đang xử lý');set('realtimePreviewMessage',job.message||job.detail||'');set('realtimePreviewPct',`${Math.round(p)}%`);
      const bar=document.getElementById('realtimePreviewBar');if(bar)bar.style.width=`${p}%`;
      this.root?.classList.toggle('is-running',!['done','completed','error','failed','cancelled'].includes(job.status));
    }
  }
  window.AIVFRealtimePreview=new RealtimePreview();
})();
