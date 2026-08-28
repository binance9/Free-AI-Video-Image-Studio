/* AI Video Factory - Unified Preview V1 compatibility shim.
   V2 intentionally has NO global listeners, observers, body classes or tool interception.
   Kept only so old references do not 404. */
(()=>{
  if(window.AIVFUnifiedPreview?.version==='2.0-safe-shim') return;
  const noop=()=>{};
  window.AIVFUnifiedPreview={
    version:'2.0-safe-shim',
    applyMode:noop,
    showFile:noop,
    showImageUrl:noop,
    hideImage:noop,
    show3D:noop,
    setHeader:noop,
    classify:()=>null,
    memory:new Map()
  };
})();
