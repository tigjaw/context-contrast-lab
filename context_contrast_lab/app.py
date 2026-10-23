"""Tkinter desktop interface for Context Contrast Lab."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import numpy as np
from PIL import Image, ImageTk, ImageOps

from .processor import Settings, process_image


class Tooltip:
    """Small hover hint for Tkinter controls."""

    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _event=None) -> None:
        if self.window is not None:
            return
        x = self.widget.winfo_pointerx() + 14
        y = self.widget.winfo_pointery() + 14
        self.window = window = tk.Toplevel(self.widget)
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x}+{y}")
        tk.Label(window, text=self.text, justify="left", wraplength=320,
                 padx=9, pady=7, bg="#303642", fg="#f3f4f6",
                 relief="solid", borderwidth=1, font=("Segoe UI", 9)).pack()

    def hide(self, _event=None) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Context Contrast Lab")
        self.geometry("1180x790")
        self.minsize(850, 580)
        self.configure(bg="#171a20")
        self.original: np.ndarray | None = None
        self.processed: np.ndarray | None = None
        self.source_path: Path | None = None
        self._photo = None
        self._image_rect = None
        self._job = None
        self._after_id = None
        self._job_running = False
        self._rerun_needed = False
        self._build()

    def _build(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#171a20")
        style.configure("Panel.TFrame", background="#20242c")
        style.configure("TLabel", background="#171a20", foreground="#e8eaf0", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Muted.TLabel", foreground="#a8afbd", font=("Segoe UI", 9))
        style.configure("Panel.TLabel", background="#20242c", foreground="#e8eaf0")
        style.configure("TButton", font=("Segoe UI", 10), padding=7)
        style.configure("Accent.TButton", background="#4e8cff", foreground="white")
        style.map("Accent.TButton", background=[("active", "#3975e2")])
        top = ttk.Frame(self, padding=(18, 14, 18, 10)); top.pack(fill="x")
        ttk.Label(top, text="Context Contrast Lab", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="Edge-aware local contrast for photos and screenshots", style="Muted.TLabel").pack(side="left", padx=16, pady=(6, 0))
        ttk.Button(top, text="Open image…", command=self.open_image, style="Accent.TButton").pack(side="right")

        body = ttk.Frame(self, padding=(14, 4, 14, 12)); body.pack(fill="both", expand=True)
        controls = ttk.Frame(body, style="Panel.TFrame", padding=14); controls.pack(side="left", fill="y", padx=(0, 12))
        ttk.Label(controls, text="ADJUSTMENTS", style="Panel.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 8))
        self.vars: dict[str, tk.DoubleVar] = {}
        slider_defs = [
            ("amount", "Contrast amount", 0, 1.5, .65),
            ("radius", "Detail scale", .25, 2.5, 1.0),
            ("fine_detail", "Fine detail", 0, 1, .7),
            ("mid_detail", "Medium detail", 0, 1, .7),
            ("coarse_detail", "Broad detail", 0, 1, .35),
            ("edge_protection", "Edge / halo protection", 0, 1, .65),
            ("noise_protection", "Noise protection", 0, 1, .7),
            ("context", "Context adaptation", 0, 1, .25),
        ]
        slider_help = {
            "amount": "Overall strength of the effect. At zero the image is unchanged; raising it makes the other adjustments more noticeable.",
            "radius": "Shifts all three detail ranges together. Lower values target smaller features; higher values move the effect toward larger features. The Fine, Medium, and Broad sliders control the strength within those ranges.",
            "fine_detail": "Controls tiny texture and edges, such as skin texture, grass, or grain. Strong fine detail can make noise more visible; Noise protection can reduce that.",
            "mid_detail": "Controls mid-sized features, such as folds, markings, and surface patterns.",
            "coarse_detail": "Controls broader variations, such as shading across a face or landscape.",
            "edge_protection": "Reduces the effect near strong edges to help avoid bright or dark outlines. More protection can also soften the contrast boost at those edges.",
            "noise_protection": "Limits boosting of fine grain and compression speckles, especially in flatter areas. It can balance stronger Fine detail.",
            "context": "Adds subtle contrast based on how bright an area is compared with its surroundings. It can help separate shadow or highlight details; Contrast amount controls its overall strength.",
        }
        for key, label, lo, hi, val in slider_defs:
            row = ttk.Frame(controls, style="Panel.TFrame"); row.pack(fill="x", pady=5)
            head = ttk.Frame(row, style="Panel.TFrame"); head.pack(fill="x")
            label_widget = ttk.Label(head, text=label, style="Panel.TLabel")
            label_widget.pack(side="left")
            Tooltip(label_widget, slider_help[key])
            var = tk.DoubleVar(value=val); self.vars[key] = var
            value_label = ttk.Label(head, text=f"{val:.2f}", style="Panel.TLabel"); value_label.pack(side="right")
            slider = ttk.Scale(row, from_=lo, to=hi, variable=var, command=lambda _v, v=value_label, x=var: (v.configure(text=f"{x.get():.2f}"), self.schedule_process()))
            slider.pack(fill="x", pady=(3, 0))
            Tooltip(slider, slider_help[key])
        ttk.Separator(controls).pack(fill="x", pady=11)
        self.mode = tk.StringVar(value="Split")
        ttk.Label(controls, text="Comparison", style="Panel.TLabel").pack(anchor="w")
        mode_row = ttk.Frame(controls, style="Panel.TFrame"); mode_row.pack(fill="x", pady=(5, 8))
        mode_help = {
            "Split": "Compare original on the left with processed on the right. Click or drag the divider across the image.",
            "Original": "Show the unedited image.",
            "Processed": "Show the enhanced image.",
        }
        for label in ("Split", "Original", "Processed"):
            radio = ttk.Radiobutton(mode_row, text=label, value=label, variable=self.mode, command=self.render)
            radio.pack(side="left", padx=(0, 4))
            Tooltip(radio, mode_help[label])
        self.split_var = tk.DoubleVar(value=.5)
        ttk.Label(controls, text="Split position", style="Panel.TLabel").pack(anchor="w")
        split_slider = ttk.Scale(controls, from_=0, to=1, variable=self.split_var, command=lambda _v: self.render())
        split_slider.pack(fill="x", pady=(3, 10))
        Tooltip(split_slider, "Moves the before/after divider. You can also click or drag the divider directly on the image.")
        actions = ttk.Frame(controls, style="Panel.TFrame"); actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Reset", command=self.reset).pack(side="left")
        ttk.Button(actions, text="Export…", command=self.export_image, style="Accent.TButton").pack(side="right")

        view = ttk.Frame(body, style="Panel.TFrame", padding=8); view.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(view, bg="#101216", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.render())
        self.canvas.bind("<Button-1>", self._canvas_click)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<Motion>", self._canvas_motion)
        self.canvas.bind("<Leave>", lambda _e: self.canvas.configure(cursor=""))
        self.status = ttk.Label(self, text="Open a photo or screenshot to begin.", anchor="w", padding=(16, 6), style="Muted.TLabel")
        self.status.pack(fill="x", side="bottom")

    def open_image(self) -> None:
        name = filedialog.askopenfilename(title="Open image", filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")])
        if not name: return
        try:
            image = ImageOps.exif_transpose(Image.open(name)).convert("RGBA")
            self.original = np.asarray(image, dtype=np.uint8)
            self.source_path = Path(name)
            self.status.configure(text=f"{self.source_path.name}  •  {image.width} × {image.height}")
            self.schedule_process(immediate=True)
        except Exception as exc:
            messagebox.showerror("Could not open image", str(exc))

    def _settings(self) -> Settings:
        return Settings(**{key: value.get() for key, value in self.vars.items()})

    def schedule_process(self, immediate: bool = False) -> None:
        if self.original is None: return
        if self._after_id: self.after_cancel(self._after_id)
        self._after_id = self.after(1 if immediate else 160, self._start_process)

    def _start_process(self) -> None:
        self._after_id = None
        if self.original is None: return
        if self._job_running:
            self._rerun_needed = True
            return
        source = self.original.copy(); settings = self._settings()
        self.status.configure(text="Processing…")
        self._job_running = True
        self._job = threading.Thread(target=self._worker, args=(source, settings), daemon=True)
        self._job.start()

    def _worker(self, source: np.ndarray, settings: Settings) -> None:
        try: result = process_image(source, settings)
        except Exception as exc: result = exc
        self.after(0, self._finish_process, result)

    def _finish_process(self, result) -> None:
        self._job_running = False
        rerun = self._rerun_needed
        self._rerun_needed = False
        if isinstance(result, Exception):
            self.status.configure(text=f"Processing failed: {result}")
            if rerun: self.schedule_process(immediate=True)
            return
        self.processed = result
        if self.source_path:
            self.status.configure(text=f"{self.source_path.name}  •  {self.original.shape[1]} × {self.original.shape[0]}  •  Ready")
        self.render()
        if rerun: self.schedule_process(immediate=True)

    def _canvas_click(self, event) -> None:
        if self.original is not None and self.mode.get() == "Split" and self.processed is not None:
            self._set_split_from_canvas_x(event.x)

    def _canvas_drag(self, event) -> None:
        if self.original is not None and self.mode.get() == "Split" and self.processed is not None:
            self._set_split_from_canvas_x(event.x)

    def _set_split_from_canvas_x(self, canvas_x: int) -> None:
        if self._image_rect is None:
            return
        image_x, _image_y, image_width, _image_height = self._image_rect
        position = np.clip((canvas_x - image_x) / max(image_width, 1), 0, 1)
        self.split_var.set(float(position))
        self.render()

    def _canvas_motion(self, event) -> None:
        if self.mode.get() != "Split" or self.processed is None or self._image_rect is None:
            self.canvas.configure(cursor="")
            return
        image_x, image_y, image_width, image_height = self._image_rect
        divider_x = image_x + int(image_width * self.split_var.get())
        over_image = image_y <= event.y <= image_y + image_height
        over_divider = abs(event.x - divider_x) <= 7
        self.canvas.configure(cursor="sb_h_double_arrow" if over_image and over_divider else "")

    def render(self) -> None:
        if self.original is None: return
        h, w = self.original.shape[:2]
        base = self.original.copy()
        if self.mode.get() == "Processed" and self.processed is not None:
            base[..., :3] = np.uint8(np.clip(self.processed[..., :3] * 255 + .5, 0, 255))
        elif self.mode.get() == "Split" and self.processed is not None:
            x = int(w * self.split_var.get())
            base[:, x:, :3] = np.uint8(np.clip(self.processed[:, x:, :3] * 255 + .5, 0, 255))
        image = Image.fromarray(base, "RGBA")
        cw, ch = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
        scale = min(cw / w, ch / h)
        size = (max(1, int(w * scale)), max(1, int(h * scale)))
        image = image.resize(size, Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        ox, oy = (cw - size[0]) // 2, (ch - size[1]) // 2
        self._image_rect = (ox, oy, size[0], size[1])
        self.canvas.create_image(ox, oy, image=self._photo, anchor="nw")
        if self.mode.get() == "Split" and self.processed is not None:
            sx = ox + int(size[0] * self.split_var.get())
            self.canvas.create_line(sx, oy, sx, oy + size[1], fill="#ffffff", width=2)
            self.canvas.create_rectangle(sx - 39, oy + 10, sx + 39, oy + 34, fill="#171a20", outline="#ffffff")
            self.canvas.create_text(sx, oy + 22, text="BEFORE | AFTER", fill="white", font=("Segoe UI", 8))

    def reset(self) -> None:
        for key, value in {"amount": .65, "radius": 1, "fine_detail": .7, "mid_detail": .7, "coarse_detail": .35, "edge_protection": .65, "noise_protection": .7, "context": .25}.items():
            self.vars[key].set(value)
        self.schedule_process(immediate=True)

    def export_image(self) -> None:
        if self.original is None or self.processed is None:
            messagebox.showinfo("Export", "Open an image and wait for processing to finish first."); return
        default = (self.source_path.stem if self.source_path else "image") + "_context_contrast.png"
        name = filedialog.asksaveasfilename(title="Export processed image", initialfile=default, defaultextension=".png", filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg *.jpeg")])
        if not name: return
        try:
            rgba = np.uint8(np.clip(self.processed * 255 + .5, 0, 255))
            image = Image.fromarray(rgba, "RGBA")
            if Path(name).suffix.lower() in (".jpg", ".jpeg"):
                image.convert("RGB").save(name, quality=96, subsampling=0, optimize=True)
            else:
                image.save(name, optimize=True)
            self.status.configure(text=f"Exported {Path(name).name}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
