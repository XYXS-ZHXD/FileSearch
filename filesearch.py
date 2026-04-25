"""
FileSearch - 便携式文件搜索工具
功能：搜索当前目录及子目录所有文件，支持模糊搜索、双击打开、右键菜单
不依赖 Everything，可放在 U 盘独立运行
"""

import os
import sys
import subprocess
import threading
import time
import fnmatch
import shutil
import ctypes
import ctypes.wintypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

# ── 获取程序所在目录（U 盘根目录）────────────────────────────────
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

# ── 文件大小格式化 ─────────────────────────────────────────────
def fmt_size(size):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != 'B' else f"{size} B"
        size /= 1024
    return f"{size:.1f} PB"

# ── 搜索核心 ───────────────────────────────────────────────────
def search_files(base_dir, keyword, result_callback, done_callback, cancel_flag):
    keyword_lower = keyword.lower()
    count = 0
    try:
        for root, dirs, files in os.walk(base_dir):
            if cancel_flag[0]:
                break
            # 跳过隐藏目录（速度优化）
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fname in files:
                if cancel_flag[0]:
                    break
                fname_lower = fname.lower()

                score = _match_score(fname_lower, keyword_lower)
                if score > 0:
                    fpath = os.path.join(root, fname)
                    try:
                        stat = os.stat(fpath)
                        size = stat.st_size
                        mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(stat.st_mtime))
                        rel_path = os.path.relpath(fpath, base_dir)
                        ext = Path(fname).suffix.lower() or '—'
                    except OSError:
                        continue
                    count += 1
                    result_callback((fname, ext, fmt_size(size), mtime, rel_path, fpath, score))
    except PermissionError:
        pass
    done_callback(count)


def _match_score(text, keyword):
    """弹性模糊匹配，返回匹配分数。
    分数 = 命中关键词数 / 总关键词数（0 表示不匹配）。
    单关键词命中返回 1.0。
    多关键词 OR 逻辑，命中越多分数越高。"""
    if not keyword:
        return 1.0  # 空关键词匹配所有
    parts = keyword.split()
    if not parts:
        return 1.0
    hits = sum(1 for p in parts if p in text)
    return hits / len(parts) if hits > 0 else 0.0

