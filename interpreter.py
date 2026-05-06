import tkinter as tk


class TACInterpreter:
    _MAX_STEPS = 5000   # 

    def __init__(self, quads, console_output):
        self.quads = quads
        self.console = console_output
        self.labels = {}

        for i, q in enumerate(self.quads):
            if q.op == "LABEL":
                self.labels[q.arg1] = i

        self.functions = {}
        for i, q in enumerate(self.quads):
            if q.op == "FUNC_BEGIN":
                self.functions[q.arg1] = i

        self.memory   = {}       
        self.var_types = {}      
        self.pc       = 0        
        self.output   = ""       
        self.param_stack  = []   
        self.call_stack   = []   
        self.running  = False
        self.waiting_input = False
        self.input_var = None   
        self.input_start = None  
        self.input_buffer = ""   
        self.last_return_value = None

        self.global_vars = set()
        for q in self.quads:
            if q.op == "FUNC_BEGIN":
                break
            if q.op in ("DECLARE", "ARRAY_DECL") and q.arg1:
                self.global_vars.add(q.arg1)

        for q in self.quads:
            if q.op == "DECLARE":
                self.var_types[q.arg1] = q.arg2

    def start(self):
        self._console_clear()
        self._console_set_editable(True)

        brain_pc = self.functions.get("brain")
        if brain_pc is None:
            self._console_write("Runtime Error: no brain() function found.\n", "#ff6b6b")
            self._console_set_editable(False)
            return

        for i, q in enumerate(self.quads):
            if q.op == "FUNC_BEGIN":
                break
            try:
                self._execute(q)
            except Exception as e:
                self._console_write(f"\nRuntime Error (global init): {e}\n", "#ff6b6b")
                self._console_set_editable(False)
                return

        self.pc = brain_pc + 1  
        self.running = True
        self._run()

    def _run(self):
        steps = 0
        while self.running and self.pc < len(self.quads):
            if steps >= self._MAX_STEPS:
                self.console.after(0, self._run)
                return
            steps += 1

            q = self.quads[self.pc]
            if q.op == "FUNC_END" and len(self.call_stack) == 0:
                self.running = False
                break

            try:
                self._execute(q)
            except Exception as e:
                self._console_write(f"\nRuntime Error: {e}\n", "#ff6b6b")
                self.running = False
                self._console_set_editable(False)
                return

            if self.waiting_input:
                return  

        if not self.waiting_input:
            self._finish()

    def _execute(self, q):
        op     = q.op
        arg1   = q.arg1
        arg2   = q.arg2
        result = q.result

        if op == "DECLARE":
            self.var_types[arg1] = arg2
            defaults = {"int": 0, "float": 0.00, "bool": "betray", "str": " ", "char": " "}
            if arg2 in defaults:
                self.memory[arg1] = defaults[arg2]
            self.pc += 1

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
            self.memory[arr_name] = [default_val] * size
            self.pc += 1

        # ---- assignment ----
        elif op == "=":
            if arg1 is None:
                val = self.last_return_value
                self.last_return_value = None
            else:
                val = self._val(arg1)

            target_type = self.var_types.get(result)
            if target_type:
                val = self._convert(val, target_type, result)
            self.memory[result] = val
            self.pc += 1

        # ---- arithmetic ----
        elif op in ("+", "-", "*", "/", "//", "%", "**", "^"):
            a = self._coerce_for_arithmetic(self._val(arg1))
            b = self._coerce_for_arithmetic(self._val(arg2))
            self.memory[result] = self._arith(op, a, b)
            self.pc += 1

        # ---- comparison ----
        elif op in ("<=", ">=", "<", ">"):
            a = self._coerce_for_arithmetic(self._val(arg1))
            b = self._coerce_for_arithmetic(self._val(arg2))
            r = self._compare(op, a, b)
            self.memory[result] = "trust" if r else "betray"
            self.pc += 1
        elif op in ("==", "!="):
            a = self._val(arg1)
            b = self._val(arg2)
            a, b = self._coerce_for_equality(a, b)
            r = self._compare(op, a, b)
            self.memory[result] = "trust" if r else "betray"
            self.pc += 1

        # ---- logical ----
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

        # ---- control flow ----
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

        # ---- I/O ----
        elif op == "SPILL":
            val = self._val(arg1)
            text = self._format_spill(val, self.var_types.get(arg1))
            text = text.replace("\\\\n", "\n").replace("\\\\t", "\t").replace("\\n", "\n").replace("\\t", "\t")
            if arg2 is not None:
                val2  = self._val(arg2)
                text += self._format_spill(val2, self.var_types.get(arg2))
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
            self.call_stack.append({
                "return_pc" : self.pc + 1,
                "memory"    : dict(self.memory),
                "ret_var"   : ret_var,
                "var_types" : dict(self.var_types),
            })

            args = []
            for _ in range(num_params):
                args.append(self.param_stack.pop(0))

            self.memory = {k: v for k, v in self.memory.items()
                           if k in self.global_vars}
            self.pc = func_pc + 1
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
            self.pc = tmp_pc   

        # ---- array operations ------------------------------------------
        elif op == "[]=":
            arr_name = arg1
            index    = int(self._val(arg2)) // 4
            val      = self._val(result)

            arr_type = self.var_types.get(arr_name)
            if arr_type:
                val = self._convert(val, arr_type, f"{arr_name}[{index}]")

            if arr_name not in self.memory or not isinstance(self.memory[arr_name], list):
                self.memory[arr_name] = []
            arr = self.memory[arr_name]
            while len(arr) <= index:
                defaults = {"int": 0, "float": 0.00, "bool": "betray", "str": " ", "char": " "}
                arr.append(defaults.get(arr_type, 0))
            arr[index] = val
            self.pc += 1

        elif op == "=[]":
            arr_name = arg1
            index    = int(self._val(arg2)) // 4
            arr      = self.memory.get(arr_name, [])
            arr_type = self.var_types.get(arr_name, "int")
            if isinstance(arr, list) and 0 <= index < len(arr):
                self.memory[result] = arr[index]
            else:
                defaults = {"int": 0, "float": 0.00, "bool": "betray", "str": " ", "char": " "}
                self.memory[result] = defaults.get(arr_type, 0)
   
            if result:
                self.var_types[result] = arr_type
            self.pc += 1

        elif op == "FUNC_BEGIN":
            self.pc += 1

        elif op == "FUNC_END":
            if self.call_stack:
                frame = self.call_stack.pop()
                ret_pc  = frame["return_pc"]
                caller_mem = frame["memory"]

                for k in self.global_vars:
                    if k in self.memory:
                        caller_mem[k] = self.memory[k]
                self.memory = caller_mem
                self.var_types = frame.get("var_types", self.var_types)
                self.pc = ret_pc
            else:
                self.running = False

        elif op == "closure":
            ret_value = self._val(arg1)
            if self.call_stack:
                frame = self.call_stack.pop()
                ret_var = frame.get("ret_var")
                caller_mem = frame["memory"]

                for k in self.global_vars:
                    if k in self.memory:
                        caller_mem[k] = self.memory[k]
                self.memory = caller_mem
                self.var_types = frame.get("var_types", self.var_types)

                if ret_var:
                    self.memory[ret_var] = ret_value
                self.last_return_value = ret_value if not ret_var else None
                self.pc = frame["return_pc"]
            else:
                self.last_return_value = ret_value
                self.running = False
             
        else:
            self.pc += 1

    def _format_spill(self, val, var_type=None):
        if var_type == "char" and isinstance(val, int):
            try:
                return chr(val)
            except (ValueError, OverflowError):
                return str(val)
        if isinstance(val, float):
            text = f"{val:.2f}"
        else:
            text = str(val)
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        return text


    def _on_key(self, event):
        if event.char and event.char.isprintable():
            self.input_buffer += event.char
            self.console.config(state="normal")
            self._console_write(event.char, "#f1f6f4")
        return "break"
    
    def _on_backspace(self, event): 
        if self.input_buffer:
            self.input_buffer = self.input_buffer[:-1]
            self.console.config(state="normal")
            self.console.delete(f"{tk.END} -2c", f"{tk.END} -1c")
        return "break"

    def _on_enter(self, event):
        self.console.unbind("<Return>")
        self.console.unbind("<Key>")
        self.console.unbind("<BackSpace>")
        raw = self.input_buffer.strip()
        if not raw:
            self.console.bind("<Key>",       self._on_key)
            self.console.bind("<Return>",    self._on_enter)
            self.console.bind("<BackSpace>", self._on_backspace)
            return "break"
        self._console_write("\n", "#f1f6f4")
        target_type = self.var_types.get(self.input_var)

        def _reject(msg):
            self._console_write(msg, "#ff6b6b")
            self.input_buffer  = ""
            self.waiting_input = True
            self.console.bind("<Key>",       self._on_key)
            self.console.bind("<Return>",    self._on_enter)
            self.console.bind("<BackSpace>", self._on_backspace)

        if target_type == "int":
            valid = False
            if "." not in raw:
                try:
                    v = int(raw)
                    valid = True
                except ValueError:
                    pass
            if not valid:
                _reject(f"Invalid input \"{raw}\": integers only, no letters or decimals. Try again: ")
                return "break"
            if abs(v) > 999999999999:
                _reject(f"Invalid input \"{raw}\": integer out of range (-999999999999 to 999999999999). Try again: ")
                return "break"

        elif target_type == "float":
            try:
                float(raw)
            except ValueError:
                _reject(f"Invalid input \"{raw}\": expected a number. Try again: ")
                return "break"
            stripped = raw.lstrip('-').lstrip('+')
            if '.' in stripped:
                int_part, frac_part = stripped.split('.', 1)
            else:
                int_part, frac_part = stripped, ''
            try:
                if int(int_part or '0') > 999999999999:
                    _reject(f"Invalid input \"{raw}\": float integer part exceeds max (999999999999). Try again: ")
                    return "break"
            except ValueError:
                pass
            if len(frac_part) > 11:
                _reject(f"Invalid input \"{raw}\": float may only have up to 11 decimal digits. Try again: ")
                return "break"

        elif target_type == "bool":
            if raw not in ("trust", "betray"):
                _reject(f"Invalid input \"{raw}\": expected trust or betray. Try again: ")
                return "break"

        elif target_type == "char" and not isinstance(self.memory.get(self.input_var), list):
            if len(raw) != 1:
                _reject(f"Invalid input \"{raw}\": expected a single character. Try again: ")
                return "break"

        self.waiting_input = False
        self.input_buffer  = ""
        if (target_type == "char" and
                isinstance(self.memory.get(self.input_var), list)):
            arr = self.memory[self.input_var]
            for i in range(len(arr)):
                arr[i] = ord(raw[i]) if i < len(raw) else ord(" ")
        else:
            if target_type == "char":
                value = raw[0]
            else:
                try:
                    value = int(raw)
                except ValueError:
                    try:
                        value = float(raw)
                    except ValueError:
                        value = raw
                if target_type:
                    try:
                        value = self._convert(value, target_type, self.input_var)
                    except RuntimeError:
                        pass
            self.memory[self.input_var] = value
        try:
            self._run()
        except Exception as e:
            self._console_write(f"\nRuntime Error: {e}\n", "#ff6b6b")
            self.running = False
            self._console_set_editable(False)
        return "break"
    
    def _finish(self):
        self._console_write("\n✓ BUILD SUCCESSFUL!.\n", "#10a37f")
        self._console_set_editable(False)

 # ----- TYPE CONVERSION -----
    _VALID_ASCII_MIN = 32
    _VALID_ASCII_MAX = 126

    def _convert(self, val, target_type, var_name="?"):
        if val is None:
            return val

        src_type = self._infer_runtime_type(val)

        # Same type (no convert)
        if src_type == target_type:
            return val

        # ── int <-> float ──
        if src_type == "int" and target_type == "float":
            return float(val)
        if src_type == "float" and target_type == "int":
            return int(val)  
        
        # ── int <-> char (ASCII) ──
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

        # ── float <-> char ──
        if src_type == "float" and target_type == "char":
            code = int(val)  
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

        # ── int <-> bool ──
        if src_type == "int" and target_type == "bool":
            return "trust" if val != 0 else "betray"
        if src_type == "bool" and target_type == "int":
            return 1 if val in (True, "trust") else 0

        # ── float <-> bool ───
        if src_type == "float" and target_type == "bool":
            return "trust" if val != 0.0 else "betray"
        if src_type == "bool" and target_type == "float":
            return 1.0 if val in (True, "trust") else 0.0

        # ── char <-> bool — NOT ALLOWED ──
        if (src_type == "char" and target_type == "bool") or \
           (src_type == "bool" and target_type == "char"):
            raise RuntimeError(
                f"Type conversion error: direct conversion between char and bool "
                f"is not allowed (variable '{var_name}')."
            )
        return val

    def _is_truthy(self, val):
        if val == "betray" or val is False:
            return False
        if val == "trust" or val is True:
            return True
        if isinstance(val, (int, float)):
            return val != 0
        return bool(val)

    def _infer_runtime_type(self, val):
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
        if isinstance(val, bool):
            return 1 if val else 0
        if val == "trust":
            return 1
        if val == "betray":
            return 0
        if isinstance(val, str) and len(val) == 1:
            return ord(val)
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

    def _coerce_to_bool(self, val):
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
        a_is_bool = a in ("trust", "betray") or isinstance(a, bool)
        b_is_bool = b in ("trust", "betray") or isinstance(b, bool)

        def to_bool_val(x):
            if x in ("trust", True):
                return True
            if x in ("betray", False):
                return False
            if isinstance(x, str) and len(x) == 1:
                return ord(x) != 0  
            if isinstance(x, (int, float)):
                return x != 0
            return bool(x)

        if a_is_bool and not b_is_bool:
            b = to_bool_val(b)
        elif b_is_bool and not a_is_bool:
            a = to_bool_val(a)

        if a in ("trust",):  a = True
        if a in ("betray",): a = False
        if b in ("trust",):  b = True
        if b in ("betray",): b = False

        return a, b

    def _val(self, x):
        if x is None:
            return None
        if x in self.memory:
            val = self.memory[x]
            if val in ("trust", "betray"):
                return val
            if isinstance(val, bool):
                return "trust" if val else "betray"
            if isinstance(val, list):
                return 0
            if isinstance(val, int) and self.var_types.get(x) == "char":
                try:
                    return chr(val)
                except (ValueError, OverflowError):
                    pass
            if isinstance(val, str):
                if val == x:
                    declared_type = self.var_types.get(x)
                    defaults = {"int": 0, "float": 0.0, "bool": "betray",
                                "str": " ", "char": " "}
                    if declared_type in defaults:
                        return defaults[declared_type]
                    return 0
                declared_type = self.var_types.get(x)
                if declared_type == "char":
                    return val
                if declared_type == "float":
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
                else:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
            return val
        if x == "trust":
            return "trust"
        if x == "betray":
            return "betray"
        try:
            return int(x)
        except (ValueError, TypeError):
            pass
        try:
            return float(x)
        except (ValueError, TypeError):
            pass
        if isinstance(x, str) and x.startswith('"') and x.endswith('"'):
            return x[1:-1]
        if isinstance(x, str) and x.startswith("'") and x.endswith("'") and len(x) == 3:
            return x[1]
        if isinstance(x, str) and x and x[0].isupper():
            declared_type = self.var_types.get(x)
            defaults = {"int": 0, "float": 0.0, "bool": "betray",
                        "str": " ", "char": " "}
            if declared_type in defaults:
                return defaults[declared_type]
            return 0
        return x

    def _arith(self, op, a, b):
        def _to_num(x):
            if isinstance(x, list):
                x = x[0] if x else 0
            if isinstance(x, (int, float)):
                return x
            if isinstance(x, str):
                if len(x) == 1 and not x.isdigit():
                    return ord(x)
                try:
                    return int(x)
                except (ValueError, TypeError):
                    pass
                try:
                    return float(x)
                except (ValueError, TypeError):
                    pass
            return x
        a = _to_num(a)
        b = _to_num(b)
        if op == "+":  return a + b
        if op == "-":  return a - b
        if op == "*":  return a * b
        if op == "/":
            if b == 0:
                raise RuntimeError("Division by zero")
            return a / b
        if op == "//":
            if b == 0:
                raise RuntimeError("Integer division by zero")
            return int(a) // int(b)
        if op == "%":
            if b == 0:
                raise RuntimeError("Modulo by zero")
            return int(a) % int(b)
        if op == "**": return a ** b
        if op == "^":  return a ** b

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
            if isinstance(x, str) and len(x) == 1:
                return ord(x)
            return x
        a = to_num(a)
        b = to_num(b)
        if op == "<=": return a <= b
        if op == ">=": return a >= b
        if op == "<":  return a < b
        if op == ">":  return a > b
        if op == "==": return a == b
        if op == "!=": return a != b
    
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