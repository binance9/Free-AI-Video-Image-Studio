from __future__ import annotations
import io, json, shutil, threading, time, uuid
from pathlib import Path
from PIL import Image, ImageFilter
from .cau_hinh_ban_do import resolve_quality, ALLOWED_TILES
from .dac_ta_ban_do import parse_prompt
from .chia_o_ban_do import build_tiles
from .khoa_bo_cuc import khoa_bo_cuc
from .phan_tich_anh_mau import analyze_reference
from .tao_o_ban_do import crop_reference_tile, tile_prompt
from .ghep_o_ban_do import stitch
from .kiem_tra_ban_do import failed_tile_ids, validate_master
from .du_lieu_layout import build_master_layout, enrich_tiles_from_layout
from .tach_map_nho import rebuild_from_chunks, split_master_map, validate_chunks
from app.core.job_log_broker import job_log_broker


def _sharpen_tile_bytes(raw: bytes) -> bytes:
    """Sharpen THAT su (unsharp mask that su, khong bia dat chi tiet) tren
    tile vua sinh - do that (xem MODULE_STATUS.md, muc "sharpness gate lien
    tuc that bai") cho thay img2img tu 1 guide bi lam mo co chu dich
    (tao_o_ban_do.crop_reference_tile) van giu lai do mem nhat dinh du
    strength cao, khien sharpness_score (kiem_tra_ban_do.sharpness - do
    nang luong canh qua FIND_EDGES) dao dong quanh 0.15-0.30, khong on dinh
    vuot nguong 0.35. UnsharpMask la phep tang tuong phan canh CO SAN (khong
    them chi tiet gia).

    radius=2/percent=200/threshold=1 duoc chon bang do that tren 8 job that
    da chay (khong mo phong): dung lai TOAN BO pipeline stitch+validate that
    tren tile that cua 8 lan chay truoc, quet nhieu muc do sharpen - muc nay
    cho ty le PASS 5/8 (so voi 0/10 truoc khi co sharpen) ma van giu duoc
    no_text_score (gate "conservative high-frequency artifact") an toan cho
    da so truong hop; sharpen manh hon nua (vd percent=250) day no_text_score
    xuong duoi nguong o cac tile von da co tuong phan cao san. 3/8 truong hop
    van khong PASS: 1 truong hop base qua tuong phan (over-sharpen -> nhu
    "chu/UI gia" theo gate), 2 truong hop base qua mo (khong du canh de
    khuech dai) - day la gioi han that con lai, khong the sua het bang
    sharpen don thuan."""
    with Image.open(io.BytesIO(raw)) as im:
        sharpened = im.convert("RGB").filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=1))
        out = io.BytesIO()
        sharpened.save(out, "PNG")
        return out.getvalue()


