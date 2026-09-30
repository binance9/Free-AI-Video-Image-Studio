from __future__ import annotations
import queue, threading, tkinter as tk
from tkinter import messagebox
from agent import GaAgent
from tools import ComputerTools
from speech_vi import VietnameseSpeechListener


class GaGUI:
    def __init__(self, root, config):
        self.root=root; self.config=config; self.q=queue.Queue(); self.drag_x=0; self.drag_y=0
        self.W=int(config.get("window_width",470)); self.H=int(config.get("window_height",620))
        self.root.overrideredirect(True); self.root.attributes("-topmost",bool(config.get("always_on_top",True))); self.root.configure(bg="#111318")
        self._place_right(); self.tools=ComputerTools(config,self.confirm); self.agent=GaAgent(config,self.tools); self.mic_on=False
        self._build()
        self.listener=VietnameseSpeechListener(on_text=lambda t:self.root.after(0,self._voice_text,t), on_status=lambda s:self.root.after(0,self._set_status,s), language="vi-VN", seconds=4.0)
        self.say("Gà","Maintenance sẵn sàng. Tao chỉ dọn rác và kiểm tra tình trạng máy.")
        if config.get("microphone_on_start",False): self.toggle_mic()
        if config.get("auto_scan_on_start",True): self.root.after(400,lambda:self.quick("maintenance_report"))
        self.root.after(100,self._poll)

    def _place_right(self):
        self.root.update_idletasks(); sw=self.root.winfo_screenwidth(); self.root.geometry(f"{self.W}x{self.H}+{max(0,sw-self.W-18)}+45")

    def _build(self):
        bg="#111318"; panel="#1d2128"; textbg="#0d0f13"; fg="#f4f6f8"; muted="#9da6b2"; green="#43d17c"
        title=tk.Frame(self.root,bg=panel,height=44); title.pack(fill="x"); title.pack_propagate(False)
        title.bind("<ButtonPress-1>",self._drag_start); title.bind("<B1-Motion>",self._drag_move)
        lab=tk.Label(title,text="GÀ MAINTENANCE",bg=panel,fg=fg,font=("Segoe UI",11,"bold")); lab.pack(side="left",padx=(12,8)); lab.bind("<ButtonPress-1>",self._drag_start); lab.bind("<B1-Motion>",self._drag_move)
        tk.Label(title,text="● SAFE MODE",bg=panel,fg=green,font=("Segoe UI",9,"bold")).pack(side="left")
        tk.Button(title,text="×",command=self.close,bg=panel,fg=fg,bd=0,width=3,font=("Segoe UI",12,"bold")).pack(side="right")
        tk.Button(title,text="—",command=self.hide,bg=panel,fg=fg,bd=0,width=3,font=("Segoe UI",11,"bold")).pack(side="right")

        body=tk.Frame(self.root,bg=bg); body.pack(fill="both",expand=True,padx=8,pady=8)
        actions=tk.Frame(body,bg=bg); actions.pack(fill="x",pady=(0,7))
        for text,tool in (("QUÉT MÁY","maintenance_report"),("QUÉT RÁC","scan_junk"),("GPU/CUDA","check_gpu_cuda"),("DỌN AN TOÀN","clean_safe_junk")):
            tk.Button(actions,text=text,command=lambda t=tool:self.quick(t),bg=panel,fg=fg,bd=0,padx=8,pady=7,font=("Segoe UI",8,"bold")).pack(side="left",expand=True,fill="x",padx=2)

        self.chat=tk.Text(body,bg=textbg,fg=fg,insertbackground=fg,bd=0,wrap="word",state="disabled",font=("Consolas",9),padx=10,pady=10)
        self.chat.pack(fill="both",expand=True); self.chat.tag_configure("ga",foreground=green); self.chat.tag_configure("me",foreground="#79b7ff"); self.chat.tag_configure("sys",foreground=muted)
        row=tk.Frame(body,bg=bg); row.pack(fill="x",pady=(7,5)); self.status=tk.Label(row,text="SAFE: không xóa model/package active",bg=bg,fg=muted,font=("Segoe UI",8)); self.status.pack(side="left")
        self.mic_btn=tk.Button(row,text="MIC OFF",command=self.toggle_mic,bg=panel,fg=fg,bd=0,padx=9,pady=3,font=("Segoe UI",9,"bold")); self.mic_btn.pack(side="right")
        inp=tk.Frame(body,bg=bg); inp.pack(fill="x"); self.entry=tk.Entry(inp,bg=panel,fg=fg,insertbackground=fg,relief="flat",font=("Segoe UI",10)); self.entry.pack(side="left",fill="x",expand=True,ipady=7); self.entry.bind("<Return>",lambda e:self.submit())
        tk.Button(inp,text="Gửi",command=self.submit,bg=panel,fg=fg,bd=0,padx=14,pady=6).pack(side="left",padx=(6,0))

    def _drag_start(self,e): self.drag_x=e.x_root-self.root.winfo_x(); self.drag_y=e.y_root-self.root.winfo_y()
    def _drag_move(self,e): self.root.geometry(f"+{e.x_root-self.drag_x}+{e.y_root-self.drag_y}")
    def hide(self): self.root.overrideredirect(False); self.root.iconify(); self.root.bind("<Map>",lambda e:self.root.after(50,self._reborderless))
    def _reborderless(self):
        try:self.root.overrideredirect(True)
        except Exception:pass
    def confirm(self,title,msg):
        if threading.current_thread() is threading.main_thread(): return bool(messagebox.askyesno(title,msg,parent=self.root))
        result={"v":False}; done=threading.Event()
        def ask(): result["v"]=bool(messagebox.askyesno(title,msg,parent=self.root)); done.set()
        self.root.after(0,ask); done.wait(); return result["v"]
    def say(self,who,text):
        self.chat.configure(state="normal"); tag="ga" if who=="Gà" else "me" if who=="Mày" else "sys"; self.chat.insert("end",who+": ",tag); self.chat.insert("end",str(text)+"\n\n"); self.chat.see("end"); self.chat.configure(state="disabled")
    def _set_status(self,text): self.status.configure(text=text)
    def toggle_mic(self):
        if self.mic_on: self.listener.stop(); self.mic_on=False; self.mic_btn.configure(text="MIC OFF",bg="#1d2128",fg="#f4f6f8")
        else: self.listener.start(); self.mic_on=True; self.mic_btn.configure(text="MIC ON",bg="#43d17c",fg="#08110c")
    def _voice_text(self,text): self.say("Mày","🎤 "+text); self._handle(text)
    def submit(self):
        text=self.entry.get().strip()
        if not text:return
        self.entry.delete(0,"end"); self.say("Mày",text); self._handle(text)
    def _handle(self,text): self._set_status("Đang xử lý..."); threading.Thread(target=self._worker,args=(text,),daemon=True).start()
    def _worker(self,text):
        try: answer,logs=self.agent.run(text); self.q.put(("ok",answer,logs))
        except Exception as e:self.q.put(("err",f"{type(e).__name__}: {e}",[]))
    def quick(self,tool):
        self._set_status("Đang chạy...")
        def work():
            try:self.q.put(("ok","Xong.",[self.tools.execute(tool,{})]))
            except Exception as e:self.q.put(("err",f"{type(e).__name__}: {e}",[]))
        threading.Thread(target=work,daemon=True).start()
    def _poll(self):
        try:
            while True:
                kind,answer,logs=self.q.get_nowait()
                for log in logs:self.say("Hệ thống",log)
                self.say("Gà",answer if kind=="ok" else "Có lỗi: "+answer); self._set_status("SAFE: không xóa model/package active")
        except queue.Empty:pass
        self.root.after(100,self._poll)
    def close(self):
        try:self.listener.stop()
        except Exception:pass
        self.root.destroy()
