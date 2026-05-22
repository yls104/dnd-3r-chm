#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, sys, shutil, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def clean_html(content):
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'</?[a-z]\d*:[a-z][^>]*>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'</?[a-z]+\d*:[a-z]+[^>]*>', '', content, flags=re.IGNORECASE)

    def clean_tag(match):
        full_match = match.group(0)
        if re.match(r'<img\b', full_match, re.IGNORECASE):
            return full_match
        if re.match(r'<meta\b', full_match, re.IGNORECASE):
            return full_match
        if full_match.startswith('</'):
            return full_match
        tag_name_match = re.match(r'<(\w+)', full_match)
        if not tag_name_match:
            return full_match
        tag_name = tag_name_match.group(1).lower()
        inner = re.sub(r'^<\w+', '', full_match, count=1)
        if inner.endswith('/>'):
            inner = inner[:-2]
            closing = '/>'
        elif inner.endswith('>'):
            inner = inner[:-1]
            closing = '>'
        else:
            return full_match
        attr_kv_pattern = re.compile(
            r'(\w[\w-]*)'
            r'(?:\s*=\s*'
            r'(?:"[^"]*"|' + "'" + r'[^' + "'" + r']*' + "'" + r'|[^\s>]+)'
            r')?',
            re.UNICODE
        )
        kept_kv = []
        for m in attr_kv_pattern.finditer(inner):
            attr_name = m.group(1)
            attr_lower = attr_name.lower()
            if attr_lower in ('class', 'style', 'lang'):
                continue
            if attr_lower.startswith('mso-'):
                continue
            kept_kv.append(m.group(0).strip())
        new_inner = ' '.join(kept_kv)
        if new_inner:
            result = '<%s %s%s' % (tag_name, new_inner, closing)
        else:
            result = '<%s%s' % (tag_name, closing)
        return result

    content = re.sub(r'<(?:\w+[^>]*|/\w+[^>]*)>', clean_tag, content, flags=re.DOTALL)
    for _ in range(5):
        content = re.sub(r'<span>\s*</span>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<span>&nbsp;</span>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content


def process_file(filepath, backup=False):
    content = None
    encoding_used = None
    for enc in ('gb2312', 'gb18030', 'utf-8'):
        try:
            with open(filepath, 'r', encoding=enc, errors='strict') as f:
                content = f.read()
            encoding_used = enc
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if content is None:
        try:
            with open(filepath, 'r', encoding='gb18030', errors='replace') as f:
                content = f.read()
            encoding_used = 'gb18030'
        except Exception:
            return None
    original_size = len(content)
    cleaned = clean_html(content)
    cleaned_size = len(cleaned)
    if original_size == cleaned_size:
        return None
    if backup:
        backup_path = filepath + '.bak'
        if not os.path.exists(backup_path):
            shutil.copy2(filepath, backup_path)
    with open(filepath, 'w', encoding=encoding_used, errors='replace') as f:
        f.write(cleaned)
    return (original_size, cleaned_size)


class HTMLCleanerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HTML Cleaner - Word HTML \u6e05\u7406\u5de5\u5177")
        self.root.geometry("820x620")
        self.root.minsize(700, 500)
        self.file_list = []
        self.is_processing = False
        self.should_cancel = False
        self._build_ui()

    def _build_ui(self):
        btn_frame = ttk.Frame(self.root, padding=5)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="\u6dfb\u52a0\u6587\u4ef6", command=self.add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="\u6dfb\u52a0\u6587\u4ef6\u5939", command=self.add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="\u79fb\u9664\u9009\u4e2d", command=self.remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="\u6e05\u7a7a\u5217\u8868", command=self.clear_list).pack(side=tk.LEFT, padx=2)
        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(btn_frame, text="\u9884\u89c8\u7ed3\u679c", command=self.preview).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="\u5f00\u59cb\u6e05\u7406", command=self.start_clean).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="\u53d6\u6d88", command=self.cancel_clean).pack(side=tk.LEFT, padx=2)

        opt_frame = ttk.Frame(self.root, padding=(5, 0, 5, 5))
        opt_frame.pack(fill=tk.X)
        self.backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="\u6e05\u7406\u524d\u521b\u5efa .bak \u5907\u4efd", variable=self.backup_var).pack(side=tk.LEFT, padx=4)
        ttk.Label(opt_frame, text="  \u6587\u4ef6\u6269\u5c55\u540d:").pack(side=tk.LEFT)
        self.ext_var = tk.StringVar(value="htm,html")
        ttk.Entry(opt_frame, textvariable=self.ext_var, width=16).pack(side=tk.LEFT, padx=2)

        list_frame = ttk.Frame(self.root, padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("file", "size", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("file", text="\u6587\u4ef6\u8def\u5f84")
        self.tree.heading("size", text="\u5927\u5c0f")
        self.tree.heading("status", text="\u72b6\u6001")
        self.tree.column("file", width=520, minwidth=300)
        self.tree.column("size", width=80, minwidth=60, anchor=tk.E)
        self.tree.column("status", width=150, minwidth=80)
        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        bottom_frame = ttk.Frame(self.root, padding=5)
        bottom_frame.pack(fill=tk.X)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(bottom_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="\u5c31\u7eea - \u8bf7\u6dfb\u52a0\u6587\u4ef6\u6216\u6587\u4ef6\u5939")
        ttk.Label(bottom_frame, textvariable=self.status_var).pack(anchor=tk.W, pady=(4, 0))
        self.stats_var = tk.StringVar(value="")
        ttk.Label(bottom_frame, textvariable=self.stats_var, foreground="green").pack(anchor=tk.W)

    def _parse_extensions(self):
        ext_str = self.ext_var.get().strip()
        if not ext_str:
            return ['.htm', '.html']
        return ['.' + e.strip().lstrip('.') for e in ext_str.split(',') if e.strip()]

    def _add_files_to_list(self, paths):
        existing = set(self.file_list)
        exts = self._parse_extensions()
        added = 0
        for p in paths:
            p = os.path.abspath(p)
            if os.path.isfile(p):
                ext = os.path.splitext(p)[1].lower()
                if ext in exts and p not in existing:
                    self.file_list.append(p)
                    size = os.path.getsize(p)
                    self.tree.insert("", tk.END, iid=p, values=(p, self._fmt_size(size), "\u5f85\u5904\u7406"))
                    existing.add(p)
                    added += 1
            elif os.path.isdir(p):
                for root, dirs, filenames in os.walk(p):
                    for fn in filenames:
                        fp = os.path.join(root, fn)
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in exts and fp not in existing:
                            try:
                                size = os.path.getsize(fp)
                            except OSError:
                                continue
                            self.file_list.append(fp)
                            self.tree.insert("", tk.END, iid=fp, values=(fp, self._fmt_size(size), "\u5f85\u5904\u7406"))
                            existing.add(fp)
                            added += 1
        self._update_stats()
        return added

    @staticmethod
    def _fmt_size(n):
        if n < 1024:
            return "%d B" % n
        elif n < 1024 * 1024:
            return "%.1f KB" % (n / 1024)
        else:
            return "%.1f MB" % (n / (1024 * 1024))

    def _update_stats(self):
        self.stats_var.set("\u5171 %d \u4e2a\u6587\u4ef6" % len(self.file_list))

    def add_files(self):
        filetypes = [("HTML files", "*.htm *.html"), ("All files", "*.*")]
        paths = filedialog.askopenfilenames(title="\u9009\u62e9 HTML \u6587\u4ef6", filetypes=filetypes)
        if paths:
            n = self._add_files_to_list(paths)
            self.status_var.set("\u5df2\u6dfb\u52a0 %d \u4e2a\u6587\u4ef6" % n)

    def add_folder(self):
        folder = filedialog.askdirectory(title="\u9009\u62e9\u6587\u4ef6\u5939\uff08\u9012\u5f52\u641c\u7d22 HTML \u6587\u4ef6\uff09")
        if folder:
            n = self._add_files_to_list([folder])
            self.status_var.set("\u4ece\u6587\u4ef6\u5939\u6dfb\u52a0\u4e86 %d \u4e2a\u6587\u4ef6" % n)

    def remove_selected(self):
        selection = self.tree.selection()
        for item in selection:
            self.file_list.remove(item)
            self.tree.delete(item)
        self._update_stats()

    def clear_list(self):
        self.file_list.clear()
        self.tree.delete(*self.tree.get_children())
        self._update_stats()

    def _update_tree_item(self, item_id, status):
        try:
            vals = self.tree.item(item_id, "values")
            self.tree.item(item_id, values=(vals[0], vals[1], status))
        except tk.TclError:
            pass

    def preview(self):
        if self.is_processing:
            messagebox.showwarning("\u63d0\u793a", "\u6b63\u5728\u5904\u7406\u4e2d\uff0c\u8bf7\u7b49\u5f85\u5b8c\u6210")
            return
        if not self.file_list:
            messagebox.showinfo("\u63d0\u793a", "\u8bf7\u5148\u6dfb\u52a0\u6587\u4ef6")
            return
        self.is_processing = True
        self.should_cancel = False
        self.progress_var.set(0)
        threading.Thread(target=self._run_preview, daemon=True).start()

    def _run_preview(self):
        total = len(self.file_list)
        changed = 0
        total_original = 0
        total_cleaned = 0
        for i, fp in enumerate(self.file_list):
            if self.should_cancel:
                self.root.after(0, lambda: self.status_var.set("\u9884\u89c8\u5df2\u53d6\u6d88"))
                break
            self.root.after(0, lambda fp=fp: self._update_tree_item(fp, "\u9884\u89c8\u4e2d..."))
            self.root.after(0, lambda v=(i / total) * 100: self.progress_var.set(v))
            content = None
            for enc in ('gb2312', 'gb18030', 'utf-8'):
                try:
                    with open(fp, 'r', encoding=enc, errors='strict') as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            if content is None:
                try:
                    with open(fp, 'r', encoding='gb18030', errors='replace') as f:
                        content = f.read()
                except Exception:
                    self.root.after(0, lambda fp=fp: self._update_tree_item(fp, "\u65e0\u6cd5\u8bfb\u53d6"))
                    continue
            orig = len(content)
            cleaned = clean_html(content)
            cln = len(cleaned)
            if orig == cln:
                self.root.after(0, lambda fp=fp: self._update_tree_item(fp, "\u65e0\u9700\u6e05\u7406"))
            else:
                pct = (orig - cln) / orig * 100
                self.root.after(0, lambda fp=fp, p=pct: self._update_tree_item(fp, "\u53ef\u51cf\u5c11 %.1f%%" % p))
                changed += 1
                total_original += orig
                total_cleaned += cln
        self.root.after(0, lambda: self.progress_var.set(100))
        self.is_processing = False
        if total_original > 0:
            saved = total_original - total_cleaned
            self.root.after(0, lambda: self.status_var.set(
                "\u9884\u89c8\u5b8c\u6210: %d/%d \u4e2a\u6587\u4ef6\u53ef\u4f18\u5316, \u5171\u53ef\u51cf\u5c11 %s" % (
                    changed, total, self._fmt_size(saved))))
        else:
            self.root.after(0, lambda: self.status_var.set(
                "\u9884\u89c8\u5b8c\u6210: %d/%d \u4e2a\u6587\u4ef6\u9700\u8981\u6e05\u7406" % (changed, total)))

    def start_clean(self):
        if self.is_processing:
            messagebox.showwarning("\u63d0\u793a", "\u6b63\u5728\u5904\u7406\u4e2d\uff0c\u8bf7\u7b49\u5f85\u5b8c\u6210")
            return
        if not self.file_list:
            messagebox.showinfo("\u63d0\u793a", "\u8bf7\u5148\u6dfb\u52a0\u6587\u4ef6")
            return
        backup = self.backup_var.get()
        msg = "\u5373\u5c06\u6e05\u7406 %d \u4e2a\u6587\u4ef6\u3002\n" % len(self.file_list)
        if backup:
            msg += "\u5c06\u521b\u5efa .bak \u5907\u4efd\u6587\u4ef6\u3002\n"
        else:
            msg += "\u672a\u542f\u7528\u5907\u4efd\uff0c\u6e05\u7406\u540e\u65e0\u6cd5\u6062\u590d\uff01\n"
        msg += "\n\u786e\u5b9a\u7ee7\u7eed\uff1f"
        if not messagebox.askyesno("\u786e\u8ba4\u6e05\u7406", msg):
            return
        self.is_processing = True
        self.should_cancel = False
        self.progress_var.set(0)
        threading.Thread(target=self._run_clean, args=(backup,), daemon=True).start()

    def _run_clean(self, backup):
        total = len(self.file_list)
        changed = 0
        errors = 0
        total_original = 0
        total_cleaned = 0
        for i, fp in enumerate(self.file_list):
            if self.should_cancel:
                self.root.after(0, lambda: self.status_var.set("\u6e05\u7406\u5df2\u53d6\u6d88"))
                break
            self.root.after(0, lambda fp=fp: self._update_tree_item(fp, "\u6e05\u7406\u4e2d..."))
            self.root.after(0, lambda v=(i / total) * 100: self.progress_var.set(v))
            try:
                result = process_file(fp, backup=backup)
                if result is None:
                    self.root.after(0, lambda fp=fp: self._update_tree_item(fp, "\u65e0\u9700\u6e05\u7406/\u8df3\u8fc7"))
                else:
                    orig, cln = result
                    pct = (orig - cln) / orig * 100
                    self.root.after(0, lambda fp=fp, p=pct: self._update_tree_item(fp, "\u5df2\u6e05\u7406 (-%.1f%%)" % p))
                    changed += 1
                    total_original += orig
                    total_cleaned += cln
            except Exception as e:
                self.root.after(0, lambda fp=fp, e=str(e): self._update_tree_item(fp, "\u9519\u8bef: %s" % e[:30]))
                errors += 1
        self.root.after(0, lambda: self.progress_var.set(100))
        self.is_processing = False
        saved = total_original - total_cleaned
        self.root.after(0, lambda: self.status_var.set(
            "\u6e05\u7406\u5b8c\u6210: %d \u4e2a\u6587\u4ef6\u5df2\u4f18\u5316, %d \u4e2a\u9519\u8bef, \u5171\u51cf\u5c11 %s" % (
                changed, errors, self._fmt_size(saved))))

    def cancel_clean(self):
        if self.is_processing:
            self.should_cancel = True
            self.status_var.set("\u6b63\u5728\u53d6\u6d88...")


def main():
    root = tk.Tk()
    app = HTMLCleanerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
