(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;
  const preset = $('ai3dPreset');
  const backend = $('ai3dBackend');
  const texture = $('ai3dTexture');
  const optimize = $('ai3dOptimizeMesh');
  const meshProfile = $('ai3dMeshProfile');
  const meshHint = $('ai3dMeshHint');
  const presetHint = $('ai3dPresetHint');
  const textureHint = $('ai3dTextureHint');
  if (!preset || !backend || !texture || !optimize || !meshProfile) return;

  const KEY = 'aivf3dPresetV0867';
  const PRESETS = {
    character_shape: {
      backend: 'character_hd', texture: false, optimize: true, mesh: 'hd',
      hint: 'Khuyến nghị: Hunyuan3D-2mini dựng shape đẹp + tối ưu mesh nhẹ; không nạp Paint.'
    },
    character_color: {
      backend: 'character_hd', texture: false, optimize: true, mesh: 'hd',
      hint: 'Màu HD an toàn: dựng shape trước; sau đó bấm TÔ MÀU GLB HIỆN CÓ để không dựng lại mesh.'
    },
    quick_object: {
      backend: 'quick', texture: false, optimize: true, mesh: 'hd',
      hint: 'Vật thể/test nhanh bằng TripoSR; không chạy Character HD.'
    }
  };

  function updateHints(){
    const hdPaint = backend.value === 'character_hd' && texture.checked;
    if (textureHint){
      textureHint.textContent = hdPaint
        ? '⚠ Legacy Paint cùng job đang BẬT. Khuyến nghị tắt và dùng nút TÔ MÀU GLB HIỆN CÓ.'
        : 'Shape job không chạy Paint. Tô màu riêng sau khi mesh đã lưu an toàn.';
      textureHint.classList.toggle('warn-text', hdPaint);
    }
    if (meshHint){
      const labels = {hd:'HD ~65–75% · mức đã test đẹp', medium:'Medium ~25–35% · nhẹ hơn cho game', light:'Light ~10–18% · ưu tiên nhẹ'};
      meshHint.textContent = optimize.checked ? (labels[meshProfile.value] || labels.hd) : 'Tối ưu đang TẮT: giữ nguyên mesh gốc 100%.';
    }
  }

  function apply(name, remember = true){
    const cfg = PRESETS[name];
    if (!cfg) return;
    preset.value = name;
    backend.value = cfg.backend;
    texture.checked = cfg.texture;
    optimize.checked = cfg.optimize;
    meshProfile.value = cfg.mesh || 'hd';
    if (presetHint) presetHint.textContent = cfg.hint;
    updateHints();
    if (remember){
      try { localStorage.setItem(KEY, name); } catch (_) {}
    }
  }

  function markCustom(){
    preset.value = 'custom';
    if (presetHint) presetHint.textContent = 'Tùy chỉnh thủ công. Nên để Paint cùng job TẮT và tô màu GLB riêng.';
    updateHints();
    try { localStorage.setItem(KEY, 'custom'); } catch (_) {}
  }

  preset.onchange = () => {
    if (preset.value === 'custom') return markCustom();
    apply(preset.value);
  };
  backend.onchange = markCustom;
  texture.onchange = markCustom;
  optimize.onchange = markCustom;
  meshProfile.onchange = markCustom;

  let saved = 'character_shape';
  try {
    const raw = localStorage.getItem(KEY);
    if (raw && PRESETS[raw]) saved = raw;
  } catch (_) {}
  apply(saved, false);

  window.AIVF3DPresets = {
    apply,
    current: () => preset.value,
    isHdPaint: () => backend.value === 'character_hd' && texture.checked,
  };
})();
