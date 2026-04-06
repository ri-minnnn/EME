from tac import TACGenerator, Quadruple
from semantic import flatten_expr


class TACWalker:

    def __init__(self):
        self.gen          = TACGenerator()   # quadruple emitter
        self.scope_stack  = [{}]             # mirrors semantic scope
        self.func_table   = {}               # function name → return type
        self.loop_stack   = []               # track nested loops for break/continue
        self.var_types    = {}               # var_name → declared dtype (for type conversion)

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
        tokens = [t for t in flatten_expr(node) if t not in (";",)]
        return self.gen.gen_expr(tokens)

    def gen_expr_tokens(self, tokens):
        tokens = [t for t in tokens if t not in (";",)]
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
            self.emit("ARRAY_DECL", name, str(size_token), dtype)
            elements = self._extract_elements(dec.get("arOpt") or {})
            for i, elem in enumerate(elements):
                self.emit("[]=", name, str(i), str(elem))
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
            self.emit("closure", tokens[0] if tokens else None, None, None)
        self.pop_scope()
        self.emit("FUNC_END", name, None, None)

    def _walk_closure(self, node):
        if node is None:
            self.emit("closure", None, None, None)
            return
        tokens = [t for t in flatten_expr(node) if t != ";"]
        self.emit("closure", tokens[0] if tokens else None, None, None)

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
                t = self.new_temp()
                self.emit("READ", None, None, t)
                self.emit("[]=", var_name, str(idx), t)
            else:
                self.emit("READ", None, None, var_name)
        elif kind == "spill":
            self._walk_spill(node)
        elif kind == "echo":
            self._walk_echo_call(node.get("name", ""), node.get("echOp"))
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
            self.emit("ARRAY_DECL", name, str(size_token), dtype)
            elements = self._extract_elements(loc_dec.get("arOpt") or {})
            for i, elem in enumerate(elements):
                self.emit("[]=", name, str(i), str(elem))
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
            self.emit("ARRAY_DECL", name, str(size_token), dtype)
            elements = self._extract_elements(fix_loc_dec.get("fArray") or fix_loc_dec)
            for i, elem in enumerate(elements):
                self.emit("[]=", name, str(i), str(elem))
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

        # ── Function call: foo(...) ──────────────────────────────────────
        if id_type == "idCallExpr":
            self._walk_echo_call(var, idExpr.get("echOp"))
            return

        # ── Array element statement: A[i] = ..., A[i]++, A[i]-- ─────────
        if id_type == "idExpr" and idExpr.get("index") is not None:
            index = self.gen_expr_tokens(flatten_expr(idExpr.get("index")))
            arr_id_tail = idExpr.get("arrIDTail") or {}

            # Check for A[i]++ or A[i]-- first
            arr_tail_op = arr_id_tail.get("op", "")
            if arr_tail_op in ("++", "--"):
                self._walk_inc_dec(arr_tail_op, var, index)
                return

            # Otherwise it's an assignment: A[i] = expr
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
                self.emit("[]=", var, index, val)
            return

        # ── Plain postfix ++/-- on variable: x++ x-- ────────────────────
        if id_type in ("postInc", "postDec"):
            self._walk_inc_dec("++" if id_type == "postInc" else "--", var)
            return

        # ── Plain variable assignment / compound assignment ──────────────
        op          = idExpr.get("op", "=")
        arr_id_tail = idExpr.get("arrIDTail") or {}
        arr_tail_op = arr_id_tail.get("op", "")

        # Catch plain x++ / x-- via arrIDTail op
        if arr_tail_op in ("++", "--"):
            self._walk_inc_dec(arr_tail_op, var)
            return

        # Compound assignment: x += expr, x -= expr, etc.
        if op in ("+=", "-=", "*=", "/=", "//=", "%=", "^="):
            rhs_node = idExpr.get("exprDec")
            if rhs_node:
                t = self.new_temp()
                self.emit(op[0], var, self.gen_expr(rhs_node), t)
                self.emit("=", t, None, var)
            return

        # Simple assignment: x = expr
        ass_val  = arr_id_tail.get("assVal") or {}
        rhs_node = ass_val if ass_val.get("kind") == "STRLIT" else ass_val.get("exprDec")
        if rhs_node:
            self.emit("=", self.gen_expr(rhs_node), None, var)

    def _walk_inc_dec(self, op, var, index=None):
        """
        Increment or decrement a plain variable or an array element.
          op    : "++" or "--"
          var   : variable name  (or array name when index is given)
          index : array index string/temp — None for plain variables
        """
        t = self.new_temp()
        if index is not None:
            # Array element:  A[index]++  →  t_read = A[index]; t = t_read ± 1; A[index] = t
            t_read = self.new_temp()
            self.emit("=[]", var, str(index), t_read)
            self.emit("+" if op == "++" else "-", t_read, "1", t)
            self.emit("[]=", var, str(index), t)
        else:
            # Plain variable:  x++  →  t = x ± 1; x = t
            self.emit("+" if op == "++" else "-", var, "1", t)
            self.emit("=", t, None, var)

    def _walk_spill(self, node):
        spill_opt = node.get("spillOpt", {}) or {}
        for arg in spill_opt.get("args", []):
            kind = arg.get("kind", "")
            if kind == "STRLIT":
                # String literal argument: spill("hello")
                val = arg.get("value")
                if val:
                    self.emit("SPILL", val, None, None)
            elif kind == "ID":
                name = arg.get("name")
                if name:
                    # Check for array subscript: spill(A[i])
                    # The parser stores the index inside unaOp.index
                    una_op = arg.get("unaOp") or {}
                    index  = una_op.get("index")
                    if index is not None:
                        t = self.new_temp()
                        self.emit("=[]", name, str(index), t)
                        self.emit("SPILL", t, None, None)
                    else:
                        # Plain variable: spill(x)
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
        # Body key varies by context: "stmt" at top level, "loopStmt" inside
        # while/do-while, "coreStmt" inside core/switch — check all three.
        body = node.get("stmt") or node.get("loopStmt") or node.get("coreStmt")
        if body:
            self.walk(body)
        if node.get("stmtOpTail"):
            self.walk(node["stmtOpTail"])
        self.pop_scope()
        hope_tail   = node.get("hopeTail", {}) or {}
        despair_opt = hope_tail.get("despairOpt")
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
        # Same multi-key body lookup as walk_hope
        body = node.get("stmt") or node.get("loopStmt") or node.get("coreStmt")
        if body:
            self.walk(body)
        if node.get("stmtOpTail"):
            self.walk(node["stmtOpTail"])
        self.pop_scope()
        inner_tail    = node.get("hopeTail", {}) or {}
        inner_despair = inner_tail.get("despairOpt")
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
        despair_opt = node.get("despairOpt")
        if despair_opt:
            self._walk_despair_opt(despair_opt)

    def walk_core(self, node):
        tokens  = [t for t in flatten_expr(node.get("condition") or {}) if t != ";"]
        var     = tokens[0] if tokens else "__core_var__"
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
        # new decl uses dinTail; existing var uses dinTail1
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
        comp_ops = {"+=", "-=", "*=", "/=", "//=", "%=", "^="}
        for i, tok in enumerate(tokens):
            if tok in comp_ops and i > 0:
                t = self.new_temp()
                self.emit(tok[0], tokens[i-1], self.gen_expr_tokens(tokens[i+1:]), t)
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
        cond_tokens = [t for t in flatten_expr(node.get("condition")) if t != ";"]
        self.emit("IF_TRUE", self.gen_expr_tokens(cond_tokens), None, start_lbl)
        self.pop_scope()
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