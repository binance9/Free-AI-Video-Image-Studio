from __future__ import annotations
from pathlib import Path
from tempfile import NamedTemporaryFile
import shutil
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

router=APIRouter(prefix="/api/ban-do-3d",tags=["ban-do-3d"])

def svc(request:Request):
    s=getattr(request.app.state,"ban_do_3d_service",None)
    if s is None:
        from .dich_vu_ban_do import Map3DService
        from app.core.config import settings
        ai=getattr(request.app.state,"ai_image_service",None)
        s=Map3DService(Path(settings.base_dir)/"data"/"ban_do_3d",ai); request.app.state.ban_do_3d_service=s
    return s

@router.get("/status")
def status(request:Request): return svc(request).status()

@router.post("/tao-tu-anh")
def create_from_image(request:Request,file:UploadFile=File(...),prompt:str=Form(""),quality:str=Form("standard"),tile_count:int|None=Form(None)):
    suffix=Path(file.filename or "map.png").suffix.lower()
    if suffix not in {".png",".jpg",".jpeg",".webp"}: raise HTTPException(400,"Ảnh map phải là PNG/JPG/WebP")
    temp=None
    try:
        with NamedTemporaryFile(delete=False,suffix=suffix) as f: shutil.copyfileobj(file.file,f); temp=Path(f.name)
        jid=svc(request).start(prompt,quality,tile_count,temp)
        return {"job_id":jid,"status_url":f"/api/ban-do-3d/job/{jid}"}
    except Exception as e: raise HTTPException(400,str(e))
    finally:
        if temp: temp.unlink(missing_ok=True)

@router.post("/tao-tu-mo-ta")
def create_from_prompt(request:Request,prompt:str=Form(...),quality:str=Form("standard"),tile_count:int|None=Form(None)):
    try:
        jid=svc(request).start(prompt,quality,tile_count,None); return {"job_id":jid,"status_url":f"/api/ban-do-3d/job/{jid}"}
    except Exception as e: raise HTTPException(400,str(e))

@router.get("/job/{job_id}")
def job(request:Request,job_id:str):
    try:return svc(request).get(job_id)
    except KeyError: raise HTTPException(404,"Không tìm thấy job map")
@router.post("/job/{job_id}/huy")
def cancel(request:Request,job_id:str): return {"cancelled":svc(request).cancel(job_id)}
@router.get("/job/{job_id}/overview")
def overview(request:Request,job_id:str):
    try:return FileResponse(svc(request).job_file(job_id,"ban_do_tong_quan.png"),media_type="image/png")
    except Exception as e: raise HTTPException(404,str(e))
@router.get("/job/{job_id}/master")
def master_preview(request:Request,job_id:str):
    try:return FileResponse(svc(request).job_file(job_id,"bo_cuc_tong.png"),media_type="image/png")
    except Exception as e:raise HTTPException(404,str(e))
@router.get("/job/{job_id}/full")
def full(request:Request,job_id:str):
    try:return FileResponse(svc(request).job_file(job_id,"ban_do_day_du.png"),media_type="image/png")
    except Exception as e: raise HTTPException(404,str(e))
@router.get("/job/{job_id}/manifest")
def manifest(request:Request,job_id:str):
    try:return FileResponse(svc(request).job_file(job_id,"manifest_tiles.json"),media_type="application/json")
    except Exception as e: raise HTTPException(404,str(e))
@router.get("/job/{job_id}/tile/{tile_id}")
def tile(request:Request,job_id:str,tile_id:str):
    if not tile_id.startswith("tile_") or any(x in tile_id for x in ("/","\\","..")): raise HTTPException(400,"tile_id không hợp lệ")
    try:return FileResponse(svc(request).job_file(job_id,f"tiles/{tile_id}.png"),media_type="image/png")
    except Exception as e: raise HTTPException(404,str(e))

@router.post("/job/{job_id}/chunks")
def split_chunks(request:Request,job_id:str):
    try:return svc(request).split_chunks(job_id)
    except KeyError: raise HTTPException(404,"Không tìm thấy job map")
    except ValueError as e: raise HTTPException(409,str(e))

@router.get("/job/{job_id}/chunks/manifest")
def chunks_manifest(request:Request,job_id:str):
    try:return FileResponse(svc(request).job_file(job_id,"map_chunks_manifest.json"),media_type="application/json")
    except Exception as e: raise HTTPException(404,str(e))

@router.get("/job/{job_id}/chunks/rebuild")
def chunks_rebuild(request:Request,job_id:str):
    try:return FileResponse(svc(request).job_file(job_id,"rebuild_from_chunks.png"),media_type="image/png")
    except Exception as e: raise HTTPException(404,str(e))

@router.get("/job/{job_id}/chunks/{chunk_id}")
def chunk_image(request:Request,job_id:str,chunk_id:str):
    if not chunk_id.startswith("chunk_") or any(x in chunk_id for x in ("/","\\","..")): raise HTTPException(400,"chunk_id không hợp lệ")
    try:return FileResponse(svc(request).job_file(job_id,f"chunks/{chunk_id}/map.png"),media_type="image/png")
    except Exception as e: raise HTTPException(404,str(e))

@router.get("/job/{job_id}/chunks/{chunk_id}/manifest")
def chunk_manifest(request:Request,job_id:str,chunk_id:str):
    if not chunk_id.startswith("chunk_") or any(x in chunk_id for x in ("/","\\","..")): raise HTTPException(400,"chunk_id không hợp lệ")
    try:return FileResponse(svc(request).job_file(job_id,f"chunks/{chunk_id}/manifest.json"),media_type="application/json")
    except Exception as e: raise HTTPException(404,str(e))
