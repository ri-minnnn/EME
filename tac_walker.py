from semantic import flatten_expr
class Quadruple:
    def __init__(self, op, arg1, arg2, result):
        self.op     = op
        self.arg1   = arg1
        self.arg2   = arg2
        self.result = result

    def __repr__(self):
        def fmt(x): return str(x) if x is not None else "_"
        return f"({fmt(self.op):<12} {fmt(self.arg1):<12} {fmt(self.arg2):<12} {fmt(self.result)})"

class TACGenerator:
    def __init__(self):
        self.quads       = []
        self.temp_count  = 0
        self.label_count = 0
        self.scope_stack = [{}]
        self.current_function = None
        self.array_dims  = {}   # name -> {"size": n} or {"rows": r, "cols": c}

    # ── Helpers ───────────────────────────────────────────────
    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self):
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, op, arg1=None, arg2=None, result=None):
        q = Quadruple(op, arg1, arg2, result)
        self.quads.append(q)
        return result

    def emit_label(self, label):
        self.quads.append(Quadruple("LABEL", label, None, None))

    # ── Print table ───────────────────────────────────────────
    def print_quads(self):
        print(f"\n{'#':<5} {'OP':<12} {'ARG1':<12} {'ARG2':<12} {'RESULT'}")
        print("─" * 55)
        for i, q in enumerate(self.quads):
            def fmt(x): return str(x) if x is not None else "_"
            print(f"{i:<5} {fmt(q.op):<12} {fmt(q.arg1):<12} {fmt(q.arg2):<12} {fmt(q.result)}")
        print("─" * 55)
        print("TERMINAL")
        print("TAC generation successful.")

    def gen_expr(self, tokens):
        if not tokens:
            return None
        tokens = [t for t in tokens if t not in (";",)]
        if not tokens:
            return None

        # ── Single token ──
        if len(tokens) == 1:
            return tokens[0]

        # ── Unary NOT ──
        if tokens[0] == "!" and len(tokens) >= 2:
            operand = self.gen_expr(tokens[1:])
            t = self.new_temp()
            self.emit("!", operand, None, t)
            return t

        # ── Strip outer parentheses ──
        if tokens[0] == "(" and tokens[-1] == ")":
            depth = 0
            matched = True
            for i, tok in enumerate(tokens):
                if tok in ("(", "["): depth += 1
                elif tok in (")", "]"): depth -= 1
                if depth == 0 and i < len(tokens) - 1:
                    matched = False
                    break
            if matched:
                return self.gen_expr(tokens[1:-1])

        # ── Array index read:  name[idx]  or  name[row][col] ──
        if "[" in tokens and tokens[-1] == "]" and tokens.index("[") > 0:
            bracket_open = tokens.index("[")
            _BIN_OPS = {"||", "&&", "==", "!=", "<=", ">=", "<", ">",
                        "+", "-", "*", "/", "//", "%", "^"}
            _pfx_depth, _pfx_has_op = 0, False
            for _tok in tokens[:bracket_open]:
                if _tok in ("(", "["): _pfx_depth += 1
                elif _tok in (")", "]"): _pfx_depth -= 1
                elif _pfx_depth == 0 and _tok in _BIN_OPS:
                    _pfx_has_op = True
                    break
            if not _pfx_has_op:
                close_idx = tokens.index("]", bracket_open)
            if not _pfx_has_op and bracket_open > 0:
                arr_name = self.gen_expr(tokens[:bracket_open])
                # ── 2D: name[row][col] ──
                if close_idx < len(tokens) - 1 and tokens[close_idx + 1] == "[":
                    row_val = self.gen_expr(tokens[bracket_open + 1:close_idx])
                    b2 = close_idx + 1
                    close_idx2 = tokens.index("]", b2 + 1)
                    if close_idx2 == len(tokens) - 1: 
                        col_val    = self.gen_expr(tokens[b2 + 1:close_idx2])
                        total_cols = str(self.array_dims.get(arr_name, {}).get("cols", 1))
                        t1 = self.new_temp(); self.emit("*", row_val, total_cols, t1)
                        t2 = self.new_temp(); self.emit("+", t1, col_val, t2)
                        t3 = self.new_temp(); self.emit("*", t2, "4", t3)
                        t  = self.new_temp(); self.emit("=[]", arr_name, t3, t)
                        return t
                # ── 1D: name[index] ──
                elif close_idx == len(tokens) - 1:
                    index_val = self.gen_expr(tokens[bracket_open + 1:close_idx])
                    t_off = self.new_temp(); self.emit("*", index_val, "4", t_off)
                    t     = self.new_temp(); self.emit("=[]", arr_name, t_off, t)
                    return t

        # ── Binary operators (lowest to highest precedence) ──
        for op_group in ( 
            ["||"],
            ["&&"],
            ["==", "!=", "<=", ">=", "<", ">"],
            ["+", "-"],
            ["*", "/", "//", "%"],
            ["^"],
        ):
            idx = self._find_op(tokens, op_group)
            if idx is not None:
                left  = self.gen_expr(tokens[:idx])
                right = self.gen_expr(tokens[idx+1:])
                t = self.new_temp()
                self.emit(tokens[idx], left, right, t)
                return t
        # ── Unary prefix ++/-- ──
        if tokens[0] in ("++", "--") and len(tokens) == 2:
            var = tokens[1]
            op  = "+" if tokens[0] == "++" else "-"
            t   = self.new_temp()
            self.emit(op, var, "1", t)
            self.emit("=", t, None, var)
            return var
        # ── Postfix ++/-- ──
        if tokens[-1] in ("++", "--") and len(tokens) == 2:
            var = tokens[0]
            op  = "+" if tokens[-1] == "++" else "-"
            t   = self.new_temp()
            self.emit(op, var, "1", t)
            self.emit("=", t, None, var)
            return t
        # ── echo function call ──
        if tokens[0] == "echo":
            if len(tokens) >= 4 and "(" in tokens:
                return self._gen_echo_call(tokens)

    def _find_op(self, tokens, ops):
        depth = 0
        result_idx = None
        for i, tok in enumerate(tokens):
            if tok in ("(", "["): depth += 1
            elif tok in (")", "]"): depth -= 1
            elif depth == 0 and tok in ops:
                result_idx = i
        return result_idx

    def _gen_echo_call(self, tokens):
        func_name = tokens[1]
        paren_start = tokens.index("(")
        arg_tokens = tokens[paren_start+1:-1]
        args, cur, depth = [], [], 0
        for tok in arg_tokens:
            if tok == "(": depth += 1; cur.append(tok)
            elif tok == ")": depth -= 1; cur.append(tok)
            elif tok == "," and depth == 0:
                if cur: args.append(cur); cur = []
            else:
                cur.append(tok)
        if cur: args.append(cur)
        for arg in args:
            val = self.gen_expr(arg)
            self.emit("PARAM", val, None, None)
        t = self.new_temp()
        self.emit("CALL", func_name, str(len(args)), t)
        return t

