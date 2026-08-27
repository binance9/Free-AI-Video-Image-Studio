from __future__ import annotations
import json, shutil, threading, time, uuid
from pathlib import Path
from PIL import Image
from .cau_hinh_ban_do import resolve_quality, ALLOWED_TILES
from .dac_ta_ban_do import parse_prompt
from .chia_o_ban_do import build_tiles
from .khoa_bo_cuc import khoa_bo_cuc
from .phan_tich_anh_mau import analyze_reference
from .tao_o_ban_do import crop_reference_tile, tile_prompt
from .ghep_o_ban_do import stitch
from .kiem_tra_ban_do import validate_tiles

class Map3DService:
    VERSION="1.1.0"
    def __init__(self, root: Path, ai_image_service=None):
        self.root=Path(root); self.jobs=self.root/"jobs"; self.jobs.mkdir(parents=True,exist_ok=True)
        self.ai=ai_image_service
        self._jobs={}; self._lock=threading.Lock()

    def status(self):
        return {"ok":True,"version":self.VERSION,"mode":"hd_tiles","deep_zoom":True,"quality":["lite","standard","final"],"prompt_ai":self.ai is not None}
    def get(self,jid):
        with self._lock:
            if jid not in self._jobs: raise KeyError(jid)
            return dict(self._jobs[jid])
    def cancel(self,jid):
        with self._lock:
            if jid not in self._jobs:return False
            self._jobs[jid]["cancel_requested"]=True; return True
    def _set(self,jid,**kw):
        with self._lock:self._jobs[jid].update(kw)
    def start(self,prompt,quality,tile_count,reference_path:Path|None):
        q,cfg=resolve_quality(quality)
        if tile_count is not None and int(tile_count) not in ALLOWED_TILES: raise ValueError("Số tile hỗ trợ: 4, 6, 8, 10, 12, 16, 20")
        spec=parse_prompt(prompt,q,cfg,tile_count,reference_path is not None)
        jid=uuid.uuid4().hex[:12]; jobdir=self.jobs/jid; jobdir.mkdir(parents=True); (jobdir/"tiles").mkdir()
        if reference_path:
            target=jobdir/("reference"+reference_path.suffix.lower()); shutil.copy2(reference_path,target); reference_path=target
        state={"job_id":jid,"status":"queued","stage":"Đang chờ","progress":0,"cancel_requested":False,"job_dir":str(jobdir),"quality":q}
        with self._lock:self._jobs[jid]=state
        threading.Thread(target=self._run,args=(jid,spec.as_dict(),cfg,reference_path),daemon=True).start()
        return jid
    def _run(self,jid,spec,cfg,reference):
        started=time.time(); jobdir=Path(self._jobs[jid]["job_dir"])
        try:
            self._set(jid,status="running",stage="Phân tích yêu cầu",progress=5)
            refctx=analyze_reference(reference) if reference else None
            self._set(jid,stage="Khóa bố cục tổng",progress=8,detail="Đang khóa bố cục chung cho toàn bộ map trước khi chia tile…")
            bo_cuc=khoa_bo_cuc(jobdir=jobdir,spec=spec,reference_path=reference,ai_image_service=self.ai)
            (jobdir/"map_spec.json").write_text(json.dumps({**spec,"reference":refctx,"bo_cuc_tong":bo_cuc.name},ensure_ascii=False,indent=2),encoding="utf-8")
            grid=build_tiles(spec["tile_count"],spec["tile_size"],spec["overlap_px"])
            (jobdir/"manifest_tiles.json").write_text(json.dumps({**grid,"quality":spec["quality"],"tile_size":spec["tile_size"],"overlap_px":spec["overlap_px"],"deep_zoom":True,"bo_cuc_khoa":True},ensure_ascii=False,indent=2),encoding="utf-8")
            tile_paths={}
            for i,tile in enumerate(grid["tiles"]):
                if self.get(jid).get("cancel_requested"): raise RuntimeError("Đã hủy job map")
                self._set(jid,stage=f"Tạo tile {i+1}/{len(grid['tiles'])}",progress=10+int(70*i/max(1,len(grid['tiles']))))
                base=jobdir/"tiles"/(tile["tile_id"]+"_base.png")
                final=jobdir/"tiles"/(tile["tile_id"]+".png")
                # Moi tile - du co anh mau nguoi dung hay khong - deu crop tu
                # CUNG MOT bo_cuc_tong da khoa, dam bao lien mach hinh hoc
                # that su thay vi chi mo ta hang xom bang chu (section 3/4).
                crop_reference_tile(bo_cuc,tile,grid,base,spec["tile_size"],spec["overlap_px"])
                # cfg["refine"]: co AI edit() tinh chinh tung tile hay khong.
                # Da do that (xem MODULE_STATUS.md): tat ca muc chat luong deu
                # refine=True, vi crop tu bo_cuc_tong roi bo qua AI se mem net
                # hon la co AI edit them chi tiet - "Nhe" nhanh hon nho it
                # tile/tile_size nho hon, khong phai nho bo qua buoc nay.
                if self.ai and cfg.get("refine", True):
                    try:
                        raw=self.ai.edit(str(base),tile_prompt(spec,tile,refctx),"fantasy","1024x1024" if spec["tile_size"]<=1024 else "2048x2048",cfg["ai_quality"])
                        final.write_bytes(raw)
                    except Exception:
                        shutil.copy2(base,final)
                else:
                    shutil.copy2(base,final)
                tile_paths[tile["tile_id"]]=final
            self._set(jid,stage="Ghép bản đồ",progress=84)
            dims=stitch(tile_paths,grid,spec["tile_size"],jobdir/"ban_do_day_du.png",spec["overlap_px"])
            with Image.open(jobdir/"ban_do_day_du.png") as im:
                ov=im.copy(); ov.thumbnail((2048,2048),Image.Resampling.LANCZOS); ov.save(jobdir/"ban_do_tong_quan.png",quality=94)
            self._set(jid,stage="Kiểm tra độ nét và mép nối",progress=92)
            gate=validate_tiles(tile_paths,grid); (jobdir/"validation.json").write_text(json.dumps(gate,indent=2),encoding="utf-8")
            (jobdir/"toa_do_do_vat.json").write_text("[]",encoding="utf-8")
            info={"job_id":jid,"status":"completed","stage":"Hoàn tất","progress":100,"width":dims["width"],"height":dims["height"],"tile_count":len(tile_paths),"quality":spec["quality"],"validation":gate,"elapsed_seconds":round(time.time()-started,2),"overview_url":f"/api/ban-do-3d/job/{jid}/overview","manifest_url":f"/api/ban-do-3d/job/{jid}/manifest"}
            (jobdir/"nhat_ky_job.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
            self._set(jid,**info)
        except Exception as e:
            status="cancelled" if "hủy" in str(e).lower() else "failed"
            self._set(jid,status=status,stage="Đã dừng" if status=="cancelled" else "Lỗi",error=str(e),progress=self.get(jid).get("progress",0))
    def job_file(self,jid,name):
        jobdir=Path(self.get(jid)["job_dir"]).resolve(); p=(jobdir/name).resolve()
        if jobdir not in p.parents and p!=jobdir: raise ValueError("Đường dẫn không hợp lệ")
        if not p.exists(): raise FileNotFoundError(name)
        return p
