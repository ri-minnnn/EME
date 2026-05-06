from lexical import perform_lexical_analysis
from syntax import perform_syntax_analysis
from semantic import perform_semantic_analysis
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from terminal import Terminal
import re
import os

class EmeCompilerLogic:
    def __init__(self):
        self.code_input = None
        self.console_output = None
        self.line_numbers = None
        self.current_mode = "LEXICAL"

        self.analysis_header_label = None
        self.analysis_header_frame = None
        self.analysis_output_frame = None
        self.terminal = None
        self.warning_terminal = None
        self.console_errors = None
        self.console_warnings = None
        
        self.warning_line_numbers = set()  # Track lines with warnings
        self.protected_ranges = {}  # Track protected warning indicator characters {line_no: True}

        self.paned_window = None
        self.right_panel = None

        self.btn_lexical = None
        self.btn_syntax = None
        self.btn_semantic = None
        self.parse_tree = None
        self.btn_tac = None
        self.btn_run = None
        
        # File operations state variables
        self.current_file_path = None
        self.root_window = None
        
        # Zoom functionality - ONLY for code editor
        self.current_font_size = 12  # Default font size for editor
        self.min_font_size = 8
        self.max_font_size = 24
        self.zoom_factor = 1.2  # 20% zoom increment
        
        # Console font size (smaller than editor, not affected by zoom)
        self.console_font_size = 10  # Reduced from 12 to 10 for smaller terminal
        
        # Color configuration
        self.COLORS = {
            "data_type": "#fd7e7e",
            "literal": "#f69aee",
            "symbol": "#ffe599",
            "identifier": "#FFFFFF",
            "keyword": "#68f4e9",
            "fixed": "#93c47d",
            "comment": "#a4a8ff",
            "default": "#CCCCCC",
            "error": "#FF0000"
        }
        
        # Define all the tokens
        self.DATA_TYPES = ["int", "char", "bool", "str", "float", "void"]
        self.RESERVED_WORDS = ["spill", "read", "hope", "despair", "core", "memory", 
                              "default", "desire", "while", "do", "over", "down", 
                              "brain", "closure", "echo", "heart"]
        self.FIXED_KEYWORDS = ["fixed"]  
        self.SYMBOLS = ["+", "-", "*", "/", "//", "%", "**", "++", "--", "+=", "-=", 
                       "*=", "/=", "//=", "%=", "**=", "&&", "||", "!", ">", "<", ">=", 
                       "<=", "==", "!=", "=", ".", "{", "}", "[", "]", ";", ":", ",", 
                       "(", ")", "⎵"]
        
        # Define token patterns for syntax highlighting
        self.token_patterns = [
            # String literals first (to avoid interference with comments)
            (r'"[^"]*"', 'literal'),
            # Multi-line comments - MUST COME BEFORE single-line comments
            (r':>>[\s\S]*?:<', 'comment', re.DOTALL),
            # Single line comments - FIXED: changed pattern to work everywhere
            (r':>[^\n]*', 'comment'),
            # Data types
            (r'\b(int|char|bool|str|float|void)\b', 'data_type'),
            (r'\b(' + '|'.join(self.FIXED_KEYWORDS) + r')\b', 'fixed'),
            # Reserved words
            (r'\b(spill|read|hope|despair|core|memory|default|desire|while|do|over|down|brain|closure|echo|heart)\b', 'keyword'),
            # Numeric literals
            (r'\b\d+(\.\d+)?\b', 'literal'),
            # Boolean literals
            (r'\b(trust|betray)\b', 'literal'),
            # Character literals
            (r"'.'", 'literal'),
            # Complex symbols
            (r'\+\+|--|\+=|-=|\*=|/=|//=|%=|\*\*=|&&|\|\||==|!=|>=|<=|//|\*\*', 'symbol'),
            # Simple symbols
            (r'[=+\-*/%><.!;:,(){}\[\]\⎵]', 'symbol'),
            # Identifiers
            (r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', 'identifier'),
        ]
        # Debug flag for highlighting
        self.debug_highlight = False

    def bind_components(self, code_input, console_output, line_numbers,
                        analysis_header_frame=None, analysis_header_label=None,
                        analysis_output_frame=None, paned_window=None, right_panel=None,
                        console_errors=None, console_warnings=None):
        self.code_input = code_input
        self.console_output = console_output
        self.console_errors = console_errors
        self.console_warnings = console_warnings
        self.line_numbers = line_numbers
        self.analysis_header_frame = analysis_header_frame
        self.analysis_header_label = analysis_header_label
        self.analysis_output_frame = analysis_output_frame
        self.terminal = Terminal(console_output)
        self.warning_terminal = Terminal(console_warnings) if console_warnings else None
        self.paned_window = paned_window
        self.right_panel = right_panel

        # Configure code input with syntax highlighting tags
        self.configure_editor_tags()

        # Bind auto-closing, syntax highlighting, and bracket pair highlighting to the code input
        self.code_input.bind("<KeyRelease>", self.handle_key_release)
        self.code_input.bind("<ButtonRelease>", self.highlight_matching_pair)
        # Only highlight on click, not on motion or focus
        # Mouse wheel for line updates and Ctrl+MouseWheel for zoom
        self.code_input.bind("<MouseWheel>", lambda e: self.update_line_numbers())
        self.code_input.bind("<Control-MouseWheel>", self.on_mousewheel_zoom)
        # Protect warning indicators from deletion
        self.code_input.bind("<Delete>", self.protect_warning_on_delete)
        self.code_input.bind("<BackSpace>", self.protect_warning_on_backspace)
    def highlight_matching_pair(self, event=None):
        """Highlight the matching bracket/quote if the cursor is next to one."""
        if not self.code_input:
            return

        # Remove previous highlight
        self.code_input.tag_remove("pair_highlight", "1.0", tk.END)

        pairs = {'{': '}', '[': ']', '(': ')', '"': '"', "'": "'"}
        openers = pairs.keys()
        closers = pairs.values()

        # Get cursor position and surrounding characters safely
        cursor = self.code_input.index(tk.INSERT)
        try:
            prev_char = self.code_input.get(f"{cursor} -1c")
        except tk.TclError:
            prev_char = ""
        try:
            next_char = self.code_input.get(cursor)
        except tk.TclError:
            next_char = ""

        # Debug output
        if getattr(self, 'debug_highlight', False):
            try:
                print(f"highlight called prev='{prev_char}' next='{next_char}'")
            except Exception:
                pass

        # Check if cursor is after an opener or before a closer
        if prev_char in openers:
            # start search from the opener character
            opener_pos = f"{cursor} -1c"
            match_index = self.find_matching_bracket(opener_pos, prev_char, pairs[prev_char], forward=True)
            if match_index:
                if getattr(self, 'debug_highlight', False):
                    print(f"found match at {match_index}")
                self.code_input.tag_add("pair_highlight", f"{cursor} -1c", cursor)
                self.code_input.tag_add("pair_highlight", match_index, f"{match_index} +1c")
        elif next_char in closers:
            # Find the opener for this closer
            opener = [k for k, v in pairs.items() if v == next_char][0]
            # start search from the closer character at cursor
            closer_pos = cursor
            match_index = self.find_matching_bracket(closer_pos, opener, next_char, forward=False)
            if match_index:
                if getattr(self, 'debug_highlight', False):
                    print(f"found match at {match_index}")
                self.code_input.tag_add("pair_highlight", cursor, f"{cursor} +1c")
                self.code_input.tag_add("pair_highlight", match_index, f"{match_index} +1c")

        # Style for highlight (simple background + foreground)
        self.code_input.tag_configure("pair_highlight", background="#7EACB5", foreground="#000000")
        # Ensure highlight is above other tags
        try:
            self.code_input.tag_raise("pair_highlight")
        except Exception:
            pass

    def find_matching_bracket(self, index, opener, closer, forward=True):
        """Find the index of the matching bracket/quote from the given index."""
        stack = 0
        if forward:
            # Search forward
            pos = self.code_input.index(index)
            while True:
                char = self.code_input.get(pos)
                if char == opener:
                    stack += 1
                elif char == closer:
                    stack -= 1
                    if stack == 0:
                        return pos
                if self.code_input.compare(pos, ">=", tk.END):
                    break
                pos = self.code_input.index(f"{pos} +1c")
        else:
            # Search backward starting at provided index
            pos = self.code_input.index(index)
            while True:
                try:
                    char = self.code_input.get(pos)
                except tk.TclError:
                    break
                if char == closer:
                    stack += 1
                elif char == opener:
                    stack -= 1
                    if stack == 0:
                        return pos
                if self.code_input.compare(pos, "<=", "1.0"):
                    break
                pos = self.code_input.index(f"{pos} -1c")
        return None

        # Set initial fonts - terminal will be smaller than editor
        self.update_editor_fonts()  # Editor font size
        self.set_terminal_size()    # Set smaller terminal font
        self.update_line_numbers()

        # Apply initial syntax highlighting
        self.highlight_syntax()

    def handle_key_release(self, event):
        """KeyRelease handler: perform auto-close, update UI."""
        try:
            self.handle_autoclose(event)
        except Exception:
            pass
        self.update_line_numbers()
        self.highlight_syntax()
        # Do not call highlight_matching_pair here; only on click
        # Remove any highlight when typing
        self.code_input.tag_remove("pair_highlight", "1.0", tk.END)


    def handle_autoclose(self, event):
        """Insert matching closing characters for paired openers (on KeyPress only)."""
        if not self.code_input:
            return

        ch = event.char
        if not ch:
            return

        pairs = {'{': '}', '[': ']', '(': ')', '"': '"', "'": "'"}

        # Only trigger on typing an opener
        if ch not in pairs and ch != '>':
            return

        # If there's a selection and user typed an opener, wrap the selection
        sel_ranges = self.code_input.tag_ranges("sel")
        if sel_ranges and ch in pairs:
            start = sel_ranges[0]
            end = sel_ranges[1]
            sel_text = self.code_input.get(start, end)
            # Replace selection with wrapped text
            self.code_input.delete(start, end)
            self.code_input.insert(start, ch + sel_text + pairs[ch])
            # Place cursor after the wrapped selection
            self.code_input.mark_set(tk.INSERT, f"{start} + {len(ch + sel_text)}c")
            return "break"

        # Handle the simple single-character openers
        if ch in pairs:
            # If the next character is already the intended closer, don't insert another
            next_char = self.code_input.get("insert", "insert +1c")
            if next_char == pairs[ch]:
                return

            # For quotes, if char before the newly-inserted char is a backslash, it's escaped -> don't autoclose
            if ch in ('"', "'"):
                try:
                    before_escape = self.code_input.get("insert -2c", "insert -1c")
                    if before_escape == "\\":
                        return
                except tk.TclError:
                    # If indices out of range, ignore escape check
                    pass

            # Insert the closing char and move the cursor to remain between the pair
            self.code_input.insert(tk.INSERT, pairs[ch])
            self.code_input.mark_set(tk.INSERT, "insert -1c")
            return "break"

        # Handle custom multi-line comment opener ':>>' which should auto-insert closing ':<'
        # Trigger when the user types the third character '>' completing ':>>'
        if ch == '>':
            try:
                last3 = self.code_input.get("insert -3c", "insert")
            except tk.TclError:
                last3 = ''

            if last3 == ':>>':
                # If closing already present, do nothing
                next_two = self.code_input.get("insert", "insert +2c")
                if next_two.startswith(':<'):
                    return

                # Insert closing ':<' and position cursor between opener and closer
                self.code_input.insert(tk.INSERT, ':<')
                self.code_input.mark_set(tk.INSERT, 'insert -2c')
                return "break"

    def set_terminal_size(self):
        """Set the terminal/console to a smaller font size than the editor"""
        if self.console_output:
            # Set console to smaller fixed font size
            console_font_spec = ("Consolas", self.console_font_size)
            self.console_output.configure(font=console_font_spec)

    def configure_editor_tags(self):
        """Configure all the color tags for the text editor ONLY"""
        if not self.code_input:
            return
            
        # Create tags for each token type with current editor font
        editor_font_spec = ("Consolas", self.current_font_size)
        for token_type, color in self.COLORS.items():
            tag_name = f"highlight_{token_type}"
            self.code_input.tag_configure(tag_name, foreground=color, font=editor_font_spec)
        
        # Add error indicator tag (red underline only)
        self.code_input.tag_configure("error_indicator", foreground="#FF0000", underline=True, font=editor_font_spec)
        
        # Add warning circle tag - small foreground circle in warning color (matching warning terminal)
        small_font_spec = ("Consolas", max(self.current_font_size - 2, 8))
        self.code_input.tag_configure("warning_circle", foreground="#ffd93d", font=small_font_spec)

    def highlight_syntax(self):
        """Apply syntax highlighting to the code editor ONLY"""
        if not self.code_input:
            return
            
        # Save current cursor position
        cursor_pos = self.code_input.index(tk.INSERT)
        
        # Get all text
        code = self.code_input.get("1.0", tk.END)
        
        # Remove all existing tags (except selection and pair_highlight)
        for tag in self.code_input.tag_names():
            if tag not in ("sel", "pair_highlight"):
                self.code_input.tag_remove(tag, "1.0", tk.END)
        
        # Apply highlighting for each pattern
        for pattern_info in self.token_patterns:
            if len(pattern_info) == 3:
                pattern, token_type, flags = pattern_info
            else:
                pattern, token_type = pattern_info
                flags = 0
        
            try:
                # For multi-line comments, use DOTALL flag
                if flags == re.DOTALL:
                    for match in re.finditer(pattern, code, flags):
                        start = f"1.0+{match.start()}c"
                        end = f"1.0+{match.end()}c"
                        tag_name = f"highlight_{token_type}"
                        self.code_input.tag_add(tag_name, start, end)
                else:
                    # For other patterns, process the entire text at once
                    for match in re.finditer(pattern, code, flags):
                        start = f"1.0+{match.start()}c"
                        end = f"1.0+{match.end()}c"
                        
                        # Check if this range is already colored
                        existing_tags = self.code_input.tag_names(start)
                        if any(tag.startswith("highlight_") for tag in existing_tags):
                            continue
                        
                        tag_name = f"highlight_{token_type}"
                        self.code_input.tag_add(tag_name, start, end)
            except re.error as e:
                # Skip invalid patterns
                continue
        
        # Restore cursor position
        self.code_input.mark_set(tk.INSERT, cursor_pos)

    def zoom_in(self):
        """Increase font size for zoom in - ONLY affects editor"""
        if self.current_font_size < self.max_font_size:
            self.current_font_size = min(self.current_font_size * self.zoom_factor, self.max_font_size)
            self.current_font_size = int(self.current_font_size)
            self.update_editor_fonts()  # Only update editor, not terminal
        return "break"

    def zoom_out(self):
        """Decrease font size for zoom out - ONLY affects editor"""
        if self.current_font_size > self.min_font_size:
            self.current_font_size = max(self.current_font_size / self.zoom_factor, self.min_font_size)
            self.current_font_size = int(self.current_font_size)
            self.update_editor_fonts()  # Only update editor, not terminal
        return "break"

    def on_mousewheel_zoom(self, event):
        """Handle Ctrl+MouseWheel zooming - ONLY affects editor"""
        if event.delta > 0 or event.num == 4:  # Scroll up
            self.zoom_in()
        else:  # Scroll down
            self.zoom_out()
        return "break"

    def update_editor_fonts(self):
        """Update font sizes for editor ONLY - terminal stays fixed at smaller size"""
        editor_font_spec = ("Consolas", self.current_font_size)
        
        # Update code editor font ONLY
        self.code_input.configure(font=editor_font_spec)
        
        # Update line numbers font ONLY
        if self.line_numbers:
            self.line_numbers.configure(font=editor_font_spec)
        
        # Terminal font stays at its smaller fixed size
        # Already set in set_terminal_size() method
        
        # Update syntax highlighting tags with editor font
        self.configure_editor_tags()
        
        # Update line numbers display
        self.update_line_numbers()
        
        # Reapply syntax highlighting with new font
        self.highlight_syntax()

    def set_root_window(self, root):
        """Set reference to root window for file dialogs"""
        self.root_window = root

    def save_file(self):
        """Save current code to file. If no file path exists, prompts Save As dialog"""
        if self.current_file_path is None:
            self.save_file_as()
        else:
            self._write_to_file(self.current_file_path)

    def save_file_as(self):
        """Open Save As dialog to save code to a new file"""
        if not self.root_window:
            messagebox.showerror("Error", "Root window not set")
            return
        
        file_path = filedialog.asksaveasfilename(
            parent=self.root_window,
            defaultextension=".eme",
            filetypes=[("EmE Source Files", "*.eme"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        
        if file_path:
            self.current_file_path = file_path
            self._write_to_file(file_path)

    def open_file(self):
        """Open file dialog to load code from a file"""
        if not self.root_window:
            messagebox.showerror("Error", "Root window not set")
            return
        
        file_path = filedialog.askopenfilename(
            parent=self.root_window,
            filetypes=[("EmE Source Files", "*.eme"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        
        if file_path:
            self._read_from_file(file_path)

    def _write_to_file(self, file_path):
        """Helper method to write code to file and show confirmation"""
        try:
            code = self.code_input.get("1.0", "end-1c")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            self.current_file_path = file_path
            file_name = os.path.basename(file_path)
            messagebox.showinfo("Success", f"File '{file_name}' saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")

    def _read_from_file(self, file_path):
        """Helper method to read code from file and load into editor"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            self.code_input.config(state="normal")
            self.code_input.delete("1.0", "end")
            self.code_input.insert("1.0", code)
            
            self.current_file_path = file_path
            file_name = os.path.basename(file_path)
            messagebox.showinfo("Success", f"File '{file_name}' opened successfully!")
            
            # Apply syntax highlighting after loading
            self.highlight_syntax()
            
            # Trigger analysis update
            self.analyze_code()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")

    def set_buttons(self, lex, syn, sem, tac=None, run=None):
        self.btn_lexical  = lex
        self.btn_syntax   = syn
        self.btn_semantic = sem
        self.btn_tac      = tac
        self.btn_run      = run
        self.update_button_states(False, False)

    def update_button_states(self, lexical_ok, syntax_ok, semantic_ok=True):
        if not self.btn_syntax or not self.btn_semantic:
            return

        # Syntax requires lexical to pass
        if lexical_ok:
            self.btn_syntax.config(state="normal", fg="white")
        else:
            self.btn_syntax.config(state="disabled", fg="#555555", bg="#1a1a1a")

        # Semantic requires lexical + syntax to pass
        if lexical_ok and syntax_ok:
            self.btn_semantic.config(state="normal", fg="white")
        else:
            self.btn_semantic.config(state="disabled", fg="#555555", bg="#1a1a1a")

        # TAC requires all 3 phases to pass
        if self.btn_tac:
            if lexical_ok and syntax_ok and semantic_ok:
                self.btn_tac.config(state="normal", fg="white")
            else:
                self.btn_tac.config(state="disabled", fg="#555555", bg="#1a1a1a")

        # Run is ALWAYS enabled regardless of errors
        if self.btn_run:
            self.btn_run.config(state="normal", fg="white")


    def update_line_numbers(self):
        if not self.code_input or not self.line_numbers:
            return
        total_lines = int(self.code_input.index('end-1c').split('.')[0])
        
        # Calculate width needed: digits + space + bullet symbol
        num_digits = len(str(total_lines))
        has_warnings = len(self.warning_line_numbers) > 0
        extra_width = 3 if has_warnings else 1  # 1 for space, 2 more for " ●"
        required_width = num_digits + extra_width
        
        # Set the width with a small buffer
        self.line_numbers.config(width=required_width + 1)
        
        lines_text = ""
        for i in range(1, total_lines + 1):
            if i in self.warning_line_numbers:
                lines_text += str(i) + " ●"
            else:
                lines_text += str(i)
            if i < total_lines:
                lines_text += "\n"
        self.line_numbers.config(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", lines_text)
        self.line_numbers.yview_moveto(self.code_input.yview()[0])
        self.line_numbers.config(state="disabled")

    def log_colored_message(self, widget, message, color="#cccccc"):
        """Log a message to a text widget with specified color"""
        if not widget:
            return
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", message)
        # Create and apply color tag
        widget.tag_configure("colored", foreground=color)
        widget.tag_add("colored", "1.0", "end")
        widget.config(state="disabled")

    def underline_lexical_errors(self, lex_errors):
        """Add red underlines to lexical error tokens in the code"""
        if not self.code_input or not lex_errors:
            return
        
        for lex, token_type, line, col in lex_errors:
            try:
                # Find the token in the code and underline it
                line_str = f"{line}.0"
                token_start = f"{line}.{col - 1}"
                token_end = f"{line}.{col - 1 + len(lex)}"
                self.code_input.tag_add("error_indicator", token_start, token_end)
            except:
                pass

    def clear_error_indicators(self):
        """Remove all error indicators from the code editor"""
        if self.code_input:
            self.code_input.tag_remove("error_indicator", "1.0", tk.END)
            self.code_input.tag_remove("warning_circle", "1.0", tk.END)
        self.warning_line_numbers.clear()
        self.protected_ranges.clear()
        self.update_line_numbers()

    def protect_warning_on_delete(self, event):
        """Prevent deletion of warning indicators with Delete key"""
        if not self.code_input:
            return "break"
        
        # Get cursor position
        cursor_pos = self.code_input.index("insert")
        line_no = int(cursor_pos.split('.')[0])
        col = int(cursor_pos.split('.')[1])
        
        # Check if this line has a warning indicator at position 0
        if line_no in self.protected_ranges and col == 0:
            # Check if the character at cursor is the warning dot
            if self.code_input.get(f"{line_no}.0", f"{line_no}.1") == "●":
                return "break"  # Prevent deletion
        
        return None  # Allow normal deletion

    def protect_warning_on_backspace(self, event):
        """Prevent deletion of warning indicators with Backspace key"""
        if not self.code_input:
            return "break"
        
        # Get cursor position
        cursor_pos = self.code_input.index("insert")
        line_no = int(cursor_pos.split('.')[0])
        col = int(cursor_pos.split('.')[1])
        
        # Check if trying to backspace a warning indicator
        if line_no in self.protected_ranges and col == 1:
            # Check if the character before cursor is the warning dot
            if self.code_input.get(f"{line_no}.0", f"{line_no}.1") == "●":
                return "break"  # Prevent deletion
        
        return None  # Allow normal deletion

    def add_error_indicator(self, line, col):
        """Add a visual error indicator at the specified line and column"""
        if not self.code_input:
            return
        
        try:
            # Get the line content
            line_start = f"{line}.0"
            line_end = f"{line}.end"
            line_content = self.code_input.get(line_start, line_end)
            
            if not line_content or col < 1:
                return
            
            # Convert 1-based column to 0-based index
            col_idx = col - 1
            
            if col_idx >= len(line_content):
                col_idx = len(line_content) - 1
            
            # Get the starting character
            start_char = line_content[col_idx]
            
            # Determine token end based on character type
            token_end = col_idx + 1
            
            # If it's an alphanumeric or underscore (identifier or number)
            if start_char.isalnum() or start_char == '_':
                while token_end < len(line_content) and (line_content[token_end].isalnum() or line_content[token_end] == '_'):
                    token_end += 1
            # If it's a symbol or operator
            else:
                # For multi-character operators like //, +=, etc., check if next char continues the operator
                while token_end < len(line_content) and not (line_content[token_end].isspace() or line_content[token_end].isalnum() or line_content[token_end] == '_'):
                    token_end += 1
            
            # Apply the error tag only to the identified token
            self.code_input.tag_add("error_indicator", f"{line}.{col_idx}", f"{line}.{token_end}")
        except Exception as ex:
            # Fallback: just mark the single character at the column
            try:
                self.code_input.tag_add("error_indicator", f"{line}.{col - 1}", f"{line}.{col}")
            except:
                pass


    def analyze_code(self, show_error_indicators=False):
        code = self.code_input.get("1.0", "end-1c")

        # Clear previous error indicators
        self.clear_error_indicators()


        # Update syntax highlighting
        self.highlight_syntax()

        # 1. Background Checks
        lexemes = perform_lexical_analysis(code, self.terminal)
        lex_errors = [t for t in lexemes if t[1] in ["UNKNOWN", "ERR"] or "INVALID" in t[1]]
        lexical_passed = len(lex_errors) == 0 and len(code.strip()) > 0

        syntax_passed = False
        syntax_report = ""
        syntax_error_line = None
        syntax_error_col = None
        
        if lexical_passed:
            ignore = ["space", "newline", "tab", "ocmt", "mcmt"]
            filtered = [t for t in lexemes if t[1] not in ignore]
            try:
                syntax_passed, syntax_report, parse_tree = perform_syntax_analysis(filtered, self.terminal)
                self.parse_tree = parse_tree
            except Exception as e:
                syntax_passed = False
                syntax_report = str(e)
                
            # Try to extract line and col from error message (both from report and exception)
            error_str = syntax_report if syntax_report else str(e) if 'e' in locals() else ""
            if "Line" in error_str and "Column" in error_str and show_error_indicators:
                # Don't show indicator if error is $ (end of input - means something is missing, not wrong)
                if "BUT FOUND '$'" not in error_str:
                    try:
                        # Extract using regex to handle various formats
                        match = re.search(r'Line\s*(\d+)\s*Column\s*(\d+)', error_str)
                        if match:
                            syntax_error_line = int(match.group(1))
                            syntax_error_col = int(match.group(2))
                            self.add_error_indicator(syntax_error_line, syntax_error_col)
                    except:
                        pass

        # Semantic pass state — determined after semantic phase runs below
        # We do a quick pre-check here so buttons reflect state immediately;
        # the full semantic result is updated at the end of the semantic block.
        self.update_button_states(lexical_passed, syntax_passed)

        # 2. MODE GUARD: If current mode is no longer valid, force back to Lexical
        if self.current_mode == "SYNTAX" and not lexical_passed:
            self.switch_mode("LEXICAL")
            return 
        
        if self.current_mode == "SEMANTIC" and (not lexical_passed or not syntax_passed):
            self.switch_mode("LEXICAL")
            return
        
        if self.current_mode == "TAC" and (not lexical_passed or not syntax_passed):
            self.switch_mode("LEXICAL")
            return

        # 3. Clear Right Panel
        if self.analysis_output_frame:
            for widget in self.analysis_output_frame.winfo_children():
                widget.destroy()

        # 4. Display Results
        if self.current_mode == "LEXICAL":
            self.display_lexical(lexemes)
            if not lexical_passed and len(code.strip()) > 0:
                error_msg = "\n".join(f"Lexical Error: line {l} col {c} {t} '{lex}'" for lex, t, l, c in lex_errors)
                self.log_colored_message(self.console_output, error_msg, "#ff6b6b")  
                self.underline_lexical_errors(lex_errors)
            elif len(code.strip()) > 0:
                self.log_colored_message(self.console_output, "No lexical errors found.", "#ff6b6b")  

        elif self.current_mode == "SYNTAX":
            self.terminal.clear()
            if syntax_report:
                self.log_colored_message(self.console_output, syntax_report, "#ff6b6b")  
            else:
                self.log_colored_message(self.console_output, "No syntax errors.", "#ff6b6b")  

        elif self.current_mode == "SEMANTIC":
            try:
                self.terminal.clear()
                if self.warning_terminal:
                    self.warning_terminal.clear()

                # Route errors to left panel, warnings to right panel
                class SplitTerminal:
                    def __init__(self, error_t, warning_t):
                        self.error_t = error_t
                        self.warning_t = warning_t if warning_t else error_t
                    def log(self, msg):
                        if msg.startswith("WARNING"):
                            self.warning_t.log(msg)
                        else:
                            self.error_t.log(msg)
                    def clear(self):
                        self.error_t.clear()
                        if self.warning_t != self.error_t:
                            self.warning_t.clear()

                error_terminal = Terminal(self.console_errors) if self.console_errors else self.terminal
                split_terminal = SplitTerminal(error_terminal, self.warning_terminal)
                perform_semantic_analysis(lexemes, split_terminal, parse_tree)
                
                # Clear previous warning line numbers
                self.warning_line_numbers.clear()
                
                # Parse warnings from warning console and collect line numbers
                if self.console_warnings:
                    warning_content = self.console_warnings.get("1.0", tk.END)
                    for line in warning_content.split("\n"):
                        match = re.search(r"at line (\d+)", line)
                        if match and "WARNING" in line:
                            warning_line_no = int(match.group(1))
                            self.warning_line_numbers.add(warning_line_no)
                
                # Update line numbers to show warning indicators
                self.update_line_numbers()
                
                # Parse terminal output for error lines - read from the console where errors were logged
                error_console = self.console_errors if self.console_errors else self.console_output
                terminal_content = error_console.get("1.0", tk.END)
                semantic_has_errors = False
                for line in terminal_content.split("\n"):
                    # Look for errors with line numbers - entire line gets underlined (excluding indentation)
                    match = re.search(r"at line (\d+)", line)
                    if match and "Semantic Error" in line:
                        semantic_has_errors = True
                        error_line_no = int(match.group(1))
                        # Changed on 2026-02-19: Skip leading whitespace when underlining error lines
                        line_start = f"{error_line_no}.0"
                        line_end = f"{error_line_no}.end"
                        line_content = self.code_input.get(line_start, line_end)
                        
                        # Find first non-whitespace character
                        first_non_ws = 0
                        for char in line_content:
                            if char == ' ' or char == '\t':
                                first_non_ws += 1
                            else:
                                break
                        
                        # Underline only from first non-whitespace to end
                        if first_non_ws < len(line_content):
                            error_start = f"{error_line_no}.{first_non_ws}"
                            self.code_input.tag_add("error_indicator", error_start, line_end)
                        else:
                            # Line is all whitespace, underline the whole thing
                            self.code_input.tag_add("error_indicator", line_start, line_end)
                
                # Update TAC button based on whether semantic passed
                semantic_passed = not semantic_has_errors
                self.update_button_states(lexical_passed, syntax_passed, semantic_passed)

                # Check if there were any errors - if not, show success message in grey
                if self.console_errors and self.console_errors.get("1.0", tk.END).strip() == "":
                    self.log_colored_message(self.console_errors, "No semantic errors.", "#ff6b6b")  # Red
            except Exception as e:
                self.terminal.log(str(e))

        
        elif self.current_mode == "TAC":
            try:
                from tac_walker import generate_tac

                if not self.parse_tree:
                    self.log_colored_message(
                        self.console_output,
                        "TAC Error: No parse tree available. Run syntax analysis first.",
                        "#ff6b6b"
                    )
                    return

                # generate_tac expects the parse tree dict directly
                walker = generate_tac(self.parse_tree)
                

                # display in right panel
                self._display_tac(walker.gen.quads)

                # show success in terminal
                self.log_colored_message(
                    self.console_output,
                    f"TAC generation successful.",
                    "#10a37f"
                )

            except Exception as e:
                import traceback
                traceback.print_exc()
                self.log_colored_message(
                    self.console_output,
                    f"TAC Error: {str(e)}",
                    "#ff6b6b"
                )
        
    def display_lexical(self, lexemes):
        if not self.analysis_output_frame: return
        
        # Added 02/10/2026: Create container frame for Treeview and scrollbars
        tree_container = tk.Frame(self.analysis_output_frame, bg="#1a263a")
        tree_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        tree = ttk.Treeview(tree_container, columns=("Lexeme", "Token"), show="headings", height=16)
        tree.pack(side="left", fill="both", expand=True)
        
        # Added 02/10/2026: Create vertical scrollbar
        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=tree.yview)
        vsb.pack(side="right", fill="y")
        tree.configure(yscrollcommand=vsb.set)
        
        tree.heading("Lexeme", text="Lexeme")
        tree.heading("Token", text="Token")
        
        # Added 02/10/2026: Set columns with word wrapping at 30 characters
        tree.column("Lexeme", anchor="center", width=250, minwidth=150)
        tree.column("Token", anchor="center", width=150, minwidth=100)

        style = ttk.Style()
        style.theme_use("default")
        # Added 02/10/2026: Increased rowheight to accommodate wrapped text
        style.configure("Treeview", background="#1a263a", foreground="white", fieldbackground="#1a263a", rowheight=60, font=("Consolas", 10))
        style.configure("Treeview.Heading", background="#ad46ff", foreground="white", font=("Consolas", 10, "bold"))

        # Added 02/10/2026: Helper function to wrap text at 30 characters
        def wrap_text(text, char_limit=30):
            """Wrap text to multiple lines at character limit"""
            if len(str(text)) <= char_limit:
                return str(text)
            
            text_str = str(text)
            lines = []
            for i in range(0, len(text_str), char_limit):
                lines.append(text_str[i:i+char_limit])
            return "\n".join(lines)

        for lex, token, _, _ in lexemes:
            if token == "UNKNOWN": 
                continue
            
            color = self.COLORS["default"]
            
            if lex in self.DATA_TYPES:
                color = self.COLORS["data_type"]
            elif lex in ["trust", "betray"] or token in ["intlit", "charlit", "strlit", "floatlit"]:
                color = self.COLORS["literal"]
            elif lex in self.RESERVED_WORDS:
                color = self.COLORS["keyword"]
            elif lex in self.FIXED_KEYWORDS:
                color = self.COLORS["fixed"]
            elif lex in self.SYMBOLS or token in ["OP", "SYM"]:
                color = self.COLORS["symbol"]
            elif token == "ID":
                color = self.COLORS["identifier"]
            elif token in ["comment", "ocmt", "mcmt"] or lex in [":>", ":>>", ":<"]:
                color = self.COLORS["comment"]
            elif token == "ERR":
                color = self.COLORS["error"]
            
            # Added 02/10/2026: Wrap long lexemes across multiple lines
            wrapped_lex = wrap_text(lex, char_limit=30)
            
            tree.insert("", "end", values=(wrapped_lex, token), tags=(token,))
            tree.tag_configure(token, foreground=color)

    def _display_tac(self, quads):
        if not self.analysis_output_frame:
            return

        for widget in self.analysis_output_frame.winfo_children():
            widget.destroy()

        from tkinter import ttk
        tree_container = tk.Frame(self.analysis_output_frame, bg="#1a263a")
        tree_container.pack(fill="both", expand=True, padx=5, pady=5)

        tree = ttk.Treeview(tree_container,
                            columns=("#", "OP", "ARG1", "ARG2", "RESULT"),
                            show="headings", height=16)
        tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=tree.yview)
        vsb.pack(side="right", fill="y")
        tree.configure(yscrollcommand=vsb.set)

        for col, width in [("#", 50), ("OP", 120), ("ARG1", 120), ("ARG2", 120), ("RESULT", 120)]:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=width, minwidth=50)

        style = ttk.Style()
        style.configure("Treeview",
                        background="#1a263a", foreground="white",
                        fieldbackground="#1a263a", rowheight=30,
                        font=("Consolas", 10))
        style.configure("Treeview.Heading",
                        background="#10a37f", foreground="white",
                        font=("Consolas", 10, "bold"))

        def fmt(x):
            return str(x) if x is not None else "_"

        for i, q in enumerate(quads):
            tree.insert("", "end", values=(i, fmt(q.op), fmt(q.arg1), fmt(q.arg2), fmt(q.result)))

    def _apply_mode_ui(self, mode):
        """Update UI chrome (header colour, panel visibility, terminal layout) for a mode,
        WITHOUT triggering analyze_code.  Used by run_all to set up each phase visually."""
        if self.right_panel:
            if mode in ("LEXICAL", "TAC"):
                # Show the right panel — pack on the right side of outer_frame
                self.right_panel.pack(side='right', fill='both', padx=(5, 0))
            else:
                # Hide the right panel reliably via pack_forget
                self.right_panel.pack_forget()
            # Flush geometry immediately so the change is visible before the next draw
            if self.root_window:
                self.root_window.update_idletasks()

        color_map = {
            "LEXICAL":  ("Lexical Analysis",  "#d0246f"),
            "SYNTAX":   ("Syntax Analysis",   "#ad46ff"),
            "SEMANTIC": ("Semantic Analysis", "#2b7fff"),
            "TAC":      ("TAC / Quadruples",  "#10a37f"),
        }
        if self.analysis_header_label and self.analysis_header_frame:
            title, color = color_map[mode]
            self.analysis_header_label.config(text=title, bg=color)
            self.analysis_header_frame.config(bg=color)

        for btn in (self.btn_lexical, self.btn_syntax, self.btn_semantic, self.btn_tac):
            if btn:
                btn.config(bg=btn._default_bg)
        btn_map = {
            "LEXICAL":  self.btn_lexical,
            "SYNTAX":   self.btn_syntax,
            "SEMANTIC": self.btn_semantic,
            "TAC":      self.btn_tac,
        }
        active_btn = btn_map.get(mode)
        if active_btn:
            active_btn.config(bg=active_btn._active_bg)

        # Terminal layout: split only in SEMANTIC, single otherwise
        if mode == "SEMANTIC":
            self.console_output.pack_forget()
            if self.console_errors and self.console_warnings:
                self.console_errors.master.master.pack(fill='both', expand=True, pady=(0, 5), padx=5)
        else:
            if self.console_errors and self.console_warnings:
                self.console_errors.master.master.pack_forget()
            self.console_output.pack(fill='both', expand=True, pady=(0, 5), padx=5)

    def switch_mode(self, mode):
        if mode == "SYNTAX" and self.btn_syntax and self.btn_syntax['state'] == 'disabled': return
        if mode == "SEMANTIC" and self.btn_semantic and self.btn_semantic['state'] == 'disabled': return
        if mode == "TAC" and self.btn_tac and self.btn_tac['state'] == 'disabled': return

        self.current_mode = mode
        
        if self.right_panel:
            if mode in ("LEXICAL", "TAC"):
                self.right_panel.pack(side='right', fill='both', padx=(5, 0))
            else:
                self.right_panel.pack_forget()
            if self.root_window:
                self.root_window.update_idletasks()

        color_map = {"LEXICAL": ("Lexical Analysis", "#d0246f"), "SYNTAX": ("Syntax Analysis", "#ad46ff"), "SEMANTIC": ("Semantic Analysis", "#2b7fff"),"TAC": ("TAC / Quadruples",  "#10a37f")}
        if self.analysis_header_label and self.analysis_header_frame:
            title, color = color_map[mode]
            self.analysis_header_label.config(text=title, bg=color)
            self.analysis_header_frame.config(bg=color)
            
        for btn in (self.btn_lexical, self.btn_syntax, self.btn_semantic, self.btn_tac):
            if btn:
                btn.config(bg=btn._default_bg)

        if mode == "LEXICAL":
            self.btn_lexical.config(bg=self.btn_lexical._active_bg)
            # Clear error indicators when switching to Lexical
            self.clear_error_indicators()
        elif mode == "SYNTAX":
            self.btn_syntax.config(bg=self.btn_syntax._active_bg)
        elif mode == "SEMANTIC":
            self.btn_semantic.config(bg=self.btn_semantic._active_bg)
            # Clear error indicators when switching to Semantic
            self.clear_error_indicators()
        elif mode == "TAC":
            if self.btn_tac:
                self.btn_tac.config(bg=self.btn_tac._active_bg)
            self.clear_error_indicators()

        # Show split terminal only in semantic mode
        if mode == "SEMANTIC":
            self.console_output.pack_forget()
            if self.console_errors and self.console_warnings:
                self.console_errors.master.master.pack(fill='both', expand=True, pady=(0, 5), padx=5)
        else:
            if self.console_errors and self.console_warnings:
                self.console_errors.master.master.pack_forget()
            self.console_output.pack(fill='both', expand=True, pady=(0, 5), padx=5)

        self.analyze_code(show_error_indicators=(mode in ("SYNTAX", "SEMANTIC")))
    
    
    def run_all(self):
        """Run all compiler phases sequentially. Stop and report error if any phase fails.
        All analysis runs silently first; UI is only updated ONCE at the end based on
        which phase failed (or succeeded). This avoids the add/forget panel flickering
        that occurred when _apply_mode_ui was called multiple times in one synchronous run."""
        code = self.code_input.get("1.0", "end-1c")
        if not code.strip():
            return

        self.clear_error_indicators()
        self.highlight_syntax()

        # ── Phase 1: Lexical (silent) ─────────────────────────────────────────
        lexemes = perform_lexical_analysis(code, self.terminal)
        lex_errors = [t for t in lexemes if t[1] in ["UNKNOWN", "ERR"] or "INVALID" in t[1]]
        lexical_passed = len(lex_errors) == 0 and len(code.strip()) > 0

        if not lexical_passed:
            # Land on LEXICAL view and show errors
            self.current_mode = "LEXICAL"
            self._apply_mode_ui("LEXICAL")
            if self.analysis_output_frame:
                for widget in self.analysis_output_frame.winfo_children():
                    widget.destroy()
            self.display_lexical(lexemes)
            error_msg = "\n".join(
                f"Lexical Error: line {l} col {c} {t} '{lex}'"
                for lex, t, l, c in lex_errors
            )
            self.log_colored_message(self.console_output, error_msg, "#ff6b6b")
            self.underline_lexical_errors(lex_errors)
            self.update_button_states(False, False, False)
            return

        # ── Phase 2: Syntax (silent) ──────────────────────────────────────────
        ignore = ["space", "newline", "tab", "ocmt", "mcmt"]
        filtered = [t for t in lexemes if t[1] not in ignore]
        syntax_passed = False
        syntax_report = ""
        parse_tree = None
        try:
            syntax_passed, syntax_report, parse_tree = perform_syntax_analysis(filtered, self.terminal)
            self.parse_tree = parse_tree
        except Exception as e:
            syntax_passed = False
            syntax_report = str(e)

        if not syntax_passed:
            # Land on SYNTAX view (no right panel) and show error
            self.current_mode = "SYNTAX"
            self._apply_mode_ui("SYNTAX")
            if self.analysis_output_frame:
                for widget in self.analysis_output_frame.winfo_children():
                    widget.destroy()
            self.log_colored_message(
                self.console_output,
                syntax_report if syntax_report else "Syntax error encountered.",
                "#ff6b6b"
            )
            if syntax_report and "Line" in syntax_report and "Column" in syntax_report:
                if "BUT FOUND '$'" not in syntax_report:
                    try:
                        match = re.search(r'Line\s*(\d+)\s*Column\s*(\d+)', syntax_report)
                        if match:
                            self.add_error_indicator(int(match.group(1)), int(match.group(2)))
                    except Exception:
                        pass
            self.update_button_states(True, False, False)
            return

        # ── Phase 3: Semantic (silent) ────────────────────────────────────────
        self.terminal.clear()
        if self.warning_terminal:
            self.warning_terminal.clear()

        class SplitTerminal:
            def __init__(self, error_t, warning_t):
                self.error_t = error_t
                self.warning_t = warning_t if warning_t else error_t
            def log(self, msg):
                if msg.startswith("WARNING"):
                    self.warning_t.log(msg)
                else:
                    self.error_t.log(msg)
            def clear(self):
                self.error_t.clear()
                if self.warning_t != self.error_t:
                    self.warning_t.clear()

        error_terminal = Terminal(self.console_errors) if self.console_errors else self.terminal
        split_terminal = SplitTerminal(error_terminal, self.warning_terminal)
        perform_semantic_analysis(lexemes, split_terminal, parse_tree)

        # Collect warning line numbers
        self.warning_line_numbers.clear()
        if self.console_warnings:
            for line in self.console_warnings.get("1.0", tk.END).split("\n"):
                match = re.search(r"at line (\d+)", line)
                if match and "WARNING" in line:
                    self.warning_line_numbers.add(int(match.group(1)))
        self.update_line_numbers()

        # Check for semantic errors
        error_console = self.console_errors if self.console_errors else self.console_output
        terminal_content = error_console.get("1.0", tk.END)
        semantic_has_errors = False
        semantic_error_lines = []
        for line in terminal_content.split("\n"):
            match = re.search(r"at line (\d+)", line)
            if match and "Semantic Error" in line:
                semantic_has_errors = True
                semantic_error_lines.append(int(match.group(1)))

        if semantic_has_errors:
            # Land on SEMANTIC view (no right panel) and show errors
            self.current_mode = "SEMANTIC"
            self._apply_mode_ui("SEMANTIC")
            if self.analysis_output_frame:
                for widget in self.analysis_output_frame.winfo_children():
                    widget.destroy()
            for error_line_no in semantic_error_lines:
                line_start = f"{error_line_no}.0"
                line_end = f"{error_line_no}.end"
                line_content = self.code_input.get(line_start, line_end)
                first_non_ws = len(line_content) - len(line_content.lstrip())
                if first_non_ws < len(line_content):
                    self.code_input.tag_add("error_indicator", f"{error_line_no}.{first_non_ws}", line_end)
                else:
                    self.code_input.tag_add("error_indicator", line_start, line_end)
            self.update_button_states(True, True, False)
            return

        # ── Phase 4: Run ──────────────────────────────────────────────────────
        if self.console_errors and self.console_errors.get("1.0", tk.END).strip() == "":
            self.log_colored_message(self.console_errors, "No semantic errors.", "#ff6b6b")
        self.update_button_states(True, True, True)

        try:
            from tac_walker import generate_tac
            from interpreter import TACInterpreter

            if not self.parse_tree:
                self.log_colored_message(self.console_output, "TAC Error: No parse tree available.", "#ff6b6b")
                return

            walker = generate_tac(self.parse_tree)

            # Switch terminal to single console view for interpreter output
            if self.console_errors and self.console_warnings:
                self.console_errors.master.master.pack_forget()
            self.console_output.pack(fill='both', expand=True, pady=(0, 5), padx=5)

            self.console_output.config(state="normal")
            self.console_output.focus_force()

            interp = TACInterpreter(walker.gen.quads, self.console_output)
            interp.start()

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log_colored_message(self.console_output, f"Runtime Error: {str(e)}", "#ff6b6b")