class RegAllocator:
    def __init__(self):
        self._map   = {}   
        self._count = 0

    def get(self, name):
        if name not in self._map:
            self._count += 1
            self._map[name] = f"R{self._count}"
        return self._map[name]

    def reset(self):
        self._map.clear()
        self._count = 0

class CodeGenerator:
    def __init__(self):
        self.instructions = []
        self.regs         = RegAllocator()
        self._label_set   = set()  

    def generate(self, quads):
        self.instructions.clear()
        self.regs.reset()
        self._label_set = {q.arg1 for q in quads if q.op == "LABEL" and q.arg1}

        for q in quads:
            self._emit_quad(q)

        return self.instructions

    def get_code(self):
        return "\n".join(self.instructions)

    def print_code(self):
        print("\n" + "=" * 60)
        print("  TARGET CODE (Pseudo-Assembly)")
        print("=" * 60)
        for line in self.instructions:
            print(line)
        print("=" * 60)
        print("Code generation successful.")

    def _emit_quad(self, q):
        op, arg1, arg2, result = q.op, q.arg1, q.arg2, q.result

        if op == "LABEL":
            self.instructions.append(f"\n{arg1}:")
            return

        if op == "FUNC_BEGIN":
            self.instructions.append(f"\n; ── function {arg1} ──────────────────")
            self.instructions.append(f"{arg1}:")
            self.instructions.append(f"    PUSH  FP")
            self.instructions.append(f"    MOV   FP, SP")
            return

        if op == "FUNC_END":
            self.instructions.append(f"    POP   FP")
            self.instructions.append(f"    RET")
            self.instructions.append(f"; ── end {arg1} ────────────────────────")
            return

        if op == "FPARAM":
            r = self.regs.get(arg1)
            self.instructions.append(f"    POP   {r}          ; param {arg1} : {arg2}")
            return

        if op == "DECLARE":
            r = self.regs.get(arg1)
            self.instructions.append(f"    ALLOC {r}          ; {arg2} {arg1}")
            return

        if op == "ARRAY_DECL":
            total_bytes = int(arg2) * 4
            self.instructions.append(
                f"    ALLOC [{arg1}], {total_bytes}  "
                f"; {result}[{arg2}] ({total_bytes} bytes)"
            )
            return

        if op == "=":
            r_dst = self.regs.get(result)
            r_src = self._operand(arg1)
            self.instructions.append(f"    MOV   {r_dst}, {r_src}")
            return

        _BINOP = {
            "+":  "ADD", "-":  "SUB", "*":  "MUL", "/":  "DIV",
            "//": "IDIV", "%": "MOD", "^":  "POW",
            "&&": "AND", "||": "OR",
            "==": "EQ",  "!=": "NEQ",
            "<":  "LT",  ">":  "GT", "<=": "LEQ", ">=": "GEQ",
        }
        if op in _BINOP:
            r_dst  = self.regs.get(result)
            r_left = self._operand(arg1)
            r_right= self._operand(arg2)
            mnemonic = _BINOP[op]
            self.instructions.append(f"    {mnemonic:<5} {r_dst}, {r_left}, {r_right}")
            return

        if op == "!":
            r_dst = self.regs.get(result)
            r_src = self._operand(arg1)
            self.instructions.append(f"    NOT   {r_dst}, {r_src}")
            return

        if op == "[]=":
            r_off = self._operand(arg2)
            r_val = self._operand(result)
            self.instructions.append(f"    STR   [{arg1} + {r_off}], {r_val}")
            return

        if op == "=[]":
            r_dst = self.regs.get(result)
            r_off = self._operand(arg2)
            self.instructions.append(f"    LDR   {r_dst}, [{arg1} + {r_off}]")
            return

        if op == "GOTO":
            self.instructions.append(f"    JMP   {result}")
            return

        if op == "IF_FALSE":
            r_cond = self._operand(arg1)
            self.instructions.append(f"    CMP   {r_cond}, 0")
            self.instructions.append(f"    JEQ   {result}")
            return

        if op == "IF_TRUE":
            r_cond = self._operand(arg1)
            self.instructions.append(f"    CMP   {r_cond}, 0")
            self.instructions.append(f"    JNE   {result}")
            return

        if op == "PARAM":
            r_val = self._operand(arg1)
            self.instructions.append(f"    PUSH  {r_val}")
            return

        if op == "CALL":
            r_ret = self.regs.get(result) if result else self.regs.get("__ret__")
            self.instructions.append(f"    CALL  {arg1}")
            self.instructions.append(f"    MOV   {r_ret}, R0   ; closure → {r_ret}")
            return

        if op in ("closure", "RETURN"):
            if arg1 is not None:
                r_val = self._operand(arg1)
                self.instructions.append(f"    MOV   R0, {r_val}  ; return {arg1}")
            self.instructions.append(f"    POP   FP")
            self.instructions.append(f"    RET")
            return

        if op == "SPILL":
            r_val = self._operand(arg1)
            self.instructions.append(f"    PRINT {r_val}")
            return

        if op == "READ":
            r_dst = self.regs.get(result)
            self.instructions.append(f"    SCAN  {r_dst}")
            return

        if op == "CORE_BEGIN":
            r_var = self._operand(arg1)
            self.instructions.append(f"    ; switch ({arg1}) → {r_var}")
            return

        if op == "MEMORY":
            self.instructions.append(f"    ; case {arg1}:")
            return

        if op == "CORE_END":
            self.instructions.append(f"    ; end switch")
            return

        def _f(x): return str(x) if x is not None else "_"
        self.instructions.append(
            f"    ; [{_f(op)}  {_f(arg1)}  {_f(arg2)}  {_f(result)}]"
        )

    def _operand(self, name):
        if name is None:
            return "0"
        s = str(name)
        try:
            int(s)
            return f"#{s}"
        except ValueError:
            pass
        try:
            float(s)
            return f"#{s}"
        except ValueError:
            pass
        if (s.startswith('"') and s.endswith('"')) or \
           (s.startswith("'") and s.endswith("'")):
            return s
        if s in ("trust", "betray"):
            return f"#{'1' if s == 'trust' else '0'}"
        return self.regs.get(s)

def generate_code(tac_walker, terminal=None):
    cg = CodeGenerator()
    cg.generate(tac_walker.gen.quads)
    if terminal:
        terminal.log("Code generation complete.")
    return cg
