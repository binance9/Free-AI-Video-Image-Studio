(() => {
  class ImagePromptInput {
    constructor({fileId,promptId,nameId,preview,clearId,defaultName}){
      this.fileElement=document.getElementById(fileId);this.promptElement=document.getElementById(promptId);this.nameElement=document.getElementById(nameId);this.clearElement=clearId?document.getElementById(clearId):null;this.preview=preview||window.AIVFRealtimePreview;this.file=null;this.defaultName=defaultName||'＋ Thêm ảnh';
      if(this.fileElement)this.fileElement.onchange=e=>{this.file=e.target.files?.[0]||null;if(this.nameElement)this.nameElement.textContent=this.file?this.file.name:this.defaultName;if(this.clearElement)this.clearElement.hidden=!this.file;if(this.file)this.preview?.showFile(this.file,'image',()=>this.clear());};
      if(this.clearElement)this.clearElement.onclick=()=>this.clear();
    }
    clear(){this.file=null;if(this.fileElement)this.fileElement.value='';if(this.nameElement)this.nameElement.textContent=this.defaultName;if(this.clearElement)this.clearElement.hidden=true;}
    value(){return{file:this.file,prompt:(this.promptElement?.value||'').trim()};}
    validate(){const value=this.value();if(!value.file&&!value.prompt)throw new Error('Hãy thêm ảnh hoặc nhập mô tả.');return value;}
  }
  window.AIVFImagePromptInput=ImagePromptInput;
})();
