#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
odt2sfb_gui.py — прост графичен интерфейс за odt2sfb.py.

Използва само стандартната библиотека (tkinter), за да може лесно да се
опакова в самостоятелен .exe с PyInstaller и да работи под Windows 11.

────────────────────────────────────────────────────────────────────────
Създаване на odt2sfb.exe (Windows):

    pip install pyinstaller
    pyinstaller --onefile --windowed --name odt2sfb odt2sfb_gui.py

  • Дръжте odt2sfb_gui.py и odt2sfb.py в една и съща папка при компилиране —
    PyInstaller автоматично включва odt2sfb.py, защото се импортира тук.
    (Ако по някаква причина не го хване: добавете --hidden-import odt2sfb.)
  • --windowed = без конзолен прозорец (нужно за GUI приложение).
  • Готовият файл е dist\\odt2sfb.exe
  • По желание с икона:  --icon app.ico
────────────────────────────────────────────────────────────────────────
"""

import argparse
import contextlib
import io
import os
import queue
import sys
import threading
import traceback

# --- по-остър текст под Windows (High-DPI); безопасно се прескача другаде ----
if sys.platform.startswith("win"):
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# --- намиране и импортиране на ядрото odt2sfb.py -----------------------------
# При компилиран .exe модулът е вграден; при стартиране от изходен код той е
# в същата папка като този файл.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import odt2sfb
except Exception as _imp_err:  # noqa: BLE001
    odt2sfb = None
    _IMPORT_ERROR = _imp_err
else:
    _IMPORT_ERROR = None


# ---------------------------------------------------------------------------
# Логика на конвертирането (без GUI — може да се тества самостоятелно)
# ---------------------------------------------------------------------------
def default_output_for(input_path):
    """Име на изхода по подразбиране: като входа, но с разширение .sfb."""
    return os.path.splitext(input_path)[0] + ".sfb"


def _same_file(a, b):
    try:
        if os.path.exists(a) and os.path.exists(b):
            return os.path.samefile(a, b)
    except OSError:
        pass
    return (os.path.normcase(os.path.abspath(a))
            == os.path.normcase(os.path.abspath(b)))


def run_conversion(input_path, output_path=None, author="", title="",
                   divider="* * *", markup="mixed", blank_as_divider=False,
                   info=""):
    """Извършва конвертирането и записва изхода.

    Връща (out_path, warnings_text). При проблем предизвиква изключение с
    разбираемо съобщение.
    """
    if odt2sfb is None:
        raise RuntimeError(
            "Не е намерен модулът odt2sfb.py. Поставете odt2sfb.py до тази "
            "програма.\nПодробност: %s" % _IMPORT_ERROR)

    input_path = (input_path or "").strip()
    if not input_path:
        raise ValueError("Изберете входен .odt файл.")
    if not os.path.isfile(input_path):
        raise ValueError("Входният файл не съществува:\n%s" % input_path)

    out_path = (output_path or "").strip() or default_output_for(input_path)

    # Изходът никога не бива да съвпадне с входа (за да не се презапише).
    if _same_file(out_path, input_path):
        raise ValueError(
            "Изходният файл съвпада с входния — това би презаписало "
            "оригинала.\nИзберете различно име за изхода.")

    info = (info or "").strip()
    if info and not os.path.isfile(info):
        raise ValueError("Файлът за информационния блок не съществува:\n%s" % info)

    args = argparse.Namespace(
        input=input_path,
        author=(author.strip() or None),
        title=(title.strip() or None),
        divider=(divider or "* * *"),
        markup=(markup if markup in ("mixed", "braces") else "mixed"),
        blank_as_divider=bool(blank_as_divider),
        info=(info or None),
    )

    # Прихващаме предупрежденията, които ядрото пише на stderr.
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result = odt2sfb.convert(input_path, args)

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(result)

    return out_path, buf.getvalue().strip()


# ---------------------------------------------------------------------------
# Графичен интерфейс
# ---------------------------------------------------------------------------
def launch_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext

    ODT_TYPES = [("OpenDocument текст", "*.odt"), ("Всички файлове", "*.*")]
    FSB_TYPES = [("SFB текст", "*.sfb"), ("SFB/FSB текст", "*.fsb"),
                 ("Всички файлове", "*.*")]

    root = tk.Tk()
    root.title("ODT → SFB конвертор")
    root.minsize(640, 520)
    try:
        ttk.Style().theme_use("vista" if sys.platform.startswith("win") else "clam")
    except tk.TclError:
        pass

    pad = dict(padx=8, pady=4)
    msgq = queue.Queue()
    busy = tk.BooleanVar(value=False)

    # --- променливи --------------------------------------------------------
    v_in = tk.StringVar()
    v_out = tk.StringVar()
    v_author = tk.StringVar()
    v_title = tk.StringVar()
    v_divider = tk.StringVar(value="* * *")
    v_markup = tk.StringVar(value="mixed")
    v_blank = tk.BooleanVar(value=False)
    v_info = tk.StringVar()

    main = ttk.Frame(root, padding=10)
    main.pack(fill="both", expand=True)
    main.columnconfigure(1, weight=1)

    # --- вход --------------------------------------------------------------
    ttk.Label(main, text="Входен .odt файл:").grid(row=0, column=0, sticky="w", **pad)
    e_in = ttk.Entry(main, textvariable=v_in)
    e_in.grid(row=0, column=1, sticky="ew", **pad)

    def browse_in():
        p = filedialog.askopenfilename(title="Изберете .odt файл",
                                       filetypes=ODT_TYPES)
        if p:
            v_in.set(p)
            if not v_out.get().strip():
                v_out.set(default_output_for(p))
    ttk.Button(main, text="Избери…", command=browse_in).grid(row=0, column=2, **pad)

    # --- изход -------------------------------------------------------------
    ttk.Label(main, text="Изходен .sfb файл:").grid(row=1, column=0, sticky="w", **pad)
    e_out = ttk.Entry(main, textvariable=v_out)
    e_out.grid(row=1, column=1, sticky="ew", **pad)

    def browse_out():
        init = v_out.get().strip() or (
            default_output_for(v_in.get().strip()) if v_in.get().strip() else "")
        p = filedialog.asksaveasfilename(
            title="Запази като", defaultextension=".sfb", filetypes=FSB_TYPES,
            initialfile=os.path.basename(init) if init else "",
            initialdir=os.path.dirname(init) if init else "")
        if p:
            v_out.set(p)
    ttk.Button(main, text="Избери…", command=browse_out).grid(row=1, column=2, **pad)

    ttk.Label(main, text="(празно = като входа, но .sfb)",
              foreground="#666").grid(row=2, column=1, sticky="w", padx=8)

    # --- опции -------------------------------------------------------------
    opt = ttk.LabelFrame(main, text="Опции", padding=8)
    opt.grid(row=3, column=0, columnspan=3, sticky="ew", **pad)
    opt.columnconfigure(1, weight=1)

    ttk.Label(opt, text="Автор:").grid(row=0, column=0, sticky="w", **pad)
    ttk.Entry(opt, textvariable=v_author).grid(row=0, column=1, columnspan=2,
                                               sticky="ew", **pad)
    ttk.Label(opt, text="(незадължително; замества | блока)",
              foreground="#666").grid(row=0, column=3, sticky="w", padx=6)

    ttk.Label(opt, text="Заглавие:").grid(row=1, column=0, sticky="w", **pad)
    ttk.Entry(opt, textvariable=v_title).grid(row=1, column=1, columnspan=2,
                                              sticky="ew", **pad)

    ttk.Label(opt, text="Разделител:").grid(row=2, column=0, sticky="w", **pad)
    ttk.Combobox(opt, textvariable=v_divider, values=["* * *", "****"],
                 width=12).grid(row=2, column=1, sticky="w", **pad)

    ttk.Label(opt, text="Маркиране:").grid(row=3, column=0, sticky="w", **pad)
    ttk.Combobox(opt, textvariable=v_markup, values=["mixed", "braces"],
                 state="readonly", width=12).grid(row=3, column=1, sticky="w", **pad)
    ttk.Label(opt, text="mixed: _курсив_ / __получер__ ; braces: {e}/{s}",
              foreground="#666").grid(row=3, column=2, columnspan=2,
                                      sticky="w", padx=6)

    ttk.Checkbutton(opt, text="Празните параграфи са сюжетни разделители",
                    variable=v_blank).grid(row=4, column=0, columnspan=3,
                                           sticky="w", **pad)

    ttk.Label(opt, text="Инфо файл:").grid(row=5, column=0, sticky="w", **pad)
    ttk.Entry(opt, textvariable=v_info).grid(row=5, column=1, sticky="ew", **pad)

    def browse_info():
        p = filedialog.askopenfilename(title="Текстов файл за I> блок",
                                       filetypes=[("Текстови файлове", "*.txt"),
                                                  ("Всички файлове", "*.*")])
        if p:
            v_info.set(p)
    ttk.Button(opt, text="Избери…", command=browse_info).grid(row=5, column=2, **pad)

    # --- бутон и прогрес ---------------------------------------------------
    actions = ttk.Frame(main)
    actions.grid(row=4, column=0, columnspan=3, sticky="ew", **pad)
    actions.columnconfigure(1, weight=1)

    btn_convert = ttk.Button(actions, text="Конвертирай")
    btn_convert.grid(row=0, column=0, padx=4)

    progress = ttk.Progressbar(actions, mode="indeterminate")
    progress.grid(row=0, column=1, sticky="ew", padx=8)

    btn_folder = ttk.Button(actions, text="Отвори папката", state="disabled")
    btn_folder.grid(row=0, column=2, padx=4)

    # --- дневник -----------------------------------------------------------
    ttk.Label(main, text="Съобщения:").grid(row=5, column=0, sticky="w", padx=8)
    log = scrolledtext.ScrolledText(main, height=10, state="disabled", wrap="word")
    log.grid(row=6, column=0, columnspan=3, sticky="nsew", **pad)
    main.rowconfigure(6, weight=1)

    last_output = {"path": None}

    def log_write(text, tag=None):
        log.configure(state="normal")
        log.insert("end", text + "\n", tag)
        log.see("end")
        log.configure(state="disabled")

    log.tag_configure("err", foreground="#b00020")
    log.tag_configure("ok", foreground="#0a7d00")
    log.tag_configure("warn", foreground="#9a6700")

    # --- изпълнение в отделна нишка ----------------------------------------
    def worker(params):
        try:
            out_path, warnings = run_conversion(**params)
            msgq.put(("warn", warnings))
            msgq.put(("done", out_path))
        except Exception as e:  # noqa: BLE001
            msgq.put(("error", str(e)))
            msgq.put(("trace", traceback.format_exc()))

    def start():
        if busy.get():
            return
        params = dict(
            input_path=v_in.get(), output_path=v_out.get(),
            author=v_author.get(), title=v_title.get(),
            divider=v_divider.get(), markup=v_markup.get(),
            blank_as_divider=v_blank.get(), info=v_info.get())
        busy.set(True)
        btn_convert.configure(state="disabled")
        btn_folder.configure(state="disabled")
        progress.start(12)
        log_write("Конвертиране…")
        threading.Thread(target=worker, args=(params,), daemon=True).start()

    btn_convert.configure(command=start)

    def open_folder():
        p = last_output["path"]
        if not p:
            return
        folder = os.path.dirname(os.path.abspath(p))
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # noqa: S606
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", folder])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:  # noqa: BLE001
            messagebox.showwarning("Отваряне на папка", str(e))
    btn_folder.configure(command=open_folder)

    def finish():
        busy.set(False)
        progress.stop()
        btn_convert.configure(state="normal")

    def poll():
        try:
            while True:
                kind, payload = msgq.get_nowait()
                if kind == "warn":
                    if payload:
                        for line in payload.splitlines():
                            log_write(line, "warn")
                elif kind == "done":
                    last_output["path"] = payload
                    btn_folder.configure(state="normal")
                    log_write("Готово → %s" % payload, "ok")
                    finish()
                    messagebox.showinfo("Готово",
                                        "Файлът е създаден:\n%s" % payload)
                elif kind == "error":
                    log_write("ГРЕШКА: %s" % payload, "err")
                    finish()
                    messagebox.showerror("Грешка", payload)
                elif kind == "trace":
                    # техническа подробност — само в дневника
                    pass
        except queue.Empty:
            pass
        root.after(100, poll)

    # предупреждение при липсващо ядро
    if odt2sfb is None:
        log_write("ГРЕШКА: не е намерен odt2sfb.py до програмата.", "err")
        log_write(str(_IMPORT_ERROR), "err")
        btn_convert.configure(state="disabled")

    # Хук за автоматичен тест (затваря прозореца) — не влияе на нормалната работа.
    if os.environ.get("ODT2SFB_GUI_SELFTEST"):
        root.after(int(os.environ.get("ODT2SFB_GUI_SELFTEST","400") or "400"), root.destroy)

    root.after(100, poll)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
