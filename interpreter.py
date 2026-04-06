import tkinter as tk


class TACInterpreter:
    def __init__(self, quads, console_output):
        self.quads = quads
        self.console = console_output

        # Build label map: label_name -> quad index
        self.labels = {}
        for i, q in enumerate(self.quads):
            if q.op == "LABEL":
                self.labels[q.arg1] = i

        # Build function map: func_name -> quad index of FUNC_BEGIN
        self.functions = {}
        for i, q in enumerate(self.quads):
            if q.op == "FUNC_BEGIN":
                self.functions[q.arg1] = i

        self.memory   = {}       # variable store
        self.var_types = {}      # variable name → declared type (from DECLARE quads)
        self.pc       = 0        # program counter
        self.output   = ""       # accumulated output string
        self.param_stack  = []   # PARAM queue before CALL
        self.call_stack   = []   # [(return_pc, return_memory, result_var)]
        self.running  = False
        self.waiting_input = False
        self.input_var = None    # which variable READ is waiting for
        self.input_start = None  # index in console where user starts typing
        self.input_buffer = ""   # tracks what user typed
        self.last_return_value = None

        # Pre-scan DECLARE quads to populate var_types
        for q in self.quads:
            if q.op == "DECLARE":
                self.var_types[q.arg1] = q.arg2

    # ------------------------------------------------------------------ #
    #  PUBLIC: start                                                       #
    # ------------------------------------------------------------------ #
    def start(self):
        """Clear terminal and begin execution from brain()."""
        self._console_clear()
        self._console_set_editable(True)

        # Find brain entry point
        brain_pc = self.functions.get("brain")
        if brain_pc is None:
            self._console_write("Runtime Error: no brain() function found.\n", "#ff6b6b")
            self._console_set_editable(False)
            return

        self.pc = brain_pc + 1   # skip FUNC_BEGIN itself
        self.running = True
        self._run()

    # ------------------------------------------------------------------ #
    #  MAIN EXECUTION LOOP                                                 #
    # ------------------------------------------------------------------ #
    def _run(self):
        """Execute quads until READ, FUNC_END of brain, or end of quads."""
        while self.running and self.pc < len(self.quads):
            q = self.quads[self.pc]
           
            if q.op == "FUNC_END" and len(self.call_stack) == 0:
                # returned from brain — we're done
                self.running = False
                break

            try:
                self._execute(q)
            except RuntimeError as e:
                self._console_write(f"\nRuntime Error: {e}\n", "#ff6b6b")
                self.running = False
                self._console_set_editable(False)
                return

            if self.waiting_input:
                return   # pause — resume in _on_enter()

        if not self.waiting_input:
            self._finish()

    def _execute(self, q):
        op     = q.op
        arg1   = q.arg1
        arg2   = q.arg2
        result = q.result

        # ---- declare (type annotation) ---------------------------------
        if op == "DECLARE":
            self.var_types[arg1] = arg2
            # Always reset to default — re-declaration inside a loop means re-initialization
            defaults = {"int": 0, "float": 0.00, "bool": "betray", "str": " ", "char": " "}
            if arg2 in defaults:
                self.memory[arg1] = defaults[arg2]
            self.pc += 1

        # ---- array declaration -----------------------------------------
        elif op == "ARRAY_DECL":
            arr_name = arg1
            size     = int(arg2) if arg2 is not None else 0
            dtype    = result
            self.var_types[arr_name] = dtype
            defaults = {
                "int":   0,
                "float": 0.00,
                "bool":  "betray",
                "str":   " ",
                "char":  " ",
            }
            default_val = defaults.get(dtype, 0)
            # Initialize all elements to the default value
            if arr_name not in self.memory:
                self.memory[arr_name] = [default_val] * size
            self.pc += 1

        # ---- assignment ------------------------------------------------
        elif op == "=":
            if arg1 is None:
                val = self.last_return_value
            else:
                val = self._val(arg1)
            # Apply implicit type conversion based on target variable's declared type
            target_type = self.var_types.get(result)
            if target_type:
                val = self._convert(val, target_type, result)
            self.memory[result] = val
            self.pc += 1

        # ---- arithmetic ------------------------------------------------
        elif op in ("+", "-", "*", "/", "//", "%", "**"):
            a = self._coerce_for_arithmetic(self._val(arg1))
            b = self._coerce_for_arithmetic(self._val(arg2))
            self.memory[result] = self._arith(op, a, b)
            self.pc += 1

        # ---- comparison ------------------------------------------------
        elif op in ("<=", ">=", "<", ">"):
            a = self._coerce_for_arithmetic(self._val(arg1))
            b = self._coerce_for_arithmetic(self._val(arg2))
            r = self._compare(op, a, b)
            self.memory[result] = "trust" if r else "betray"
            self.pc += 1
        elif op in ("==", "!="):
            a = self._val(arg1)
            b = self._val(arg2)
            # Equality: if one side is bool, convert the other to bool first
            a, b = self._coerce_for_equality(a, b)
            r = self._compare(op, a, b)
            self.memory[result] = "trust" if r else "betray"
            self.pc += 1

        # ---- logical ---------------------------------------------------
        elif op == "&&":
            result_bool = self._coerce_to_bool(self._val(arg1)) and self._coerce_to_bool(self._val(arg2))
            self.memory[result] = "trust" if result_bool else "betray"
            self.pc += 1
        elif op == "||":
            result_bool = self._coerce_to_bool(self._val(arg1)) or self._coerce_to_bool(self._val(arg2))
            self.memory[result] = "trust" if result_bool else "betray"
            self.pc += 1
        elif op == "!":
            result_bool = not self._coerce_to_bool(self._val(arg1))
            self.memory[result] = "trust" if result_bool else "betray"
            self.pc += 1

        # ---- control flow ----------------------------------------------
        elif op == "LABEL":
            self.pc += 1

        elif op == "GOTO":
            target = result
            if target not in self.labels:
                raise RuntimeError(f"Unknown label: {target}")
            self.pc = self.labels[target]

        elif op == "IF_FALSE":
            cond = self._val(arg1)
            if not self._is_truthy(cond):
                target = result
                if target not in self.labels:
                    raise RuntimeError(f"Unknown label: {target}")
                self.pc = self.labels[target]
            else:
                self.pc += 1

        elif op == "IF_TRUE":
            cond = self._val(arg1)
            if self._is_truthy(cond):
                target = result
                if target not in self.labels:
                    raise RuntimeError(f"Unknown label: {target}")
                self.pc = self.labels[target]
            else:
                self.pc += 1

        # ---- I/O -------------------------------------------------------
        
        elif op == "SPILL":
            val = self._val(arg1)
            # Format floats to always show 2 decimal places
            if isinstance(val, float):
                text = f"{val:.2f}"
            else:
                text = str(val)
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1]
            text = text.replace("\\\\n", "\n").replace("\\\\t", "\t").replace("\\n", "\n").replace("\\t", "\t")
            if arg2 is not None:
                val2 = self._val(arg2)
                if isinstance(val2, float):
                    text2 = f"{val2:.2f}"
                else:
                    text2 = str(val2)
                if text2.startswith('"') and text2.endswith('"'):
                    text2 = text2[1:-1]
                text += text2
            self._console_write(text, "#f1f6f4")
            self.pc += 1

        elif op == "READ":
            self.input_var     = result
            self.waiting_input = True
            self.input_start   = self.console.index(tk.END)
            self.input_buffer  = ""
            self.console.config(state="normal")
            self.console.focus_force()
            self.console.bind("<Key>",     self._on_key)
            self.console.bind("<Return>",  self._on_enter)
            self.console.bind("<BackSpace>", self._on_backspace)
            self.pc += 1
        
        # ---- functions -------------------------------------------------
        elif op == "PARAM":
            self.param_stack.append(self._val(arg1))
            self.pc += 1

        elif op == "CALL":
            func_name  = arg1
            num_params = int(arg2)
            ret_var    = result

            if func_name not in self.functions:
                raise RuntimeError(f"Unknown function: {func_name}")

            func_pc = self.functions[func_name]

            # Save current state
            self.call_stack.append({
                "return_pc" : self.pc + 1,
                "memory"    : dict(self.memory),
                "ret_var"   : ret_var,
                "var_types" : dict(self.var_types),
            })

            # Collect params — they are on param_stack in order
            args = []
            for _ in range(num_params):
                args.append(self.param_stack.pop(0))

            # Jump to function, skip FUNC_BEGIN
            self.pc = func_pc + 1

            # Bind params to formal names (next num_params quads are FPARAM)
            arg_idx = 0
            tmp_pc  = self.pc
            while arg_idx < num_params and tmp_pc < len(self.quads):
                fq = self.quads[tmp_pc]
                if fq.op == "FPARAM":
                    self.memory[fq.arg1] = args[arg_idx]
                    arg_idx += 1
                    tmp_pc += 1
                else:
                    break
            self.pc = tmp_pc   # start after all FPARAMs

        # ---- array operations ------------------------------------------
        elif op == "[]=":
            # arr[index] = val  →  arg1=arr_name, arg2=index, result=value
            arr_name = arg1
            index    = int(self._val(arg2))
            val      = self._val(result)
            # Apply type conversion if array has a known element type
            arr_type = self.var_types.get(arr_name)
            if arr_type:
                val = self._convert(val, arr_type, f"{arr_name}[{index}]")
            # Ensure array exists as a list; grow if needed
            if arr_name not in self.memory or not isinstance(self.memory[arr_name], list):
                self.memory[arr_name] = []
            arr = self.memory[arr_name]
            # Extend list with defaults if index is beyond current length
            while len(arr) <= index:
                defaults = {"int": 0, "float": 0.00, "bool": "betray", "str": " ", "char": " "}
                arr.append(defaults.get(arr_type, 0))
            arr[index] = val
            self.pc += 1

        elif op == "=[]":
            # t = arr[index]  →  arg1=arr_name, arg2=index, result=temp
            arr_name = arg1
            index    = int(self._val(arg2))
            arr      = self.memory.get(arr_name, [])
            if isinstance(arr, list) and 0 <= index < len(arr):
                self.memory[result] = arr[index]
            else:
                # Out of bounds — store default based on array type
                arr_type = self.var_types.get(arr_name, "int")
                defaults = {"int": 0, "float": 0.00, "bool": "betray", "str": " ", "char": " "}
                self.memory[result] = defaults.get(arr_type, 0)
            self.pc += 1

        elif op == "FUNC_BEGIN":
            self.pc += 1

        elif op == "FUNC_END":
            if self.call_stack:
                frame = self.call_stack.pop()
                ret_pc  = frame["return_pc"]
                ret_var = frame["ret_var"]
                # restore caller memory but keep any globals updated
                caller_mem = frame["memory"]
                # propagate global-like vars (I, J, K, etc.) back
                for k, v in self.memory.items():
                    caller_mem[k] = v
                self.memory = caller_mem
                # restore caller var_types
                self.var_types = frame.get("var_types", self.var_types)
                self.pc = ret_pc
            else:
                self.running = False

        elif op == "closure":
            ret_value = self._val(arg1)
            self.last_return_value = ret_value
            if self.call_stack:
                frame = self.call_stack.pop()
                ret_var = frame.get("ret_var")
                caller_mem = frame["memory"]
                for k, v in self.memory.items():
                    caller_mem[k] = v
                self.memory = caller_mem
                self.var_types = frame.get("var_types", self.var_types)
                if ret_var:
                    self.memory[ret_var] = ret_value
                self.last_return_value = ret_value
                self.pc = frame["return_pc"]
            else:
                self.running = False
             
        else:
            # unknown op — skip
            self.pc += 1

    # ------------------------------------------------------------------ #
    #  INPUT HANDLING                                                      #
    # ------------------------------------------------------------------ #
    
    def _on_key(self, event):
        # Only allow printable characters
        if event.char and event.char.isprintable():
            self.input_buffer += event.char
            self.console.config(state="normal")
            self._console_write(event.char, "#f1f6f4")
        return "break"
    
    def _on_backspace(self, event):   # ← add here
        if self.input_buffer:
            self.input_buffer = self.input_buffer[:-1]
            self.console.config(state="normal")
            self.console.delete(f"{tk.END} -2c", f"{tk.END} -1c")
        return "break"

    def _on_enter(self, event):
        raw = self.input_buffer.strip()

        if not raw:
            return "break"

        self._console_write("\n", "#f1f6f4")

        self.console.unbind("<Return>")
        self.console.unbind("<Key>")
        self.console.unbind("<BackSpace>")
        self.waiting_input = False
        self.input_buffer  = ""

        try:
            value = int(raw)
        except ValueError:
            try:
                value = float(raw)
            except ValueError:
                value = raw

        self.memory[self.input_var] = value

        # Resume execution
        self._run()
        return "break"
    

    # ------------------------------------------------------------------ #
    #  FINISH                                                              #
    # ------------------------------------------------------------------ #
    def _finish(self):
        self._console_write("\n✓ BUILD SUCCESSFUL!.\n", "#10a37f")
        self._console_set_editable(False)

    # ------------------------------------------------------------------ #
    #  TYPE CONVERSION (EmE Language Rules)                               #
    # ------------------------------------------------------------------ #

    _VALID_ASCII_MIN = 32
    _VALID_ASCII_MAX = 126

    def _convert(self, val, target_type, var_name="?"):
        """
        Apply EmE implicit type-conversion rules when storing val into a
        variable whose declared type is target_type.
        Raises RuntimeError for illegal conversions (e.g. char ↔ bool,
        out-of-range ASCII).
        """
        if val is None:
            return val

        src_type = self._infer_runtime_type(val)

        # Same type — no conversion needed
        if src_type == target_type:
            return val

        # ── int ↔ float ──────────────────────────────────────────────
        if src_type == "int" and target_type == "float":
            return float(val)
        if src_type == "float" and target_type == "int":
            return int(val)   # truncation, not rounding

        # ── int ↔ char (ASCII) ───────────────────────────────────────
        if src_type == "int" and target_type == "char":
            code = int(val)
            if not (self._VALID_ASCII_MIN <= code <= self._VALID_ASCII_MAX):
                raise RuntimeError(
                    f"Type conversion error: int value {code} is outside "
                    f"valid ASCII range ({self._VALID_ASCII_MIN}–{self._VALID_ASCII_MAX}) "
                    f"when assigning to char variable '{var_name}'."
                )
            return chr(code)
        if src_type == "char" and target_type == "int":
            code = ord(val) if isinstance(val, str) and len(val) == 1 else int(val)
            return code

        # ── float ↔ char ─────────────────────────────────────────────
        if src_type == "float" and target_type == "char":
            code = int(val)   # truncate
            if not (self._VALID_ASCII_MIN <= code <= self._VALID_ASCII_MAX):
                raise RuntimeError(
                    f"Type conversion error: float value {val} truncates to {code}, "
                    f"outside valid ASCII range ({self._VALID_ASCII_MIN}–{self._VALID_ASCII_MAX}) "
                    f"when assigning to char variable '{var_name}'."
                )
            return chr(code)
        if src_type == "char" and target_type == "float":
            code = ord(val) if isinstance(val, str) and len(val) == 1 else int(val)
            return float(code)

        # ── int ↔ bool ───────────────────────────────────────────────
        if src_type == "int" and target_type == "bool":
            return "trust" if val != 0 else "betray"
        if src_type == "bool" and target_type == "int":
            return 1 if val in (True, "trust") else 0

        # ── float ↔ bool ─────────────────────────────────────────────
        if src_type == "float" and target_type == "bool":
            return "trust" if val != 0.0 else "betray"
        if src_type == "bool" and target_type == "float":
            return 1.0 if val in (True, "trust") else 0.0

        # ── char ↔ bool — NOT ALLOWED ────────────────────────────────
        if (src_type == "char" and target_type == "bool") or \
           (src_type == "bool" and target_type == "char"):
            raise RuntimeError(
                f"Type conversion error: direct conversion between char and bool "
                f"is not allowed (variable '{var_name}')."
            )

        # Fallback: return unchanged
        return val

    def _is_truthy(self, val):
        """Correctly evaluate truthiness for EmE values including trust/betray strings."""
        if val == "betray" or val is False:
            return False
        if val == "trust" or val is True:
            return True
        # 0 and 0.0 are falsy, everything else truthy
        if isinstance(val, (int, float)):
            return val != 0
        # non-empty strings are truthy
        return bool(val)

    def _infer_runtime_type(self, val):
        """Infer the EmE type of a runtime Python value."""
        if isinstance(val, bool):
            return "bool"
        if val in ("trust", "betray"):
            return "bool"
        if isinstance(val, int):
            return "int"
        if isinstance(val, float):
            return "float"
        if isinstance(val, str) and len(val) == 1 and not val.isdigit():
            return "char"
        return "str"

    def _coerce_for_arithmetic(self, val):
        """
        Rule 8a: In arithmetic/relational expressions:
        - bool → int  (betray=0, trust=1)
        - char → int  (ASCII value)
        """
        if val in ("trust", True):
            return 1
        if val in ("betray", False):
            return 0
        if isinstance(val, str) and len(val) == 1:
            return ord(val)
        return val

    def _coerce_to_bool(self, val):
        """
        Rule 8b: In logical expressions:
        - int/float → bool  (0/0.0 = False, else True)
        - char → int → bool
        - bool string → Python bool
        """
        if val in ("trust", True):
            return True
        if val in ("betray", False):
            return False
        if isinstance(val, str) and len(val) == 1:
            return ord(val) != 0
        if isinstance(val, (int, float)):
            return val != 0
        return bool(val)

    def _coerce_for_equality(self, a, b):
        """
        Rule 8c: In equality expressions:
        - If either side is bool, convert the other to bool first.
        - char → int → bool if compared with bool.
        """
        a_is_bool = a in ("trust", "betray") or isinstance(a, bool)
        b_is_bool = b in ("trust", "betray") or isinstance(b, bool)

        def to_bool_val(x):
            if x in ("trust", True):
                return True
            if x in ("betray", False):
                return False
            if isinstance(x, str) and len(x) == 1:
                return ord(x) != 0   # char → int → bool
            if isinstance(x, (int, float)):
                return x != 0
            return bool(x)

        if a_is_bool and not b_is_bool:
            b = to_bool_val(b)
        elif b_is_bool and not a_is_bool:
            a = to_bool_val(a)

        # Normalise bool strings to Python bools for comparison
        if a in ("trust",):  a = True
        if a in ("betray",): a = False
        if b in ("trust",):  b = True
        if b in ("betray",): b = False

        return a, b

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #
    
    def _val(self, x):
        """Resolve a value: variable lookup or literal parse."""
        if x is None:
            return None
        # Check memory first
        if x in self.memory:
            val = self.memory[x]
            # Keep trust/betray as canonical bool strings
            if val in ("trust", "betray"):
                return val
            if isinstance(val, bool):
                return "trust" if val else "betray"
            if isinstance(val, str):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
            return val
        # Bool literals
        if x == "trust":
            return "trust"
        if x == "betray":
            return "betray"
        # Try int
        try:
            return int(x)
        except (ValueError, TypeError):
            pass
        # Try float
        try:
            return float(x)
        except (ValueError, TypeError):
            pass
        # String literal
        if isinstance(x, str) and x.startswith('"') and x.endswith('"'):
            return x[1:-1]
        # Char literal
        if isinstance(x, str) and x.startswith("'") and x.endswith("'") and len(x) == 3:
            return x[1]
        return x

    def _arith(self, op, a, b):
        if op == "+":  return a + b
        if op == "-":  return a - b
        if op == "*":  return a * b
        if op == "/":
            if isinstance(a, int) and isinstance(b, int):
                return a // b
            return a / b
        if op == "//": return int(a) // int(b)
        if op == "%":  return int(a) % int(b)
        if op == "**": return a ** b

    def _compare(self, op, a, b):
        def to_num(x):
            if isinstance(x, (int, float)):
                return x
            try:
                return int(x)
            except (ValueError, TypeError):
                pass
            try:
                return float(x)
            except (ValueError, TypeError):
                pass
            return x
        a = to_num(a)
        b = to_num(b)
        if op == "<=": return a <= b
        if op == ">=": return a >= b
        if op == "<":  return a < b
        if op == ">":  return a > b
        if op == "==": return a == b
        if op == "!=": return a != b
    
    # ------------------------------------------------------------------ #
    #  CONSOLE HELPERS                                                     #
    # ------------------------------------------------------------------ #
    def _console_clear(self):
        self.console.config(state="normal")
        self.console.delete("1.0", tk.END)

    def _console_write(self, text, color="#f1f6f4"):
        self.console.config(state="normal")
        tag = f"color_{color.replace('#','')}"
        self.console.tag_configure(tag, foreground=color)
        self.console.insert(tk.END, text, tag)
        self.console.see(tk.END)

    def _console_set_editable(self, editable):
        if editable:
            self.console.config(state="normal")
        else:
            self.console.config(state="disabled")