# ── 主界面 ─────────────────────────────────────────────────────
class FileSearchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FileSearch — 便携文件搜索")
        self.geometry("1000x620")
        self.minsize(700, 400)
        
        # 设置窗口图标
        self._set_icon()
        
        self._apply_theme()

        self._cancel_flag = [False]
        self._search_thread = None
        self._pending_rows = []
        self._flush_id = None
        self._all_results = []    # 缓存搜索结果（用于二次过滤）
        self._sort_col = None
        self._sort_rev = False

        self._build_ui()
        self._update_status(f"当前目录：{BASE_DIR}")

        # 启动后立即列出所有文件
        self.after(100, lambda: self._start_search(""))

    # ── 图标设置 ──────────────────────────────────────────────
    def _set_icon(self):
        """设置窗口图标
        
        查找顺序：
        1. PyInstaller 打包后的临时解压目录（_MEIPASS）
        2. 程序所在目录（BASE_DIR，便携版放置 icon.ico 的位置）
        """
        # PyInstaller 单文件模式：资源解压到 sys._MEIPASS
        candidate_dirs = []
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            candidate_dirs.append(sys._MEIPASS)
        candidate_dirs.append(BASE_DIR)

        for d in candidate_dirs:
            ico_path = os.path.join(d, "icon.ico")
            if os.path.exists(ico_path):
                try:
                    self.iconbitmap(ico_path)
                    return
                except Exception:
                    pass  # 继续尝试下一个

    # ── 主题 ──────────────────────────────────────────────────
    def _apply_theme(self):
        self.configure(bg="#1e1e2e")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#1e1e2e", foreground="#cdd6f4",
                        fieldbackground="#313244", font=("微软雅黑", 10))
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4")
        style.configure("TButton", background="#313244", foreground="#cdd6f4",
                        relief="flat", padding=6)
        style.map("TButton", background=[("active", "#45475a")])
        style.configure("Treeview", background="#181825", foreground="#cdd6f4",
                        fieldbackground="#181825", rowheight=24,
                        font=("微软雅黑", 10))
        style.configure("Treeview.Heading", background="#313244",
                        foreground="#89b4fa", relief="flat",
                        font=("微软雅黑", 10, "bold"))
        style.map("Treeview", background=[("selected", "#45475a")],
                  foreground=[("selected", "#cdd6f4")])
        style.configure("TScrollbar", background="#313244", troughcolor="#181825",
                        arrowcolor="#6c7086")
        style.configure("Status.TLabel", background="#11111b", foreground="#6c7086",
                        font=("微软雅黑", 9), padding=(8, 3))
        style.configure("Search.TEntry", fieldbackground="#313244",
                        foreground="#cdd6f4", insertcolor="#cdd6f4",
                        font=("微软雅黑", 12), padding=6)

    # ── 构建 UI ────────────────────────────────────────────────
    def _build_ui(self):
        # ── 顶部搜索栏
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Label(top, text="🔍", font=("", 14)).pack(side="left", padx=(0, 6))

        self._var_kw = tk.StringVar()
        self._var_kw.trace_add("write", self._on_kw_change)
        entry = ttk.Entry(top, textvariable=self._var_kw, style="Search.TEntry")
        entry.pack(side="left", fill="x", expand=True)
        entry.focus()
        entry.bind("<Escape>", lambda e: self._var_kw.set(""))

        self._btn_clear = ttk.Button(top, text="✕", width=3, command=lambda: self._var_kw.set(""))
        self._btn_clear.pack(side="left", padx=4)

        # ── 路径显示
        path_bar = ttk.Frame(self)
        path_bar.pack(fill="x", padx=12, pady=(0, 4))
        ttk.Label(path_bar, text="搜索目录：", foreground="#6c7086").pack(side="left")
        self._lbl_dir = ttk.Label(path_bar, text=BASE_DIR, foreground="#89b4fa")
        self._lbl_dir.pack(side="left")

        # ── 结果列表
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=12, pady=4)

        cols = ("name", "ext", "size", "mtime", "path")
        col_names = {"name": "文件名", "ext": "类型", "size": "大小", "mtime": "修改时间", "path": "相对路径"}
        col_widths = {"name": 280, "ext": 70, "size": 90, "mtime": 130, "path": 360}

        self._tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                  selectmode="extended")
        for c in cols:
            self._tree.heading(c, text=col_names[c],
                               command=lambda col=c: self._sort_by(col))
            self._tree.column(c, width=col_widths[c], minwidth=50)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        # 斑马纹
        self._tree.tag_configure("odd",  background="#181825")
        self._tree.tag_configure("even", background="#1e1e2e")

        # 双击打开
        self._tree.bind("<Double-1>", self._on_double_click)
        # 回车打开
        self._tree.bind("<Return>", self._on_double_click)
        # 右键菜单
        self._tree.bind("<Button-3>", self._on_right_click)

        # ── 状态栏
        self._lbl_status = ttk.Label(self, text="", style="Status.TLabel")
        self._lbl_status.pack(fill="x", side="bottom")

        # ── 右键菜单
        self._ctx_menu = tk.Menu(self, tearoff=0, bg="#313244", fg="#cdd6f4",
                                 activebackground="#45475a", activeforeground="#cdd6f4",
                                 relief="flat", font=("微软雅黑", 10))
        self._ctx_menu.add_command(label="📂 打开文件",              command=self._open_selected)
        self._ctx_menu.add_command(label="📁 打开所在文件夹",        command=self._open_folder)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="📋 复制文件名",            command=lambda: self._copy_field(0))
        self._ctx_menu.add_command(label="📋 复制完整路径",          command=self._copy_fullpath)
        self._ctx_menu.add_command(label="📋 复制相对路径",          command=lambda: self._copy_field(4))
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="📤 复制文件到剪贴板",      command=self._copy_file_to_clipboard)

    # ── 关键词变化 ────────────────────────────────────────────
    def _on_kw_change(self, *_):
        # 取消前一个延迟调用
        if hasattr(self, '_debounce_id') and self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(280, self._do_search)

    def _do_search(self):
        kw = self._var_kw.get().strip()
        self._start_search(kw)

    # ── 启动搜索 ──────────────────────────────────────────────
    def _start_search(self, keyword):
        # 取消上一次搜索
        self._cancel_flag[0] = True
        if self._flush_id:
            self.after_cancel(self._flush_id)
        # 清空列表
        self._tree.delete(*self._tree.get_children())
        self._all_results.clear()
        self._pending_rows.clear()
        self._update_status("搜索中…")

        self._cancel_flag = [False]
        self._search_thread = threading.Thread(
            target=search_files,
            args=(BASE_DIR, keyword,
                  self._on_result, self._on_done,
                  self._cancel_flag),
            daemon=True
        )
        self._search_thread.start()
        self._schedule_flush()

    # ── 接收结果（子线程回调）────────────────────────────────
    def _on_result(self, row):
        self._pending_rows.append(row)

    def _on_done(self, count):
        self.after(0, lambda: self._flush_rows(final=True, count=count))

    # ── 批量刷新到 Treeview ───────────────────────────────────
    def _schedule_flush(self):
        self._flush_id = self.after(150, self._flush_rows)

    def _flush_rows(self, final=False, count=None):
        rows = self._pending_rows[:]
        self._pending_rows.clear()

        # 收集新行并暂存（等搜索结束后统一排序）
        for row in rows:
            self._all_results.append(row)

        if not final:
            self._schedule_flush()
            # 期间也展示（追加到末尾）
            n = len(self._tree.get_children())
            for i, row in enumerate(rows):
                tag = "odd" if (n + i) % 2 else "even"
                self._tree.insert("", "end", iid=row[5],
                                  values=(row[0], row[1], row[2], row[3], row[4]),
                                  tags=(tag,))
        else:
            # 搜索完成，按评分降序重排
            if self._all_results:
                # row[6] = score
                sorted_results = sorted(self._all_results, key=lambda r: r[6], reverse=True)
                self._tree.delete(*self._tree.get_children())
                for i, row in enumerate(sorted_results):
                    tag = "odd" if i % 2 else "even"
                    self._tree.insert("", "end", iid=row[5],
                                      values=(row[0], row[1], row[2], row[3], row[4]),
                                      tags=(tag,))
            total = len(self._tree.get_children())
            self._update_status(f"共找到 {total} 个文件  |  目录：{BASE_DIR}")

    # ── 排序 ─────────────────────────────────────────────────
    def _sort_by(self, col):
        col_idx = {"name": 0, "ext": 1, "size": 2, "mtime": 3, "path": 4}
        idx = col_idx[col]
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False

        items = [(self._tree.set(iid, col), iid) for iid in self._tree.get_children()]

        # 大小列按数值排序
        if col == "size":
            def size_key(x):
                try:
                    num, unit = x[0].split()
                    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
                    return float(num) * mult.get(unit, 1)
                except Exception:
                    return 0
            items.sort(key=size_key, reverse=self._sort_rev)
        else:
            items.sort(key=lambda x: x[0].lower(), reverse=self._sort_rev)

        for i, (_, iid) in enumerate(items):
            self._tree.move(iid, "", i)
            tag = "odd" if i % 2 else "even"
            self._tree.item(iid, tags=(tag,))

    # ── 打开文件 ──────────────────────────────────────────────
    def _open_selected(self, event=None):
        sel = self._tree.selection()
        if not sel:
            return
        for iid in sel:
            fpath = iid  # iid 就是完整路径
            if os.path.exists(fpath):
                os.startfile(fpath)
            else:
                messagebox.showwarning("提示", f"文件不存在：\n{fpath}")

    def _on_double_click(self, event):
        self._open_selected()

    # ── 打开所在文件夹 ────────────────────────────────────────
    def _open_folder(self):
        sel = self._tree.selection()
        if not sel:
            return
        fpath = sel[0]
        folder = os.path.dirname(fpath)
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{fpath}"')
        else:
            os.startfile(folder)

    # ── 复制字段 ──────────────────────────────────────────────
    def _copy_field(self, idx):
        sel = self._tree.selection()
        if not sel:
            return
        texts = [self._tree.item(iid, "values")[idx] for iid in sel]
        self.clipboard_clear()
        self.clipboard_append("\n".join(texts))

    def _copy_fullpath(self):
        sel = self._tree.selection()
        if not sel:
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(sel))

    # ── 复制文件到剪贴板（纯 Win32 API，瞬间完成）─────────────
    def _copy_file_to_clipboard(self):
        sel = self._tree.selection()
        if not sel:
            return
        paths = [p for p in sel if os.path.exists(p)]
        if not paths:
            messagebox.showwarning("提示", "所选文件不存在。")
            return
        if sys.platform != "win32":
            messagebox.showinfo("提示", "此功能仅 Windows 支持。")
            return

        # 使用 ctypes.windll 的 kernel32/user32，并正确设置返回值类型
        k32 = ctypes.windll.kernel32
        u32 = ctypes.windll.user32

        # 定义函数签名，确保64位指针正确处理
        k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        k32.GlobalAlloc.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.restype = ctypes.c_int
        k32.GlobalFree.argtypes = [ctypes.c_void_p]
        k32.GlobalFree.restype = ctypes.c_void_p

        u32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        u32.FindWindowW.restype = ctypes.c_void_p
        u32.OpenClipboard.argtypes = [ctypes.c_void_p]
        u32.OpenClipboard.restype = ctypes.c_int
        u32.CloseClipboard.argtypes = []
        u32.CloseClipboard.restype = ctypes.c_int
        u32.EmptyClipboard.argtypes = []
        u32.EmptyClipboard.restype = ctypes.c_int
        u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        u32.SetClipboardData.restype = ctypes.c_void_p

        # 通过窗口标题找句柄
        hwnd = u32.FindWindowW(None, self.title())
        if not hwnd:
            hwnd = u32.GetForegroundWindow()

        CF_HDROP = 15
        GMEM_MOVEABLE = 0x0002
        GMEM_ZEROINIT = 0x0040

        # 构造 DROPFILES 结构 + 路径数据
        DROPFILES_SIZE = 20
        paths_wstr = "\0".join(paths) + "\0\0"
        paths_bytes = paths_wstr.encode("utf-16-le")
        buf_size = DROPFILES_SIZE + len(paths_bytes)

        hMem = k32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, buf_size)
        if not hMem:
            messagebox.showerror("错误", "内存分配失败")
            return

        ptr = k32.GlobalLock(hMem)
        if not ptr:
            k32.GlobalFree(hMem)
            messagebox.showerror("错误", "内存锁定失败")
            return

        try:
            # 写 DROPFILES 头部（pFiles 偏移 + fWide=1）
            ctypes.memset(ptr, 0, DROPFILES_SIZE)
            ctypes.c_uint32.from_address(ptr).value = DROPFILES_SIZE
            ctypes.c_uint32.from_address(ptr + 16).value = 1
            # 写路径
            ctypes.memmove(ptr + DROPFILES_SIZE, paths_bytes, len(paths_bytes))
            k32.GlobalUnlock(hMem)

            # 打开剪贴板 → 清空 → 写入
            ok = u32.OpenClipboard(hwnd)
            if not ok:
                ok = u32.OpenClipboard(ctypes.c_void_p(0))
            if not ok:
                messagebox.showerror("错误", "无法打开剪贴板")
                k32.GlobalFree(hMem)
                return

            u32.EmptyClipboard()
            u32.SetClipboardData(CF_HDROP, hMem)
            u32.CloseClipboard()
            self._update_status(f"已复制 {len(paths)} 个文件到剪贴板")
        except Exception as e:
            try:
                u32.CloseClipboard()
            except Exception:
                pass
            messagebox.showerror("错误", f"复制失败：{e}")

    # ── 右键菜单 ──────────────────────────────────────────────
    def _on_right_click(self, event):
        row = self._tree.identify_row(event.y)
        if row:
            if row not in self._tree.selection():
                self._tree.selection_set(row)
            self._ctx_menu.post(event.x_root, event.y_root)

    # ── 状态栏 ────────────────────────────────────────────────
    def _update_status(self, msg):
        self._lbl_status.config(text=msg)


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = FileSearchApp()
    app.mainloop()
