(() => {
  const S=window.Studio,$=S.$;let presets=[];let active='caption_clean';
  function byId(id){return presets.find(x=>x.id===id)}
  function applyPreset(p){if(!p)return;active=p.id;$('fontFamily').value=p.font_family;$('fontSizeRatio').value=p.font_size_ratio;$('textColor').value=p.color;$('outlineColor').value=p.outline_color;$('outlineWidth').value=p.outline_width;$('backgroundColor').value=p.background;$('backgroundOpacity').value=Math.round(p.background_opacity*100);$('bgOpacityLabel').textContent=Math.round(p.background_opacity*100)+'%';$('shadowColor').value=p.shadow_color||'#000000';$('shadowOpacity').value=Math.round((p.shadow_opacity||0)*100);$('shadowBlur').value=p.shadow_blur||0;render()}
  function render(){const box=$('textPresetGrid');box.innerHTML='';presets.forEach(p=>{const b=document.createElement('button');b.className='preset-card'+(p.id===active?' active':'');b.innerHTML=`<strong>${S.esc(p.name)}</strong><small>${S.esc(p.group)}</small>`;b.onclick=()=>applyPreset(p);box.appendChild(b)})}
  async function load(){try{const d=await S.jsonRequest('/api/text/presets');presets=d.items||[];render();if(presets.length)applyPreset(byId(active)||presets[0])}catch(e){$('textPresetGrid').innerHTML='<div class="hint">Không tải được mẫu chữ.</div>'}}
  $('addLyrics').onclick=()=>{
    if(!S.hasVideo())return S.setStatus('Tải video lên trước.',true);
    const lines=$('lyricsInput').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);if(!lines.length)return S.setStatus('Nhập ít nhất một dòng lời.',true);
    const start=Math.max(0,+$('lyricsStart').value||0),end=Math.min(S.state.duration,+$('lyricsEnd').value||S.state.duration);if(end<=start)return S.setStatus('Khoảng thời gian lời bài hát chưa đúng.',true);
    const p=byId(active)||byId('karaoke_gold')||presets[0];const step=(end-start)/lines.length;
    lines.slice(0,80).forEach((text,i)=>{const l=S.newLayer({type:'text',name:'♪ '+text,text,widthRatio:.55,color:p.color,outlineColor:p.outline_color,outlineWidth:p.outline_width,background:p.background,backgroundOpacity:p.background_opacity,fontFamily:p.font_family,fontSizeRatio:p.font_size_ratio,shadowColor:p.shadow_color,shadowOpacity:p.shadow_opacity,shadowBlur:p.shadow_blur});l.start=start+i*step;l.end=Math.min(end,start+(i+1)*step+.08);l.x=.5;l.y=.82;S.createLayerElement(l)});S.renderTimeline();S.setStatus(`Đã tạo ${Math.min(lines.length,80)} lớp karaoke. Có thể sửa timing từng lớp.`)
  };
  window.TextTemplates={getPreset:byId,applyPreset,all:()=>presets};load();
})();
