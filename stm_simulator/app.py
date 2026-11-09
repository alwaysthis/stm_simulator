"""Desktop control panel for STM simulation."""
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import numpy as np
from .core import read_parchg, simulate, demo_volume

BG, PANEL, TEXT, MUTED, ACCENT = "#242424", "#1c1c1c", "#ffffff", "#9e9e9e", "#4a90d9"

class App(tk.Tk):
    def __init__(self):
        import sys
        if sys.platform == "win32":
            import ctypes
            try:
                ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except (AttributeError, OSError):
                pass
        super().__init__()
        self.tk.call("tk", "scaling", 4 / 3)
        self.title("STM Simulator")
        self.geometry("1240x860")
        self.minsize(1000, 720)
        self.configure(bg=BG)
        self.volume = self.result = self.photo = None
        self.rgb = None
        self.busy = False
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=PANEL)
        style.configure("TLabel", background=PANEL, foreground=TEXT, font=("Microsoft YaHei UI", 10))
        style.configure("TButton", padding=(8, 5), background="#4a4a4a", foreground=TEXT,
                        bordercolor="#3a3a3a", lightcolor="#4a4a4a", darkcolor="#4a4a4a", font=("Microsoft YaHei UI", 10))
        style.map("TButton", background=[("active", "#5a5a5a"), ("pressed", "#333333")])
        style.configure("Run.TButton", background=ACCENT)
        style.map("Run.TButton", background=[("active", "#5b9fe5")])
        style.configure("TEntry", fieldbackground="#1e1e1e", foreground=TEXT, padding=4, bordercolor="#3a3a3a", insertcolor=TEXT)
        style.configure("TCombobox", fieldbackground="#1e1e1e", background="#333333", foreground=TEXT, padding=4, arrowcolor=MUTED)
        style.map("TCombobox", fieldbackground=[("readonly", "#1e1e1e")], foreground=[("readonly", TEXT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#303030", foreground=MUTED, padding=(16, 7), font=("Microsoft YaHei UI", 10))
        style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", TEXT)])
        style.configure("TLabelframe", background=PANEL, bordercolor="#303030")
        style.configure("TLabelframe.Label", background=PANEL, foreground=MUTED, font=("Microsoft YaHei UI", 9))
        toolbar = tk.Frame(self, bg=BG, height=44)
        toolbar.pack(fill="x", padx=12, pady=(7, 5))
        tk.Label(toolbar, text="STM Simulator", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 11, "bold")).pack(side="left", padx=(0, 24))
        ttk.Button(toolbar, text="打开文件", command=self.open_file).pack(side="left", padx=3)
        ttk.Button(toolbar, text="演示数据", command=self.demo).pack(side="left", padx=3)
        ttk.Button(toolbar, text="导出图像", command=self.export_image).pack(side="left", padx=3)
        ttk.Button(toolbar, text="导出数据", command=self.export_data).pack(side="left", padx=3)
        tk.Label(toolbar, text="●  离线分析", bg=BG, fg="#83bd8b", font=("Microsoft YaHei UI", 9)).pack(side="right", padx=8)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=8)
        rail = tk.Frame(body, bg=BG, width=48)
        rail.pack(side="left", fill="y", padx=(0, 6))
        tk.Label(rail, text="STM", bg="#3d6a9a", fg=TEXT, padx=6, pady=12).pack(fill="x", pady=3)
        tk.Label(rail, text="分析", bg=BG, fg=MUTED, pady=12).pack(fill="x")
        split = tk.PanedWindow(body, orient="horizontal", bg=BG, sashwidth=6, borderwidth=0)
        split.pack(fill="both", expand=True)
        workspace = ttk.Notebook(split)
        self.view = ttk.Frame(workspace)
        workspace.add(self.view, text="STM 图像")
        help_page = ttk.Frame(workspace, padding=20)
        workspace.add(help_page, text="方法说明")
        ttk.Label(help_page, text="Tersoff–Hamann 近似\n\n恒高：对三维部分密度取水平切片。\n恒流：从所选真空侧寻找首次达到阈值的高度。\n\n偏压能窗由 VASP 的 EINT 设置，需载入对应 PARCHG。\n等密度阈值沿用文件原始数值。平滑宽度以网格间距计。\n洋红色表示搜索范围内没有交点。", justify="left").pack(anchor="nw")
        split.add(workspace, stretch="always", minsize=500)
        controls = ttk.Frame(split, padding=12, width=286)
        split.add(controls, stretch="never", minsize=280)
        ttk.Label(controls, text="模拟设置", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        source = ttk.LabelFrame(controls, text=" 数据源 ", padding=10)
        source.pack(fill="x", pady=(0, 10))
        self.file_label = ttk.Label(source, text="尚未载入 PARCHG", wraplength=240, foreground=MUTED)
        self.file_label.pack(anchor="w")
        scan = ttk.LabelFrame(controls, text=" 扫描参数 ", padding=10)
        scan.pack(fill="x", pady=(0, 10))
        self.mode = self.combo(scan, "扫描模式", ["恒流 / Constant current", "恒高 / Constant height"])
        self.side = self.combo(scan, "扫描表面", ["上表面 / Top", "下表面 / Bottom"])
        self.threshold = self.entry(scan, "等密度阈值", "0.001")
        self.height = self.entry(scan, "针尖距外层原子  /  Å", "4.0")
        self.sigma = self.entry(scan, "高斯平滑  /  网格 σ", "0")
        bounds = ttk.LabelFrame(controls, text=" 搜索范围 · 留空自动 ", padding=10)
        bounds.pack(fill="x", pady=(0, 10))
        self.zmin = self.entry(bounds, "z 下界  /  Å", "")
        self.zmax = self.entry(bounds, "z 上界  /  Å", "")
        self.run_button = ttk.Button(controls, text="运行模拟", style="Run.TButton", command=self.run)
        self.run_button.pack(fill="x", pady=5)
        self.summary = tk.Label(self.view, text="等待数据", bg=PANEL, fg=MUTED, anchor="w", padx=12, pady=9)
        self.summary.pack(fill="x")
        self.canvas = tk.Canvas(self.view, bg="#111111", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8)
        self.canvas.bind("<Configure>", lambda event: self.render())
        self.canvas.bind("<Motion>", self.inspect)
        self.canvas.create_text(250, 200, text="打开 PARCHG 或载入演示数据", fill=MUTED, font=("Microsoft YaHei UI", 12))
        self.readout = tk.Label(self.view, text="x  —     y  —     value  —", bg=PANEL, fg=MUTED, anchor="w", padx=12, pady=9)
        self.readout.pack(fill="x")
        dock = ttk.Notebook(self, height=66)
        dock.pack(fill="x", padx=62, pady=(6, 0))
        log_page = ttk.Frame(dock)
        dock.add(log_page, text="日志")
        self.log = tk.Text(log_page, height=3, bg="#1a1a1a", fg=MUTED, font=("Consolas", 9), relief="flat", padx=10, pady=5, state="disabled")
        self.log.pack(fill="both", expand=True)
        self.status = tk.Label(self, text="就绪  ·  等密度阈值采用 PARCHG 原始数值", bg=BG, fg=MUTED, anchor="w", padx=12, pady=5)
        self.status.pack(fill="x")
        self.status.bind("<Configure>", self.update_log)
        self._last_status = ""
        self.after(200, self.poll_status)

    def update_log(self, event=None):
        text = self.status.cget("text")
        if text == self._last_status:
            return
        self._last_status = text
        self.log.config(state="normal")
        self.log.insert("end", text+"\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def poll_status(self):
        self.update_log()
        self.after(200, self.poll_status)

    def combo(self, parent, label, values):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 3))
        widget = ttk.Combobox(parent, values=values, state="readonly")
        widget.current(0)
        widget.pack(fill="x")
        return widget

    def entry(self, parent, label, default):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 3))
        variable = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=variable).pack(fill="x")
        return variable

    def background(self, operation, callback):
        if self.busy:
            return
        self.busy = True
        self.run_button.state(["disabled"])
        self.status.config(text="WORKING  ·  正在处理…")
        def worker():
            try:
                value = operation()
                self.after(0, lambda: finish(value, None))
            except Exception as error:
                self.after(0, lambda message=str(error): finish(None, message))
        def finish(value, error):
            self.busy = False
            self.run_button.state(["!disabled"])
            if error:
                self.status.config(text="ERROR  ·  "+error)
                messagebox.showerror("STM Simulator", error)
            else:
                callback(value)
        threading.Thread(target=worker, daemon=True).start()

    def open_file(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(title="选择 PARCHG", filetypes=[("VASP volume", "PARCHG* CHGCAR*"), ("All files", "*")])
        if path:
            self.background(lambda: read_parchg(path), self.loaded)

    def loaded(self, volume):
        self.volume = volume
        self.result = self.rgb = self.photo = None
        self.canvas.delete("all")
        self.file_label.config(text=f"{volume.name}\nGrid  {volume.values.shape}\nAtoms  {len(volume.positions)}")
        self.status.config(text="LOADED  ·  第一数据块 / total density")

    def demo(self):
        if not self.busy:
            self.loaded(demo_volume())
            self.run()

    def run(self):
        if self.volume is None:
            messagebox.showinfo("STM Simulator", "请先打开 PARCHG 或演示数据")
            return
        if self.busy:
            return
        try:
            mode = "current" if self.mode.current() == 0 else "height"
            kwargs = dict(mode=mode, side="top" if self.side.current() == 0 else "bottom",
                          height=float(self.height.get()), threshold=float(self.threshold.get()), sigma=float(self.sigma.get()),
                          z_min=float(self.zmin.get()) if self.zmin.get().strip() else None,
                          z_max=float(self.zmax.get()) if self.zmax.get().strip() else None)
        except ValueError:
            messagebox.showerror("Parameters", "请输入有效数值")
            return
        volume = self.volume
        self.background(lambda: simulate(volume, **kwargs), lambda value: self.calculated(value, kwargs))

    def calculated(self, output, parameters):
        self.result, self.plane_height = output
        self.parameters = parameters
        finite = self.result[np.isfinite(self.result)]
        if not finite.size:
            self.result = self.photo = None
            self.rgb = None
            self.canvas.delete("all")
            self.status.config(text="NO CROSSINGS  ·  请调整阈值或搜索范围")
            return
        self.unit = "Å" if parameters["mode"] == "current" else "raw density"
        self.minimum, self.maximum = float(finite.min()), float(finite.max())
        self.summary.config(text=f"{parameters['mode'].upper()}   |   {parameters['side'].upper()}   |   {self.minimum:.5g} — {self.maximum:.5g} {self.unit}")
        missing = 100*np.isnan(self.result).mean()
        self.status.config(text=f"COMPLETE  ·  Δ = {self.maximum-self.minimum:.5g} {self.unit}  ·  无交点 {missing:.1f}%")
        self.make_rgb()
        self.render()

    def make_rgb(self):
        span = self.maximum-self.minimum
        normalized = np.nan_to_num((self.result-self.minimum)/(span if span else 1), nan=0.)
        anchors = np.array([[11, 17, 34], [21, 69, 109], [29, 153, 150], [147, 215, 148], [255, 239, 172]])
        levels = np.linspace(0, 1, len(anchors))
        self.rgb = np.stack([np.interp(normalized, levels, anchors[:, channel]) for channel in range(3)], axis=-1).astype(np.uint8)
        self.rgb[np.isnan(self.result)] = [110, 30, 70]

    def render(self):
        if self.rgb is None:
            return
        lattice = self.volume.lattice
        corners = np.array([[0, 0], lattice[0,:2], lattice[1,:2], lattice[0,:2]+lattice[1,:2]])
        low, high = corners.min(axis=0), corners.max(axis=0)
        available = np.array([max(100,self.canvas.winfo_width()-60), max(100,self.canvas.winfo_height()-60)])
        scale = min(available/(high-low))
        width, height = np.maximum(1, ((high-low)*scale).astype(int))
        xx, yy = np.meshgrid(np.linspace(low[0],high[0],width), np.linspace(high[1],low[1],height))
        fractional = np.stack([xx,yy],axis=-1) @ np.linalg.inv(lattice[:2,:2])
        mask = np.all((fractional>=0)&(fractional<=1),axis=-1)
        ij = np.clip((fractional*np.array(self.result.shape)).astype(int),0,np.array(self.result.shape)-1)
        pixels = self.rgb[ij[:,:,0],ij[:,:,1]].copy()
        pixels[~mask] = [17,17,17]
        ppm = f"P6\n{width} {height}\n255\n".encode()+pixels.tobytes()
        self.photo = tk.PhotoImage(data=ppm, format="PPM")
        ox, oy = (self.canvas.winfo_width()-width)//2, (self.canvas.winfo_height()-height)//2
        self.image_geometry = (ox,oy,width,height,low,high)
        self.canvas.delete("all")
        self.canvas.create_image(ox,oy,image=self.photo,anchor="nw")
        self.canvas.create_text(ox,oy+height+14,text="x / y (Å)   ·   dark → low    light → high    magenta → no crossing",fill=MUTED,anchor="w")

    def inspect(self,event):
        if self.rgb is None or not hasattr(self,"image_geometry"):
            return
        ox,oy,w,h,low,high = self.image_geometry
        point = np.array([low[0]+(event.x-ox)/w*(high[0]-low[0]), high[1]-(event.y-oy)/h*(high[1]-low[1])])
        frac = point @ np.linalg.inv(self.volume.lattice[:2,:2])
        if np.all((frac>=0)&(frac<1)):
            i,j = (frac*np.array(self.result.shape)).astype(int)
            self.readout.config(text=f"x {point[0]:.3f} Å    y {point[1]:.3f} Å    value {self.result[i,j]:.6g} {self.unit}")

    def export_data(self):
        if self.result is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".npz",filetypes=[("NumPy archive", "*.npz")])
        if path:
            np.savez_compressed(path, values=self.result, lattice=self.volume.lattice,
                                parameters=str(self.parameters), unit=self.unit)
            i,j = np.indices(self.result.shape)
            xy = (np.stack([i/self.result.shape[0],j/self.result.shape[1]],axis=-1) @ self.volume.lattice[:2,:2])
            np.savetxt(str(Path(path).with_suffix(".csv")), np.column_stack([xy.reshape(-1,2),self.result.ravel()]), delimiter=",",header=f"x_A,y_A,value_{self.unit}",comments="")
            self.status.config(text="EXPORTED  ·  NPZ + CSV")

    def export_image(self):
        if self.photo is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG", "*.png")])
        if path:
            self.photo.write(path,format="png")
            self.status.config(text="EXPORTED  ·  PNG")

if __name__ == "__main__":
    App().mainloop()
