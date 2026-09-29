"""Tkinter GUI for Namer."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from namer.rename import (
    CaseMode,
    NumberPosition,
    RenameOptions,
    apply_plan,
    build_plan,
)


class NamerApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.master = master
        self.folder = tk.StringVar()
        self.remove_prefix = tk.BooleanVar(value=True)
        self.manual_prefix = tk.StringVar()
        self.add_prefix = tk.StringVar()
        self.case_mode = tk.StringVar(value=CaseMode.NONE.value)
        self.do_number = tk.BooleanVar(value=False)
        self.number_start = tk.IntVar(value=1)
        self.number_digits = tk.IntVar(value=3)
        self.number_sep = tk.StringVar(value="_")
        self.number_pos = tk.StringVar(value=NumberPosition.AFTER_STEM.value)
        self.recursive = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="フォルダを選択してください。")
        self._plan = None

        self._build()
        self.pack(fill=tk.BOTH, expand=True)

    def _build(self) -> None:
        # --- Folder row ---
        folder_row = ttk.Frame(self)
        folder_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(folder_row, text="対象フォルダ").pack(side=tk.LEFT)
        ttk.Entry(folder_row, textvariable=self.folder).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=8
        )
        ttk.Button(folder_row, text="参照…", command=self._pick_folder).pack(side=tk.LEFT)

        # --- Options ---
        opts = ttk.LabelFrame(self, text="リネームオプション", padding=10)
        opts.pack(fill=tk.X, pady=(0, 8))

        # Prefix remove
        pref = ttk.Frame(opts)
        pref.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(
            pref,
            text="共通接頭語を除去",
            variable=self.remove_prefix,
            command=self._refresh_preview,
        ).pack(side=tk.LEFT)
        ttk.Label(pref, text="手動指定（空なら自動検出）").pack(side=tk.LEFT, padx=(16, 4))
        ttk.Entry(pref, textvariable=self.manual_prefix, width=24).pack(side=tk.LEFT)
        self.manual_prefix.trace_add("write", lambda *_: self._refresh_preview())

        # Prefix add
        add = ttk.Frame(opts)
        add.pack(fill=tk.X, pady=2)
        ttk.Label(add, text="接頭語を追加").pack(side=tk.LEFT)
        ttk.Entry(add, textvariable=self.add_prefix, width=24).pack(side=tk.LEFT, padx=8)
        self.add_prefix.trace_add("write", lambda *_: self._refresh_preview())

        # Case
        case = ttk.Frame(opts)
        case.pack(fill=tk.X, pady=2)
        ttk.Label(case, text="大文字・小文字").pack(side=tk.LEFT)
        self._case_labels = {
            "変更しない": CaseMode.NONE,
            "すべて小文字 (lower)": CaseMode.LOWER,
            "すべて大文字 (upper)": CaseMode.UPPER,
            "単語先頭大文字 (title)": CaseMode.TITLE,
        }
        self.case_label = tk.StringVar(value="変更しない")
        case_box = ttk.Combobox(
            case,
            textvariable=self.case_label,
            values=list(self._case_labels.keys()),
            state="readonly",
            width=28,
        )
        case_box.pack(side=tk.LEFT, padx=8)
        case_box.bind("<<ComboboxSelected>>", lambda *_: self._on_case_change())

        # Numbering
        num = ttk.LabelFrame(opts, text="番号付け（拡張子の直前）", padding=8)
        num.pack(fill=tk.X, pady=(6, 0))
        ttk.Checkbutton(
            num,
            text="番号を振る",
            variable=self.do_number,
            command=self._refresh_preview,
        ).pack(anchor=tk.W)

        num_row = ttk.Frame(num)
        num_row.pack(fill=tk.X, pady=4)
        ttk.Label(num_row, text="開始").pack(side=tk.LEFT)
        ttk.Spinbox(
            num_row,
            from_=0,
            to=99999,
            textvariable=self.number_start,
            width=6,
            command=self._refresh_preview,
        ).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(num_row, text="桁数").pack(side=tk.LEFT)
        ttk.Spinbox(
            num_row,
            from_=1,
            to=10,
            textvariable=self.number_digits,
            width=4,
            command=self._refresh_preview,
        ).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(num_row, text="区切り").pack(side=tk.LEFT)
        ttk.Entry(num_row, textvariable=self.number_sep, width=4).pack(
            side=tk.LEFT, padx=(4, 12)
        )
        self.number_sep.trace_add("write", lambda *_: self._refresh_preview())
        ttk.Label(num_row, text="位置").pack(side=tk.LEFT)
        self._pos_labels = {
            "名前の後 (name_001.ext)": NumberPosition.AFTER_STEM,
            "名前の前 (001_name.ext)": NumberPosition.BEFORE_STEM,
        }
        self.pos_label = tk.StringVar(value="名前の後 (name_001.ext)")
        pos_box = ttk.Combobox(
            num_row,
            textvariable=self.pos_label,
            values=list(self._pos_labels.keys()),
            state="readonly",
            width=28,
        )
        pos_box.pack(side=tk.LEFT, padx=4)
        pos_box.bind("<<ComboboxSelected>>", lambda *_: self._on_pos_change())

        # Misc
        misc = ttk.Frame(opts)
        misc.pack(fill=tk.X, pady=(6, 0))
        ttk.Checkbutton(
            misc,
            text="サブフォルダも含める",
            variable=self.recursive,
            command=self._refresh_preview,
        ).pack(side=tk.LEFT)

        # --- Preview ---
        preview_frame = ttk.LabelFrame(self, text="プレビュー（変更前 → 変更後）", padding=8)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cols = ("before", "arrow", "after")
        self.tree = ttk.Treeview(
            preview_frame,
            columns=cols,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("before", text="変更前")
        self.tree.heading("arrow", text="")
        self.tree.heading("after", text="変更後")
        self.tree.column("before", width=280, anchor=tk.W)
        self.tree.column("arrow", width=40, anchor=tk.CENTER)
        self.tree.column("after", width=280, anchor=tk.W)

        scroll_y = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("changed", foreground="#0a5")
        self.tree.tag_configure("same", foreground="#888")
        self.tree.tag_configure("error", foreground="#c00")

        # --- Actions ---
        actions = ttk.Frame(self)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="プレビュー更新", command=self._refresh_preview).pack(
            side=tk.LEFT
        )
        ttk.Button(actions, text="リネーム実行", command=self._apply).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Label(actions, textvariable=self.status).pack(side=tk.LEFT, padx=8)

    def _pick_folder(self) -> None:
        path = filedialog.askdirectory(title="リネーム対象フォルダを選択")
        if path:
            self.folder.set(path)
            self._refresh_preview()

    def _on_case_change(self) -> None:
        mode = self._case_labels[self.case_label.get()]
        self.case_mode.set(mode.value)
        self._refresh_preview()

    def _on_pos_change(self) -> None:
        pos = self._pos_labels[self.pos_label.get()]
        self.number_pos.set(pos.value)
        self._refresh_preview()

    def _rename_options(self) -> RenameOptions:
        try:
            start = int(self.number_start.get())
        except (tk.TclError, ValueError):
            start = 1
        try:
            digits = int(self.number_digits.get())
        except (tk.TclError, ValueError):
            digits = 3
        return RenameOptions(
            remove_common_prefix=self.remove_prefix.get(),
            prefix_to_remove=self.manual_prefix.get(),
            add_prefix=self.add_prefix.get(),
            case_mode=CaseMode(self.case_mode.get()),
            number=self.do_number.get(),
            number_start=start,
            number_digits=max(1, digits),
            number_separator=self.number_sep.get(),
            number_position=NumberPosition(self.number_pos.get()),
        )

    def _refresh_preview(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        folder = Path(self.folder.get()) if self.folder.get() else None
        if not folder or not folder.is_dir():
            self.status.set("フォルダを選択してください。")
            self._plan = None
            return

        plan = build_plan(folder, self._rename_options(), recursive=self.recursive.get())
        self._plan = plan

        error_names = set()
        for err in plan.errors:
            # Highlight rows that appear in error messages by matching filenames later
            error_names.add(err)

        for src, dst in plan.items:
            changed = src.name != dst.name
            tag = "changed" if changed else "same"
            # Mark conflict targets
            if any(src.name in e or dst.name in e for e in plan.errors):
                tag = "error"
            self.tree.insert(
                "",
                tk.END,
                values=(src.name, "→", dst.name),
                tags=(tag,),
            )

        parts = [f"{len(plan.items)} 件"]
        parts.append(f"変更 {len(plan.changed)} 件")
        if plan.common_prefix_detected:
            parts.append(f"検出接頭語: 「{plan.common_prefix_detected}」")
        if plan.errors:
            parts.append(f"エラー {len(plan.errors)} 件")
        self.status.set(" / ".join(parts))

    def _apply(self) -> None:
        if self._plan is None:
            self._refresh_preview()
        plan = self._plan
        if plan is None:
            messagebox.showwarning("警告", "フォルダを選択してください。")
            return
        if plan.errors:
            messagebox.showerror(
                "エラー",
                "衝突や既存ファイルがあるため実行できません。\n\n"
                + "\n".join(plan.errors[:12]),
            )
            return
        if not plan.changed:
            messagebox.showinfo("情報", "変更対象がありません。")
            return

        if not messagebox.askyesno(
            "確認",
            f"{len(plan.changed)} 件のファイルをリネームします。よろしいですか？",
        ):
            return

        try:
            logs = apply_plan(plan)
        except OSError as exc:
            messagebox.showerror("失敗", f"リネーム中にエラーが発生しました:\n{exc}")
            self._refresh_preview()
            return
        except ValueError as exc:
            messagebox.showerror("失敗", str(exc))
            return

        messagebox.showinfo(
            "完了",
            f"{len(logs)} 件リネームしました。\n\n" + "\n".join(logs[:20])
            + ("\n…" if len(logs) > 20 else ""),
        )
        self._refresh_preview()


def run() -> None:
    root = tk.Tk()
    root.title("Namer — 一括リネーム")
    root.geometry("780x560")
    root.minsize(640, 440)

    # Prefer a readable theme on Windows
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")

    NamerApp(root)
    root.mainloop()