class TACWalker:
    def __init__(self):
        self.gen          = TACGenerator()   
        self.scope_stack  = [{}]             
        self.func_table   = {}               
        self.loop_stack   = []              
        self.var_types    = {}               
        self.array_dims   = self.gen.array_dims 

    def emit(self, op, arg1=None, arg2=None, result=None):
        return self.gen.emit(op, arg1, arg2, result)

    def emit_label(self, lbl):
        self.gen.emit_label(lbl)

    def new_temp(self):
        return self.gen.new_temp()

    def new_label(self):
        return self.gen.new_label()

    def push_scope(self):
        self.scope_stack.append({})

    def pop_scope(self):
        if len(self.scope_stack) > 1:
            self.scope_stack.pop()

    def set_var(self, name, value=None): 
        self.scope_stack[-1][name] = value

    def gen_expr(self, node):
        return self.gen_expr_tokens(flatten_expr(node))

    def gen_expr_tokens(self, tokens):
        return self.gen.gen_expr(tokens)

    def walk(self, node):
        if node is None:
            return
        if not isinstance(node, dict):
            return
        t = node.get("type", "")
        method = getattr(self, f"walk_{t}", self.walk_generic)
        method(node)

    def walk_generic(self, node):
        for key, val in node.items():
            if key in ("type", "line"):
                continue
            if isinstance(val, dict):
                self.walk(val)
            elif isinstance(val, list):
                for item in val:
                    self.walk(item)

    def walk_program(self, node):
        if node.get("global"):
            self.walk(node["global"])
        if node.get("function"):
            self.walk(node["function"])
        self.emit("FUNC_BEGIN", "brain", None, None)
        self.push_scope()
        if node.get("stmt"):
            self.walk(node["stmt"])
        self.emit("closure", "0", None, None)
        self.pop_scope()
        self.emit("FUNC_END", "brain", None, None)

    def walk_global(self, node):
        for decl in node.get("declarations", []):
            self._walk_global_decl(decl)

    def _walk_global_decl(self, decl):
        dtype = decl.get("dtype", "")
        name  = decl.get("name", "")
        dec   = decl.get("dec", {}) or {}
        size_token = dec.get("size")
        if size_token is not None:
            ar_opt = dec.get("arOpt") or {}
            size2  = ar_opt.get("size2")
            if size2 is not None:
                rows, cols = int(size_token), int(size2)
                self.array_dims[name] = {"rows": rows, "cols": cols}
                self.emit("ARRAY_DECL", name, str(rows * cols), dtype)
                two_d = ar_opt.get("2dArray") or {}
                flat  = [str(lit) for row in two_d.get("rows", [])
                         for lit in row.get("literals", []) if lit is not None]
                for i, elem in enumerate(flat):
                    t_off = self.new_temp(); self.emit("*", str(i), "4", t_off)
                    self.emit("[]=", name, t_off, elem)
            else:
                self.array_dims[name] = {"size": int(size_token)}
                self.emit("ARRAY_DECL", name, str(size_token), dtype)
                elements = self._extract_elements(ar_opt)
                for i, elem in enumerate(elements):
                    t_off = self.new_temp(); self.emit("*", str(i), "4", t_off)
                    self.emit("[]=", name, t_off, str(elem))
            self.set_var(name)
            return
        self.set_var(name)
        self.var_types[name] = dtype
        self.emit("DECLARE", name, dtype, None)
        rhs_node = dec.get("value")
        if rhs_node:
            val = self.gen_expr(rhs_node)
            self.emit("=", val, None, name)
        g_dec_op = dec.get("gDecOp") or {}
        multi_v  = g_dec_op.get("multiV") or {}
        for extra in (multi_v.get("vars") or []):
            e_name = extra.get("name", "")
            self.set_var(e_name)
            self.var_types[e_name] = dtype
            self.emit("DECLARE", e_name, dtype, None)
            e_rhs = (extra.get("gDecOp") or {}).get("value")
            if e_rhs:
                val = self.gen_expr(e_rhs)
                self.emit("=", val, None, e_name)

    def walk_func(self, node):
        for func in node.get("functions", []):
            self._walk_heart(func)

    def _walk_heart(self, func):
        name       = func.get("name", "")
        params     = func.get("param", {}) or {}
        param_list = params.get("params", [])
        self.func_table[name] = func.get("return_type", "void")
        self.emit("FUNC_BEGIN", name, None, None)
        self.push_scope()
        for p in param_list:
            p_name = p.get("name", "")
            p_type = p.get("dtype", "")
            self.emit("FPARAM", p_name, p_type, None)
            self.set_var(p_name)
            self.var_types[p_name] = p_type
        if func.get("stmt"):
            self.walk(func["stmt"])
        closure = func.get("closureCon")
        if closure:
            tokens = [t for t in flatten_expr(closure) if t != ";"]
            ret_val = self.gen_expr_tokens(tokens) if tokens else None
            self.emit("closure", ret_val, None, None)
        self.pop_scope()
        self.emit("FUNC_END", name, None, None)

    def _walk_closure(self, node):
        if node is None:
            self.emit("closure", None, None, None)
            return
        tokens = [t for t in flatten_expr(node) if t != ";"]
        ret_val = self.gen_expr_tokens(tokens) if tokens else None
        self.emit("closure", ret_val, None, None)

    def walk_stmt(self, node):
        for stmt in node.get("stmts", []):
            self.walk(stmt)

    def walk_stmtOp(self, node):
        kind = node.get("kind", "")
        if kind in ("str", "dtype1"):
            self._walk_local_decl(node)
        elif kind == "fixed":
            self._walk_fixed_decl(node)
        elif kind == "ID":
            self._walk_id_stmt(node.get("name", ""), node.get("idExpr", {}) or {})
        elif kind == "read":
            var_name  = node.get("id", "")
            ele_index = node.get("eleIndex") or {}
            idx       = ele_index.get("index") if isinstance(ele_index, dict) else None
            if idx is not None:
                idx2_node = ele_index.get("index2") or {}
                idx2      = idx2_node.get("index") if isinstance(idx2_node, dict) else None
                t = self.new_temp()
                arr_type = self.var_types.get(var_name)
                if arr_type:
                    self.emit("DECLARE", t, arr_type, None)
                self.emit("READ", None, None, t)
                if idx2 is not None:
                    dims  = self.array_dims.get(var_name, {})
                    tcols = str(dims.get("cols", 1))
                    t1 = self.new_temp(); self.emit("*", str(idx), tcols, t1)
                    t2 = self.new_temp(); self.emit("+", t1, str(idx2), t2)
                    t3 = self.new_temp(); self.emit("*", t2, "4", t3)
                    self.emit("[]=", var_name, t3, t)
                else:
                    t_off = self.new_temp(); self.emit("*", str(idx), "4", t_off)
                    self.emit("[]=", var_name, t_off, t)
            else:
                self.emit("READ", None, None, var_name)
        elif kind == "spill":
            self._walk_spill(node)
        elif kind == "echo":
            fname = node.get("name", "")
            self._walk_echo_call(fname, node.get("echOp"))
        elif kind == "desire":
            self._walk_desire(node)
        elif kind == "while":
            self._walk_while(node)
        elif kind == "do":
            self._walk_do_while(node)
        elif kind == "una":
            self._walk_inc_dec(node.get("op", ""), node.get("name", ""))

    def _walk_local_decl(self, node):
        kind     = node.get("kind", "")
        dtype    = "str" if kind == "str" else node.get("dtype", "")
        name     = node.get("name", "")
        loc_dec  = node.get("locDec",  {}) or {}
        str_tail = node.get("strTail", {}) or {}
        size_token = loc_dec.get("index")
        if size_token is not None:
            ar_opt = loc_dec.get("arOpt") or {}
            size2  = ar_opt.get("size2")
            if size2 is not None:
                rows, cols = int(size_token), int(size2)
                self.array_dims[name] = {"rows": rows, "cols": cols}
                self.emit("ARRAY_DECL", name, str(rows * cols), dtype)
                two_d = ar_opt.get("2dArray") or {}
                flat  = [str(lit) for row in two_d.get("rows", [])
                         for lit in row.get("literals", []) if lit is not None]
                for i, elem in enumerate(flat):
                    t_off = self.new_temp(); self.emit("*", str(i), "4", t_off)
                    self.emit("[]=", name, t_off, elem)
            else:
                self.array_dims[name] = {"size": int(size_token)}
                self.emit("ARRAY_DECL", name, str(size_token), dtype)
                elements = self._extract_elements(ar_opt)
                for i, elem in enumerate(elements):
                    t_off = self.new_temp(); self.emit("*", str(i), "4", t_off)
                    self.emit("[]=", name, t_off, str(elem))
            self.set_var(name)
            return
        if kind == "str" and str_tail.get("index") is not None:
            self.emit("ARRAY_DECL", name, str(str_tail.get("index")), "str")
            self.set_var(name)
            return
        self.set_var(name)
        self.var_types[name] = dtype
        self.emit("DECLARE", name, dtype, None)
        loc_dec_op = loc_dec.get("locDecOp", {}) or {}
        str_tail1  = str_tail.get("strTail1", {}) or {}
        rhs_node   = loc_dec_op.get("value") or str_tail1.get("value")
        if rhs_node:
            val = self.gen_expr(rhs_node)
            self.emit("=", val, None, name)
        def process_locMV(mv):
            for extra in (mv.get("vars") or []):
                e_name = extra.get("name", "")
                self.set_var(e_name)
                self.var_types[e_name] = dtype
                self.emit("DECLARE", e_name, dtype, None)
                e_rhs = (extra.get("locDecOp") or {}).get("value")
                if e_rhs:
                    v = self.gen_expr(e_rhs)
                    self.emit("=", v, None, e_name)
                nested = (extra.get("locDecOp") or {}).get("locMV") or {}
                if nested.get("vars"):
                    process_locMV(nested)
        process_locMV(loc_dec_op.get("locMV") or {})

    def _walk_fixed_decl(self, node):
        lf          = node.get("locFDOp", {}) or {}
        name        = lf.get("name", "")
        dtype       = lf.get("dtype", "")
        fix_loc_dec = lf.get("fixLocDec") or {}
        size_token  = node.get("size") or lf.get("size") or fix_loc_dec.get("index")
        if size_token is not None:
            f_array = fix_loc_dec.get("fArray") or fix_loc_dec
            size2   = f_array.get("size2") if isinstance(f_array, dict) else None
            if size2 is not None:
                rows, cols = int(size_token), int(size2)
                self.array_dims[name] = {"rows": rows, "cols": cols}
                self.emit("ARRAY_DECL", name, str(rows * cols), dtype)
                two_d = f_array.get("2dArray") or {}
                flat  = [str(lit) for row in two_d.get("rows", [])
                         for lit in row.get("literals", []) if lit is not None]
                for i, elem in enumerate(flat):
                    t_off = self.new_temp(); self.emit("*", str(i), "4", t_off)
                    self.emit("[]=", name, t_off, elem)
            else:
                self.array_dims[name] = {"size": int(size_token)}
                self.emit("ARRAY_DECL", name, str(size_token), dtype)
                elements = self._extract_elements(f_array)
                for i, elem in enumerate(elements):
                    t_off = self.new_temp(); self.emit("*", str(i), "4", t_off)
                    self.emit("[]=", name, t_off, str(elem))
            self.set_var(name)
            return
        self.set_var(name)
        self.var_types[name] = dtype
        self.emit("DECLARE", name, dtype, None)
        rhs_node = lf.get("value")
        if rhs_node:
            val = self.gen_expr(rhs_node)
            self.emit("=", val, None, name)

    def _walk_id_stmt(self, var, idExpr):
        if not idExpr:
            return

        id_type = idExpr.get("type", "")

        # ── Function call: ───
        if id_type == "idCallExpr":
            self._walk_echo_call(var, idExpr.get("echOp"))
            return

        # ── Array element statement ─
        if id_type == "idExpr" and idExpr.get("index") is not None:
            row_val = self.gen_expr_tokens(flatten_expr(idExpr.get("index")))
            idx2_node = idExpr.get("index2") or {}
            idx2      = idx2_node.get("index") if isinstance(idx2_node, dict) else None
            arr_id_tail = idExpr.get("arrIDTail") or {}

            if idx2 is not None:
                col_val = str(idx2)
                dims    = self.array_dims.get(var, {})
                tcols   = str(dims.get("cols", 1))
                t1 = self.new_temp(); self.emit("*", row_val, tcols, t1)
                t2 = self.new_temp(); self.emit("+", t1, col_val, t2)
                t_offset = self.new_temp(); self.emit("*", t2, "4", t_offset)
            else:
                t_offset = self.new_temp(); self.emit("*", row_val, "4", t_offset)
            arr_tail_op = arr_id_tail.get("op", "")

            if arr_tail_op in ("++", "--"):
                self._walk_inc_dec(arr_tail_op, var, t_offset)
                return
            ass_val  = arr_id_tail.get("assVal") or {}
            rhs_node = None

            if ass_val.get("kind") == "STRLIT":
                rhs_node = ass_val
            elif ass_val.get("exprDec"):
                rhs_node = ass_val.get("exprDec")
            elif ass_val.get("value"):
                rhs_node = ass_val.get("value")
            elif arr_id_tail.get("exprDec"):
                rhs_node = arr_id_tail.get("exprDec")
            elif arr_id_tail.get("value"):
                rhs_node = arr_id_tail.get("value")
            elif idExpr.get("exprDec"):
                rhs_node = idExpr.get("exprDec")
            elif idExpr.get("value"):
                rhs_node = idExpr.get("value")

            if rhs_node:
                val = self.gen_expr(rhs_node)
            else:
                rhs_tokens = [t for t in flatten_expr(ass_val) if t not in (";",)]
                val = self.gen_expr_tokens(rhs_tokens) if rhs_tokens else None

            if val is not None:
                self.emit("[]=", var, t_offset, val)
            return

        # ── Plain postfix ++/-- on variable ────
        if id_type in ("postInc", "postDec"):
            self._walk_inc_dec("++" if id_type == "postInc" else "--", var)
            return

        # ── Plain variable assignment / compound assignment ───
        op          = idExpr.get("op", "=")
        arr_id_tail = idExpr.get("arrIDTail") or {}
        arr_tail_op = arr_id_tail.get("op", "")

        # Catch plain x++ / x-- 
        if arr_tail_op in ("++", "--"):
            self._walk_inc_dec(arr_tail_op, var)
            return

        # Compound assignment
        _COMP_OP = {"+=": "+", "-=": "-", "*=": "*", "/=": "/", "//=": "//", "%=": "%", "^=": "^"}
        if op in _COMP_OP:
            rhs_node = idExpr.get("exprDec")
            if rhs_node:
                t = self.new_temp()
                self.emit(_COMP_OP[op], var, self.gen_expr(rhs_node), t)
                self.emit("=", t, None, var)
            return

        # Simple assignment
        ass_val  = arr_id_tail.get("assVal") or {}
        rhs_node = ass_val if ass_val.get("kind") == "STRLIT" else ass_val.get("exprDec")
        if rhs_node:
            self.emit("=", self.gen_expr(rhs_node), None, var)

    def _walk_inc_dec(self, op, var, index=None):
        t = self.new_temp()
        if index is not None:
            t_read = self.new_temp()
            self.emit("=[]", var, str(index), t_read)
            self.emit("+" if op == "++" else "-", t_read, "1", t)
            self.emit("[]=", var, str(index), t)
        else:
            self.emit("+" if op == "++" else "-", var, "1", t)
            self.emit("=", t, None, var)

    def _walk_spill(self, node):
        spill_opt = node.get("spillOpt", {}) or {}
        for arg in spill_opt.get("args", []):
            kind = arg.get("kind", "")
            if kind == "STRLIT":
                val = arg.get("value")
                if val:
                    self.emit("SPILL", val, None, None)
            elif kind == "ID":
                name = arg.get("name")
                if name:
                    una_op  = arg.get("unaOp") or {}
                    ele_idx = una_op.get("eleIndex") or {}
                    index   = ele_idx.get("index") if isinstance(ele_idx, dict) else None
                    if index is not None:
                        idx2_node = ele_idx.get("index2") or {}
                        index2    = idx2_node.get("index") if isinstance(idx2_node, dict) else None
                        if index2 is not None:
                            dims  = self.array_dims.get(name, {})
                            tcols = str(dims.get("cols", 1))
                            t1 = self.new_temp(); self.emit("*", str(index), tcols, t1)
                            t2 = self.new_temp(); self.emit("+", t1, str(index2), t2)
                            t3 = self.new_temp(); self.emit("*", t2, "4", t3)
                            t  = self.new_temp(); self.emit("=[]", name, t3, t)
                        else:
                            t_off = self.new_temp(); self.emit("*", str(index), "4", t_off)
                            t     = self.new_temp(); self.emit("=[]", name, t_off, t)
                        self.emit("SPILL", t, None, None)
                    else:
                        self.emit("SPILL", name, None, None)
            else:
                tokens = [t for t in flatten_expr(arg)
                          if t not in (";", "ID", "spill")]
                if tokens:
                    result = self.gen_expr_tokens(tokens)
                    self.emit("SPILL", result, None, None)

    def _walk_echo_call(self, fname, ech_op_node):
        args = []
        if ech_op_node and isinstance(ech_op_node, dict):
            for arg in ech_op_node.get("args", []):
                args.append(flatten_expr(arg))
        for arg_tokens in args:
            self.emit("PARAM", self.gen_expr_tokens(arg_tokens), None, None)
        t = self.new_temp()
        self.emit("CALL", fname, str(len(args)), t)
        return t

    def walk_hope(self, node):
        cond_tokens = [t for t in flatten_expr(node.get("condition")) if t != ";"]
        cond        = self.gen_expr_tokens(cond_tokens)
        else_lbl    = self.new_label()
        end_lbl     = self.new_label()
        self.emit("IF_FALSE", cond, None, else_lbl)
        self.push_scope()
        body = node.get("stmt") or node.get("loopStmt") or node.get("coreStmt")
        if body:
            self.walk(body)
        if node.get("stmtOpTail"):
            self.walk(node["stmtOpTail"])
        self.pop_scope()
        hope_tail   = node.get("hopeTail") or node.get("hopeTailLoop") or {}
        despair_opt = hope_tail.get("despairOpt") or hope_tail.get("despairOptLoop")
        if despair_opt:
            self.emit("GOTO", None, None, end_lbl)
            self.emit_label(else_lbl)
            self._walk_despair_opt(despair_opt)
            self.emit_label(end_lbl)
        else:
            self.emit_label(else_lbl)

    def _walk_despair_opt(self, node):
        if node.get("condition"):
            cond_tokens = [t for t in flatten_expr(node["condition"]) if t != ";"]
            cond        = self.gen_expr_tokens(cond_tokens)
            inner_else  = self.new_label()
            inner_end   = self.new_label()
            self.emit("IF_FALSE", cond, None, inner_else)
        self.push_scope()
        body = node.get("stmt") or node.get("loopStmt") or node.get("coreStmt")
        if body:
            self.walk(body)
        if node.get("stmtOpTail"):
            self.walk(node["stmtOpTail"])
        self.pop_scope()
        inner_tail    = node.get("hopeTail") or node.get("hopeTailLoop") or {}
        inner_despair = inner_tail.get("despairOpt") or inner_tail.get("despairOptLoop")
        if node.get("condition"):
            if inner_despair:
                self.emit("GOTO", None, None, inner_end)
                self.emit_label(inner_else)
                self._walk_despair_opt(inner_despair)
                self.emit_label(inner_end)
            else:
                self.emit_label(inner_else)
        elif inner_despair:
            self._walk_despair_opt(inner_despair)

    def walk_hopeTail(self, node):
        despair_opt = node.get("despairOpt") or node.get("despairOptLoop")
        if despair_opt:
            self._walk_despair_opt(despair_opt)

    def walk_core(self, node):
        tokens  = [t for t in flatten_expr(node.get("condition") or {}) if t != ";"]
        var     = self.gen_expr_tokens(tokens) if tokens else "__core_var__"
        end_lbl = self.new_label()
        self.emit("CORE_BEGIN", var, None, None)
        body = node.get("body", {}) or {}
        for case in body.get("cases", []):
            self._walk_memory_case(case, var, end_lbl)
        default = body.get("default")
        if default:
            self._walk_default_case(default)
        self.emit_label(end_lbl)
        self.emit("CORE_END", None, None, None)

    def _walk_memory_case(self, case, switch_var, end_lbl):
        label    = str(case.get("memVal", ""))
        skip_lbl = self.new_label()
        t = self.new_temp()
        self.emit("==", switch_var, label, t)
        self.emit("IF_FALSE", t, None, skip_lbl)
        self.emit("MEMORY", label, None, None)
        self.push_scope()
        stmt_node = case.get("loopStmt") or case.get("coreStmt") or case.get("stmt")
        if stmt_node:
            self.walk(stmt_node)
        self.pop_scope()
        self.emit("GOTO", None, None, end_lbl)
        self.emit_label(skip_lbl)

    def _walk_default_case(self, stmt_node):
        self.emit("MEMORY", "default", None, None)
        self.push_scope()
        if stmt_node:
            self.walk(stmt_node)
        self.pop_scope()

    def _walk_desire(self, node):
        din           = node.get("din", {}) or {}
        dup           = node.get("dup")
        loop_var_name = din.get("name", "")
        din_kind      = din.get("kind", "")
        if din_kind == "decl":
            init_node = (din.get("dinTail") or {}).get("value")
        else:
            init_node = (din.get("dinTail1") or {}).get("value")

        start_lbl    = self.new_label()
        end_lbl      = self.new_label()
        continue_lbl = self.new_label()
        self.loop_stack.append({"break_lbl": end_lbl, "continue_lbl": continue_lbl})
        self.push_scope()

        if loop_var_name:
            self.set_var(loop_var_name)
            if din_kind == "decl":
                loop_dtype = din.get("dtype", "int")
                self.var_types[loop_var_name] = loop_dtype
                self.emit("DECLARE", loop_var_name, loop_dtype, None)
            if init_node:
                self.emit("=", self.gen_expr(init_node), None, loop_var_name)

        self.emit_label(start_lbl)
        cond_node = node.get("condition")
        if cond_node:
            cond_tokens = [t for t in flatten_expr(cond_node) if t != ";"]
            cond        = self.gen_expr_tokens(cond_tokens)
            self.emit("IF_FALSE", cond, None, end_lbl)

        loop_body = node.get("loopStmt")
        if loop_body:
            self.walk(loop_body)

        self.emit_label(continue_lbl)
        dup = node.get("dup")
        if dup:
            dup_tokens = [t for t in flatten_expr(dup) if t not in (";", "ID", "INT", "FLOAT", "STRING", "BOOL")]
            self._emit_update(dup_tokens, loop_var_name)

        self.emit("GOTO", None, None, start_lbl)
        self.emit_label(end_lbl)
        self.loop_stack.pop()
        self.pop_scope()

    def _emit_update(self, tokens, loop_var):
        if not tokens:
            return
        cleaned = [t for t in tokens if t not in ("ID", "INT", "FLOAT", "STRING", "BOOL")]
        tokens = cleaned
        if len(tokens) == 2 and tokens[1] in ("++", "--"):
            t = self.new_temp()
            self.emit("+" if tokens[1] == "++" else "-", tokens[0], "1", t)
            self.emit("=", t, None, tokens[0])
            return
        if len(tokens) == 2 and tokens[0] in ("++", "--"):
            t = self.new_temp()
            self.emit("+" if tokens[0] == "++" else "-", tokens[1], "1", t)
            self.emit("=", t, None, tokens[1])
            return
        _COMP_OP = {"+=": "+", "-=": "-", "*=": "*", "/=": "/", "//=": "//", "%=": "%", "^=": "^"}
        for i, tok in enumerate(tokens):
            if tok in _COMP_OP and i > 0:
                t = self.new_temp()
                self.emit(_COMP_OP[tok], tokens[i-1], self.gen_expr_tokens(tokens[i+1:]), t)
                self.emit("=", t, None, tokens[i-1])
                return
        self.gen_expr_tokens(tokens)

    def _walk_while(self, node):
        start_lbl    = self.new_label()
        end_lbl      = self.new_label()
        continue_lbl = self.new_label()
        self.loop_stack.append({"break_lbl": end_lbl, "continue_lbl": continue_lbl})
        cond_tokens = [t for t in flatten_expr(node.get("condition")) if t != ";"]
        self.emit_label(start_lbl)
        self.emit("IF_FALSE", self.gen_expr_tokens(cond_tokens), None, end_lbl)
        self.push_scope()
        if node.get("loopStmt"):
            self.walk(node["loopStmt"])
        self.emit_label(continue_lbl)
        self.pop_scope()
        self.emit("GOTO", None, None, start_lbl)
        self.emit_label(end_lbl)
        self.loop_stack.pop()

    def _walk_do_while(self, node):
        start_lbl    = self.new_label()
        continue_lbl = self.new_label()
        end_lbl      = self.new_label()
        self.loop_stack.append({"break_lbl": end_lbl, "continue_lbl": continue_lbl})
        self.emit_label(start_lbl)
        self.push_scope()
        if node.get("loopStmt"):
            self.walk(node["loopStmt"])
        self.emit_label(continue_lbl)
        self.pop_scope()
        cond_tokens = [t for t in flatten_expr(node.get("condition")) if t != ";"]
        self.emit("IF_TRUE", self.gen_expr_tokens(cond_tokens), None, start_lbl)
        self.emit_label(end_lbl)
        self.loop_stack.pop()

    def walk_loopStmt(self, node):
        if node.get("break") == "down":
            if self.loop_stack:
                self.emit("GOTO", None, None, self.loop_stack[-1]["break_lbl"])
            return
        if node.get("continue") == "over":
            if self.loop_stack:
                self.emit("GOTO", None, None, self.loop_stack[-1]["continue_lbl"])
            return
        if node.get("return") is not None:
            self._walk_closure(node.get("return"))
            return
        for stmt in node.get("stmts", []):
            self.walk(stmt)

    def walk_coreStmt(self, node):
        if node.get("continue") == "over":
            return
        if node.get("return") is not None:
            self._walk_closure(node.get("return"))
            return
        for stmt in node.get("stmts", []):
            self.walk(stmt)

    def walk_stmtOpt1(self, node):
        if node.get("return") is not None:
            self._walk_closure(node.get("return"))
        if node.get("stmt"):
            self.walk(node["stmt"])

    def walk_stmtOpTail(self, node):
        if node.get("return") is not None:
            self._walk_closure(node.get("return"))

    def _extract_elements(self, node):
        if not node or not isinstance(node, dict):
            return []
        lits = node.get("literals")
        if lits is not None:
            return [str(e) for e in lits if e is not None]
        elems = node.get("elements") or {}
        if isinstance(elems, dict):
            lits = elems.get("literals", [])
            return [str(e) for e in lits if e is not None]
        result = []
        for row in node.get("rows", []):
            if isinstance(row, dict):
                for lit in row.get("literals", []):
                    if lit is not None:
                        result.append(str(lit))
        return result

    def generate(self, parse_tree):
        self.walk(parse_tree)
        return self.gen.quads

    def print_quads(self):
        self.gen.print_quads()

def generate_tac(parse_tree, terminal=None):
    walker = TACWalker()
    walker.generate(parse_tree)
    if terminal:
        terminal.log("TAC generation complete.")
    return walker