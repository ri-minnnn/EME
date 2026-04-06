
from semantic import flatten_expr, lookup, resolve_type


# ══════════════════════════════════════════════════════════════
#  QUADRUPLE CLASS
# ══════════════════════════════════════════════════════════════
class Quadruple:
    def __init__(self, op, arg1, arg2, result):
        self.op     = op       # e.g. '+', '-', '=', 'GOTO', 'IF_FALSE', 'LABEL', 'PARAM', 'CALL'
        self.arg1   = arg1     # first operand  (None if unused)
        self.arg2   = arg2     # second operand (None if unused)
        self.result = result   # destination    (None if unused)

    def __repr__(self):
        def fmt(x): return str(x) if x is not None else "_"
        return f"({fmt(self.op):<12} {fmt(self.arg1):<12} {fmt(self.arg2):<12} {fmt(self.result)})"


# ══════════════════════════════════════════════════════════════
#  TAC GENERATOR
# ══════════════════════════════════════════════════════════════
class TACGenerator:
    def __init__(self):
        self.quads       = []   # final list of Quadruple
        self.temp_count  = 0
        self.label_count = 0
        self.scope_stack = [{}] # mirrors semantic scope for value lookup
        self.current_function = None  # Track current function for better debugging

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


    # ══════════════════════════════════════════════════════════
    #  EXPRESSION HANDLER
    #  Walks your flatten_expr() token list and emits quads
    # ══════════════════════════════════════════════════════════

    def gen_expr(self, tokens):
        """
        Takes a flat token list from flatten_expr() and returns
        the temp/variable holding the final result.
        """
        if not tokens:
            return None
            
        tokens = [t for t in tokens if t not in (";",)]
        if not tokens:
            return None

        # ── Single token (literal or variable) ──
        if len(tokens) == 1:
            return tokens[0]

        # ── Unary NOT:  ! expr ──
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

        # ── Array index read:  name [ index_expr ] ──
        # Detect tokens like: ["NUMBERS", "[", "I", "]"]
        # or as sub-expression within larger expression (handled via _find_op skipping [...])
        if "[" in tokens and tokens[-1] == "]":
            bracket_open = tokens.index("[")
            # Make sure the last ] closes this [ at depth 0
            depth = 0
            close_idx = None
            for i in range(bracket_open, len(tokens)):
                if tokens[i] == "[": depth += 1
                elif tokens[i] == "]":
                    depth -= 1
                    if depth == 0:
                        close_idx = i
                        break
            if close_idx == len(tokens) - 1 and bracket_open > 0:
                arr_name  = self.gen_expr(tokens[:bracket_open])
                index_val = self.gen_expr(tokens[bracket_open+1:close_idx])
                t = self.new_temp()
                self.emit("=[]", arr_name, index_val, t)
                return t

        # ── Binary operators (respects precedence via split order) ──
        # Priority order (lowest to highest precedence, split rightmost first):
        # ||  →  &&  →  relational  →  +/-  →  *// %  →  ^

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

        # ── Unary prefix ++/-- (e.g. ++x) ──
        if tokens[0] in ("++", "--") and len(tokens) == 2:
            var = tokens[1]
            op  = "+" if tokens[0] == "++" else "-"
            t   = self.new_temp()
            self.emit(op, var, "1", t)
            self.emit("=", t, None, var)
            return var

        # ── Postfix ++/-- (e.g. x++) ──
        if tokens[-1] in ("++", "--") and len(tokens) == 2:
            var = tokens[0]
            op  = "+" if tokens[-1] == "++" else "-"
            t   = self.new_temp()
            self.emit(op, var, "1", t)
            self.emit("=", t, None, var)
            return t  # Return old value for postfix

        # ── echo function call:  echo funcName ( args ) ──
        if tokens[0] == "echo" and len(tokens) >= 4 and "(" in tokens:
            return self._gen_echo_call(tokens)

        # ── Function call without echo ──
        if len(tokens) >= 3 and "(" in tokens:
            return self._gen_function_call(tokens)

        # Fallback
        return tokens[0]


    def _find_op(self, tokens, ops):
        """
        Find the RIGHTMOST operator from ops at depth 0.
        Rightmost = left-associative evaluation.
        Depth tracks both () and [] so operators inside array indices are skipped.
        """
        depth = 0
        result_idx = None
        for i, tok in enumerate(tokens):
            if tok in ("(", "["): depth += 1
            elif tok in (")", "]"): depth -= 1
            elif depth == 0 and tok in ops:
                result_idx = i   # keep updating → rightmost
        return result_idx

    def _gen_function_call(self, tokens):
        """Handle: funcName ( arg1, arg2, ... )"""
        func_name = tokens[0]
        
        # Find parentheses
        try:
            paren_start = tokens.index("(")
        except ValueError:
            return tokens[0]
            
        arg_tokens = tokens[paren_start+1:-1]

        # Split by commas at depth 0
        args, cur, depth = [], [], 0
        for tok in arg_tokens:
            if tok == "(": depth += 1; cur.append(tok)
            elif tok == ")": depth -= 1; cur.append(tok)
            elif tok == "," and depth == 0:
                if cur: args.append(cur); cur = []
            else:
                cur.append(tok)
        if cur: args.append(cur)

        # Emit PARAM for each arg
        for arg in args:
            val = self.gen_expr(arg)
            self.emit("PARAM", val, None, None)

        # Emit CALL and store result in temp
        t = self.new_temp()
        self.emit("CALL", func_name, str(len(args)), t)
        return t

    def _gen_echo_call(self, tokens):
        """Handle: echo funcName ( arg1, arg2, ... )"""
        # echo funcName ( args )
        func_name = tokens[1]
        
        # Find parentheses
        try:
            paren_start = tokens.index("(")
        except ValueError:
            return tokens[0]
            
        arg_tokens = tokens[paren_start+1:-1]

        # Split by commas at depth 0
        args, cur, depth = [], [], 0
        for tok in arg_tokens:
            if tok == "(": depth += 1; cur.append(tok)
            elif tok == ")": depth -= 1; cur.append(tok)
            elif tok == "," and depth == 0:
                if cur: args.append(cur); cur = []
            else:
                cur.append(tok)
        if cur: args.append(cur)

        # Emit PARAM for each arg
        for arg in args:
            val = self.gen_expr(arg)
            self.emit("PARAM", val, None, None)

        # Emit CALL (echo doesn't need to store result)
        self.emit("CALL", func_name, str(len(args)), None)
        return None


    # ══════════════════════════════════════════════════════════
    #  STATEMENT GENERATORS
    # ══════════════════════════════════════════════════════════

    def gen_assign(self, var_name, rhs_tokens):
        """var_name = expression"""
        val = self.gen_expr(rhs_tokens)
        self.emit("=", val, None, var_name)

    def gen_compound_assign(self, var_name, op, rhs_tokens):
        """var_name += / -= / *= ... expression"""
        # e.g.  +=  becomes  var = var + rhs
        arith_op = op[0]   # '+=' → '+'
        rhs_val  = self.gen_expr(rhs_tokens)
        t = self.new_temp()
        self.emit(arith_op, var_name, rhs_val, t)
        self.emit("=", t, None, var_name)

    def gen_array_store(self, arr_name, index, rhs_tokens):
        """arr_name[index] = expression"""
        val = self.gen_expr(rhs_tokens)
        self.emit("[]=", arr_name, index, val)   # arr[index] = val

    def gen_array_load(self, arr_name, index):
        """t = arr_name[index]"""
        t = self.new_temp()
        self.emit("=[]", arr_name, index, t)     # t = arr[index]
        return t

    # ── SPILL (print) ──
    def gen_spill(self, tokens):
        """Print a string or expression"""
        # Handle string literals directly
        if tokens and isinstance(tokens[0], str) and tokens[0].startswith('"'):
            self.emit("SPILL", tokens[0], None, None)
        else:
            val = self.gen_expr(tokens)
            self.emit("SPILL", val, None, None)

    # ── READ (input) ──
    def gen_read(self, var_name):
        self.emit("READ", None, None, var_name)

    # ── HOPE / DESPAIR (if / else if / else) ──
    def gen_hope(self, cond_tokens, stmt_gen_fn, else_gen_fn=None):
        """
        cond_tokens  : flat token list for condition
        stmt_gen_fn  : callable → generates quads for the hope body
        else_gen_fn  : callable → generates quads for despair body (optional)
        """
        cond     = self.gen_expr(cond_tokens)
        else_lbl = self.new_label()
        end_lbl  = self.new_label()

        self.emit("IF_FALSE", cond, None, else_lbl)
        stmt_gen_fn()                          # hope body

        if else_gen_fn:
            self.emit("GOTO", None, None, end_lbl)
            self.emit_label(else_lbl)
            else_gen_fn()                      # despair body
            self.emit_label(end_lbl)
        else:
            self.emit_label(else_lbl)

    # ── DESIRE (for loop) ──
    def gen_desire(self, init_fn, cond_tokens, update_fn, body_fn):
        """
        init_fn      : callable → emits init quads (e.g. i = 0)
        cond_tokens  : flat token list for condition
        update_fn    : callable → emits update quads (e.g. i++)
        body_fn      : callable → emits loop body quads
        """
        start_lbl = self.new_label()
        end_lbl   = self.new_label()

        init_fn()
        self.emit_label(start_lbl)

        cond = self.gen_expr(cond_tokens)
        self.emit("IF_FALSE", cond, None, end_lbl)

        body_fn()
        update_fn()

        self.emit("GOTO", None, None, start_lbl)
        self.emit_label(end_lbl)

    # ── WHILE loop ──
    def gen_while(self, cond_tokens, body_fn):
        start_lbl = self.new_label()
        end_lbl   = self.new_label()

        self.emit_label(start_lbl)
        cond = self.gen_expr(cond_tokens)
        self.emit("IF_FALSE", cond, None, end_lbl)

        body_fn()

        self.emit("GOTO", None, None, start_lbl)
        self.emit_label(end_lbl)

    # ── DO-WHILE loop ──
    def gen_do_while(self, body_fn, cond_tokens):
        start_lbl = self.new_label()

        self.emit_label(start_lbl)
        body_fn()

        cond = self.gen_expr(cond_tokens)
        self.emit("IF_TRUE", cond, None, start_lbl)

    # ── HEART function declaration ──
    def gen_heart_begin(self, func_name, param_names):
        self.current_function = func_name
        self.emit("FUNC_BEGIN", func_name, None, None)
        for p in param_names:
            self.emit("FPARAM", p, "int", None)

    def gen_heart_end(self, func_name):
        self.emit("FUNC_END", func_name, None, None)
        self.current_function = None

    # ── CLOSURE (return) ──
    def gen_closure(self, tokens):
        if tokens and tokens[0] is not None:
            # Handle return with value
            if tokens[0] == "0" or tokens[0] == "θ":
                self.emit("RETURN", "0", None, None)
            else:
                val = self.gen_expr(tokens)
                self.emit("RETURN", val, None, None)
        else:
            # Handle return without value
            self.emit("RETURN", None, None, None)

    # ── CORE / MEMORY (switch / case) ──
    def gen_core_begin(self, var):
        self.emit("CORE_BEGIN", var, None, None)

    def gen_memory(self, label, body_fn, end_lbl):
        """One memory (case) block"""
        self.emit("MEMORY", label, None, None)
        body_fn()
        self.emit("GOTO", None, None, end_lbl)   # break equivalent

    def gen_core_end(self, end_lbl):
        self.emit_label(end_lbl)
        self.emit("CORE_END", None, None, None)