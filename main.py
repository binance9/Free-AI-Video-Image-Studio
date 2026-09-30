from __future__ import annotations
import json, tkinter as tk
from pathlib import Path

BASE=Path(__file__).resolve().parent
CFG=BASE/"config.json"
DEFAULT={
  "microphone_on_start":False,"always_on_top":True,"window_width":470,"window_height":620,
  "ollama_url":"http://127.0.0.1:11434","ollama_model":"qwen3:8b","max_agent_steps":6,
  "low_disk_threshold_gb":25,"temp_max_age_days":7,"hf_incomplete_min_age_hours":24,
  "auto_scan_on_start":True,"auto_clean_on_start":False
}
def load_config():
    data={}
    if CFG.exists():
        try:data=json.loads(CFG.read_text(encoding="utf-8"))
        except Exception:pass
    c=DEFAULT.copy(); c.update(data); return c

def main():
    from gui import GaGUI
    root=tk.Tk(); GaGUI(root,load_config()); root.mainloop()
if __name__=="__main__": main()
