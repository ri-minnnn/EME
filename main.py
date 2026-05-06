import tkinter as tk
from logic import EmeCompilerLogic


def create_ui():
    root = tk.Tk()
    root.title("EmE Compiler")

    # Responsive sizing
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = min(int(screen_width * 0.9), 1366)
    window_height = min(int(screen_height * 0.85), 768)
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    root.configure(bg="#1e1e1e")
    root.minsize(900, 600)

    compiler_logic = EmeCompilerLogic()

    # --- Toolbar ---
    toolbar = tk.Frame(root, bg="#111828", height=50)
    toolbar.pack(fill='x')

    buttons = []

    def make_mode_button(parent, text, color_active, emoji, command):
        frame = tk.Frame(parent, bg="#111828")
        frame.pack(side="left", padx=5)
        btn = tk.Button(frame, text=f"{emoji} {text}", font=("Consolas", 10, "bold"),
                        fg="white", bg="#2a2a3b", activebackground=color_active,
                        activeforeground="white", relief="flat", padx=15, pady=8,
                        highlightthickness=0, cursor="hand2")
        btn.pack(side="left")

        btn._default_bg = "#2a2a3b"
        btn._active_bg = color_active

        def on_click():
            if btn['state'] != 'disabled':
                command()

        btn.config(command=on_click)
        buttons.append(btn)
        return btn

    # Mode buttons — commands are rewired after frames are created below
    btn_lexical = make_mode_button(toolbar, "Lexical", "#d0246f", "😊",
                                   lambda: compiler_logic.switch_mode("LEXICAL"))
    btn_syntax = make_mode_button(toolbar, "Syntax", "#ad46ff", "🙁",
                                  lambda: compiler_logic.switch_mode("SYNTAX"))
    btn_semantic = make_mode_button(toolbar, "Semantic", "#2b7fff", "😌",
                                    lambda: compiler_logic.switch_mode("SEMANTIC"))
    btn_run = make_mode_button(toolbar, "Run", "#e67e22", "▶",
                               lambda: compiler_logic.run_all())

    # Added 02/10/2026: File menu dropdown button
    def show_file_menu():
        """Create and show file menu dropdown"""
        file_menu = tk.Menu(root, tearoff=False, bg="#2a2a3b", fg="white", font=("Consolas", 9))
        file_menu.add_command(label="📂 Open", command=compiler_logic.open_file)
        file_menu.add_command(label="💾 Save", command=compiler_logic.save_file)
        file_menu.add_command(label="💾 Save As", command=compiler_logic.save_file_as)
        file_menu.post(root.winfo_pointerx(), root.winfo_pointery())

    file_menu_frame = tk.Frame(toolbar, bg="#111828")
    file_menu_frame.pack(side="left", padx=10)
    btn_file_menu = tk.Button(file_menu_frame, text="📁", font=("Consolas", 10, "bold"),
                              fg="white", bg="#ad46ff", activebackground="#2b7fff",
                              activeforeground="white", relief="flat", padx=15, pady=8,
                              highlightthickness=0, cursor="hand2", command=show_file_menu)
    btn_file_menu.pack(side="left")

    # Logo on the right
    logo_frame = tk.Frame(toolbar, bg="#111828")
    logo_frame.pack(side='right', padx=10)
    tk.Label(logo_frame, text=":≫EmE", font=("Consolas", 16, "bold"), fg="white", bg="#111828").pack(anchor='e')
    tk.Label(logo_frame, text="LANGUAGE COMPILER :<", font=("Consolas", 7, "bold"), fg="#cccccc", bg="#111828").pack(anchor='e')

    # --- Body Layout ---
    body = tk.Frame(root, bg="#121c31")
    body.pack(fill=tk.BOTH, expand=True)

    # Main horizontal PanedWindow: left pane (editor + terminal) is always visible.
    # Right pane (TAC panel) is added/removed dynamically — only shown for the TAC tab.
    main_paned = tk.PanedWindow(body, orient=tk.HORIZONTAL, bg="#121c31",
                                sashwidth=10, sashrelief=tk.FLAT, bd=0)
    main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ── Left pane: code editor + terminal (always visible) ───────────────────
    left_frame = tk.Frame(main_paned, bg="#1a263a")
    main_paned.add(left_frame, minsize=450, stretch="always")

    left_paned = tk.PanedWindow(left_frame, orient=tk.VERTICAL, sashwidth=8, bg="#1a263a")
    left_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Top pane: code editor
    code_container = tk.Frame(left_paned, bg="#1a263a",
                              highlightbackground="#444444", highlightthickness=1)
    left_paned.add(code_container, minsize=300, stretch="always")

    code_frame = tk.Frame(code_container, bg="#1a263a")
    code_frame.pack(fill=tk.BOTH, expand=True)

    line_numbers = tk.Text(code_frame, width=3, padx=5, takefocus=0, border=0,
                           background="#121a2f", fg="#888", state="disabled",
                           font=("Consolas", 12))
    line_numbers.pack(side="left", fill="y")

    code_scroll_frame = tk.Frame(code_frame, bg="#1a263a")
    code_scroll_frame.pack(side="left", fill=tk.BOTH, expand=True)

    # Added 02/10/2026: Enable undo/redo with undo=True parameter
    code_input = tk.Text(code_scroll_frame, wrap='none', bg="#1a263a", fg="#f1f6f4",
                         insertbackground='white', font=("Consolas", 12), bd=0,
                         highlightthickness=0, undo=True, maxundo=-1)
    code_input.pack(side="left", fill=tk.BOTH, expand=True)

    # --- Custom tab and newline behavior ---
    def insert_tab(event):
        code_input.insert("insert", "    ")  # 4 spaces
        return "break"

    def auto_indent(event):
        # Get current line's indentation
        line_start = code_input.index("insert linestart")
        line_end = code_input.index("insert lineend")
        line_text = code_input.get(line_start, line_end)
        indent = ""
        for char in line_text:
            if char == " ":
                indent += char
            else:
                break
        code_input.insert("insert", "\n" + indent)
        return "break"

    code_input.bind("<Tab>", insert_tab)
    code_input.bind("<Return>", auto_indent)

    # --- Auto-pairing for ( and { ---
    def on_open_paren(event):
        sel = code_input.tag_ranges("sel")
        if sel:
            selected = code_input.get(sel[0], sel[1])
            code_input.delete(sel[0], sel[1])
            code_input.insert("insert", "(" + selected + ")")
        else:
            code_input.insert("insert", "()")
            code_input.mark_set("insert", "insert -1c")
        return "break"

    def on_open_brace(event):
        sel = code_input.tag_ranges("sel")
        if sel:
            selected = code_input.get(sel[0], sel[1])
            code_input.delete(sel[0], sel[1])
            code_input.insert("insert", "{" + selected + "}")
        else:
            code_input.insert("insert", "{}")
            code_input.mark_set("insert", "insert -1c")
        return "break"

    def on_close_paren(event):
        if code_input.get("insert", "insert +1c") == ")":
            code_input.mark_set("insert", "insert +1c")
            return "break"

    def on_close_brace(event):
        if code_input.get("insert", "insert +1c") == "}":
            code_input.mark_set("insert", "insert +1c")
            return "break"

    def on_backspace(event):
        _PAIRS = {"(": ")", "{": "}"}
        prev_char = code_input.get("insert -1c", "insert")
        next_char = code_input.get("insert", "insert +1c")
        if prev_char in _PAIRS and next_char == _PAIRS[prev_char]:
            code_input.delete("insert -1c", "insert +1c")
            return "break"

    code_input.bind("(", on_open_paren)
    code_input.bind("{", on_open_brace)
    code_input.bind(")", on_close_paren)
    code_input.bind("}", on_close_brace)
    code_input.bind("<BackSpace>", on_backspace)

    # Synchronized Scrolling
    def sync_scroll(*args):
        line_numbers.yview(*args)
        code_input.yview(*args)

    code_scrollbar = tk.Scrollbar(code_scroll_frame, command=sync_scroll, width=12,
                                  bg="#1a263a", troughcolor="#121a2f", bd=0, highlightthickness=0)

    def on_text_scroll(first, last):
        line_numbers.yview_moveto(first)
        first_f, last_f = float(first), float(last)
        if first_f <= 0 and last_f >= 1:
            code_scrollbar.pack_forget()
        else:
            code_scrollbar.pack(side="right", fill="y")
        code_scrollbar.set(first, last)

    code_input.config(yscrollcommand=on_text_scroll)

    # Set default code on startup
    default_code = "brain(){\n\n    closure 0; \n}"
    code_input.insert("1.0", default_code)

    # Bottom pane: terminal
    console_container = tk.Frame(left_paned, bg="#1a263a")
    left_paned.add(console_container, minsize=100, stretch="always")

    # ── Terminal zoom state ──────────────────────────────────────────────────
    _TERM_FONT      = "Consolas"
    _TERM_MIN_SZ    = 6
    _TERM_MAX_SZ    = 28
    _TERM_DEF_SZ    = 9
    terminal_font_size = [_TERM_DEF_SZ]   # mutable list so closures can write it

    def _apply_terminal_zoom():
        sz = terminal_font_size[0]
        for w in _term_widgets:
            try:
                w.config(font=(_TERM_FONT, sz))
            except tk.TclError:
                pass
        _zoom_lbl.config(text=f"{sz}pt")

    def _zoom_in(event=None):
        if terminal_font_size[0] < _TERM_MAX_SZ:
            terminal_font_size[0] += 1
            _apply_terminal_zoom()
        return "break"

    def _zoom_out(event=None):
        if terminal_font_size[0] > _TERM_MIN_SZ:
            terminal_font_size[0] -= 1
            _apply_terminal_zoom()
        return "break"

    def _zoom_reset(event=None):
        terminal_font_size[0] = _TERM_DEF_SZ
        _apply_terminal_zoom()
        return "break"

    def _on_ctrl_scroll(event):
        if event.delta > 0:
            _zoom_in()
        else:
            _zoom_out()
        return "break"

    # ── Terminal header row: label + zoom controls ───────────────────────────
    terminal_header = tk.Frame(console_container, bg="#121c31")
    terminal_header.pack(fill='x', pady=(5, 0), padx=5)

    tk.Label(terminal_header, text="TERMINAL", font=(_TERM_FONT, 9, "bold"),
             bg="#121c31", fg="white", padx=10, pady=4, anchor='w').pack(side="left")

    zoom_ctrl = tk.Frame(terminal_header, bg="#121c31")
    zoom_ctrl.pack(side="right", padx=6)

    _btn_cfg = dict(font=(_TERM_FONT, 9, "bold"), fg="white", bg="#2a2a3b",
                    activebackground="#444466", activeforeground="white",
                    relief="flat", bd=0, padx=6, pady=2,
                    highlightthickness=0, cursor="hand2")

    tk.Button(zoom_ctrl, text="−", command=_zoom_out, **_btn_cfg).pack(side="left")
    _zoom_lbl = tk.Label(zoom_ctrl, text=f"{_TERM_DEF_SZ}pt",
                         font=(_TERM_FONT, 8), fg="#aaaaaa", bg="#121c31",
                         width=4, anchor="center")
    _zoom_lbl.pack(side="left", padx=2)
    tk.Button(zoom_ctrl, text="+", command=_zoom_in,  **_btn_cfg).pack(side="left")
    tk.Button(zoom_ctrl, text="⊙", command=_zoom_reset, **_btn_cfg).pack(side="left", padx=(4, 0))

    # ── Single terminal (lexical / syntax / tac / run) ───────────────────────
    console_output = tk.Text(
        console_container, wrap=tk.WORD,
        bg="#1a263a", fg="#fbf8f8",
        font=(_TERM_FONT, _TERM_DEF_SZ),
        highlightbackground="#444444", highlightthickness=0,
    )
    console_output.pack(fill=tk.BOTH, expand=True, pady=(0, 5), padx=5)

    # ── Split terminal (semantic only, hidden by default) ────────────────────
    terminal_split = tk.Frame(console_container, bg="#1a263a")

    error_frame = tk.Frame(terminal_split, bg="#1a263a")
    error_frame.pack(side="left", fill="both", expand=True, padx=(0, 2))
    tk.Label(error_frame, text="ERRORS", font=(_TERM_FONT, 8, "bold"),
             bg="#3a1a1a", fg="#ff6b6b", pady=2).pack(fill='x')

    console_errors = tk.Text(
        error_frame, wrap='none',
        bg="#1a263a", fg="#ff6b6b",
        font=(_TERM_FONT, _TERM_DEF_SZ),
        highlightbackground="#444444", highlightthickness=0,
    )
    console_errors.pack(side="left", fill='both', expand=True)

    warning_frame = tk.Frame(terminal_split, bg="#1a263a")
    warning_frame.pack(side="right", fill="both", expand=True, padx=(2, 0))
    tk.Label(warning_frame, text="WARNINGS", font=(_TERM_FONT, 8, "bold"),
             bg="#1a2a1a", fg="#ffd93d", pady=2).pack(fill='x')

    console_warnings = tk.Text(
        warning_frame, wrap='none',
        bg="#1a263a", fg="#ffd93d",
        font=(_TERM_FONT, _TERM_DEF_SZ),
        highlightbackground="#444444", highlightthickness=0,
    )
    console_warnings.pack(side="left", fill='both', expand=True)

    # Collect all terminal text widgets so zoom affects them together
    _term_widgets = [console_output, console_errors, console_warnings]

    for _tw in _term_widgets:
        _tw.bind("<Control-MouseWheel>", _on_ctrl_scroll)
        _tw.bind("<Control-plus>",  _zoom_in)
        _tw.bind("<Control-equal>", _zoom_in)
        _tw.bind("<Control-minus>", _zoom_out)
        _tw.bind("<Control-0>",     _zoom_reset)

    # ── Right pane: TAC analysis panel (NOT added to main_paned yet) ─────────
    # Visibility is managed entirely from this file via _show_tac_panel /
    # _hide_tac_panel.  logic.py receives right_panel=None so it never tries
    # to pack/pack_forget this frame itself.
    right_frame = tk.Frame(main_paned, bg="#1a263a", relief="flat",
                           highlightbackground="#777777", highlightthickness=1)

    analysis_header_frame = tk.Frame(right_frame, bg="#d0246f")
    analysis_header_frame.pack(fill='x')
    analysis_header_label = tk.Label(analysis_header_frame, text="Lexical Analysis",
                                     font=("Consolas", 11, "bold"), fg="white",
                                     bg="#d0246f", pady=8)
    analysis_header_label.pack(fill='x')

    analysis_output_frame = tk.Frame(right_frame, bg="#1a263a")
    analysis_output_frame.pack(fill=tk.BOTH, expand=True)

    # ── TAC panel visibility helpers ─────────────────────────────────────────
    _tac_panel_visible = [False]

    def _show_tac_panel():
        if not _tac_panel_visible[0]:
            main_paned.add(right_frame, minsize=280, stretch="always")
            _tac_panel_visible[0] = True
        root.update_idletasks()

    def _hide_tac_panel():
        if _tac_panel_visible[0]:
            main_paned.forget(right_frame)
            _tac_panel_visible[0] = False
        root.update_idletasks()

    # ── Rewire button commands to control TAC panel visibility ───────────────
    # Each wrapper preserves the disabled-state guard from make_mode_button.
    def _wrap(btn, cmd):
        def on_click():
            if btn['state'] != 'disabled':
                cmd()
        return on_click

    def _on_lexical():
        compiler_logic.switch_mode("LEXICAL")
        _show_tac_panel()

    def _on_syntax():
        compiler_logic.switch_mode("SYNTAX")
        _hide_tac_panel()

    def _on_semantic():
        compiler_logic.switch_mode("SEMANTIC")
        _hide_tac_panel()

    def _on_run():
        compiler_logic.run_all()
        _hide_tac_panel()

    btn_lexical.config(command=_wrap(btn_lexical, _on_lexical))
    btn_syntax.config(command=_wrap(btn_syntax,   _on_syntax))
    btn_semantic.config(command=_wrap(btn_semantic, _on_semantic))
    btn_run.config(command=_wrap(btn_run, _on_run))

    # --- Bind UI components to logic ---
    # right_panel=None: logic.py must not pack/pack_forget right_frame;
    # visibility is managed exclusively by _show_tac_panel / _hide_tac_panel.
    compiler_logic.bind_components(
        code_input, console_output, line_numbers,
        analysis_header_frame, analysis_header_label, analysis_output_frame,
        paned_window=main_paned,
        right_panel=None,
        console_errors=console_errors,
        console_warnings=console_warnings
    )

    compiler_logic.set_buttons(btn_lexical, btn_syntax, btn_semantic, run=btn_run)

    # Added 02/10/2026: Set root window reference for file dialogs
    compiler_logic.set_root_window(root)

    # Added 02/10/2026: Keyboard shortcuts for file operations
    root.bind('<Control-s>', lambda e: compiler_logic.save_file())
    root.bind('<Control-o>', lambda e: compiler_logic.open_file())
    root.bind('<Control-Shift-S>', lambda e: compiler_logic.save_file_as())

    # Added 02/10/2026: Keyboard shortcuts for undo/redo
    root.bind('<Control-z>', lambda e: code_input.edit_undo())
    root.bind('<Control-y>', lambda e: code_input.edit_redo())

    # Start in Lexical mode by default (panel visible for lexical table)
    compiler_logic.switch_mode("LEXICAL")
    _show_tac_panel()

    root.mainloop()

if __name__ == "__main__":
    create_ui()
