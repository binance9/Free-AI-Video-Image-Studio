(() => {
  class ImagePromptInput {
    constructor({fileId,promptId,nameId,preview}){this.fileElement=document.getElementById(fileId);this.promptElement=document.getElementById(promptId);this.nameElement=document.getElementById(nameId);this.preview=preview||window.AIVFRealtimePreview;this.file=null;if(this.fileElement)this.fileElement.onchange=e=>{this.file=e.target.files?.[0]||null;if(this.nameElement)this.nameElement.textContent=this.file?this.file.name:'＋ Thêm ảnh';if(this.file)this.preview?.showFile(this.file,'image');};}
    value(){return{file:this.file,prompt:(this.promptElement?.value||'').trim()};}
    validate(){const value=this.value();if(!value.file&&!value.prompt)throw new Error('Hãy thêm ảnh hoặc nhập mô tả.');return value;}
  }
  window.AIVFImagePromptInput=ImagePromptInput;
})();
