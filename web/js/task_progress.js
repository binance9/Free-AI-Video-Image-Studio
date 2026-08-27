(() => {
  class TaskProgress {
    constructor(opts = {}) {
      this.root = document.getElementById(opts.rootId || 'busy');
      this.stage = document.getElementById(opts.stageId || 'busyText');
      this.pct = document.getElementById(opts.pctId || 'busyPct');
      this.bar = document.getElementById(opts.barId || 'busyBar');
      this.detail = document.getElementById(opts.detailId || 'busyDetail');
      this.elapsed = document.getElementById(opts.elapsedId || 'busyElapsed');
      this.timer = null;
      this.startedAt = 0;
      this.value = 0;
      this.mode = 'auto';
      this.active = false;
      this.hideTimer = null;
    }

    _fmtElapsed(seconds) {
      seconds = Math.max(0, Math.floor(seconds || 0));
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }

    _autoValue(seconds) {
      // Smooth estimated progress for synchronous endpoints where the backend
      // cannot expose byte/frame-level progress. It deliberately never reaches
      // 100 until the operation actually finishes.
      const t = Math.max(0, Number(seconds) || 0);
      if (t < 4) return 4 + t * 5.5;           // 4 -> 26
      if (t < 15) return 26 + (t - 4) * 2.2;  // 26 -> 50
      if (t < 45) return 50 + (t - 15) * .7;  // 50 -> 71
      if (t < 120) return 71 + (t - 45) * .18;// 71 -> 84.5
      if (t < 300) return 84.5 + (t - 120) * .035; // -> 90.8
      return Math.min(94, 90.8 + (t - 300) * .005);
    }

    _render() {
      if (this.pct) this.pct.textContent = `${Math.round(this.value)}%`;
      if (this.bar) this.bar.style.width = `${Math.max(0, Math.min(100, this.value))}%`;
      if (this.elapsed && this.startedAt) {
        this.elapsed.textContent = this._fmtElapsed((Date.now() - this.startedAt) / 1000);
      }
    }

    _tick() {
      if (!this.active) return;
      if (this.mode === 'auto') {
        const seconds = (Date.now() - this.startedAt) / 1000;
        this.value = Math.max(this.value, this._autoValue(seconds));
      }
      this._render();
    }

    start(stage, detail = '', mode = 'auto') {
      if (!this.root) return;
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
      if (this.timer) clearInterval(this.timer);
      this.active = true;
      this.mode = mode === 'real' ? 'real' : 'auto';
      this.startedAt = Date.now();
      this.value = this.mode === 'real' ? 1 : 4;
      if (this.stage) this.stage.textContent = stage || 'Đang xử lý…';
      if (this.detail) this.detail.textContent = detail || (this.mode === 'real' ? 'Đang xử lý…' : 'Tiến trình ước tính · backend local đang xử lý…');
      this.root.classList.remove('hidden');
      this._render();
      this.timer = setInterval(() => this._tick(), 500);
    }

    update(value, stage, detail, mode = 'real') {
      if (!this.root) return;
      if (!this.active) this.start(stage || 'Đang xử lý…', detail || '', mode);
      this.mode = mode === 'real' ? 'real' : this.mode;
      const n = Number(value);
      if (Number.isFinite(n)) this.value = Math.max(0, Math.min(100, n));
      if (stage && this.stage) this.stage.textContent = stage;
      if (detail && this.detail) this.detail.textContent = detail;
      this._render();
    }

    finish(stage = 'Hoàn tất', detail = 'Đã xử lý xong') {
      if (!this.root || !this.active) return;
      this.value = 100;
      if (stage && this.stage) this.stage.textContent = stage;
      if (detail && this.detail) this.detail.textContent = detail;
      this._render();
      this.active = false;
      if (this.timer) clearInterval(this.timer);
      this.timer = null;
      this.hideTimer = setTimeout(() => this.root?.classList.add('hidden'), 450);
    }

    cancel(stage = 'Đã dừng', detail = 'Tác vụ đã được dừng theo yêu cầu') {
      if (!this.root) return;
      this.mode = 'real';
      if (this.stage) this.stage.textContent = stage;
      if (this.detail) this.detail.textContent = detail;
      this.root.classList.remove('hidden');
      this._render();
      this.active = false;
      if (this.timer) clearInterval(this.timer);
      this.timer = null;
      this.hideTimer = setTimeout(() => this.root?.classList.add('hidden'), 900);
    }

    fail(stage = 'Lỗi', detail = 'Không xử lý được') {
      if (!this.root || !this.active) return;
      this.mode = 'real';
      if (this.stage) this.stage.textContent = stage;
      if (this.detail) this.detail.textContent = detail;
      this.root.classList.remove('hidden');
      this._render();
      this.active = false;
      if (this.timer) clearInterval(this.timer);
      this.timer = null;
      this.hideTimer = setTimeout(() => this.root?.classList.add('hidden'), 1800);
    }
  }

  window.AIVFTaskProgress = {
    create(options) { return new TaskProgress(options); },
  };
})();
