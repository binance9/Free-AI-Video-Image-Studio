(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;

  let referenceFile = null;
  let referenceObjectUrl = '';
  let lastResult = null;
  let lastImageUrl = '';
  const realtime = window.AIVFRealtimePreview;

  const pct = (v) => v == null ? '--' : `${Math.round(Number(v) * (Number(v) <= 1 ? 100 : 1))}%`;

  function setReference(file){
    referenceFile = file || null;
    if (referenceObjectUrl){ URL.revokeObjectURL(referenceObjectUrl); referenceObjectUrl = ''; }
    if (!referenceFile){
      $('char2dRefName').textContent = 'Ảnh mẫu · không bắt buộc';
      return;
    }
    $('char2dRefName').textContent = referenceFile.name;
    referenceObjectUrl = URL.createObjectURL(referenceFile);
    realtime?.showFile(referenceFile,'image',() => { const el = $('char2dRefFile'); if (el) el.value = ''; setReference(null); });
  }

  $('char2dRefFile')?.addEventListener('change', e => setReference(e.target.files?.[0] || null));

  function showResult(data){
    lastResult = data;
    const accepted = Boolean(data.accepted);
    const imgUrl = accepted ? data.image_url : data.best_rejected_url;
    lastImageUrl = accepted ? (data.image_url || '') : '';
    const result = $('char2dResult');
    result?.classList.remove('hidden');

    const badge = $('char2dResultBadge');
    if (badge){
      badge.textContent = accepted ? 'PASS' : 'REJECT';
      badge.classList.toggle('reject', !accepted);
    }
    $('char2dResultTitle').textContent = accepted ? 'Ảnh đạt gate · sẵn sàng' : 'Chưa đạt gate · xem ảnh tốt nhất';
    $('char2dOperation').textContent = String(data.operation || 'auto').replaceAll('-', ' ');

    if (imgUrl){
      realtime?.show('image',imgUrl);
    }

    const gate = data.gate_summary || {};
    $('char2dScore').textContent = gate.score == null ? '--' : `${Math.round(Number(gate.score))}%`;
    $('char2dIdentity').textContent = pct(gate.identity);
    $('char2dColor').textContent = pct(gate.target_color);
    $('char2dWeapon').textContent = pct(gate.weapon);

    const blockers = gate.blockers || [];
    const blockerBox = $('char2dBlockers');
    if (blockers.length){
      blockerBox.textContent = `Cần sửa: ${blockers.join(' · ')}`;
      blockerBox.classList.remove('hidden');
    }else blockerBox.classList.add('hidden');

    const dl = $('char2dDownload');
    if (dl){
      dl.href = imgUrl || '#';
      dl.classList.toggle('disabled', !imgUrl);
    }
    const to3d = $('char2dTo3D');
    if (to3d){
      to3d.disabled = !accepted || !lastImageUrl;
      to3d.title = accepted ? 'Gửi ảnh PASS sang AI 3D Studio' : 'Ảnh phải PASS trước khi gửi sang 3D';
    }
  }

  async function generate(){
    const prompt = $('char2dPrompt')?.value.trim() || '';
    if (prompt.length < 3 && !referenceFile) return S.setStatus('Hãy thêm ảnh hoặc nhập mô tả.', true);
    const btn = $('char2dGenerate');
    if (btn) btn.disabled = true;
    realtime?.activate('image','NHÂN VẬT 2D REALTIME');
    realtime?.update({status:'running',progress:1,stage:referenceFile?'Ảnh nguồn':'Chuẩn bị',message:'Character 2D đang xử lý',preview_type:'image'});
    S.setStatus('Character 2D đang tạo ảnh…');
    try{
      const form = new FormData();
      form.append('prompt', prompt);
      form.append('preset', 'compact_game');
      form.append('strength', $('char2dStrength')?.value || '0.28');
      form.append('quality', $('char2dQuality')?.value || 'medium');
      if (referenceFile) form.append('image', referenceFile);
      const started = await S.jsonRequest('/api/character-2d/jobs', {method:'POST', body:form});
      window.AIVFJobTerminal?.start({scope:'character_2d',jobId:started.job_id,title:'ĐANG TẠO NHÂN VẬT 2D'});
      const job = await window.AIVFRealtimeProgress.poll({url:started.status_url});
      const data = job.result;
      showResult(data);
      if (data.accepted){
        S.setStatus(`Character 2D PASS · gate ${Math.round(data.gate_summary?.score || 0)}% · có thể gửi thẳng sang 3D.`);
      }else{
        const blockers = data.gate_summary?.blockers || [];
        S.setStatus(`Character 2D chưa PASS${blockers.length ? ': ' + blockers.join(', ') : ''}`, true);
      }
    }catch(e){
      S.setStatus('Character 2D lỗi: ' + e.message, true);
    }finally{
      if (btn) btn.disabled = false;
    }
  }

  $('char2dGenerate')?.addEventListener('click', generate);
  $('char2dAgain')?.addEventListener('click', generate);

  $('char2dTo3D')?.addEventListener('click', async () => {
    if (!lastResult?.accepted || !lastImageUrl) return S.setStatus('Ảnh 2D phải PASS trước.', true);
    try{
      S.setStatus('Đang chuyển ảnh Character 2D sang AI 3D Studio…');
      const res = await fetch(lastImageUrl);
      if (!res.ok) throw new Error('Không đọc được ảnh Character 2D đã PASS');
      const blob = await res.blob();
      if (!window.AIVF3D?.useImageBlob) throw new Error('Module AI 3D chưa sẵn sàng');
      window.AIVF3D.useImageBlob(blob, 'AI_Video_Factory_Character2D.png');
    }catch(e){
      S.setStatus('Không chuyển được sang 3D: ' + e.message, true);
    }
  });

  // Small status probe so the panel can immediately tell the user if the engine is available.
  fetch('/api/character-2d/status').then(r => r.ok ? r.json() : null).then(data => {
    if (!data) return;
    const hero = document.querySelector('.character2d-local');
    if (hero) hero.textContent = data.engine?.device === 'cuda' ? 'RTX · LOCAL' : 'LOCAL';
  }).catch(() => {});

  window.AIVFCharacter2D = { generate, setReference, get lastResult(){ return lastResult; } };
})();