class Map3DService:
    VERSION="1.3.0"
    def __init__(self, root: Path, ai_image_service=None):
        self.root=Path(root); self.jobs=self.root/"jobs"; self.jobs.mkdir(parents=True,exist_ok=True)
        self.ai=ai_image_service
        self._jobs={}; self._lock=threading.Lock()

    def status(self):
        return {"ok":True,"version":self.VERSION,"mode":"master_and_chunks","deep_zoom":True,"quality":["lite","standard","final"],"prompt_ai":self.ai is not None,"chunk_split":True}
    def get(self,jid):
        with self._lock:
            if jid not in self._jobs:
                if not jid.isalnum(): raise KeyError(jid)
                jobdir=(self.jobs/jid).resolve()
                log=jobdir/"nhat_ky_job.json"
                if self.jobs.resolve() not in jobdir.parents or not log.is_file(): raise KeyError(jid)
                recovered=json.loads(log.read_text(encoding="utf-8")); recovered["job_dir"]=str(jobdir); recovered.setdefault("cancel_requested",False)
                chunk_validation=jobdir/"chunks_validation.json"
                chunk_manifest=jobdir/"map_chunks_manifest.json"
                if chunk_validation.is_file() and chunk_manifest.is_file():
                    validation=json.loads(chunk_validation.read_text(encoding="utf-8")); manifest=json.loads(chunk_manifest.read_text(encoding="utf-8"))
                    recovered.update({"chunk_count":manifest["chunk_count"],"rows":manifest["rows"],"cols":manifest["cols"],"overlap":manifest["overlap"],"chunk_validation":validation,"chunks_manifest_url":f"/api/ban-do-3d/job/{jid}/chunks/manifest","rebuild_url":f"/api/ban-do-3d/job/{jid}/chunks/rebuild"})
                self._jobs[jid]=recovered
            result=dict(self._jobs[jid])
            result.setdefault("message",result.get("detail") or result.get("stage") or "")
            result.setdefault("preview_type","map")
            if result.get("status")=="completed": result["preview_url"]=result.get("overview_url")
            return result
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
        threading.Thread(target=job_log_broker.bound("map_hd",jid,self._run),args=(jid,spec.as_dict(),cfg,reference_path),daemon=True).start()
        return jid
    def _run(self,jid,spec,cfg,reference):
        started=time.time(); jobdir=Path(self._jobs[jid]["job_dir"])
        try:
            self._set(jid,status="running",stage="Phân tích yêu cầu",progress=5)
            refctx=analyze_reference(reference) if reference else None
            self._set(jid,stage="Khóa bố cục tổng",progress=8,detail="Đang khóa bố cục chung cho toàn bộ map trước khi chia tile…")
            bo_cuc=khoa_bo_cuc(jobdir=jobdir,spec=spec,reference_path=reference,ai_image_service=self.ai)
            self._set(jid,message="Master layout đã khóa",preview_type="map",preview_url=f"/api/ban-do-3d/job/{jid}/master")
            with Image.open(bo_cuc) as master_image:
                master_layout_gate={"width":master_image.width,"height":master_image.height,"layout_locked":True,"terrain_only":True,"pass":master_image.width>=512 and master_image.height>=512}
            if not master_layout_gate["pass"]:raise RuntimeError("Master Layout chưa đạt kích thước tối thiểu")
            grid=build_tiles(spec["tile_count"],spec["tile_size"],spec["overlap_px"])
            step=spec["tile_size"]-spec["overlap_px"]
            expected_width=grid["cols"]*step+spec["overlap_px"]
            expected_height=grid["rows"]*step+spec["overlap_px"]
            master_layout=build_master_layout(spec,expected_width,expected_height,refctx)
            master_layout["validation"]=master_layout_gate
            enrich_tiles_from_layout(grid,spec,master_layout)
            prompt_words=len(tile_prompt(spec,grid["tiles"][0],refctx).split()) if grid["tiles"] else 0
            map_spec={**spec,"reference":refctx,"bo_cuc_tong":bo_cuc.name,"master_layout":"master_layout.json","tile_prompt_word_count":prompt_words,"pipeline":"master-reference -> ai-generated-hd-tiles -> stitch -> chunks","asset_placement":"deferred"}
            (jobdir/"map_spec.json").write_text(json.dumps(map_spec,ensure_ascii=False,indent=2),encoding="utf-8")
            (jobdir/"master_layout.json").write_text(json.dumps(master_layout,ensure_ascii=False,indent=2),encoding="utf-8")
            tile_manifest={**grid,"quality":spec["quality"],"tile_size":spec["tile_size"],"overlap_px":spec["overlap_px"],"deep_zoom":True,"bo_cuc_khoa":True,"tile_output":"ai-generated-hd","preview_is_not_tile_source":True,"tile_prompt_word_count":prompt_words}
            (jobdir/"manifest_tiles.json").write_text(json.dumps(tile_manifest,ensure_ascii=False,indent=2),encoding="utf-8")
            tile_paths={};tile_sources={};retry_counts={};prompt_token_count=None
            def render_tile(tile, retry=False):
                nonlocal prompt_token_count
                tile_id=tile["tile_id"]
                base=jobdir/"tiles"/(tile_id+"_base.png");final=jobdir/"tiles"/(tile_id+".png")
                crop_reference_tile(bo_cuc,tile,grid,base,spec["tile_size"],spec["overlap_px"])
                if not (self.ai and cfg.get("refine",True)):
                    shutil.copy2(base,final);tile_sources[tile_id]="reference-crop-fallback";return
                try:
                    short_prompt=tile_prompt(spec,tile,refctx)
                    # strength cao (0.85) CO CHU DICH: base la anh da bi lam mo
                    # manh + giam contrast (xem tao_o_ban_do.py::crop_reference_tile,
                    # chi con y nghia mau/bo cuc tho) - img2img can "ve lai" that su
                    # thay vi bam sat init mo, neu khong tile ra van mo (da do that:
                    # strength mac dinh 0.58 -> sharpness_score ~0.147, that bai gate
                    # 2/2 lan; xem MODULE_STATUS.md).
                    raw=self.ai.edit(str(base),short_prompt,"fantasy","1024x1024" if spec["tile_size"]<=1024 else "2048x2048",cfg["ai_quality"],strength=0.85,progress=lambda _pct,stage,detail:self._set(jid,stage=f"Tạo tile {tile['index']+1}/{len(grid['tiles'])}",detail=f"{stage}: {detail}"))
                    raw=_sharpen_tile_bytes(raw)
                    final.write_bytes(raw);tile_sources[tile_id]="ai-generated-hd"
                    tokenizer=getattr(getattr(self.ai,"_img_pipe",None),"tokenizer",None)
                    if tokenizer is not None:
                        prompt_token_count=len(tokenizer(self.ai._prompt(short_prompt,"fantasy"),truncation=False).input_ids)
                except Exception:
                    shutil.copy2(base,final);tile_sources[tile_id]="reference-crop-fallback"
            for i,tile in enumerate(grid["tiles"]):
                if self.get(jid).get("cancel_requested"): raise RuntimeError("Đã hủy job map")
                self._set(jid,stage=f"Tạo tile {i+1}/{len(grid['tiles'])}",progress=10+int(70*i/max(1,len(grid['tiles']))))
                final=jobdir/"tiles"/(tile["tile_id"]+".png")
                # Moi tile - du co anh mau nguoi dung hay khong - deu crop tu
                # CUNG MOT bo_cuc_tong da khoa, dam bao lien mach hinh hoc
                # that su thay vi chi mo ta hang xom bang chu (section 3/4).
                # cfg["refine"]: co AI edit() tinh chinh tung tile hay khong.
                # Da do that (xem MODULE_STATUS.md): tat ca muc chat luong deu
                # refine=True, vi crop tu bo_cuc_tong roi bo qua AI se mem net
                # hon la co AI edit them chi tiet - "Nhe" nhanh hon nho it
                # tile/tile_size nho hon, khong phai nho bo qua buoc nay.
                render_tile(tile)
                tile_paths[tile["tile_id"]]=final
                self._set(jid,current_tile=tile["tile_id"],message=f"Tile {i+1}/{len(grid['tiles'])} đã sẵn sàng",preview_type="map",preview_url=f"/api/ban-do-3d/job/{jid}/tile/{tile['tile_id']}")
            # Chỉ retry tile lỗi; không regenerate toàn map.
            for retry in range(int(cfg.get("tile_retries",1))):
                failed=failed_tile_ids(tile_paths,grid)
                if not failed:break
                for tile_id in failed:
                    if self.get(jid).get("cancel_requested"):raise RuntimeError("Đã hủy job map")
                    tile=next(item for item in grid["tiles"] if item["tile_id"]==tile_id)
                    retry_counts[tile_id]=retry_counts.get(tile_id,0)+1
                    self._set(jid,stage=f"Sửa tile lỗi {tile_id}",progress=82,detail=f"Retry riêng tile {tile_id}, không tạo lại toàn map")
                    render_tile(tile,retry=True)
            for tile in grid["tiles"]:
                tile["render_source"]=tile_sources.get(tile["tile_id"],"unknown")
                tile["retry_count"]=retry_counts.get(tile["tile_id"],0)
            tile_manifest.update({"tiles":grid["tiles"],"all_tiles_generated_hd":all(value=="ai-generated-hd" for value in tile_sources.values()),"tile_sources":tile_sources})
            tile_manifest["tile_prompt_token_count"]=prompt_token_count
            map_spec["tile_prompt_token_count"]=prompt_token_count
            (jobdir/"map_spec.json").write_text(json.dumps(map_spec,ensure_ascii=False,indent=2),encoding="utf-8")
            (jobdir/"manifest_tiles.json").write_text(json.dumps(tile_manifest,ensure_ascii=False,indent=2),encoding="utf-8")
            self._set(jid,stage="Ghép bản đồ",progress=84)
            dims=stitch(tile_paths,grid,spec["tile_size"],jobdir/"ban_do_day_du.png",spec["overlap_px"])
            shutil.copy2(jobdir/"ban_do_day_du.png",jobdir/"map_nen_full_hd.png")
            with Image.open(jobdir/"ban_do_day_du.png") as im:
                ov=im.copy(); ov.thumbnail((2048,2048),Image.Resampling.LANCZOS); ov.save(jobdir/"ban_do_tong_quan.png",quality=94)
            shutil.copy2(jobdir/"ban_do_tong_quan.png",jobdir/"master_preview.png")
            self._set(jid,stage="Kiểm tra độ nét và mép nối",progress=92)
            gate=validate_master(tile_paths,grid,jobdir/"ban_do_day_du.png",bo_cuc,spec.get("constraints",[]),tile_sources,master_layout);gate["tile_sources"]=tile_sources;gate["tile_retry_counts"]=retry_counts;(jobdir/"validation.json").write_text(json.dumps(gate,indent=2),encoding="utf-8")
            (jobdir/"toa_do_do_vat.json").write_text("[]",encoding="utf-8")
            info={"job_id":jid,"status":"completed","stage":"Hoàn tất" if gate["pass"] else "Map tổng chưa đạt chuẩn","progress":100,"width":dims["width"],"height":dims["height"],"tile_count":len(tile_paths),"tile_resolution":spec["tile_size"],"overlap":spec["overlap_px"],"quality":spec["quality"],"validation":gate,"master_pass":gate["pass"],"can_split_chunks":gate["pass"],"tile_prompt_word_count":prompt_words,"tile_prompt_token_count":prompt_token_count,"tile_output_generated_hd":gate["generated_hd_ratio"]==1.0,"elapsed_seconds":round(time.time()-started,2),"overview_url":f"/api/ban-do-3d/job/{jid}/overview","manifest_url":f"/api/ban-do-3d/job/{jid}/manifest"}
            (jobdir/"nhat_ky_job.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
            self._set(jid,**info)
        except Exception as e:
            status="cancelled" if "hủy" in str(e).lower() else "failed"
            self._set(jid,status=status,stage="Đã dừng" if status=="cancelled" else "Lỗi",error=str(e),progress=self.get(jid).get("progress",0))
    def split_chunks(self,jid):
        current=self.get(jid)
        if current.get("status")!="completed": raise ValueError("Map tổng chưa hoàn tất")
        if not current.get("validation",{}).get("pass"): raise ValueError("Map tổng chưa PASS; không được tách map nhỏ")
        jobdir=Path(current["job_dir"])
        spec=json.loads((jobdir/"map_spec.json").read_text(encoding="utf-8"))
        self._set(jid,stage="Đang tách map thành khu vực",progress=96)
        tile_manifest=json.loads((jobdir/"manifest_tiles.json").read_text(encoding="utf-8"))
        manifest=split_master_map(master_path=jobdir/"map_nen_full_hd.png",out_dir=jobdir/"chunks",source_map_id=jid,quality=current["quality"],seed=spec["seed"],biomes=spec.get("biomes",[]),constraints=spec.get("constraints",[]),tile_manifest=tile_manifest)
        rebuild_from_chunks(chunks_dir=jobdir/"chunks",manifest=manifest,output_path=jobdir/"rebuild_from_chunks.png")
        validation=validate_chunks(master_path=jobdir/"ban_do_day_du.png",rebuilt_path=jobdir/"rebuild_from_chunks.png",manifest=manifest)
        (jobdir/"chunks_validation.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf-8")
        result={"chunk_count":manifest["chunk_count"],"rows":manifest["rows"],"cols":manifest["cols"],"overlap":manifest["overlap"],"chunk_validation":validation,"chunks_manifest_url":f"/api/ban-do-3d/job/{jid}/chunks/manifest","rebuild_url":f"/api/ban-do-3d/job/{jid}/chunks/rebuild"}
        self._set(jid,stage="Hoàn tất tách khu vực",progress=100,**result)
        return result
    def job_file(self,jid,name):
        jobdir=Path(self.get(jid)["job_dir"]).resolve(); p=(jobdir/name).resolve()
        if jobdir not in p.parents and p!=jobdir: raise ValueError("Đường dẫn không hợp lệ")
        if not p.exists(): raise FileNotFoundError(name)
        return p
