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

    # --- Toolbar (No Run Button) ---
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

        def on_click():    #changed 
            if btn['state'] != 'disabled':
                command()

        btn.config(command=on_click)
        buttons.append(btn)
        return btn

    # Mode buttons
    btn_lexical = make_mode_button(toolbar, "Lexical", "#d0246f", "😊",
                                   lambda: compiler_logic.switch_mode("LEXICAL"))
    btn_syntax = make_mode_button(toolbar, "Syntax", "#ad46ff", "🙁",
                                  lambda: compiler_logic.switch_mode("SYNTAX"))
    btn_semantic = make_mode_button(toolbar, "Semantic", "#2b7fff", "😌",   
                                    lambda: compiler_logic.switch_mode("SEMANTIC"))
    btn_tac = make_mode_button(toolbar, "TAC", "#10a37f", "⚙",
                               lambda: compiler_logic.switch_mode("TAC"))

    btn_run = make_mode_button(toolbar, "Run", "#e67e22", "▶",
                               lambda: compiler_logic.run_all())
    
    # Added 02/10/2026: File menu dropdown button
    def show_file_menu():
        """Create and show file menu dropdown"""
        file_menu = tk.Menu(root, tearoff=False, bg="#2a2a3b", fg="white", font=("Consolas", 9))
        file_menu.add_command(label="📂 Open", command=compiler_logic.open_file)
        file_menu.add_command(label="💾 Save", command=compiler_logic.save_file)
        file_menu.add_command(label="💾 Save As", command=compiler_logic.save_file_as)
        # Display menu at cursor position
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
    body.pack(fill='both', expand=True)

    # outer_frame holds paned (left) + right_frame (right) via pack.
    # right_frame is NOT inside PanedWindow so pack/pack_forget is reliable.
    outer_frame = tk.Frame(body, bg="#121c31")
    outer_frame.pack(fill='both', expand=True, padx=5, pady=5)

    paned = tk.PanedWindow(outer_frame, orient=tk.HORIZONTAL, bg="#121c31", sashwidth=10, sashrelief=tk.FLAT, bd=0)
    paned.pack(side='left', fill='both', expand=True)

    # Left Side: Code + Console
    left_frame = tk.Frame(paned, bg="#1a263a")
    paned.add(left_frame, minsize=450)

    left_paned = tk.PanedWindow(left_frame, orient=tk.VERTICAL, sashwidth=8, bg="#1a263a")    
    left_paned.pack(fill='both', expand=True, padx=5, pady=5)           

    # Top pane: code editor
    code_container = tk.Frame(left_paned, bg="#1a263a", highlightbackground="#444444", highlightthickness=1)
    left_paned.add(code_container, minsize=300)            

    code_frame = tk.Frame(code_container, bg="#1a263a")    
    code_frame.pack(fill='both', expand=True)

    line_numbers = tk.Text(code_frame, width=3, padx=5, takefocus=0, border=0, background="#121a2f", fg="#888", state="disabled", font=("Consolas", 12))
    line_numbers.pack(side="left", fill="y")              

    code_scroll_frame = tk.Frame(code_frame, bg="#1a263a") 
    code_scroll_frame.pack(side="left", fill="both", expand=True)

    # Added 02/10/2026: Enable undo/redo with undo=True parameter

    code_input = tk.Text(code_scroll_frame, wrap='none', bg="#1a263a", fg="#f1f6f4", insertbackground='white', font=("Consolas", 12), bd=0, highlightthickness=0, undo=True, maxundo=-1)
    code_input.pack(side="left", fill="both", expand=True)

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


    # Synchronized Scrolling
    def sync_scroll(*args):
        line_numbers.yview(*args)
        code_input.yview(*args)

    code_scrollbar = tk.Scrollbar(code_scroll_frame, command=sync_scroll, width=12, bg="#1a263a", troughcolor="#121a2f", bd=0, highlightthickness=0)

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

    # --- Terminal changed by vien 02/19/2026 ---
    console_container = tk.Frame(left_paned, bg="#1a263a")
    left_paned.add(console_container, minsize=100)

    terminal_label = tk.Label(console_container, text="TERMINAL", font=("Consolas", 9, "bold"), bg="#121c31", fg="white", padx=10, pady=4, anchor='w')
    terminal_label.pack(fill='x', pady=(5, 2), padx=5)

    # Single terminal (used for lexical and syntax)
    console_output = tk.Text(console_container, bg="#1a263a", fg="#fbf8f8", font=("Consolas", 9), highlightbackground="#444444", highlightthickness=0)
    console_output.pack(fill='both', expand=True, pady=(0, 5), padx=5)

    # Split terminal (used for semantic only, hidden by default)
    terminal_split = tk.Frame(console_container, bg="#1a263a")

    error_frame = tk.Frame(terminal_split, bg="#1a263a")
    error_frame.pack(side="left", fill="both", expand=True, padx=(0, 2))
    tk.Label(error_frame, text="ERRORS", font=("Consolas", 8, "bold"), bg="#3a1a1a", fg="#ff6b6b", pady=2).pack(fill='x')
    console_errors = tk.Text(error_frame, bg="#1a263a", fg="#ff6b6b", font=("Consolas", 9), highlightbackground="#444444", highlightthickness=0)
    console_errors.pack(fill='both', expand=True)

    warning_frame = tk.Frame(terminal_split, bg="#1a263a")
    warning_frame.pack(side="right", fill="both", expand=True, padx=(2, 0))
    tk.Label(warning_frame, text="WARNINGS", font=("Consolas", 8, "bold"), bg="#1a2a1a", fg="#ffd93d", pady=2).pack(fill='x')
    console_warnings = tk.Text(warning_frame, bg="#1a263a", fg="#ffd93d", font=("Consolas", 9), highlightbackground="#444444", highlightthickness=0)
    console_warnings.pack(fill='both', expand=True)

    # --- Right side: Output Frame ---
    # right_frame is a child of outer_frame (not paned) so pack/pack_forget works reliably
    right_frame = tk.Frame(outer_frame, bg="#1a263a", relief="flat", highlightbackground="#777777", highlightthickness=1)
    # Start hidden; logic will pack it when needed
    # right_frame.pack(side='right', fill='both', width=320)

    analysis_header_frame = tk.Frame(right_frame, bg="#d0246f")
    analysis_header_frame.pack(fill='x')
    analysis_header_label = tk.Label(analysis_header_frame, text="Lexical Analysis", font=("Consolas", 11, "bold"), fg="white", bg="#d0246f", pady=8)
    analysis_header_label.pack(fill='x')

    analysis_output_frame = tk.Frame(right_frame, bg="#1a263a")
    analysis_output_frame.pack(fill='both', expand=True)

    # --- Bind UI components to logic ---
    compiler_logic.bind_components(
        code_input, console_output, line_numbers,
        analysis_header_frame, analysis_header_label, analysis_output_frame,
        paned_window=paned,
        right_panel=right_frame,
        console_errors=console_errors,
        console_warnings=console_warnings
    )

    compiler_logic.set_buttons(btn_lexical, btn_syntax, btn_semantic, btn_tac, btn_run)

    # Added 02/10/2026: Set root window reference for file dialogs
    compiler_logic.set_root_window(root)
    
    # Added 02/10/2026: Keyboard shortcuts for file operations
    root.bind('<Control-s>', lambda e: compiler_logic.save_file())  # Ctrl+S = Save
    root.bind('<Control-o>', lambda e: compiler_logic.open_file())  # Ctrl+O = Open
    root.bind('<Control-Shift-S>', lambda e: compiler_logic.save_file_as())  # Ctrl+Shift+S = Save As
    
    # Added 02/10/2026: Keyboard shortcuts for undo/redo
    root.bind('<Control-z>', lambda e: code_input.edit_undo())  # Ctrl+Z = Undo
    root.bind('<Control-y>', lambda e: code_input.edit_redo())  # Ctrl+Y = Redo

    # Start in Lexical mode by default
    compiler_logic.switch_mode("LEXICAL")

    root.mainloop()

if __name__ == "__main__":
    create_ui()