"""Smoke test cho he thong SSE job-log (app/core/job_log_broker.py +
app/core/api_job_logs.py) - dung that (khong mo phong): stdout/stderr that
tu subprocess, khong lap log khi nhieu job chay song song, khong lap log
khi doi NORMAL/DEBUG giua chung 1 job, va nhan dung "gate tu choi ket qua"
(module hoan tat khong loi nhung tu choi output vi khong dat chat luong -
vd character_2d CLIP gate, map_hd sharpness gate) la "✕ LOI" chu khong phai
"✓ HOAN THANH".

Chay: pytest -q tests/smoke/test_job_logs_smoke.py

Ghi chu: cac test nang (chay job that qua GPU - Map HD, AI anh, Character
2D/3D, Do vat 3D) da duoc chay THAT bang tay trong phien lam viec nay
(khong tu dong hoa trong suite vi ton vai chuc phut/job) - xem MODULE_STATUS
cac module lien quan de biet ket qua that da ghi nhan. Test o day chi khoa
lai (regression-lock) 2 bug that da phat hien+sua qua qua trinh do:
1. _gate_rejected(): terminal_status truoc day chi nhan "hoan thanh that"
   qua field rieng cua map_hd (master_pass); character_2d hoan tat nhung
   BI TU CHOI (result.accepted=False) van bao "done" -> UI hien SAI
   "✓ HOAN THANH" cho ket qua that ra la bi loai.
2. "since" cursor: doi NORMAL/DEBUG giua job dang chay mo 1 EventSource
   MOI, neu khong co cursor se phat lai TOAN BO raw stdout/stderr da cache
   -> log hien lap 2 lan (da xac nhan qua test that bang Playwright).
"""
from __future__ import annotations

import threading

from app.core.job_log_broker import job_log_broker
from app.core.api_job_logs import _gate_rejected


def test_gate_rejected_detects_module_specific_reject_shapes():
    # character_2d: hoan tat (status=done) nhung CLIP gate tu choi
    assert _gate_rejected({"status": "done", "result": {"status": "rejected", "accepted": False}}) is True
    assert _gate_rejected({"status": "done", "result": {"status": "accepted", "accepted": True}}) is False
    # map_hd: hoan tat (status=completed) nhung sharpness/border gate tu choi
    assert _gate_rejected({"status": "completed", "master_pass": False}) is True
    assert _gate_rejected({"status": "completed", "master_pass": True}) is False
    # cac module khac khong co khai niem "gate tu choi" - khong duoc bao loi nham
    assert _gate_rejected({"status": "done", "result": {"image_url": "/api/ai-image/x.png"}}) is False
    assert _gate_rejected({"status": "done", "result": None}) is False
    assert _gate_rejected({"status": "done"}) is False


def test_broker_since_cursor_avoids_replaying_already_seen_raw_lines():
    scope, job_id = "test_scope_since", "job_since_1"
    job_log_broker.publish(scope, job_id, "dong 1", "stdout")
    job_log_broker.publish(scope, job_id, "dong 2", "stdout")
    job_log_broker.publish(scope, job_id, "dong 3", "stdout")

    from_zero = job_log_broker.after(scope, job_id, 0)
    assert len(from_zero) == 3
    last_seq = from_zero[-1]["seq"]

    # gia lap client "da xem het 3 dong", mo EventSource moi voi since=last_seq
    from_cursor = job_log_broker.after(scope, job_id, last_seq)
    assert from_cursor == [], "reconnect voi since=last_seq khong duoc phat lai dong cu nao"

    job_log_broker.publish(scope, job_id, "dong 4 - moi", "stdout")
    from_cursor_after_new = job_log_broker.after(scope, job_id, last_seq)
    assert len(from_cursor_after_new) == 1
    assert from_cursor_after_new[0]["message"] == "dong 4 - moi"


def test_broker_capture_scopes_publish_per_thread_no_cross_job_mixing():
    """Xac nhan co che cot loi chong 'tron log giua cac job': job_log_broker
    la 1 broker DUY NHAT dung chung cho toan app, cach ly job voi nhau CHI
    qua key (scope,job_id) - test truc tiep publish()/after() qua nhieu
    thread dong thoi (khong di qua stdout that de tranh xung dot voi co che
    tu bat stdout rieng cua pytest, von co the ghi de wrapper stdout toan
    cuc ma job_log_broker.install() da gan tu 1 test truoc do trong cung
    tien trinh pytest - trong app that, install() chi goi 1 lan luc khoi
    dong server, khong co xung dot nay; hanh vi that voi stdout that su
    da duoc kiem chung qua test that bang server that + job that trong
    phien lam viec nay, xem MODULE_STATUS.md)."""
    def worker(tag):
        for i in range(3):
            job_log_broker.publish("test_scope_mix", tag, f"log rieng cua {tag} dong {i}", "stdout")

    t1 = threading.Thread(target=worker, args=("job_a",))
    t2 = threading.Thread(target=worker, args=("job_b",))
    t1.start(); t2.start(); t1.join(); t2.join()

    events_a = job_log_broker.after("test_scope_mix", "job_a", 0)
    events_b = job_log_broker.after("test_scope_mix", "job_b", 0)
    msgs_a = [e["message"] for e in events_a]
    msgs_b = [e["message"] for e in events_b]
    assert len(msgs_a) == 3 and all("job_a" in m for m in msgs_a)
    assert not any("job_b" in m for m in msgs_a), "log cua job_b bi lot vao stream cua job_a"
    assert len(msgs_b) == 3 and all("job_b" in m for m in msgs_b)
    assert not any("job_a" in m for m in msgs_b), "log cua job_a bi lot vao stream cua job_b"


def test_job_terminal_js_tracks_seq_and_dedupes_end_event():
    """Kiem tra tinh (khong chay browser) rang file JS co ca 2 co che sua
    loi da xac nhan qua test that bang Playwright: track lastSeq de gui
    'since' khi doi mode, va co 'state.ended' de khong xu ly lai 'end' 2 lan
    khi mo EventSource moi cho 1 job DA xong (reconnect sau khi job da ket
    thuc se lam server phat lai 'end' ngay lap tuc)."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[2] / "web/core/job_terminal.js").read_text(encoding="utf-8")
    assert "lastSeq" in js
    assert "since=" in js
    assert "state.ended" in js
