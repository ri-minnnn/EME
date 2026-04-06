from FRST import FIRST as FST
from FF import FOLLOW as FF

class SyntaxAnalyzer:
    def __init__(self, tokens, terminal=None):
        lex_errors = [t for t in tokens if "error" in str(t[1]).lower() or str(t[1]).lower() in ["invalid", "unknown"]]
        if lex_errors:
            val, t_type, line, col = lex_errors[0]
            err_msg = f"Lexical Error: Found '{val}' at line {line}, col {col}. Syntax Analysis aborted."
            if terminal: terminal.log(err_msg)
            raise Exception(err_msg)
        self.tokens = tokens
        self.terminal = terminal
        self.pos = 0

    def get_token_info(self):
        ignore = ["space", "newline", "tab", "ocmt", "mcmt"]
        while self.pos < len(self.tokens):
            t_type = self.tokens[self.pos][1]
            if t_type in ignore: self.pos += 1
            else: break
        if self.pos >= len(self.tokens):
            last_line = self.tokens[-1][2] if self.tokens else 1
            last_col = self.tokens[-1][3] if self.tokens else 1
            return ("$", "$", last_line, last_col)
        return self.tokens[self.pos]

    def peek_token(self, offset=1):
        count = 0
        ignore = ["space", "newline", "tab", "ocmt", "mcmt"]
        temp_pos = self.pos
        while temp_pos < len(self.tokens):
            t_type = self.tokens[temp_pos][1]
            if t_type not in ignore:
                if count == offset: return self.tokens[temp_pos]
                count += 1
            temp_pos += 1
        return ("$", "$", 0, 0)

    def error(self, expected, local_follow=None):
        val, t_type, line, col = self.get_token_info()
        found = "$" if val == "$" else val
        combined = []
        for e in expected:
            if e not in combined and e != "λ":
                combined.append(e)
        expected_str = ", ".join([f"'{item}'" for item in combined])
        if len(combined) > 1:
            expected_str = f"( {expected_str} )"
        msg = f"Syntax Error : Line {line} Column {col} . EXPECTED {expected_str} . BUT FOUND '{found}'"
        if self.terminal: self.terminal.log(msg)
        raise Exception(msg)

    def match(self, expected, follow=None):
        val, t_type, line, col = self.get_token_info()
        is_id_match = (expected == "ID" and t_type.startswith("ID"))
        if val == expected or t_type == expected or is_id_match:
            self.pos += 1
            return val
        else:
            if isinstance(expected, list):
                self.error(expected, follow)
            else:
                self.error([expected], follow)

    def parse_program(self):
        _, _, line, _ = self.get_token_info()
        node = {"type": "program", "global": None, "function": None, "stmt": None, "line": line}
        val, t_type, line, col = self.get_token_info()
        if t_type in FST["global"] or val == "fixed" or t_type.startswith("ID"):
            node["global"] = self.parse_global({"heart", "void", "brain"} | FST["dtype"])
        val, t_type, line, col = self.get_token_info()
        if t_type in FST["dtype"] or val == "void":
            node["function"] = self.parse_func({"brain"})
        self.match("brain")
        self.match("(")
        self.match(")")
        self.match("{")
        node["stmt"] = self.parse_stmt({"closure", "}"})
        self.match("closure")
        self.match("0")
        self.match(";")
        self.match("}")
        return node

    def parse_global(self, local_follow):
        node = {"type": "global", "declarations": []}
        val, t_type, line, col = self.get_token_info()
        if t_type in ["brain", "void"]:
            return node
        if t_type in FST["dtype"]:
            decl_line = line
            self.pos += 1
            nv, nt, nl, nc = self.get_token_info()
            if nt != "ID" and not nt.startswith("ID") and nv != "heart":
                self.error(["ID", "heart"])
            if nv == "heart":
                self.pos -= 1
                return node
            decl = {"type": "global", "dtype": val, "line": decl_line}
            decl["name"] = self.match("ID", FST["gDec"] | {";"})
            decl["dec"] = self.parse_gDec({";"})
            node["declarations"].append(decl)
            self.match(";", FST["global"] | local_follow)
            rest = self.parse_global(local_follow)
            node["declarations"].extend(rest["declarations"])
        elif val == "fixed":
            decl_line = line
            self.pos += 1
            decl = {"type": "global", "fixed": True, "line": decl_line}
            decl["dtype"] = self.parse_dtype(FST["dtype"])
            decl["name"] = self.match("ID", FST["fDec"] | {";"})
            decl["dec"] = self.parse_fDec({";"})
            node["declarations"].append(decl)
            self.match(";", FST["global"] | local_follow)
            rest = self.parse_global(local_follow)
            node["declarations"].extend(rest["declarations"])
        elif t_type in FST["func"] and val == "brain":
            return node
        else:
            self.error(list(FF["global"]), local_follow)
        return node

    def parse_dtype(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        if t_type == "str":
            self.pos += 1
            return val
        elif t_type in FST["dtype1"]:
            return self.parse_dtype1(local_follow)
        else:
            self.error(list(FST["dtype"]), local_follow)

    def parse_dtype1(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        if t_type in FST["dtype1"]:
            self.pos += 1
            return val
        else:
            self.error(list(FST["dtype1"]), local_follow)

    def parse_gDec(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "gDec", "line": line}
        if val == "[":
            self.pos += 1
            node["size"] = self.match("INTLIT", ["]"])
            self.match("]", FST["arOpt"] | {";"})
            node["arOpt"] = self.parse_arOpt(local_follow)
        elif val in FST["gDecOp"] or val == ";":
            node["gDecOp"] = self.parse_gDecOp(";")
        else:
            self.error(list(FST["gDec"]) + [";"], local_follow)
        return node

    def parse_arOpt(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "arOpt", "line": line}
        if val == "[":
            self.pos += 1
            node["size2"] = self.match("INTLIT", ["]"])
            self.match("]")
            node["2dArray"] = self.parse_2dArray(local_follow)
        elif val == "=":
            self.pos += 1
            self.match("{")
            node["elements"] = self.parse_element({"}"})
            self.match("}")
        elif val in FF["arOpt"]:
            return node
        else:
            self.error(list(FST["arOpt"]) + list(FF["arOpt"]), local_follow)
        return node

    def parse_2dArray(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "2dArray", "rows": [], "line": line}
        if val == "=":
            self.pos += 1
            self.match("{")
            self.match("{")
            row1 = self.parse_element({"}"})
            self.match("}")
            self.match(",")
            self.match("{")
            row2 = self.parse_element({"}"})
            self.match("}")
            self.match("}")
            node["rows"] = [row1, row2]
        elif val in FF["arOpt"]:
            return node
        else:
            return node
        return node
   
    # 2D ROW PROBLEM 
    

    def parse_element(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "element", "literals": [], "line": line}
        if t_type in FST["literal"]:
            node["literals"].append(self.parse_literal([{",", "}"}]))
            node["literals"].extend(self.parse_eLit("}") or [])
        elif val in FF["element"]:
            return node
        else:
            self.error(list(FST["element"]) + ["}"], local_follow)
        return node

    def parse_literal(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        if t_type == "STRLIT":
            self.pos += 1
            return val
        elif t_type in FST["litOp"]:
            return self.parse_litOp(local_follow)
        else:
            self.error(list(FST["literal"]), local_follow)

    def parse_litOp(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        if t_type in FST["litOp"]:
            self.pos += 1
            return val
        else:
            self.error(list(FST["litOp"]), local_follow)

    def parse_eLit(self, local_follow):
        items = []
        val, t_type, line, col = self.get_token_info()
        if val == ",":
            self.pos += 1
            items.append(self.parse_literal(local_follow))
            items.extend(self.parse_eLit(local_follow) or [])
        elif val in FF["eLit"]:
            return items
        else:
            self.error(list(FST["eLit"]) + ["}"], local_follow)
        return items

    def parse_gDecOp(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "gDecOp", "line": line}
        if val == "=":
            self.pos += 1
            node["value"] = self.parse_literal(local_follow)
            node["multiV"] = self.parse_multiV(local_follow)
        elif val in FST["multiV"]:
            node["multiV"] = self.parse_multiV(local_follow)
        elif val in FF["gDecOp"]:
            return node
        else:
            self.error(list(FST["gDecOp"]) + list(FST["multiV"]) + list(FF["gDecOp"]), local_follow)
        return node

    def parse_multiV(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "multiV", "vars": [], "line": line}
        if val == ",":
            self.pos += 1
            entry = {"name": self.match("ID"), "line": line}
            entry["gDecOp"] = self.parse_gDecOp(local_follow)
            node["vars"].append(entry)
        elif val in FF["multiV"]:
            return node
        else:
            self.error(list(FF["multiV"]) + list(FST["multiV"]), local_follow)
        return node

    def parse_fDec(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "fDec", "line": line}
        if val == "[":
            self.pos += 1
            node["size"] = self.match("INTLIT", ["]"])
            self.match("]")
            node["fArray"] = self.parse_fArray(local_follow)
        elif val == "=":
            self.pos += 1
            node["value"] = self.parse_literal(local_follow)
            node["multiFix"] = self.parse_multiFix(local_follow)
        else:
            self.error(list(FST["fDec"]), local_follow)
        return node

    def parse_fArray(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "fArray", "line": line}

        if val == "[":
            self.pos += 1
            node["size2"] = self.match("INTLIT", ["]"])
            self.match("]")
            self.match("=")
            self.match("{")

            rows = []
            self.match("{")
            row_lits = [self.parse_literal({"}", ","})]
            row_lits.extend(self.parse_eLit({"}"}) or [])
            self.match("}")
            rows.append({"literals": row_lits})

            while True:
                v, _, _, _ = self.get_token_info()
                if v != ",":
                    break
                self.pos += 1  
                v2, _, _, _ = self.get_token_info()
                if v2 != "{":
                    break
                self.match("{")
                row_lits = [self.parse_literal({"}", ","})]
                row_lits.extend(self.parse_eLit({"}"}) or [])
                self.match("}")
                rows.append({"literals": row_lits})

            self.match("}")
            node["2dArray"] = {"rows": rows}
            node["literals"] = [lit for row in rows for lit in row["literals"]]

        elif val == "=":
            self.pos += 1
            self.match("{")
            node["literals"] = [self.parse_literal({"}"})]
            node["literals"].extend(self.parse_eLit({"}"}) or [])
            self.match("}")

        else:
            self.error(["[", "="], local_follow)

        return node
    
    def parse_multiFix(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "multiFix", "vars": [], "line": line}
        if val == ",":
            self.pos += 1
            entry = {"name": self.match("ID"), "line": line}
            self.match("=")
            entry["value"] = self.parse_literal(local_follow)
            node["vars"].append(entry)
            rest = self.parse_multiFix(local_follow)
            node["vars"].extend(rest["vars"])
        elif val in FF["multiFix"]:
            return node
        else:
            self.error(list(FST["multiFix"]) + list(FF["multiFix"]), local_follow)
        return node

    def parse_func(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "func", "functions": [], "line": line}
        if val == "brain":
            return node
        if val in FST["func"]:
            func = {"line": line}
            func["return_type"] = self.parse_cloType({"heart"})
            self.match("heart", ["ID"])
            func["name"] = self.match("ID", ["("])
            self.match("(", FST["dtype"] | {")"})
            func["param"] = self.parse_param({")"})
            self.match(")", ["{"])
            self.match("{")
            func["stmt"] = self.parse_stmt({"closure"})
            self.match("closure")
            func["closureCon"] = self.parse_closureCon({";"})
            self.match(";", ["}"])
            self.match("}")
            node["functions"].append(func)
            rest = self.parse_func(local_follow)
            node["functions"].extend(rest["functions"])
        else:
            self.error(list(FST["func"]) + list(FF["func"]), local_follow)
        return node

    def parse_cloType(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        if val == "void":
            self.pos += 1
            return val
        elif t_type in FST["dtype"]:
            return self.parse_dtype(local_follow)
        else:
            self.error(list(FST["cloType"]), local_follow)

    def parse_param(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "param", "params": [], "line": line}
        if t_type in FST["dtype"]:
            entry = {"line": line}
            entry["dtype"] = self.parse_dtype({"ID"})
            entry["name"] = self.match("ID", FST["multiPar"] | FF["multiPar"])
            node["params"].append(entry)
            rest = self.parse_multiPar(local_follow)
            node["params"].extend(rest["params"])
        elif val in FF["param"]:
            return node
        else:
            self.error(list(FST["param"]) + list(FF["param"]), local_follow)
        return node

    def parse_multiPar(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "multiPar", "params": [], "line": line}
        if val == ",":
            self.pos += 1
            entry = {"line": line}
            entry["dtype"] = self.parse_dtype({"ID"})
            entry["name"] = self.match("ID", FST["multiPar"] | FF["multiPar"])
            node["params"].append(entry)
            rest = self.parse_multiPar(local_follow)
            node["params"].extend(rest["params"])
        elif val in FF["multiPar"]:
            return node
        else:
            self.error(list(FST["multiPar"]) + list(FF["multiPar"]))
        return node

    def parse_stmt(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "stmt", "stmts": [], "line": line}
        if val == "hope":
            self.pos += 1
            stmt = {"type": "hope", "line": line}
            self.match("(")
            stmt["condition"] = self.parse_exprDec({")"})
            self.match(")")
            self.match("{")
            stmt["stmt"] = self.parse_stmt({"closure", "}"})
            stmt["stmtOpTail"] = self.parse_stmtOpTail({ "}"})
            self.match("}")
            stmt["hopeTail"] = self.parse_hopeTail(FST["stmt"] | local_follow)
            node["stmts"].append(stmt)
            rest = self.parse_stmt(local_follow)
            node["stmts"].extend(rest["stmts"])
        elif val == "core":
            self.pos += 1
            stmt = {"type": "core", "line": line}
            self.match("(")
            stmt["condition"] = self.parse_coreCon({")"})
            self.match(")")
            self.match("{")
            stmt["body"] = self.parse_coreBody({"}"})
            self.match("}")
            node["stmts"].append(stmt)
            rest = self.parse_stmt(local_follow)
            node["stmts"].extend(rest["stmts"])
        elif t_type in FST["stmtOp"] or val in FST["stmtOp"] or t_type.startswith("ID"):
            node["stmts"].append(self.parse_stmtOp(FST["stmt"] | local_follow))
            rest = self.parse_stmt(local_follow)
            node["stmts"].extend(rest["stmts"])
        elif val in ["closure", "}"] or val in local_follow:
            return node
        else:
            self.error(list(FST["stmt"]) + list(local_follow), local_follow)
        return node

    def parse_stmtOp(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "stmtOp", "line": line}
        if t_type == "str":
            self.pos += 1
            node["kind"] = "str"
            node["name"] = self.match("ID")
            node["strTail"] = self.parse_strTail({";"})
            self.match(";")
        elif t_type in FST["dtype1"]:
            node["kind"] = "dtype1"
            node["dtype"] = self.parse_dtype1(local_follow)
            node["name"] = self.match("ID")
            node["locDec"] = self.parse_locDec({";"})
            self.match(";")
        elif val == "fixed":
            self.pos += 1
            node["kind"] = "fixed"
            node["locFDOp"] = self.parse_locFDOp({";"})
            self.match(";")
        elif t_type == "ID" or t_type.startswith("ID"):
            node["kind"] = "ID"
            node["name"] = val
            self.pos += 1
            node["idExpr"] = self.parse_idExpr({";"})
            self.match(";")
        elif val == "read":
            self.pos += 1
            node["kind"] = "read"
            self.match("(")
            node["id"] = self.match("ID")
            node["eleIndex"] = self.parse_eleIndex({")"})
            self.match(")")
            self.match(";")
        elif val == "spill":
            self.pos += 1
            node["kind"] = "spill"
            self.match("(")
            node["spillOpt"] = self.parse_spillOpt({")"})
            self.match(")")
            self.match(";")
        elif val == "desire":
            self.pos += 1
            node["kind"] = "desire"
            self.match("(")
            node["din"] = self.parse_din({";"})
            self.match(";")
            node["condition"] = self.parse_exprDec({";"})
            self.match(";")
            node["dup"] = self.parse_dup({")"})
            self.match(")")
            self.match("{")
            node["loopStmt"] = self.parse_loopStmt({"}"})
            self.match("}")
        elif val == "while":
            self.pos += 1
            node["kind"] = "while"
            self.match("(")
            node["condition"] = self.parse_exprDec({")"})
            self.match(")")
            self.match("{")
            node["loopStmt"] = self.parse_loopStmt({"}"})
            self.match("}")
        elif val == "do":
            self.pos += 1
            node["kind"] = "do"
            self.match("{")
            node["loopStmt"] = self.parse_loopStmt({"}"})
            self.match("}")
            self.match("while")
            self.match("(")
            node["condition"] = self.parse_exprDec({")"})
            self.match(")")
            self.match(";")
        elif val == "echo":
            self.pos += 1
            node["kind"] = "echo"
            node["name"] = self.match("ID")
            self.match("(")
            node["echOp"] = self.parse_echOp({")"})
            self.match(")")
            self.match(";")
        elif t_type in FST["una"]:
            node["kind"] = "una"
            node["op"] = self.parse_una({"ID"})
            node["name"] = self.match("ID")
            node["eleIndex"] = self.parse_eleIndex({";"})
            self.match(";")
        else:
            self.error(list(FST["stmtOp"]), local_follow)
        return node

    def parse_strTail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "strTail", "line": line}
        if val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
            node["strArrTail"] = self.parse_strArrTail(local_follow)
        elif val in FST["strTail1"] or val in FF["strTail1"]:
            node["strTail1"] = self.parse_strTail1(local_follow)
        else:
            self.error(list(FST["strTail"]) + list(FF["strTail"]), local_follow)
        return node

    def parse_index(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        if t_type == "INTLIT":
            self.pos += 1
            return val
        elif t_type == "ID" or t_type.startswith("ID"):
            self.pos += 1
            return val
        else:
            self.error(["INTLIT", "ID"], local_follow)

    def parse_strTail1(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "strTail1", "line": line}
        if val == "=":
            self.pos += 1
            node["value"] = self.parse_strVal(FST["strMulti"] | local_follow)
            node["strMulti"] = self.parse_strMulti(local_follow)
        elif val in FST["strMulti"] or val in FF["strMulti"]:
            node["strMulti"] = self.parse_strMulti(local_follow)
        else:
            self.error(list(FST["strTail1"]) + list(FF["strTail1"]), local_follow)
        return node

    def parse_strArrTail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "strArrTail", "line": line}
        if val == "=":
            self.pos += 1
            self.match("{")
            node["elements"] = self.parse_element({"}"})
            self.match("}")
        elif val in FF["strArrTail"]:
            return node
        else:
            self.error(list(FST["strArrTail"]) + list(FF["strArrTail"]), local_follow)
        return node

    def parse_strMulti(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "strMulti", "vars": [], "line": line}
        if val == ",":
            self.pos += 1
            entry = {"line": line}
            entry["name"] = self.match("ID")
            entry["strTail1"] = self.parse_strTail1(local_follow)
            node["vars"].append(entry)
        elif val in FF["strMulti"]:
            return node
        else:
            self.error(list(FST["strMulti"]) + list(FF["strMulti"]), local_follow)
        return node

    def parse_strVal(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "strVal", "line": line}
        if val == "echo":
            self.pos += 1
            node["kind"] = "echo"
            node["name"] = self.match("ID")
            self.match("(")
            node["echOp"] = self.parse_echOp({")"})
            self.match(")")
        elif t_type == "STRLIT":
            self.pos += 1
            node["kind"] = "STRLIT"
            node["value"] = val
        elif t_type == "ID" or t_type.startswith("ID"):
            self.pos += 1
            node["kind"] = "ID"
            node["name"] = val
            node["eleIndex"] = self.parse_eleIndex({"[", ",", ";"})
        else:
            self.error(list(FST["strVal"]), local_follow)
        return node

    def parse_eleIndex(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "eleIndex", "index": None, "index2": None, "line": line}
        if val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
            node["index2"] = self.parse_2dIndex(local_follow)
        elif val in FF["eleIndex"] or t_type in FF["eleIndex"]:
            return node
        else:
            self.error(list(FST["eleIndex"]) + list(local_follow), local_follow)
        return node

    def parse_2dIndex(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "2dIndex", "index": None, "line": line}
        if val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
        else:
            return node
        return node

    def parse_echOp(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "echOp", "args": [], "line": line}
        if t_type in FST["assVal"] or val in FST["assVal"] or t_type.startswith("ID"):
            node["args"].append(self.parse_assVal(FST["echoMulti"] | local_follow))
            node["args"].extend(self.parse_echoMulti(local_follow))
        elif val in FF["echOp"]:
            return node
        else:
            self.error(list(FST["echOp"]) + list(FF["echOp"]), local_follow)
        return node

    def parse_echoMulti(self, local_follow):
        items = []
        val, t_type, line, col = self.get_token_info()
        if val == ",":
            self.pos += 1
            items.append(self.parse_assVal(FST["echoMulti"] | local_follow))
            items.extend(self.parse_echoMulti(local_follow))
        elif val in FF["echoMulti"]:
            return items
        else:
            self.error(list(FST["echoMulti"]) + list(FF["echoMulti"]), local_follow)
        return items

    def parse_locDec(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "locDec", "line": line}
        if val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
            node["arOpt"] = self.parse_arOpt(local_follow)
        elif val in FST["locDecOp"] or val in FF["locDecOp"]:
            node["locDecOp"] = self.parse_locDecOp(local_follow)
        else:
            self.error(list(FST["locDec"]) + list(FF["locDecOp"]), local_follow)
        return node

    def parse_locDecOp(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "locDecOp", "line": line}
        if val == "=":
            self.pos += 1
            node["value"] = self.parse_exprDec({","} | local_follow)
            node["locMV"] = self.parse_locMV(local_follow)
        elif val in FST["locMV"] or val in FF["locMV"]:
            node["locMV"] = self.parse_locMV(local_follow)
        else:
            self.error(list(FST["locDecOp"]) + list(FF["locDecOp"]), local_follow)
        return node

    def parse_locMV(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "locMV", "vars": [], "line": line}
        if val == ",":
            self.pos += 1
            entry = {"line": line}
            entry["name"] = self.match("ID")
            entry["locDecOp"] = self.parse_locDecOp(local_follow)
            node["vars"].append(entry)
        elif val in FF["locMV"]:
            return node
        else:
            self.error(list(FST["locMV"]) + list(FF["locMV"]), local_follow)
        return node

    def parse_exprDec(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprDec", "line": line}
        node["exprOr"] = self.parse_expr_or(local_follow)
        return node

    def parse_expr_or(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprOr", "line": line}
        node["left"] = self.parse_expr_and({"||"} | local_follow)
        node["tail"] = self.parse_expr_or_tail(local_follow)
        return node

    def parse_expr_or_tail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprOrTail", "op": None, "right": None, "line": line}
        if val == "||":
            node["op"] = val
            self.pos += 1
            node["right"] = self.parse_expr_and({"||"} | local_follow)
            node["tail"] = self.parse_expr_or_tail(local_follow)
        else:
            return node
        return node

    def parse_expr_and(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprAnd", "line": line}
        node["left"] = self.parse_expr_rel({"&&"} | local_follow)
        node["tail"] = self.parse_expr_and_tail(local_follow)
        return node

    def parse_expr_and_tail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprAndTail", "op": None, "right": None, "line": line}
        if val == "&&":
            node["op"] = val
            self.pos += 1
            node["right"] = self.parse_expr_rel({"&&"} | local_follow)
            node["tail"] = self.parse_expr_and_tail(local_follow)
        else:
            return node
        return node

    def parse_expr_rel(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprRel", "line": line}
        rel_ops = {"==", "!=", ">", "<", ">=", "<="}
        node["left"] = self.parse_expr_add(rel_ops | local_follow)
        node["tail"] = self.parse_expr_rel_tail(local_follow)
        return node

    def parse_expr_rel_tail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprRelTail", "op": None, "right": None, "line": line}
        rel_ops = {"==", "!=", ">", "<", ">=", "<="}
        if val in rel_ops:
            node["op"] = val
            self.pos += 1
            node["right"] = self.parse_expr_add(rel_ops | local_follow)
            node["tail"] = self.parse_expr_rel_tail(local_follow)
        else:
            return node
        return node

    def parse_expr_add(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprAdd", "line": line}
        node["left"] = self.parse_expr_mul({"+", "-"} | local_follow)
        node["tail"] = self.parse_expr_add_tail(local_follow)
        return node

    def parse_expr_add_tail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprAddTail", "op": None, "right": None, "line": line}
        if val in {"+", "-"}:
            node["op"] = val
            self.pos += 1
            node["right"] = self.parse_expr_mul({"+", "-"} | local_follow)
            node["tail"] = self.parse_expr_add_tail(local_follow)
        else:
            return node
        return node

    def parse_expr_mul(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprMul", "line": line}
        node["left"] = self.parse_expr_exp({"*", "/", "%", "//"} | local_follow)
        node["tail"] = self.parse_expr_mul_tail(local_follow)
        return node

    def parse_expr_mul_tail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprMulTail", "op": None, "right": None, "line": line}
        if val in {"*", "/", "%", "//"}:
            node["op"] = val
            self.pos += 1
            node["right"] = self.parse_expr_exp({"*", "/", "%", "//"} | local_follow)
            node["tail"] = self.parse_expr_mul_tail(local_follow)
        else:
            return node
        return node

    def parse_expr_exp(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprExp", "line": line}
        node["left"] = self.parse_expr_unary({"^"} | local_follow)
        node["tail"] = self.parse_expr_exp_tail(local_follow)
        return node

    def parse_expr_exp_tail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprExpTail", "op": None, "right": None, "line": line}
        if val == "^":
            node["op"] = val
            self.pos += 1
            node["right"] = self.parse_expr_unary({"^"} | local_follow)
            node["tail"] = self.parse_expr_exp_tail(local_follow)
        else:
            return node
        return node

    def parse_expr_unary(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "exprUnary", "line": line}
        if val == "!":
            self.pos += 1
            node["kind"] = "!"
            node["operand"] = self.parse_expr_unary(local_follow)
        elif val in {"++", "--"}:
            node["kind"] = val
            self.pos += 1
            node["name"] = self.match("ID")
            node["eleIndex"] = self.parse_eleIndex(local_follow)
        else:
            node["kind"] = "primary"
            node["primary"] = self.parse_primary(local_follow)
        return node

    def parse_primary(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "primary", "line": line}
        if val == "echo":
            self.pos += 1
            node["kind"] = "echo"
            node["name"] = self.match("ID")
            self.match("(")
            node["echOp"] = self.parse_echOp({")"})
            self.match(")")
        elif val == "(":
            self.pos += 1
            node["kind"] = "grouped"
            node["inner"] = self.parse_exprDec({")"})
            self.match(")")
        elif t_type in {"INTLIT", "FLOATLIT", "CHARLIT"} or val in {"trust", "betray"}:
            node["kind"] = t_type if t_type in {"INTLIT", "FLOATLIT", "CHARLIT"} else val
            node["value"] = val
            self.pos += 1
        elif t_type == "ID" or t_type.startswith("ID"):
            node["kind"] = "ID"
            node["name"] = val
            self.pos += 1
            node["postfix"] = self.parse_postfix(local_follow)
        else:
            self.error(["ID", "INTLIT", "FLOATLIT", "CHARLIT", "trust", "betray", "echo", "("], local_follow)
        return node

    def parse_postfix(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "postfix", "index": None, "index2": None, "line": line}
        if val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
            node["index2"] = self.parse_2dIndex(local_follow)
            node["unaPost"] = self.parse_una_post(local_follow)
        else:
            node["unaPost"] = self.parse_una_post(local_follow)
        return node

    def parse_una_post(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "unaPost", "op": None, "line": line}
        if val in {"++", "--"}:
            node["op"] = val
            self.pos += 1
        else:
            return node
        return node

    def parse_una(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        if val in FST["una"]:
            self.pos += 1
            return val
        else:
            self.error(list(FST["una"]), local_follow)

    def parse_unaOp(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "unaOp", "line": line}
        if val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
            node["una1"] = self.parse_una1(local_follow)
        elif val in {"++", "--"}:
            node["op"] = val
            self.pos += 1
        else:
            return node
        return node

    def parse_una1(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "una1", "op": None, "line": line}
        if val in {"++", "--"}:
            node["op"] = val
            self.pos += 1
        elif val in local_follow:
            return node
        else:
            expected = ["++", "--"] + list(local_follow)
            self.error(sorted(list(set(expected))), local_follow)
        return node

    def parse_locFDOp(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "locFDOp", "line": line}
        if t_type == "str":
            self.pos += 1
            node["kind"] = "str"
            node["name"] = self.match("ID")
            node["fixStrTail"] = self.parse_fixStrTail(local_follow)
        elif t_type in FST["dtype1"]:
            node["kind"] = "dtype1"
            node["dtype"] = self.parse_dtype1(local_follow)
            node["name"] = self.match("ID")
            node["fixLocDec"] = self.parse_fixLocDec(local_follow)
        else:
            self.error(list(FST["locFDOp"]), local_follow)
        return node

    def parse_fixStrTail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "fixStrTail", "line": line}
        if val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
            self.match("=")
            self.match("{")
            node["literals"] = [self.parse_literal(FST["eLit"])]
            node["literals"].extend(self.parse_eLit({"}"}) or [])
            self.match("}")
        elif val == "=":
            self.pos += 1
            node["value"] = self.match("STRLIT")
            node["fixStrMulti"] = self.parse_fixStrMulti(local_follow)
        else:
            self.error(list(FST["fixStrTail"]), local_follow)
        return node

    def parse_fixStrMulti(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "fixStrMulti", "vars": [], "line": line}
        if val == ",":
            self.pos += 1
            entry = {"line": line}
            entry["name"] = self.match("ID")
            self.match("=")
            entry["value"] = self.match("STRLIT")
            node["vars"].append(entry)
            rest = self.parse_fixStrMulti(local_follow)
            node["vars"].extend(rest["vars"])
        elif val in FF["fixStrMulti"]:
            return node
        else:
            self.error(list(FST["fixStrMulti"]) + list(FF["fixStrMulti"]), local_follow)
        return node

    def parse_fixLocDec(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "fixLocDec", "line": line}
        if val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
            node["fArray"] = self.parse_fArray(local_follow)
        elif val == "=":
            self.pos += 1
            node["value"] = self.parse_literal(FST["multiFix"] | local_follow)
            node["multiFix"] = self.parse_multiFix(local_follow)
        else:
            self.error(list(FST["fixLocDec"]) + list(FF["fixLocDec"]), local_follow)
        return node

    def parse_idExpr(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "idExpr", "line": line}
        comOp = ["+=", "-=", "*=", "/=", "%=", "//=", "^="]
        if val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
            node["index2"] = self.parse_2dIndex({val for val in comOp} | {"++", "--", "="} | local_follow)
            node["arrIDTail"] = self.parse_arrIDTail(local_follow)
        elif val in comOp:
            node["op"] = val
            self.pos += 1
            node["exprDec"] = self.parse_exprDec(local_follow)
        elif val in ["++", "--"] or val == "=" or val in local_follow:
            node["arrIDTail"] = self.parse_arrIDTail(local_follow)
        else:
            expected = ["[", "++", "--", "="] + comOp
            self.error(expected, local_follow)
        return node

    def parse_arrIDTail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "arrIDTail", "line": line}
        if val in ["++", "--"]:
            node["op"] = val
            self.pos += 1
        elif val == "=":
            self.pos += 1
            node["assVal"] = self.parse_assVal(local_follow)
        elif val in local_follow:
            return node
        else:
            self.error(["++", "--", "="], local_follow)
        return node

    def parse_assVal(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "assVal", "line": line}
        if t_type == "STRLIT":
            self.pos += 1
            node["kind"] = "STRLIT"
            node["value"] = val
        else:
            node["kind"] = "exprDec"
            node["exprDec"] = self.parse_exprDec(local_follow)
        return node

    def parse_spillOpt(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "spillOpt", "args": [], "line": line}
        if t_type == "ID" or t_type == "STRLIT" or val in ["++", "--"] or t_type.startswith("ID"):
            node["args"].append(self.parse_spillOpt1(local_follow | {","}))
            node["args"].extend(self.parse_spillTail(local_follow))
        elif val in local_follow:
            return node
        else:
            self.error(["ID", "STRLIT", "++", "--"] + list(local_follow), local_follow)
        return node

    def parse_spillOpt1(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "spillOpt1", "line": line}
        if t_type.startswith("ID"):
            node["kind"] = "ID"
            node["name"] = val
            self.pos += 1
            node["unaOp"] = self.parse_unaOp(local_follow)
        elif t_type == "STRLIT":
            self.pos += 1
            node["kind"] = "STRLIT"
            node["value"] = val
        elif val in ["++", "--"]:
            node["kind"] = val
            self.pos += 1
            node["name"] = self.match("ID")
            node["eleIndex"] = self.parse_eleIndex(local_follow)
        else:
            self.error(["ID", "STRLIT", "++", "--"], local_follow)
        return node

    def parse_spillTail(self, local_follow):
        items = []
        val, t_type, line, col = self.get_token_info()
        if val == ",":
            self.pos += 1
            items.append(self.parse_spillOpt1(local_follow | {","}))
            items.extend(self.parse_spillTail(local_follow))
        elif val in local_follow:
            return items
        else:
            expected = [","] + list(local_follow)
            prev_val, prev_type, _, _ = self.tokens[self.pos - 1] if self.pos > 0 else (None, None, None, None)
            if prev_type == "ID" or (prev_type and prev_type.startswith("ID")):
                if "[" not in expected: expected.append("[")
                if "++" not in expected: expected.append("++")
                if "--" not in expected: expected.append("--")
            self.error(sorted(list(set(expected))), local_follow)
        return items

    def parse_din(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "din", "line": line}
        if t_type in FST["dtype1"]:
            node["kind"] = "decl"
            node["dtype"] = self.parse_dtype1({";"})
            node["name"] = self.match("ID")
            node["dinTail"] = self.parse_dinTail(local_follow)
        elif t_type == "ID" or t_type.startswith("ID"):
            node["kind"] = "ID"
            node["name"] = val
            self.pos += 1
            node["dinTail1"] = self.parse_dinTail1(local_follow)
        elif val == "echo":
            self.pos += 1
            node["kind"] = "echo"
            node["name"] = self.match("ID")
            self.match("(")
            node["echOp"] = self.parse_echOp({")"})
            self.match(")")
            node["exprTail"] = self.parse_expr_or_tail(local_follow)
        elif val in ["++", "--"]:
            node["kind"] = val
            self.pos += 1
            node["name"] = self.match("ID")
            node["eleIndex"] = self.parse_eleIndex(local_follow)
            node["exprTail"] = self.parse_expr_or_tail(local_follow)
        else:
            self.error(list(FST["dtype1"]) + ["ID", "echo", "++", "--"], local_follow)
        return node

    def parse_dinTail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "dinTail", "line": line}
        if val == "=":
            self.pos += 1
            node["value"] = self.parse_exprDec(local_follow)
        elif val in local_follow:
            return node
        else:
            self.error(["="] + list(local_follow), local_follow)
        return node

    def parse_dinTail1(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "dinTail1", "line": line}
        operators = {"+", "-", "*", "/", "%", "//", "^", "==", "!=", ">", "<", ">=", "<=", "&&", "||"}
        if val == "=":
            self.pos += 1
            node["value"] = self.parse_exprDec(local_follow)
        elif val in local_follow:
            return node
        elif val == "[":
            self.pos += 1
            node["index"] = self.parse_index({"]"})
            self.match("]")
            self.parse_una1({"="} | local_follow)
            node["dinTail"] = self.parse_dinTail(local_follow)
        elif val in {"++", "--"} or val in operators:
            node["una1"] = self.parse_una1(local_follow)
            node["exprTail"] = self.parse_expr_or_tail(local_follow)
        else:
            self.error(["=", "[", "++", "--"] + sorted(list(operators)) + list(local_follow), local_follow)
        return node

    def parse_dup(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "dup", "line": line}
        if t_type == "ID" or t_type.startswith("ID"):
            node["kind"] = "ID"
            node["name"] = val
            self.pos += 1
            node["dupTail"] = self.parse_dupTail(local_follow)
        elif val in ["++", "--"]:
            node["kind"] = val
            self.pos += 1
            node["name"] = self.match("ID")
            node["eleIndex"] = self.parse_eleIndex(local_follow)
            node["exprTail"] = self.parse_expr_or_tail(local_follow)
        else:
            self.error(["ID", "++", "--"], local_follow)
        return node

    def parse_dupTail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "dupTail", "line": line}
        comOp = ["+=", "-=", "*=", "/=", "%=", "//=", "^="]
        if val in ["++", "--", "["]:
            node["unaOp"] = self.parse_unaOp(local_follow)
            node["exprTail"] = self.parse_expr_or_tail(local_follow)
        elif val in comOp:
            node["op"] = val
            self.pos += 1
            node["exprDec"] = self.parse_exprDec(local_follow)
        elif val in local_follow:
            return node
        else:
            self.error(["++", "--", "["] + comOp, local_follow)
        return node

    def parse_loopStmt(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "loopStmt", "stmts": [], "line": line}
        if val == "hope":
            self.pos += 1
            stmt = {"type": "hope", "line": line}
            self.match("(")
            stmt["condition"] = self.parse_exprDec({")"})
            self.match(")")
            self.match("{")
            stmt["loopStmt"] = self.parse_loopStmt({"}"})
            self.match("}")
            stmt["hopeTailLoop"] = self.parse_hopeTailLoop(local_follow)
            node["stmts"].append(stmt)
            rest = self.parse_loopStmt(local_follow)
            node["stmts"].extend(rest["stmts"])
        elif val == "core":
            self.pos += 1
            stmt = {"type": "core", "line": line}
            self.match("(")
            stmt["condition"] = self.parse_coreCon({")"})
            self.match(")")
            self.match("{")
            stmt["body"] = self.parse_coreLoopBody({"}"})
            self.match("}")
            node["stmts"].append(stmt)
            rest = self.parse_loopStmt(local_follow)
            node["stmts"].extend(rest["stmts"])
        elif val == "down":
            self.pos += 1
            self.match(";")
            node["break"] = "down"
            return node
        elif val == "over":
            self.pos += 1
            self.match(";")
            node["continue"] = "over"
            return node
        elif val == "closure":
            self.pos += 1
            node["return"] = self.parse_closureCon({";"})
            self.match(";")
            return node
        elif t_type in FST["stmtOp"] or val in FST["stmtOp"] or t_type.startswith("ID"):
            node["stmts"].append(self.parse_stmtOp(local_follow))
            rest = self.parse_loopStmt(local_follow)
            node["stmts"].extend(rest["stmts"])
        elif val in local_follow:
            return node
        else:
            expected = ["hope", "core", "down", "over", "closure"] + list(FST["stmtOp"])
            self.error(expected, local_follow)
        return node

    def parse_hopeTailLoop(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "hopeTailLoop", "line": line}
        loop_follow = local_follow | {"hope", "core", "down", "over", "closure"} | set(FST["stmtOp"])
        if val == "despair":
            self.pos += 1
            node["despairOptLoop"] = self.parse_despairOptLoop(local_follow)
        elif val in loop_follow or t_type.startswith("ID"):
            return node
        else:
            self.error(["despair"] + sorted(list(loop_follow)), local_follow)
        return node

    def parse_despairOptLoop(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "despairOptLoop", "line": line}
        if val == "hope":
            self.pos += 1
            self.match("(")
            node["condition"] = self.parse_exprDec({")"})
            self.match(")")
            self.match("{")
            node["loopStmt"] = self.parse_loopStmt({"}"})
            self.match("}")
            node["hopeTailLoop"] = self.parse_hopeTailLoop(local_follow)
        elif val == "{":
            self.pos += 1
            node["loopStmt"] = self.parse_loopStmt({"}"})
            self.match("}")
        else:
            self.error(["hope", "{"], local_follow)
        return node

    def parse_coreCon(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreCon", "line": line}
        node["coreAdd"] = self.parse_core_add(local_follow)
        return node

    def parse_core_add(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreAdd", "line": line}
        node["left"] = self.parse_core_mul({"+", "-"} | local_follow)
        node["tail"] = self.parse_core_add_tail(local_follow)
        return node

    def parse_core_add_tail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreAddTail", "op": None, "right": None, "line": line}
        if val in {"+", "-"}:
            node["op"] = val
            self.pos += 1
            node["right"] = self.parse_core_mul({"+", "-"} | local_follow)
            node["tail"] = self.parse_core_add_tail(local_follow)
        else:
            return node
        return node

    def parse_core_mul(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreMul", "line": line}
        node["left"] = self.parse_core_exp({"*", "/", "%", "//"} | local_follow)
        node["tail"] = self.parse_core_mul_tail(local_follow)
        return node

    def parse_core_mul_tail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreMulTail", "op": None, "right": None, "line": line}
        if val in {"*", "/", "%", "//"}:
            node["op"] = val
            self.pos += 1
            node["right"] = self.parse_core_exp({"*", "/", "%", "//"} | local_follow)
            node["tail"] = self.parse_core_mul_tail(local_follow)
        else:
            return node
        return node

    def parse_core_exp(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreExp", "line": line}
        node["left"] = self.parse_core_unary({"^"} | local_follow)
        node["tail"] = self.parse_core_exp_tail(local_follow)
        return node

    def parse_core_exp_tail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreExpTail", "op": None, "right": None, "line": line}
        if val == "^":
            node["op"] = val
            self.pos += 1
            node["right"] = self.parse_core_unary({"^"} | local_follow)
            node["tail"] = self.parse_core_exp_tail(local_follow)
        else:
            return node
        return node

    def parse_core_unary(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreUnary", "line": line}
        if val in {"++", "--"}:
            node["kind"] = val
            self.pos += 1
            node["name"] = self.match("ID")
            node["eleIndex"] = self.parse_eleIndex(local_follow)
        else:
            node["kind"] = "primary"
            node["primary"] = self.parse_core_primary(local_follow)
        return node

    def parse_core_primary(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "corePrimary", "line": line}
        if t_type in {"INTLIT", "CHARLIT"}:
            node["kind"] = t_type
            node["value"] = val
            self.pos += 1
        elif val == "echo":
            self.pos += 1
            node["kind"] = "echo"
            node["name"] = self.match("ID")
            self.match("(")
            node["echOp"] = self.parse_echOp({")"})
            self.match(")")
        elif val == "(":
            self.pos += 1
            node["kind"] = "grouped"
            node["inner"] = self.parse_coreCon({")"})
            self.match(")")
        elif t_type == "ID" or t_type.startswith("ID"):
            node["kind"] = "ID"
            node["name"] = val
            self.pos += 1
            node["postfix"] = self.parse_postfix(local_follow)
        else:
            self.error(["INTLIT", "CHARLIT", "ID", "echo", "("], local_follow)
        return node

    def parse_memVal(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        if t_type in FST["memVal"]:
            self.pos += 1
            return val
        else:
            self.error(list(FST["memVal"]), local_follow)

    def parse_coreLoopBody(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreLoopBody", "cases": [], "line": line}
        if val == "memory":
            self.pos += 1
            entry = {"line": line}
            entry["memVal"] = self.parse_memVal({":"})
            self.match(":")
            self.match("{")
            entry["loopStmt"] = self.parse_loopStmt({"}"})
            self.match("}")
            node["cases"].append(entry)
            rest = self.parse_coreLoopBody(local_follow)
            node["cases"].extend(rest["cases"])
        elif val == "default":
            self.pos += 1
            self.match(":")
            self.match("{")
            node["default"] = self.parse_loopStmt({"}"})
            self.match("}")
        elif val in local_follow:
            return node
        else:
            self.error(["memory", "default"] + list(local_follow), local_follow)
        return node

    def parse_closureCon(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "closureCon", "line": line}
        if t_type in FST["assVal"] or val in FST["assVal"] or t_type.startswith("ID"):
            node["value"] = self.parse_assVal(local_follow)
        elif val in local_follow:
            return node
        else:
            self.error(["ID", "INTLIT", "FLOATLIT", "CHARLIT", "STRLIT", "echo", "(", "trust", "betray"] + list(local_follow), local_follow)
        return node

    def parse_hopeTail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "hopeTail", "line": line}
        if val == "despair":
            self.pos += 1
            node["despairOpt"] = self.parse_despairOpt(local_follow)
        return node

    def parse_despairOpt(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "despairOpt", "line": line}
        if val == "hope":
            self.pos += 1
            self.match("(")
            node["condition"] = self.parse_exprDec({")"})
            self.match(")")
            self.match("{")
            node["stmt"] = self.parse_stmt({"closure", "}"})
            node["stmtOpTail"] = self.parse_stmtOpTail({"closure", "}"})
            self.match("}")
            node["hopeTail"] = self.parse_hopeTail(local_follow)
        elif val == "{":
            self.pos += 1
            node["stmt"] = self.parse_stmt({"closure", "}"})
            node["stmtOpTail"] = self.parse_stmtOpTail({"closure", "}"})
            self.match("}")
        else:
            self.error(["hope", "{"] + list(local_follow), local_follow)
        return node

    def parse_stmtOpTail(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "stmtOpTail", "line": line}
        if val == "closure":
            self.pos += 1
            node["return"] = self.parse_closureCon({";"})
            self.match(";")
            return node
        return node

    def parse_coreBody(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreBody", "cases": [], "line": line}
        if val == "memory":
            self.pos += 1
            entry = {"line": line}
            entry["memVal"] = self.parse_memVal({":"})
            self.match(":")
            self.match("{")
            entry["coreStmt"] = self.parse_coreStmt({"}"} | local_follow)
            self.match("}")
            node["cases"].append(entry)
            rest = self.parse_coreLoopBody(local_follow)
            node["cases"].extend(rest["cases"])
        elif val == "default":
            self.pos += 1
            self.match(":")
            self.match("{")
            node["default"] = self.parse_coreStmt({"}"})
            self.match("}")
        elif val in local_follow:
            return node
        else:
            self.error(["memory", "default"] + list(local_follow), local_follow)
        return node

    def parse_coreStmt(self, local_follow):
        val, t_type, line, col = self.get_token_info()
        node = {"type": "coreStmt", "stmts": [], "line": line}
        if val == "over" or t_type == "over":
            self.pos += 1
            self.match(";")
            node["continue"] = "over"
            return node
        elif val == "closure":
            self.pos += 1
            node["return"] = self.parse_closureCon({";"})
            self.match(";")
            return node
        elif t_type in FST["stmt"] or val in FST["stmt"] or t_type.startswith("ID") or val == "over":
            node["stmts"].append(self.parse_stmt({"over", "closure", "}"} | local_follow))
            rest = self.parse_coreStmt(local_follow)
            node["stmts"].extend(rest["stmts"])
        elif val in local_follow:
            return node
        else:
            self.error(["over", "closure"] + list(FST["stmt"]), local_follow)
        return node


def perform_syntax_analysis(tokens, terminal):
    parser = SyntaxAnalyzer(tokens, terminal)
    try:
        if not tokens:
            return (False, "Syntax Error: No code provided.", None)

        parse_tree = parser.parse_program()
        val, t_type, line, col = parser.get_token_info()
        if t_type != "$":
            parser.error(["$"], [])

        return (True, "SYNTAX ANALYSIS: SUCCESS!", parse_tree)

    except Exception as e:
        error_message = str(e)
        return (False, error_message, None)