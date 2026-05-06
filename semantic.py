_LITERAL_TOKEN_TYPES = {"INTLIT", "FLOATLIT", "CHARLIT", "STRLIT"}
_token_type_map: dict = {}

def _build_token_type_map(tokens):
    _SKIP = {"space", "tab", "newline", "ocmt", "mcmt"}
    tmap = {}
    if tokens and isinstance(tokens[0], tuple):
        for value, token_type, *_ in tokens:
            if token_type not in _SKIP and token_type not in ("UNKNOWN",):
                tmap[value] = token_type
    return tmap
                                           
def is_literal(token, token_type_map=None):
    if not token:
        return False
    tmap = token_type_map if token_type_map is not None else _token_type_map
    if tmap and token in tmap:
        return tmap[token] in _LITERAL_TOKEN_TYPES or token in ("trust", "betray")
    if token in ("trust", "betray"):
        return True
    return False

_LEXER_TO_SEMANTIC_TYPE = {
    "STRLIT":   "str",
    "CHARLIT":  "char",
    "INTLIT":   "int",
    "FLOATLIT": "float",
}

def resolve_type(token, scope_stack, token_type_map=None):
    # First check if the token is a literal with a known type from the lexer
    # determines the datatype of a token by checking the token type map and applying rules for literals and identifiers
    tmap = token_type_map if token_type_map is not None else _token_type_map
    if tmap and token in tmap:
        ltype = tmap[token]
        if ltype in _LEXER_TO_SEMANTIC_TYPE:
            return _LEXER_TO_SEMANTIC_TYPE[ltype]
    if token in ("trust", "betray"):
        return "bool"
    if token.startswith('"') and token.endswith('"'):
        return "str"
    if token.startswith("'") and token.endswith("'"):
        return "char"
    if token.lstrip("-").isdigit():
        return "int"
    if "." in token:
        try:
            float(token)
            return "float"
        except ValueError:
            pass
    entry = lookup(token, scope_stack)
    if entry:
        return entry["type"]
    return None

def lookup(var, scope_stack):
    # Look up a variable in the scope stack, starting from the innermost scope.
    for scope in reversed(scope_stack):
        if var in scope:
            return scope[var]
    return None

def is_identifier(token):
    return (
        token.isidentifier() and
        token not in {
            "int", "float", "char", "str", "bool",
            "fixed", "brain", "heart", "closure",
            "trust", "betray", "desire", "down"
        }
    )

def contains_expression(tokens):
    operators = {
        "+", "-", "*", "/", "%", "//", "^",
        "+=", "-=", "/=", "%=", "//=", "*=", "^=",
        "<", ">", "<=", ">=", "==", "!=",
        "&&", "||", "!",
        "++", "--"
    }
    return any(tok in operators for tok in tokens)

#  Type-checking helpers                                              
def resolve_expression_type(expr_tokens, scope_stack, function_table):
    if not expr_tokens:
        return None
    if len(expr_tokens) == 1:
        return resolve_type(expr_tokens[0], scope_stack)
    if expr_tokens[0] == "echo" and len(expr_tokens) >= 2:
        func_name = expr_tokens[1]
        if func_name in function_table:
            return function_table[func_name]["return"]
        return None

    while (len(expr_tokens) >= 2 and
           expr_tokens[0] == "(" and
           expr_tokens[-1] == ")"):
        depth_check = 0
        matched = False
        for idx, tok in enumerate(expr_tokens):
            if tok == "(":
                depth_check += 1
            elif tok == ")":
                depth_check -= 1
            if depth_check == 0 and idx == len(expr_tokens) - 1:
                matched = True
                break
            elif depth_check == 0:
                break
        if matched:
            expr_tokens = expr_tokens[1:-1]
        else:
            break

    # after stripping parens, if single token resolve directly
    if len(expr_tokens) == 1:
        return resolve_type(expr_tokens[0], scope_stack)

    arithmetic_ops = {"+", "-", "*", "/", "//", "%", "^"}
    relational_ops = {"<", ">", "<=", ">=", "==", "!="}
    logical_ops    = {"&&", "||"}

    depth = 0
    has_top_arithmetic = has_top_relational = has_top_logical = False
    for tok in expr_tokens:
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
        elif depth == 0:
            if tok in arithmetic_ops:
                has_top_arithmetic = True
            elif tok in relational_ops:
                has_top_relational = True
            elif tok in logical_ops:
                has_top_logical = True

    if (has_top_relational or has_top_logical) and not has_top_arithmetic:
        return "bool"
    if has_top_arithmetic:
        skip = arithmetic_ops | relational_ops | logical_ops | {"!"}
        has_float = any(
            resolve_type(tok, scope_stack) == "float"
            for tok in expr_tokens if tok not in skip
        )
        # If any operand is float, or if the assignment target is float, prefer float
        return "float" if has_float else "int"
    
    if any(tok in relational_ops for tok in expr_tokens):
        return "bool"
    if any(tok in logical_ops or tok == "!" for tok in expr_tokens):
        return "bool"
    has_float = any(resolve_type(tok, scope_stack) == "float" for tok in expr_tokens)
    return "float" if has_float else "int"

def type_check(dtype, value, scope_stack):
    # type mismatch for heart echo with expression (e.g., echo MYFUNC() + 1)
    if value.startswith("__echo_") and value.endswith("__"):
        inner = value[7:-2]
        # echo with expression
        if inner.endswith("_expr"):
            echo_type = inner[:-5]
            if echo_type == "void":
                return False, "VOID_IN_EXPR"
            if echo_type == dtype:
                return True, None
            elif dtype == "int" and echo_type == "float":
                return True, "FLOAT_TRUNC"
            elif dtype == "float" and echo_type == "int":
                return True, "INT_TO_FLOAT"
            elif dtype == "bool" and echo_type in ("int", "float"):
                return True, None
            elif dtype == "char" and echo_type in ("int", "float"):
                return True, None
            elif dtype in ("int", "float") and echo_type == "char":
                return True, None
            else:
                return False, None 
        # echo with direct return
        elif inner.endswith("_direct"):
            echo_type = inner[:-7]
            if echo_type == "void":
                return False, "VOID_IN_EXPR"
            return dtype == echo_type, None
        # echo with plain type
        else:
            echo_type = inner
            if echo_type == "void":
                return False, "VOID_IN_EXPR"
            return dtype == echo_type, None
    # type mismatch for expressions 
    if value.startswith("__expr_") and value.endswith("__"):
        expr_type = value[7:-2]
        if expr_type == dtype:
            return True, None
        elif dtype == "int" and expr_type == "float":
            return True, "FLOAT_TRUNC"
        elif dtype == "float" and expr_type == "int":
            return True, "INT_TO_FLOAT"
        elif dtype == "bool" and expr_type in ("int", "float"):
            return True, None
        elif dtype == "char" and expr_type in ("int", "float"):
            return True, None
        elif dtype in ("int", "float") and expr_type == "char":
            return True, None
        elif expr_type == "bool" and dtype in ("int", "float"):
            return True, None
        elif expr_type == "bool" and dtype in ("char", "str"):
            return False, None
        else:
            return False, None

    if value == "__expr__":
        if dtype in ("int", "float", "bool", "char"):
            return True, None
        
    # other lit/ID is allowed in bool dtype as long as it is in expr 
    if value == "__bool_expr__":
        return (dtype == "bool", None)
    
    # only string is valid for str dtype
    if value.startswith('"') and value.endswith('"'):
        return (dtype == "str", None)

    # int and char is valid for char dtype 
    if value.startswith("'") and value.endswith("'"):
        is_normal_char = len(value) == 3
        is_escape_char = len(value) == 4 and value[1] == '\\' # escape sequence 
        if is_normal_char or is_escape_char:
            if dtype in ("char", "int"):
                return True, None
            return False, None

    # trust & betray is only valid for bool dtype
    if value in ("trust", "betray"):
        if dtype == "bool":
            return True, None
        return False, None

    # int dtype 
    if value.lstrip("-").isdigit():
        num = int(value)
        if dtype == "int":
            return True, None
        if dtype == "char":
            return (32 <= num <= 126, "ASCII_RANGE" if not (32 <= num <= 126) else None)
        if dtype == "bool":
            return False, None
        return False, None
    
    # float dtype 
    if "." in value:
        try:
            float(value)
            if dtype == "float":
                return True, None
            return False, None
        except ValueError:
            pass

    # variable assignment for dtype
    entry = lookup(value, scope_stack)
    if entry:
        src = entry["type"]
        if src == dtype:
            return True, None
        if src == "char" and dtype == "int":
            return True, None
        if src == "int" and dtype == "char":
            return True, None

    return False, None

def log_type_error(dtype, value, var, line_no, terminal, reason):
    if reason == "ASCII_RANGE":
        terminal.log(f"Semantic Error: Not Fit to the allowable ASCII range 32 - 126 '{var}' at line {line_no}")
    elif reason == "VOID_IN_EXPR":
        # Void errors are already logged by _validate_echo_call_args(), skip duplicate logging
        pass
    else:
        terminal.log(f"Semantic Error: Type mismatch involving '{var}' at line {line_no}")

def log_warning(dtype, value, var, line_no, terminal, reason):
    if reason == "FLOAT_FORMAT":
        terminal.log(f"WARNING!: Float literal exceeds allowed precision for '{var}' at line {line_no}")
    elif reason == "FLOAT_TRUNC":
        terminal.log(f"WARNING!: Floating point value truncated during assignment to '{var}' at line {line_no}")
    elif reason == "INT_TO_FLOAT":
        terminal.log(f"WARNING!: Integer expression converted to floating point for '{var}' at line {line_no}")

def strict_type_check_array(dtype, value, scope_stack):
    resolved = resolve_type(value, scope_stack)
    if resolved is None and _token_type_map:
        if _token_type_map.get(f"'{value}'") == "CHARLIT":
            resolved = "char"
        elif _token_type_map.get(f'"{value}"') == "STRLIT":
            resolved = "str"
        elif value in _token_type_map:
            ltype = _token_type_map[value]
            resolved = _LEXER_TO_SEMANTIC_TYPE.get(ltype)

    if dtype == "int":
        return resolved == "int"
    if dtype == "float":
        return resolved == "float"   
    if dtype == "char":
        return resolved == "char"
    if dtype == "str":
        return resolved == "str"
    if dtype == "bool":
        return value in ("trust", "betray")
    return False

def evaluate_expression(expr_tokens, scope_stack):
    if not expr_tokens:
        return None, False
    tokens = list(expr_tokens)
    while tokens and tokens[0] == "(" and tokens[-1] == ")":
        depth = 0
        all_balanced = True
        for i, t in enumerate(tokens):
            if t == "(":
                depth += 1
            elif t == ")":
                depth -= 1
            if depth == 0 and i < len(tokens) - 1:
                all_balanced = False
                break
        if all_balanced:
            tokens = tokens[1:-1]
        else:
            break
    if len(tokens) == 1:
        tok = tokens[0]
        if tok in ("0", "0.0"):
            return 0, True
        elif tok.isidentifier():
            entry = lookup(tok, scope_stack)
            if entry and "value" in entry:
                try:
                    num_val = float(str(entry["value"]).replace("_", ""))
                    return num_val, num_val == 0.0
                except Exception:
                    return None, False
        else:
            try:
                num_val = float(tok.replace("_", ""))
                return num_val, num_val == 0.0
            except Exception:
                return None, False
    try:
        values, operators = [], []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in ("+", "-", "*", "/", "//", "%", "^"):
                operators.append(tok)
            elif tok in ("(", ")"):
                i += 1
                continue
            else:
                if tok.isidentifier():
                    entry = lookup(tok, scope_stack)
                    if entry and "value" in entry:
                        values.append(float(str(entry["value"]).replace("_", "")))
                    else:
                        return None, False
                else:
                    values.append(float(tok.replace("_", "")))
            i += 1
        if not values or len(values) != len(operators) + 1:
            return None, False
        result = values[0]
        for op, nv in zip(operators, values[1:]):
            if op == "+":   result += nv
            elif op == "-": result -= nv
            elif op == "*": result *= nv
            elif op in ("/", "//"):
                if nv == 0: return None, False
                result = result / nv if op == "/" else int(result) // int(nv)
            elif op == "%":
                if nv == 0: return None, False
                result = int(result) % int(nv)
            elif op == "^": result **= nv
        return result, result == 0.0
    except Exception:
        return None, False

def evaluate_expression_with_chars(expr_tokens, scope_stack):
    tokens = list(expr_tokens)
    arithmetic_ops = {"+", "-", "*", "/", "//", "%", "^"}

    def tok_to_num(t):
        if t.startswith("'") and t.endswith("'") and len(t) >= 3:
            inner = t[1:-1]
            escape_map = {"\\n": 10, "\\t": 9, "\\\\": 92, "\\'": 39}
            if inner in escape_map:
                return float(escape_map[inner])
            if len(inner) == 1:
                return float(ord(inner))
            return None
        try:
            return float(t.replace("_", ""))
        except ValueError:
            pass
        entry = lookup(t, scope_stack)
        if entry and "value" in entry:
            v = entry["value"]
            if isinstance(v, str) and v.startswith("'") and v.endswith("'") and len(v) >= 3:
                inner = v[1:-1]
                if len(inner) == 1:
                    return float(ord(inner))
            try:
                return float(str(v).replace("_", ""))
            except Exception:
                return None
        return None

    values, operators = [], []
    for t in tokens:
        if t in ("(", ")"): continue
        if t in arithmetic_ops: operators.append(t)
        else:
            num = tok_to_num(t)
            if num is None: return None, False
            values.append(num)

    if not values or len(values) != len(operators) + 1:
        return None, False

    result = values[0]
    for op, nv in zip(operators, values[1:]):
        if op == "+": result += nv
        elif op == "-": result -= nv
        elif op == "*": result *= nv
        elif op in ("/", "//"):
            if nv == 0: return None, False
            result = result / nv if op == "/" else int(result) // int(nv)
        elif op == "%":
            if nv == 0: return None, False
            result = int(result) % int(nv)
        elif op == "^": result **= nv
    return result, True


def extract_echo_function_arg(tokens, start_idx):
    if start_idx >= len(tokens) or tokens[start_idx] != "echo":
        return None, None
    if start_idx + 1 >= len(tokens):
        return None, None
    func_name = tokens[start_idx + 1]
    if not func_name.isidentifier() or func_name in ("echo", "read", "spill", "core", "hope", "despair", "desire", "down"):
        return None, None
    paren_idx = start_idx + 2
    if paren_idx >= len(tokens) or tokens[paren_idx] != "(":
        return None, None
    arg_tokens, depth, idx = [], 1, paren_idx + 1
    while idx < len(tokens) and depth > 0:
        t = tokens[idx]
        if t == "(":
            depth += 1
            arg_tokens.append(t)
        elif t == ")":
            depth -= 1
            if depth > 0:
                arg_tokens.append(t)
        else:
            arg_tokens.append(t)
        idx += 1
    return func_name, arg_tokens


def check_array_element_access(tokens, scope_stack, variable_usage=None):
    if len(tokens) < 3:
        return None, None, None
    if tokens[0].isidentifier() and tokens[1] == "[":
        array_name = tokens[0]
        bracket_depth, bracket_end = 0, -1
        for idx, t in enumerate(tokens[1:], start=1):
            if t == "[":
                bracket_depth += 1
            elif t == "]":
                bracket_depth -= 1
                if bracket_depth == 0:
                    bracket_end = idx
                    break
        if bracket_end == -1:
            return None, None, None
        index_tokens = tokens[2:bracket_end]
        if not index_tokens:
            return None, None, None
        return array_name, index_tokens, tokens[bracket_end + 1:] if bracket_end + 1 < len(tokens) else []
    return None, None, None

#  validate_expression_and_operators                                  
def validate_expression_and_operators(tokens, scope_stack, terminal, line_no,
                                      check_standalone=True, variable_usage=None,
                                      popped_block_vars=None, in_spill=False):
    if not tokens:
        return True
    tokens = list(tokens)
    operator_skip_set = {
        "&&", "||", "!", "+", "-", "*", "/", "//", "%", "^",
        "=", "==", "!=", "<", ">", "<=", ">=",
        "+=", "-=", "*=", "/=", "//=", "%=", "^=",
        "(", ")", "++", "--", ";", ",", ":", ".", "[", "]", "{", "}",
        "echo", "read", "spill", "core", "hope", "nope", "desire", "down",
        "despair", "memory", "default",
        "brain", "heart", "closure", "fixed", "int", "float", "char", "str",
       "bool", "trust", "betray", "ID", "STRLIT", "INTLIT", "FLOATLIT", "CHARLIT"
    }

    # ++ / -- on fixed or str
    for i, token in enumerate(tokens):
        if token in ("++", "--"):
            candidate = None
            if i + 1 < len(tokens) and tokens[i + 1].isidentifier():
                candidate = tokens[i + 1]
            elif i > 0 and tokens[i - 1].isidentifier():
                candidate = tokens[i - 1]
            if candidate:
                entry = lookup(candidate, scope_stack)
                if entry and entry.get("fixed"):
                    terminal.log(f"Semantic Error: Fixed variable '{candidate}' cannot be modified with '{token}' operator at line {line_no}")
                    return False
                if entry and entry.get("type") == "str":
                    terminal.log(f"Semantic Error: str variable '{candidate}' cannot be used with unary operator at line {line_no}")
                    return False

    # division by zero
    division_ops = {"/", "//", "%", "/=", "//=", "%="}
    for i, token in enumerate(tokens):
        if token in division_ops and i + 1 < len(tokens):
            rhs_tokens = tokens[i + 1:]
            if rhs_tokens[0] in ("0", "0.0"):
                terminal.log(f"Semantic Error: Division by zero at line {line_no}")
                return False
            array_name, index_tokens, _ = check_array_element_access(rhs_tokens, scope_stack, variable_usage)
            if array_name:
                array_entry = lookup(array_name, scope_stack)
                if array_entry and array_entry.get("type") not in ("heart",):
                    index_val, _ = evaluate_expression(index_tokens, scope_stack)
                    if index_val is not None and isinstance(index_val, (int, float)):
                        idx = int(index_val)
                        elements = array_entry.get("elements", [])
                        array_size = array_entry.get("size", 0)
                        if 0 <= idx < len(elements) and 0 <= idx < array_size:
                            element_val = elements[idx]
                            is_partially_init = array_entry.get("partially_initialized", False)
                            has_init = array_entry.get("initialized", False)
                            try:
                                clean_val = str(element_val).replace("_", "")
                                if clean_val in ("0", "0.0") or element_val in (0, 0.0):
                                    if not has_init:
                                        # Array declared with empty initializer (e.g. int ARR[2] = {})
                                        # — all elements default to zero, so dividing by any element
                                        # is a guaranteed division by zero.
                                        terminal.log(f"Semantic Error: Division by zero at line {line_no}")
                                        return False
                                    elif is_partially_init:
                                        terminal.log(f"WARNING: Potential division by zero at line {line_no}")
                                    else:
                                        terminal.log(f"Semantic Error: Division by zero at line {line_no}")
                                        return False
                            except Exception:
                                if is_partially_init:
                                    terminal.log(f"WARNING: Potential division by zero at line {line_no}")
                if variable_usage and array_name in variable_usage:
                    variable_usage[array_name]["used"] = True
                continue
            if rhs_tokens[0] == "echo":
                func_name, arg_tokens = extract_echo_function_arg(rhs_tokens, 0)
                if func_name and arg_tokens:
                    val, is_zero = evaluate_expression(arg_tokens, scope_stack)
                    if is_zero:
                        terminal.log(f"Semantic Error: Division by zero at line {line_no}")
                        return False
                    for arg_tok in arg_tokens:
                        if arg_tok.isidentifier() and variable_usage and arg_tok in variable_usage:
                            variable_usage[arg_tok]["used"] = True
                    continue
                else:
                    terminal.log(f"Semantic Error: Invalid echo function call at line {line_no}")
                    return False
            if rhs_tokens[0] == "(":
                paren_depth, expr_end = 0, 0
                for j, t in enumerate(rhs_tokens):
                    if t == "(":
                        paren_depth += 1
                    elif t == ")":
                        paren_depth -= 1
                        if paren_depth == 0:
                            expr_end = j
                            break
                if expr_end > 0:
                    expr_tokens = rhs_tokens[1:expr_end]
                    val, is_zero = evaluate_expression(expr_tokens, scope_stack)
                    if is_zero:
                        terminal.log(f"Semantic Error: Division by zero at line {line_no}")
                        return False
                    for expr_tok in expr_tokens:
                        if expr_tok.isidentifier() and variable_usage and expr_tok in variable_usage:
                            variable_usage[expr_tok]["used"] = True
                continue
            if rhs_tokens[0].isidentifier():
                entry = lookup(rhs_tokens[0], scope_stack)
                if variable_usage and rhs_tokens[0] in variable_usage:
                    variable_usage[rhs_tokens[0]]["used"] = True
                if not entry:
                    terminal.log(f"Semantic Error: Undeclared identifier '{rhs_tokens[0]}' at line {line_no}")
                    return False
                # If the identifier is an array (has "elements"), skip the scalar
                # division-by-zero check — array element access is handled above.
                if "elements" in entry:
                    continue
                # Skip check if the variable is known to be modified at runtime
                # (assigned inside a desire/hope block) — let the interpreter handle it.
                if entry.get("modified_in_loop"):
                    continue
                if "value" in entry and entry.get("value") is not None:
                    try:
                        clean = str(entry["value"]).replace("_", "")
                        if clean in ("0", "0.0") or float(clean) == 0.0:
                            terminal.log(f"Semantic Error: Division by zero at line {line_no}")
                            return False
                    except Exception:
                        terminal.log(f"WARNING: Potential division by zero at line {line_no}")
                else:
                    # Value unknown at compile time; emit a warning, not a hard error
                    terminal.log(f"WARNING: Potential division by zero at line {line_no}")
            else:
                val, is_zero = evaluate_expression(rhs_tokens, scope_stack)
                if is_zero:
                    terminal.log(f"Semantic Error: Division by zero at line {line_no}")
                    return False

    # str cannot appear in any expression involving operators (no exceptions)
    _all_operators = {
        "+", "-", "*", "/", "//", "%", "^",
        "==", "!=", ">", "<", ">=", "<=",
        "&&", "||", "!",
        "+=", "-=", "*=", "/=", "//=", "%=", "^=",
        "++", "--"
    }
    has_any_operator = any(t in _all_operators for t in tokens)
    has_string = False
    has_numeric = False
    has_boolean = False
    for token in tokens:
        if token in operator_skip_set:
            continue
        tt = resolve_type(token, scope_stack)
        if tt == "str":
            has_string = True
        elif tt in ("int", "float", "char"):
            has_numeric = True
        elif tt == "bool":
            has_boolean = True

    # Check if this is an echo function call - arguments can have different types per parameter
    is_echo_call = (len(tokens) >= 4 and 
                    tokens[0] == "echo" and 
                    tokens[1].isidentifier() and 
                    tokens[2] == "(")
    
    if has_string and (has_numeric or has_boolean) and not in_spill and not is_echo_call:
        terminal.log(f"Semantic Error: Cannot mix str with numeric or bool types at line {line_no}")
        return False

    if has_string and has_any_operator:
        arithmetic_ops = {"+", "-", "*", "/", "//", "%", "^"}
        relational_ops = {">", "<", ">=", "<=", "==", "!="}
        logical_ops    = {"&&", "||", "!"}
        compound_ops   = {"+=", "-=", "*=", "/=", "//=", "%=", "^="}
        unary_ops      = {"++", "--"}
        for t in tokens:
            if t in arithmetic_ops:
                terminal.log(f"Semantic Error: str variable cannot be used with operator at line {line_no}")
                return False
            if t in relational_ops:
                terminal.log(f"Semantic Error: str variable cannot be used with operator at line {line_no}")
                return False
            if t in logical_ops:
                terminal.log(f"Semantic Error: str variable cannot be used with operator at line {line_no}")
                return False
            if t in compound_ops:
                terminal.log(f"Semantic Error: str variable cannot be used with operator at line {line_no}")
                return False
            if t in unary_ops:
                terminal.log(f"Semantic Error: str variable cannot be used with unary operator at line {line_no}")
                return False

    # arithmetic operators
    for i, token in enumerate(tokens):
        if token in ("+", "-", "*", "/", "//", "%") and 0 < i < len(tokens) - 1:
            lt = resolve_type(tokens[i - 1], scope_stack)
            rt = resolve_type(tokens[i + 1], scope_stack)
            if token == "+":
                if lt == "str" or rt == "str":
                    terminal.log(f"Semantic Error: Invalid operand for operator '+', str cannot be used in expressions at line {line_no}")
                    return False
            else:
                if lt == "str" or rt == "str":
                    terminal.log(f"Semantic Error: Invalid operand for operator '{token}', str not allowed at line {line_no}")
                    return False
                if lt == "bool" or rt == "bool":
                    terminal.log(f"Semantic Error: Invalid operand for operator '{token}', bool not allowed at line {line_no}")
                    return False
        elif token in ("+=", "-=", "*=", "/=", "//=", "%=", "^=") and i > 0:
            lt = resolve_type(tokens[i - 1], scope_stack)
            if lt == "str":
                terminal.log(f"Semantic Error: Invalid operand for operator '{token}': str not allowed at line {line_no}")
                return False
            if token != "+=":
                pass  # other checks handled above

    # logical operators
    for i, token in enumerate(tokens):
        if token in ("&&", "||") and 0 < i < len(tokens) - 1:
            if tokens[i - 1] == ")":
                left_type = "bool"
            else:
                has_relational = any(tokens[j] in ("<", ">", "<=", ">=", "==", "!=")
                                     for j in range(max(0, i - 5), i))
                left_type = "bool" if has_relational else resolve_type(tokens[i - 1], scope_stack)
            if tokens[i + 1] == "(":
                right_type = "bool"
            else:
                right_type = resolve_type(tokens[i + 1], scope_stack)
            if left_type and left_type == "str":
                terminal.log(f"Semantic Error: Invalid operand for logical operator '{token}' at line {line_no}")
                return False
            if right_type and right_type == "str":
                terminal.log(f"Semantic Error: Invalid operand for logical operator '{token}' at line {line_no}")
                return False
        elif token == "!" and i < len(tokens) - 1:
            operand_type = resolve_type(tokens[i + 1], scope_stack)
            if operand_type and operand_type == "str":
                terminal.log(f"Semantic Error: Invalid operand for logical operator '!' at line {line_no}")
                return False

    # relational / equality — str cannot be used with ANY operator including == and !=
    if any(tok in ("<", ">", "<=", ">=", "==", "!=") for tok in tokens):
        if any(resolve_type(t, scope_stack) == "str" for t in tokens):
            relational_ops = [t for t in tokens if t in ("<", ">", "<=", ">=", "==", "!=")]
            op = relational_ops[0] if relational_ops else "relational"
            terminal.log(f"Semantic Error: str variable cannot be used with operator at line {line_no}")
            return False

    # undeclared operand + mark used
    i = 0
    while i < len(tokens):
        token = tokens[i]
        
        # Skip entire echo call: echo FuncName ( ... )
        if token == "echo":
            i += 1  # skip "echo"
            if i < len(tokens):
                i += 1  # skip function name
            # Skip until end of parentheses
            if i < len(tokens) and tokens[i] == "(":
                paren_depth = 1
                i += 1
                while i < len(tokens) and paren_depth > 0:
                    if tokens[i] == "(":
                        paren_depth += 1
                    elif tokens[i] == ")":
                        paren_depth -= 1
                    i += 1
            continue
        
        if token not in operator_skip_set and not resolve_type(token, scope_stack):
            if is_literal(token):
                i += 1
                continue
            if popped_block_vars and token in popped_block_vars:
                terminal.log(f"Semantic Error: Variable in local control scope cannot be accessed outside. Error found at line {line_no}")
                return False
            terminal.log(f"Semantic Error: Undeclared identifier '{token}' at line {line_no}")
            return False
        
        # Check for array access without index (e.g. ARR instead of ARR[0])
        if token not in operator_skip_set:
            resolved = resolve_type(token, scope_stack)
            if resolved and token.isidentifier():
                entry = lookup(token, scope_stack)
                if entry and "size" in entry and not entry.get("is_2d"):
                    next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
                    if next_tok != "[":
                        terminal.log(f"Semantic Error: Array '{token}' must be accessed with an index  at line {line_no}")
                        return False
                elif entry and entry.get("is_2d"):
                    next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
                    if next_tok != "[":
                        terminal.log(f"Semantic Error: 2D array '{token}' must be accessed with two indices at line {line_no}")
                        return False
            if resolved and variable_usage and token in variable_usage:
                variable_usage[token]["used"] = True

        if variable_usage and token in variable_usage and token not in operator_skip_set:
            variable_usage[token]["used"] = True
        
        i += 1

    # check array index out of bounds when index is a loop variable
    i = 0
    while i < len(tokens):
        if tokens[i] == "[" and i > 0 and i + 1 < len(tokens):
            arr_name = tokens[i - 1]
            idx_tok  = tokens[i + 1]
            arr_entry = lookup(arr_name, scope_stack)
            if arr_entry and "size" in arr_entry:
                size = arr_entry.get("size", 0)
                if idx_tok.lstrip("-").isdigit():
                    idx_val = int(idx_tok)
                    if idx_val < 0 or idx_val >= size:
                        terminal.log(f"Semantic Error: Array index {idx_val} out of bounds for '{arr_name}' at line {line_no}")
                        return False
                elif idx_tok.isidentifier():
                    idx_entry = lookup(idx_tok, scope_stack)
                    if idx_entry and "max_value" in idx_entry:
                        if idx_entry["max_value"] > size:
                            terminal.log(f"Semantic Error: Array index of '{arr_name}' may exceed bounds (max index {idx_entry['max_value'] - 1}, size {size}) at line {line_no}")
                            return False
        i += 1

    return True

#  flatten_expr — parse-tree node -> flat token list                  
def flatten_expr(node):
    if node is None:
        return []
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        out = []
        for item in node:
            out.extend(flatten_expr(item))
        return out
    if not isinstance(node, dict):
        return []

    t = node.get("type", "")
    tokens = []

    if t == "exprDec":
        if "inner" in node:
            tokens.append("(")
            tokens.extend(flatten_expr(node.get("inner")))
            tokens.append(")")
        elif "exprOr" in node:                       
            tokens.extend(flatten_expr(node.get("exprOr")))  
        else:
            tokens.extend(flatten_expr(node.get("value")))
        tokens.extend(flatten_expr(node.get("exprTail")))

    elif t == "exprOr":
        tokens.extend(flatten_expr(node.get("left")))
        tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprOrTail":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))
            tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprAnd":
        tokens.extend(flatten_expr(node.get("left")))
        tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprAndTail":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))
            tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprRel":
        tokens.extend(flatten_expr(node.get("left")))
        tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprRelTail":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))
            tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprAdd":
        tokens.extend(flatten_expr(node.get("left")))
        tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprAddTail":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))
            tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprMul":
        tokens.extend(flatten_expr(node.get("left")))
        tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprMulTail":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))
            tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprExp":
        tokens.extend(flatten_expr(node.get("left")))
        tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprExpTail":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))
            tokens.extend(flatten_expr(node.get("tail")))

    elif t == "exprUnary":
        kind = node.get("kind")
        if kind == "!":
            tokens.append("!")
            tokens.extend(flatten_expr(node.get("operand")))
        elif kind in ("++", "--"):
            tokens.append(kind)
            tokens.append(node.get("name", ""))
            tokens.extend(flatten_expr(node.get("eleIndex")))
        else:
            tokens.extend(flatten_expr(node.get("primary")))

    elif t == "primary":
        kind = node.get("kind")
        if kind == "echo":
            tokens.append("echo")
            tokens.append(node.get("name", ""))
            tokens.append("(")
            tokens.extend(flatten_expr(node.get("echOp")))
            tokens.append(")")
        elif kind == "grouped":
            tokens.append("(")
            tokens.extend(flatten_expr(node.get("inner")))
            tokens.append(")")
        elif kind == "ID":
            tokens.append(node.get("name", ""))
            tokens.extend(flatten_expr(node.get("eleIndex")))
            una1 = node.get("una1") or {}
            if una1.get("op"):
                tokens.append(una1["op"])
        elif kind in ("INTLIT", "FLOATLIT", "CHARLIT", "trust", "betray"):
            tokens.append(node.get("value", ""))
        else:
            v = node.get("value") or node.get("name", "")
            if v:
                tokens.append(str(v))

    elif t == "exprTail":
        op = node.get("op")
        if op:
            tokens.append(op)
            tokens.extend(flatten_expr(node.get("right")))
        tokens.extend(flatten_expr(node.get("tail")))
        tokens.extend(flatten_expr(node.get("exprTail")))

    elif t == "assVal":
        tokens.extend(flatten_expr(node.get("value")))
        tokens.extend(flatten_expr(node.get("exprDec")))

    elif t == "closureCon":
        tokens.extend(flatten_expr(node.get("value")))

    elif t == "coreCon":
        tokens.extend(flatten_expr(node.get("coreAdd")))

    elif t == "coreAdd":
        tokens.extend(flatten_expr(node.get("left")))
        tokens.extend(flatten_expr(node.get("tail")))

    elif t == "coreAddTail":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))
            tokens.extend(flatten_expr(node.get("tail")))

    elif t == "coreMul":
        tokens.extend(flatten_expr(node.get("left")))
        tokens.extend(flatten_expr(node.get("tail")))

    elif t == "coreMulTail":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))
            tokens.extend(flatten_expr(node.get("tail")))

    elif t == "coreExp":
        tokens.extend(flatten_expr(node.get("left")))
        tokens.extend(flatten_expr(node.get("tail")))

    elif t == "coreExpTail":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))
            tokens.extend(flatten_expr(node.get("tail")))

    elif t == "coreUnary":
        kind = node.get("kind")
        if kind in ("++", "--"):
            tokens.append(kind)
            tokens.append(node.get("name", ""))
            tokens.extend(flatten_expr(node.get("eleIndex")))
        else:
            tokens.extend(flatten_expr(node.get("primary")))

    elif t == "corePrimary":
        kind = node.get("kind")
        if kind == "echo":
            tokens.append("echo")
            tokens.append(node.get("name", ""))
            tokens.append("(")
            tokens.extend(flatten_expr(node.get("echOp")))
            tokens.append(")")
        elif kind == "grouped":
            tokens.append("(")
            tokens.extend(flatten_expr(node.get("inner")))
            tokens.append(")")
        elif kind == "ID":
            tokens.append(node.get("name", ""))
            tokens.extend(flatten_expr(node.get("eleIndex")))
            una1 = node.get("una1") or {}
            if una1.get("op"):
                tokens.append(una1["op"])
        elif kind in ("INTLIT", "CHARLIT"):
            tokens.append(node.get("value", ""))
        else:
            v = node.get("value") or node.get("name", "")
            if v:
                tokens.append(str(v))

    elif t == "locDecOp":
        tokens.extend(flatten_expr(node.get("value")))

    elif t == "locDec":
        tokens.extend(flatten_expr(node.get("locDecOp")))
        tokens.extend(flatten_expr(node.get("arOpt")))

    elif t == "gDecOp":
        tokens.extend(flatten_expr(node.get("value")))

    elif t == "echOp":
        args = node.get("args", [])
        for i, arg in enumerate(args):
            if i:
                tokens.append(",")
            tokens.extend(flatten_expr(arg))

    elif t == "unaOp":
        tokens.extend(flatten_expr(node.get("eleIndex")))
        tokens.extend(flatten_expr(node.get("una1")))

    elif t == "eleIndex":
        if node.get("index") is not None:
            tokens.append("[")
            idx = node["index"]
            if isinstance(idx, dict):
                tokens.extend(flatten_expr(idx))
            else:
                tokens.append(str(idx))
            tokens.append("]")
        idx2_node = node.get("index2") or {}
        idx2 = idx2_node.get("index")
        if idx2 is not None:
            tokens.append("[")
            tokens.append(str(idx2))
            tokens.append("]")

    elif t == "coreVal":
        if node.get("op"):
            tokens.append(node["op"])
            tokens.extend(flatten_expr(node.get("right")))

    elif t in ("literal", "litOp"):
        tokens.append(str(node.get("value", "")))

    elif t == "strVal":
        kind = node.get("kind")
        if kind == "echo":
            tokens.append("echo")
            tokens.append(node.get("name", ""))
            tokens.append("(")
            tokens.extend(flatten_expr(node.get("echOp")))
            tokens.append(")")
        elif kind == "STRLIT":
            tokens.append(node.get("value", ""))
        elif kind == "ID":
            tokens.append(node.get("name", ""))
            tokens.extend(flatten_expr(node.get("eleIndex")))

    elif t in ("strTail", "strTail1"):
        tokens.extend(flatten_expr(node.get("strTail1")))
        tokens.extend(flatten_expr(node.get("arOpt")))
        tokens.extend(flatten_expr(node.get("value")))

    else:
        for key, val in node.items():
            if key in ("type", "line"):
                continue
            tokens.extend(flatten_expr(val))

    return [tok for tok in tokens if tok is not None and tok != ""]

#  get_rhs_value from a tree node                                     
def get_rhs_value_from_node(rhs_node, function_table, scope_stack):
    if rhs_node is None:
        return "__expr__"
    rhs_tokens = [t for t in flatten_expr(rhs_node) if t != ";"]

    if len(rhs_tokens) >= 2 and rhs_tokens[0] == "echo":
        func_name = rhs_tokens[1]
        if function_table and func_name in function_table:
            paren_start = -1
            for idx, t in enumerate(rhs_tokens):
                if t == "(":
                    paren_start = idx
                    break
            if paren_start >= 0:
                depth, paren_end = 0, paren_start
                for idx in range(paren_start, len(rhs_tokens)):
                    if rhs_tokens[idx] == "(":
                        depth += 1
                    elif rhs_tokens[idx] == ")":
                        depth -= 1
                        if depth == 0:
                            paren_end = idx
                            break
                remaining = rhs_tokens[paren_end + 1:]
                operators = {"+", "-", "*", "/", "%", "//", "^", "<", ">",
                             "<=", ">=", "==", "!=", "&&", "||", "("}
                has_operator = any(t in operators for t in remaining if t != ";")
                if has_operator:
                    return f"__echo_{function_table[func_name]['return']}_expr__"
                else:
                    return f"__echo_{function_table[func_name]['return']}_direct__"
            else:
                return f"__echo_{function_table[func_name]['return']}_direct__"

    if len(rhs_tokens) > 1:
        # check if it's just a parenthesized single literal e.g. (trust), (1), ('A')
        inner = [t for t in rhs_tokens if t not in ("(", ")")]
        if len(inner) == 1:
            # treat as direct literal, not expression
            return inner[0]
        if scope_stack:
            expr_type = resolve_expression_type(rhs_tokens, scope_stack, function_table)
            if expr_type:
                return f"__expr_{expr_type}__"
        return "__expr__"

    rhs_clean = [t for t in rhs_tokens if t not in ("(", ")", ";")]
    if any(t in ("<", ">", "<=", ">=", "==", "!=") for t in rhs_clean):
        return "__bool_expr__"

    return rhs_tokens[0] if rhs_tokens else ""

# =============================== Semantic array check ========================                                            
def semantic_array_check(array_name, dtype, declared_size, elements, line_no, terminal,
                          has_initializer=False, scope_stack=None):
    # zero as array size error
    if declared_size <= 0:
        terminal.log(f"Semantic Error: Array '{array_name}' size must be positive/nonzero at line {line_no}")
        return [], True
    checked = []
    had_error = False 

    # array element mistmach error
    for elem in elements:
        if not strict_type_check_array(dtype, str(elem), scope_stack or []):
            terminal.log(f"Semantic Error: Array '{array_name}' element '{elem}' does not match type '{dtype}' at line {line_no}")
            had_error = True
        checked.append(elem)

    # array initialized with too many elements error
    if len(checked) > declared_size:
        terminal.log(f"Semantic Error: Array '{array_name}' initialized with too many elements at line {line_no}")
        checked = checked[:declared_size]
        had_error = True

    # array partially initialized takes default value warning
    if len(checked) < declared_size:
        defaults = {"int": 0, "float": 0.0, "char": "", "str": " ", "bool": "trust"}
        missing = declared_size - len(checked)
        default_val = defaults.get(dtype, 0)
        if has_initializer: 
            terminal.log(f"WARNING: Array '{array_name}' is partially initialized at line {line_no}. "
                         f"{missing} missing element(s) will default to '{default_val}'.")
        checked += [default_val] * missing
    return checked, had_error

# ================================= SemanticVisitor ===================================================                                                 
class SemanticVisitor:

    def __init__(self, terminal):
        self.terminal             = terminal
        self.ok                   = True
        self.scope_stack          = [{}]
        self.function_table       = {}
        self.variable_usage       = {}
        # Maps var_name -> (scope_depth, cond_depth) where:
        #   scope_depth = len(scope_stack) when the var's scope was popped
        #   cond_depth  = self._cond_depth when popped (conditional nesting counter)
        # This lets declare_var distinguish:
        #   - vars from sibling/outer scopes (should conflict) 
        #   - vars from inside a sibling hope/despair branch (should NOT conflict)
        # Maps var_name -> list of (scope_depth, cond_id) entries.
        # scope_depth = len(scope_stack) when the var's scope was popped.
        # cond_id     = the ID of the innermost active hope/despair structure (or None).
        # Each visit_hope() call generates a unique cond_id for the whole hope+despair chain.
        # Conflict: scope_depth<=current AND cond_id matches current active cond_id.
        self.popped_block_vars    = {}
        # Stack of active conditional structure IDs (one per nested hope/despair chain).
        self._cond_id_stack       = []
        # Monotonically increasing counter for unique cond IDs.
        self._cond_id_counter     = 0
        self.core_type            = None
        self.core_type_stack      = []
        self.memory_labels        = set()
        self.memory_labels_stack  = []
        self.default_seen         = False
        self.function_context_stack = []
        self.block_context_stack    = []
        self.void_errors_reported  = set()  # Track (line, func_name) to avoid duplicate void errors
        self.init_errors_reported  = set()  # Track (line, var_name) to avoid duplicate initialization errors
        # Track which memory blocks have already emitted a missing-'over' warning
        self._warned_memory_blocks = set()
        # Incremental id used to tag memory scopes for deduplication
        self._memory_id_counter = 0
        # Track parameters for each function to detect duplicates across different hearts
        self.function_params      = {}
        # Track which functions have been called via echo
        self.called_functions     = set()
        # Track line numbers where functions are declared
        self.function_decl_lines  = {}
        # Track names declared anywhere inside the current core (to detect redecls across memory blocks)
        self.core_declared_names_stack = []
        # Stack to track names declared within the current conditional structure
        # (a 'hope' and its corresponding 'despair' blocks). Each entry is a set
        # of variable names declared anywhere inside that conditional structure.
        self.conditional_decl_stack = []

    # ---- helpers ----
    def err(self, msg, line):
        self.terminal.log(f"Semantic Error: {msg} at line {line}")
        self.ok = False

    def warn(self, msg, line):
        self.terminal.log(f"WARNING: {msg} at line {line}")

    def push_scope(self, ctx):
        self.scope_stack.append({})
        self.block_context_stack.append(ctx)

    def pop_scope(self, line_no):
        if len(self.scope_stack) <= 1:
            return
        popped = self.scope_stack.pop()
        popped_ctx = self.block_context_stack.pop() if self.block_context_stack else None

        if popped_ctx == "core":
            if self.core_type_stack:
                self.core_type_stack.pop()
            self.core_type = self.core_type_stack[-1] if self.core_type_stack else None
            if self.memory_labels_stack:
                self.memory_labels.clear()
                self.memory_labels.update(self.memory_labels_stack.pop())
            # pop core-declared names stack if present
            if self.core_declared_names_stack:
                try:
                    self.core_declared_names_stack.pop()
                except Exception:
                    pass

        if popped_ctx in ("hope", "despair", "desire", "while", "do-while", "core", "memory"):
            # Record each popped variable as a (scope_depth, cond_id) entry.
            # We store a LIST of entries per var so that the same name declared
            # in multiple independent conditional structures all get tracked.
            current_sd = len(self.scope_stack)  # depth AFTER the pop
            # Only hope/despair scopes tag vars with a cond_id so that vars from one
            # conditional branch don't falsely conflict in a sibling branch.
            # Vars from loops/core/memory use cid=None, meaning they conflict on
            # depth alone regardless of which hope/despair chain is currently active.
            if popped_ctx in ("hope", "despair"):
                current_cid = self._cond_id_stack[-1] if self._cond_id_stack else None
            else:
                current_cid = None
            for v in popped:
                if not str(v).startswith("__"):
                    entry = (current_sd, current_cid)
                    if v not in self.popped_block_vars:
                        self.popped_block_vars[v] = [entry]
                    else:
                        self.popped_block_vars[v].append(entry)

        if popped_ctx == "memory":
            if not popped.get("__over_seen__", False):
                # Determine a stable key for this memory (prefer assigned id)
                mem_id = popped.get("__memory_id__")
                if mem_id is None:
                    mem_id = popped.get("__mem_key__")
                # If we haven't warned for this memory id/key yet, emit warning
                if mem_id not in self._warned_memory_blocks:
                    self._warned_memory_blocks.add(mem_id)
                    mem_key = popped.get("__mem_key__")
                    mem_label = None
                    if isinstance(mem_key, tuple) and len(mem_key) >= 1:
                        mem_label = mem_key[0]
                    elif isinstance(mem_key, str):
                        mem_label = mem_key

                    if mem_label:
                        self.terminal.log(f"WARNING: 'over' is missing for memory '{mem_label}' at line {line_no}")
                    else:
                        self.terminal.log(f"WARNING: 'over' is missing for memory at line {line_no}")

    def current_scope(self):
        return self.scope_stack[-1]
    
    def mark_initialized(self, var_name):
        """Mark a variable as initialized in its scope."""
        entry = lookup(var_name, self.scope_stack)
        if entry:
            entry["initialized"] = True
        if var_name in self.variable_usage:
            self.variable_usage[var_name]["initialized"] = True

    def exists_in_any_scope(self, name):
        """Return True if the name exists in any active scope (including global)."""
        if not name or str(name).startswith("__"):
            return False
        for scope in self.scope_stack:
            if name in scope:
                return True
        return False

    def _popped_is_conflict(self, name):
        #Return True if any entry for 'name' in popped_block_vars is a conflict.
        if name not in self.popped_block_vars:
            return False
        current_sd  = len(self.scope_stack)
        current_cid = self._cond_id_stack[-1] if self._cond_id_stack else None
        for (sd, cid) in self.popped_block_vars[name]:
            if cid is None:
                # loop / core / memory var: depth-based check
                if sd <= current_sd:
                    return True
            else:
                # hope / despair var
                if cid == current_cid:
                    # same chain → sibling branch → no conflict
                    pass
                else:
                    # different chain → independent prior declaration → conflict
                    return True
        return False


    def is_global(self):
        return len(self.scope_stack) == 1 and len(self.function_context_stack) == 0
    
    # redeclaration / shadowing not allowed error 
    def declare_var(self, name, dtype, fixed, line, is_array=False):
        # Disallow shadowing: variable name must be unique across all scopes
        cur = self.current_scope()
        if name and not str(name).startswith("__") and self.exists_in_any_scope(name):
            # If it's in the same scope we still show the same message; otherwise
            # report as a shadowing/redeclaration error.
            self.err(f"Variable '{name}' already declared in this scope. Error found", line)
            return False

        # If the name was previously declared in any control-structure scope that has
        # since been popped at the SAME OR OUTER nesting level (sibling blocks, outer
        # loops, etc.), disallow redeclaration.  Variables that were declared only
        # inside a deeper nested block that has since closed are NOT a conflict here.
        if name and not str(name).startswith("__") and self._popped_is_conflict(name):
            self.err(f"Variable '{name}' already declared in this scope. Error found", line)
            return False

        # If we're inside a core, also disallow redeclaration across memory blocks
        if self.core_declared_names_stack:
            core_names = self.core_declared_names_stack[-1]
            if name in core_names:
                self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                return False

        # If we are inside an active hope/despair conditional structure,
        # disallow redeclaration of the same identifier anywhere within that
        # conditional structure (covers hope vs despair redecls).
        try:
            current_ctx = self.block_context_stack[-1] if self.block_context_stack else None
            if self.conditional_decl_stack and current_ctx in ("hope", "despair"):
                if name in self.conditional_decl_stack[-1]:
                    self.err(f"Redeclaration of variable '{name}' inside the same conditional structure. Error found", line)
                    return False
        except Exception:
            pass

        # Declare variable in current scope
        cur[name] = {"type": dtype, "fixed": fixed, "is_array": is_array, "initialized": False}
        self.variable_usage[name] = {"declared_line": line, "used": False,
                                      "type": "fixed" if fixed else "normal"}

        # If inside a core, record the name to prevent redecls in sibling memory blocks
        if self.core_declared_names_stack:
            try:
                self.core_declared_names_stack[-1].add(name)
            except Exception:
                pass
        # If we are inside a hope/despair conditional structure, record this
        # declaration so that the matching counterpart block can detect
        # redeclarations within the same conditional structure.
        try:
            current_ctx = self.block_context_stack[-1] if self.block_context_stack else None
            if self.conditional_decl_stack and current_ctx in ("hope", "despair"):
                # Add name to the active conditional declaration set
                self.conditional_decl_stack[-1].add(name)
        except Exception:
            pass
        return True

    def _max_line_in_node(self, node):
        """Recursively find the maximum 'line' value inside a parse-tree node."""
        if node is None:
            return 0
        max_line = 0
        if isinstance(node, dict):
            max_line = max(max_line, node.get("line", 0) or 0)
            for val in node.values():
                if isinstance(val, dict) or isinstance(val, list):
                    mx = self._max_line_in_node(val)
                    if mx > max_line:
                        max_line = mx
        elif isinstance(node, list):
            for item in node:
                mx = self._max_line_in_node(item)
                if mx > max_line:
                    max_line = mx
        return max_line

    def _split_function_args(self, arg_tokens):
        """Split argument tokens by commas at depth 0."""
        if not arg_tokens:
            return []
        args = []
        current_arg = []
        depth = 0
        
        for tok in arg_tokens:
            if tok == "(":
                depth += 1
                current_arg.append(tok)
            elif tok == ")":
                depth -= 1
                current_arg.append(tok)
            elif tok == "," and depth == 0:
                if current_arg:
                    args.append(current_arg)
                current_arg = []
            else:
                current_arg.append(tok)
        
        if current_arg:
            args.append(current_arg)
        
        return args

    def _validate_echo_calls_in_tokens(self, tokens, line, skip_void_check=False):
        """Find and validate all echo calls in a flat token list."""
        processed_indices = set()
        for echo_idx, tok in enumerate(tokens):
            if tok == "echo" and echo_idx not in processed_indices:
                func_name, arg_tokens_all = extract_echo_function_arg(tokens, echo_idx)
                if func_name and arg_tokens_all is not None:
                    processed_indices.add(echo_idx)
                    args = self._split_function_args(arg_tokens_all)
                    self._validate_echo_call_args(func_name, args, line, tokens, echo_idx, skip_void_check)

    def _validate_echo_call_args(self, func_name, args, line, all_tokens=None, echo_idx=None, skip_void_check=False):
        """Validate an echo call with already-split arguments (flat tokens)."""
        ft = self.function_table.get(func_name)
        if not ft:
            self.err(f"Function called before declaration: `{func_name}()`", line)
            return
        
        # Mark function as called
        self.called_functions.add(func_name)
        expected_count = ft["params"]
        expected_types = ft.get("param_types", [])
        return_type = ft.get("return", "void")
        
        actual = len(args)
        if actual != expected_count:
            self.err(f"Function '{func_name}' requires {expected_count} arguments, but received {actual}", line)
            return
        
        # Check for recursive heart calls (warning only)
        if self.function_context_stack:
            current_func_ctx = self.function_context_stack[-1]
            if current_func_ctx.get("type") == "heart" and current_func_ctx.get("func_name") == func_name:
                self.warn(f"Heart '{func_name}' calls itself recursively", line)
        
        # Check if void heart is used in an expression (skip if in condition context)
        if return_type == "void" and all_tokens is not None and echo_idx is not None and not skip_void_check:
            error_key = (line, func_name)
            if error_key not in self.void_errors_reported:
                if self._check_void_in_expression(all_tokens, echo_idx, func_name, line):
                    self.err(f"Void heart used in expression: Using `void` heart as operand", line)
                    self.void_errors_reported.add(error_key)
        
        # Validate each argument's type
        for idx, arg_tokens in enumerate(args):
            if idx >= len(expected_types):
                break
            
            expected_type = expected_types[idx]
            arg_type = None
            
            # Clean up the argument tokens
            arg_tokens_clean = [t for t in arg_tokens if t not in ("(", ")", ";")]
            
            if not arg_tokens_clean:
                continue
            
            # Check if it's an echo function call
            if arg_tokens_clean[0] == "echo" and len(arg_tokens_clean) > 1:
                nested_func = arg_tokens_clean[1]
                if nested_func in self.function_table:
                    arg_type = self.function_table[nested_func].get("return")
                else:
                    arg_type = resolve_type(arg_tokens_clean[0], self.scope_stack)
            else:
                arg_type = resolve_expression_type(arg_tokens_clean, self.scope_stack, self.function_table)
                if not arg_type:
                    arg_type = resolve_type(arg_tokens_clean[0], self.scope_stack) if arg_tokens_clean else None
            
            # --- Array index used as argument: strict type check + ASCII bounds ---
            arr_name_arg, arr_idx_tokens, arr_rest = check_array_element_access(arg_tokens_clean, self.scope_stack)
            if arr_name_arg and arr_rest is not None and len(arr_rest) == 0:
                arr_entry = lookup(arr_name_arg, self.scope_stack)
                if arr_entry and "size" in arr_entry:
                    arr_dtype = arr_entry.get("type")  # e.g. "int"
                    # Strict mismatch: array element type must match param type
                    # except int <-> char with ASCII bounds check
                    if arr_dtype and arr_dtype != expected_type:
                        if arr_dtype == "int" and expected_type == "char":
                            # Allow only if element value is in ASCII 32-125
                            idx_val, _ = evaluate_expression(arr_idx_tokens, self.scope_stack)
                            if idx_val is not None:
                                idx_int = int(idx_val)
                                elements = arr_entry.get("elements", [])
                                arr_size = arr_entry.get("size", 0)
                                if 0 <= idx_int < len(elements) and 0 <= idx_int < arr_size:
                                    elem_val = elements[idx_int]
                                    try:
                                        num_val = int(str(elem_val))
                                        if not (32 <= num_val <= 125):
                                            self.err(f"Argument {idx + 1} is out of the allowable ASCII range (32-125)", line)
                                    except (ValueError, TypeError):
                                        self.err(f"Type mismatch: Expected type '{expected_type}', got '{arr_dtype}'", line)
                                else:
                                    pass  # out of bounds handled elsewhere
                            else:
                                pass  # dynamic index, skip static check
                        elif arr_dtype == "char" and expected_type == "int":
                            # char -> int is allowed if value in ASCII 32-125
                            idx_val, _ = evaluate_expression(arr_idx_tokens, self.scope_stack)
                            if idx_val is not None:
                                idx_int = int(idx_val)
                                elements = arr_entry.get("elements", [])
                                arr_size = arr_entry.get("size", 0)
                                if 0 <= idx_int < len(elements) and 0 <= idx_int < arr_size:
                                    elem_val = elements[idx_int]
                                    elem_str = str(elem_val)
                                    if elem_str.startswith("'") and elem_str.endswith("'") and len(elem_str) == 3:
                                        ascii_val = ord(elem_str[1])
                                        if not (32 <= ascii_val <= 125):
                                            self.err(f"Argument {idx + 1} is out of the allowable ASCII range (32-125)", line)
                        else:
                            self.err(f"Type mismatch: Expected type '{expected_type}', got '{arr_dtype}'", line)
                    continue

            # --- Char literal used as int argument: ASCII bounds check ---
            if len(arg_tokens_clean) == 1 and arg_tokens_clean[0].startswith("'") and arg_tokens_clean[0].endswith("'"):
                char_tok = arg_tokens_clean[0]
                if expected_type == "int" and len(char_tok) == 3:
                    ascii_val = ord(char_tok[1])
                    if not (32 <= ascii_val <= 125):
                        self.err(f"Character '{char_tok}' is out of the allowable ASCII range (32-125)", line)
                    continue
                elif expected_type == "char":
                    continue  # char to char is fine

            # --- Int literal used as char argument: ASCII bounds check ---
            if len(arg_tokens_clean) == 1 and arg_tokens_clean[0].lstrip("-").isdigit():
                int_tok = arg_tokens_clean[0]
                if expected_type == "char":
                    num_val = int(int_tok)
                    if not (32 <= num_val <= 125):
                        self.err(f"Argument {idx + 1} is out of the allowable ASCII range (32-125)", line)
                    continue

            # Type checking: for literals, enforce strict type matching
            if arg_type and arg_type != expected_type:
                is_expr = contains_expression(arg_tokens_clean) or len(arg_tokens_clean) > 1

                if is_expr:
                    # For expressions, allow some automatic conversions
                    allowed = (
                        (arg_type == "int"   and expected_type == "float") or
                        (arg_type == "float" and expected_type == "int")   or
                        (arg_type == "char"  and expected_type == "int")   or
                        (arg_type == "int"   and expected_type == "char")  or
                        (arg_type == "float" and expected_type == "char")  or
                        (arg_type == "char"  and expected_type == "float") or
                        (arg_type == "int"   and expected_type == "bool")  or
                        (arg_type == "bool"  and expected_type == "int")   or
                        (arg_type == "float" and expected_type == "bool")  or
                        (arg_type == "bool"  and expected_type == "float")
                    )
                    if not allowed:
                        self.err(f"Type mismatch: Expected type '{expected_type}', got '{arg_type}'", line)
                else:
                    # For literal values, enforce strict type matching
                    self.err(f"Type mismatch: Expected type '{expected_type}', got '{arg_type}'", line)
            
            # Mark variables as used and check for undeclared identifiers
            operator_skip_set = {
                "&&", "||", "!", "+", "-", "*", "/", "//", "%", "^",
                "=", "==", "!=", "<", ">", "<=", ">=",
                "+=", "-=", "*=", "/=", "//=", "%=", "^=",
                "(", ")", "++", "--", ";", ",", ":", ".", "[", "]", "{", "}",
                "echo", "read", "spill", "core", "hope", "nope", "desire", "down",
                "despair", "memory", "default",
                "brain", "heart", "closure", "fixed", "int", "float", "char", "str",
                "bool", "trust", "betray"
            }
            for i, tok in enumerate(arg_tokens_clean):
                if tok not in operator_skip_set:
                    # If this token is a function name immediately following an
                    # `echo` inside the same argument (i.e. a nested echo call),
                    # skip the undeclared identifier check because functions are
                    # tracked in `self.function_table`, not the scope stack.
                    if tok.isidentifier() and i > 0 and arg_tokens_clean[i - 1] == "echo":
                        # still mark as used if it's a variable name (unlikely for
                        # a function name) but do not treat it as an undeclared id
                        # error here.
                        continue

                    # Check if it's an undeclared identifier
                    if tok.isidentifier() and not resolve_type(tok, self.scope_stack):
                        self.err(f"Undeclared identifier '{tok}' in argument {idx + 1}", line)
                    # Mark as used if it exists
                    if tok in self.variable_usage:
                        self.variable_usage[tok]["used"] = True

    def _check_void_in_expression(self, all_tokens, echo_idx, func_name, line):
        """Check if a void heart is being used as an operand in an expression."""
        operators = {"+", "-", "*", "/", "//", "%", "^", "==", "!=", "<", ">", "<=", ">=", "&&", "||"}
        
        # Find the end of the echo call in the token list
        # echo FuncName ( args )
        paren_depth = 0
        echo_end_idx = echo_idx + 2  # Skip "echo" and function name
        
        if echo_end_idx < len(all_tokens) and all_tokens[echo_end_idx] == "(":
            paren_depth = 1
            echo_end_idx += 1
            while echo_end_idx < len(all_tokens) and paren_depth > 0:
                if all_tokens[echo_end_idx] == "(":
                    paren_depth += 1
                elif all_tokens[echo_end_idx] == ")":
                    paren_depth -= 1
                echo_end_idx += 1
            echo_end_idx -= 1  # Point to the closing parenthesis
        
        # Check if there's an operator before or after the echo call
        has_operator_before = echo_idx > 0 and all_tokens[echo_idx - 1] in operators
        has_operator_after = echo_end_idx + 1 < len(all_tokens) and all_tokens[echo_end_idx + 1] in operators
        
        # Note: Error message is handled by log_type_error() to avoid duplicate messages
        return has_operator_before or has_operator_after

    def check_and_store_value(self, dtype, name, rhs_node, line, fixed=False):
        if rhs_node is None:
            return
        rhs_tokens = [t for t in flatten_expr(rhs_node) if t != ";"]

        # self-reference check: variable must not appear in its own initialization
        if name and name in rhs_tokens:
            self.err(f"Variable '{name}' cannot be referenced in its own initialization", line)
            self.ok = False
            return
        
        if self.is_global() and contains_expression(rhs_tokens):
            self.err("Expressions are not allowed in global scope", line)
            return
        # str cannot appear in any expression with operators (including ++ / --)
        if contains_expression(rhs_tokens):
            unary_ops = {"++", "--"}
            for idx, tok in enumerate(rhs_tokens):
                # Check str literal (e.g. "hello") in an expression
                if (tok.startswith('"') and tok.endswith('"')) or (tok.isidentifier() and resolve_type(tok, self.scope_stack) == "str"):
                    self.err(f"str value cannot be used in an expression", line)
                    self.ok = False
                    return
                # Check ++ / -- applied to a str identifier
                if tok in unary_ops:
                    # prefix: tok at i, identifier at i+1
                    if idx + 1 < len(rhs_tokens) and rhs_tokens[idx + 1].isidentifier():
                        candidate = rhs_tokens[idx + 1]
                        if resolve_type(candidate, self.scope_stack) == "str":
                            self.err(f"str variable cannot be used with unary operator", line)
                            self.ok = False
                            return
                    # postfix: tok at i, identifier at i-1
                    if idx > 0 and rhs_tokens[idx - 1].isidentifier():
                        candidate = rhs_tokens[idx - 1]
                        if resolve_type(candidate, self.scope_stack) == "str":
                            self.err(f"str variable cannot be used with unary operator", line)
                            self.ok = False
                            return
        
        # Validate echo calls in RHS
        self._validate_echo_calls_in_tokens(rhs_tokens, line)

        # Check if void heart is being assigned to a variable during declaration (e.g., int X = echo VOID_FUNC();)
        if len(rhs_tokens) >= 2 and rhs_tokens[0] == "echo":
            echo_func_name = rhs_tokens[1]
            if echo_func_name in self.function_table:
                func_return_type = self.function_table[echo_func_name].get("return", "void")
                if func_return_type == "void":
                    self.err(f"Void heart '{echo_func_name}' cannot be assigned to variable '{name}'", line)
                    self.ok = False
                    return

        for tok in rhs_tokens:
            if tok in self.variable_usage:
                self.variable_usage[tok]["used"] = True

        # check array out of bounds sa RHS ng declaration
        for i, tok in enumerate(rhs_tokens):
            if tok == "[" and i > 0 and i + 1 < len(rhs_tokens):
                arr_name = rhs_tokens[i - 1]
                idx_tok = rhs_tokens[i + 1]
                arr_entry = lookup(arr_name, self.scope_stack)
                if arr_entry and "size" in arr_entry and idx_tok.lstrip("-").isdigit():
                    idx_val = int(idx_tok)
                    size = arr_entry.get("size", 0)
                    if idx_val < 0 or idx_val >= size:
                        self.err(f"Array index {idx_val} out of bounds for '{arr_name}'", line)
                        self.ok = False
                        return
        
        if not validate_expression_and_operators(rhs_tokens, self.scope_stack, self.terminal, line,
                                                  check_standalone=False,
                                                  variable_usage=self.variable_usage,
                                                  popped_block_vars=self.popped_block_vars):
            self.ok = False
            return
        
        # 03/1/2026: check for char literals and int literals that are out of ASCII range.
        if dtype in ("char", "int") and contains_expression(rhs_tokens):
            has_char_lit = any(t.startswith("'") and t.endswith("'") and len(t) >= 3 for t in rhs_tokens)
            has_int_lit = any(t.lstrip("-").isdigit() for t in rhs_tokens)
            if has_char_lit or (dtype == "char" and has_int_lit):
                computed, success = evaluate_expression_with_chars(rhs_tokens, self.scope_stack)
                if success and computed is not None:
                    if not (32 <= int(computed) <= 126):
                        self.terminal.log(f"Semantic Error: Not Fit to the allowable ASCII range 32 - 126 '{name}' at line {line}")
                        self.ok = False
                        return
                    
        value = get_rhs_value_from_node(rhs_node, self.function_table, self.scope_stack)
        ok, reason = type_check(dtype, value, self.scope_stack)
    
        if not ok:
            log_type_error(dtype, value, name, line, self.terminal, reason)
            self.ok = False
        elif reason:
            log_warning(dtype, value, name, line, self.terminal, reason)

        self.mark_initialized(name)
        if len(rhs_tokens) == 1:
            # Mark variable as initialized after successful assignment
            tv = rhs_tokens[0]
            

            if is_literal(tv):
                self.current_scope()[name]["value"] = tv
            elif tv.isidentifier():
                src = lookup(tv, self.scope_stack)
                if src and "value" in src:
                    self.current_scope()[name]["value"] = src.get("value")

    
    #  =================== Visit dispatcher ============================                                               

    def visit(self, node):
        if node is None:
            return
        if not isinstance(node, dict):
            return
        t = node.get("type", "")
        method = getattr(self, f"visit_{t}", self.visit_generic)
        method(node)

    def visit_generic(self, node):
        for key, val in node.items():
            if key in ("type", "line"):
                continue
            if isinstance(val, dict):
                self.visit(val)
            elif isinstance(val, list):
                for item in val:
                    self.visit(item)

    # ============================ visit program ===================================                                                         

    def visit_program(self, node):
        if node.get("global"):
            self.visit(node["global"])
        if node.get("function"):
            self.visit(node["function"])
        self.scope_stack.append({})
        self.function_table["brain"] = {"params": 0, "return": "int"}
        self.function_context_stack.append({
            "type": "brain",
            "closure_type": "int",
            "top_level_closure_seen": False
        })
        if node.get("stmt"):
            self.visit(node["stmt"])

        if self.function_context_stack:
            self.function_context_stack.pop()

    # ========================== global declarations ==================================                                           
    def visit_global(self, node):
        for decl in node.get("declarations", []):
            self._handle_global_decl(decl)

    def _handle_global_decl(self, decl):
        line  = decl.get("line", 0)
        dtype = decl.get("dtype", "")
        name  = decl.get("name", "")
        fixed = decl.get("fixed", False)
        dec_node = decl.get("dec")

        if dec_node and isinstance(dec_node, dict):
            size_token = dec_node.get("size")
            if size_token is not None:
                declared_size = 1
                if str(size_token).lstrip("-").isdigit():
                    declared_size = int(size_token)
                else:
                    var_entry = lookup(size_token, self.scope_stack)
                    if not var_entry:
                        self.err(f"Array size '{size_token}' is not declared", line)
                        return
                    elif var_entry["type"] != "int":
                        self.err(f"Array size must be 'int' type, but '{size_token}' is '{var_entry['type']}'", line)
                        return
                    if size_token in self.variable_usage:
                        self.variable_usage[size_token]["used"] = True
                    stored = var_entry.get("value")
                    declared_size = int(stored) if stored and str(stored).lstrip("-").isdigit() else 1

                for scope in self.scope_stack:
                    if name in scope:
                        self.err(f"Array '{name}' already declared. Identifier must be unique throughout the code", line)
                        return

                arOpt = dec_node.get("arOpt") or {}
                f_array_global = dec_node.get("fArray") or {}

                # global fixed 2D array
                if fixed and f_array_global.get("size2") is not None:
                    num_cols   = int(str(f_array_global.get("size2", 1)))
                    num_rows   = declared_size
                    two_d_node = f_array_global.get("2dArray") or {}
                    raw_rows   = two_d_node.get("rows", [])
                    has_init   = bool(raw_rows)
                    if not has_init:
                        self.err(f"Fixed 2D array '{name}' must be fully initialized at declaration", line)
                        return
                    if len(raw_rows) < num_rows:
                        self.err(f"Fixed 2D array '{name}' must be fully initialized: expected {num_rows} rows, got {len(raw_rows)}", line)
                        return
                    if len(raw_rows) > num_rows:
                        self.err(f"Fixed 2D array '{name}' initialized with too many rows: expected {num_rows}", line)
                        return
                    all_ok = True
                    final_rows = []
                    for ri, row_node in enumerate(raw_rows):
                        row_lits = [str(e) for e in (row_node.get("literals") or []) if e is not None]
                        if len(row_lits) < num_cols:
                            self.err(f"Fixed 2D array '{name}' row {ri} must be fully initialized: expected {num_cols} elements, got {len(row_lits)}", line)
                            all_ok = False
                        elif len(row_lits) > num_cols:
                            self.err(f"Fixed 2D array '{name}' row {ri} has too many elements: expected {num_cols}", line)
                            all_ok = False
                        for elem in row_lits:
                            if not strict_type_check_array(dtype, str(elem), self.scope_stack):
                                self.terminal.log(f"Semantic Error: Fixed 2D array '{name}' element '{elem}' does not match type '{dtype}' at line {line}")
                                self.ok = False
                                all_ok = False
                        final_rows.append(row_lits)
                    if not all_ok:
                        self.ok = False
                        return
                    if self.exists_in_any_scope(name):
                        self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                        return
                    self.current_scope()[name] = {
                        "type": dtype, "size": num_rows, "size2": num_cols,
                        "rows": final_rows, "fixed": True,
                        "is_2d": True, "initialized": True,
                    }
                    self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": True}
                    return

                # global non-fixed 2D array
                if arOpt.get("size2") is not None:
                    num_cols   = int(str(arOpt.get("size2", 1)))
                    num_rows   = declared_size
                    two_d_node = arOpt.get("2dArray") or {}
                    raw_rows   = two_d_node.get("rows", [])
                    has_init   = bool(raw_rows)
                    if has_init and len(raw_rows) > num_rows:
                        self.err(f"2D array '{name}' has too many rows: expected {num_rows}, got {len(raw_rows)}", line)
                        self.ok = False
                    elif has_init and len(raw_rows) < num_rows:
                        missing = num_rows - len(raw_rows)
                        self.terminal.log(f"WARNING: 2D array '{name}' is missing {missing} row(s) at line {line}. Missing rows will default to 0.")
                    final_rows = []
                    for ri, row_node in enumerate(raw_rows):
                        row_lits = [str(e) for e in (row_node.get("literals") or []) if e is not None]
                        if len(row_lits) > num_cols:
                            self.err(f"2D array '{name}' row {ri} has too many elements: expected {num_cols}, got {len(row_lits)}", line)
                            self.ok = False
                        elif len(row_lits) < num_cols:
                            missing_cols = num_cols - len(row_lits)
                            self.terminal.log(f"WARNING: 2D array '{name}' row {ri} partially initialized at line {line}. {missing_cols} element(s) default to 0.")
                        for elem in row_lits:
                            if not strict_type_check_array(dtype, str(elem), self.scope_stack):
                                self.terminal.log(f"Semantic Error: 2D array '{name}' element '{elem}' does not match type '{dtype}' at line {line}")
                                self.ok = False
                        final_rows.append(row_lits)
                    if self.exists_in_any_scope(name):
                        self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                        return
                    self.current_scope()[name] = {
                        "type": dtype, "size": num_rows, "size2": num_cols,
                        "rows": final_rows, "fixed": False,
                        "is_2d": True, "initialized": has_init,
                    }
                    self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": has_init}
                    return

                # global 1D array (original)
                elements_nodes = arOpt.get("elements", {}) or {}
                elements_raw = elements_nodes.get("literals", []) if isinstance(elements_nodes, dict) else []
                if not elements_raw:
                    elements_raw = dec_node.get("literals", []) or []
                if not elements_raw and fixed:
                    elements_raw = f_array_global.get("literals", []) or []
                elements = [str(e) for e in elements_raw if e is not None]
                has_init = bool(elements_raw)
                

                # fixed arrays must be fully initialized
                is_fixed = (fixed is True)
                if is_fixed and not has_init:
                    self.err(f"Fixed array '{name}' must be fully initialized at declaration", line)
                    self.current_scope()[name] = {
                        "type": dtype, "size": declared_size,
                        "elements": [], "fixed": True,
                        "initialized": False, "partially_initialized": False
                    }
                    self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": False}
                    return
                if is_fixed and len(elements) < declared_size:
                    self.err(f"Fixed array '{name}' must be fully initialized: expected {declared_size} elements", line)
                    self.current_scope()[name] = {
                        "type": dtype, "size": declared_size,
                        "elements": elements, "fixed": True,
                        "initialized": True, "partially_initialized": True
                    }
                    self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": True}
                    return

                # Semantic check for array
                final_elems, arr_had_error  = semantic_array_check(name, dtype, declared_size, elements, line,
                                                    self.terminal, has_init, self.scope_stack)
                if arr_had_error: 
                    self.ok = False

                # to check if the array is used before initialized
                is_partially = has_init and len(elements) == 0
                # enforce no-shadowing: ensure name is not already declared in any scope
                if self.exists_in_any_scope(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                if self._popped_is_conflict(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                self.current_scope()[name] = {
                    "type": dtype, "size": declared_size,
                    "elements": final_elems, "fixed": fixed,
                    "initialized": has_init,
                    "partially_initialized": is_partially
                }
                # record name in core-declared set if inside a core
                if self.core_declared_names_stack:
                    try:
                        self.core_declared_names_stack[-1].add(name)
                    except Exception:
                        pass
                
                self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": has_init}
                try:
                    current_ctx = self.block_context_stack[-1] if self.block_context_stack else None
                    if self.conditional_decl_stack and current_ctx in ("hope", "despair"):
                        self.conditional_decl_stack[-1].add(name)
                except Exception:
                    pass
                return

        if not self.declare_var(name, dtype, fixed, line):
            return

        rhs_node = None
        if dec_node and isinstance(dec_node, dict):
            rhs_node = dec_node.get("value")
            if rhs_node is None:
                gDecOp = dec_node.get("gDecOp")
                if gDecOp and isinstance(gDecOp, dict):
                    rhs_node = gDecOp.get("value")

        if rhs_node is not None:
            self.check_and_store_value(dtype, name, rhs_node, line, fixed)

        # handle chained fixed global vars: fixed int A=1, B=2, C=3;
        if fixed and dec_node:
            multi_fix = dec_node.get("multiFix") or {}
            for extra in (multi_fix.get("vars") or []):
                e_name = extra.get("name", "")
                e_line = extra.get("line", line)
                if not self.declare_var(e_name, dtype, True, e_line):
                    continue
                e_val = extra.get("value")
                if e_val is not None:
                    self.check_and_store_value(dtype, e_name, e_val, e_line, fixed=True)

        def process_multiV(mv_node):
            for extra in (mv_node.get("vars") or []):
                extra_name = extra.get("name", "")
                extra_line = extra.get("line", line)
                if not self.declare_var(extra_name, dtype, fixed, extra_line):
                    continue
                e_gdecop = extra.get("gDecOp") or {}
                extra_rhs = e_gdecop.get("value")
                if extra_rhs is not None:
                    self.check_and_store_value(dtype, extra_name, extra_rhs, extra_line, fixed)
                nested_mv = e_gdecop.get("multiV") or {}
                if nested_mv.get("vars"):
                    process_multiV(nested_mv)

        gDecOp = dec_node.get("gDecOp") if dec_node else None
        multiV = (gDecOp or {}).get("multiV") if gDecOp else None
        if multiV and multiV.get("vars"):
            process_multiV(multiV)

#  ======================= heart functions ==============================                                              
    def visit_func(self, node):
        for func in node.get("functions", []):
            self._handle_heart(func)

    def _handle_heart(self, func):
        line        = func.get("line", 0)
        return_type = func.get("return_type", "void")
        name        = func.get("name", "")
        params      = func.get("param", {}) or {}
        param_list  = params.get("params", [])
        param_types = [p["dtype"] for p in param_list]
        param_names = [p["name"] for p in param_list]

        if name in self.function_table:
            self.err(f"Duplication of '{name}' heart function", line)
            return

        for scope in self.scope_stack:
            if name in scope:
                self.err(f"Function name '{name}' conflicts with previously declared variable", line)
                self.ok = False
                return

        if len(param_names) != len(set(param_names)):
            self.err(f"Duplicate parameter name in heart '{name}'", line)
            return

        for p_name in param_names:
            for scope in self.scope_stack:
                if p_name in scope:
                    self.err(f"Parameter '{p_name}' conflicts with previously declared identifier", line)
                    self.ok = False
                    return
        
        # Check if parameter names conflict with parameters from other heart functions
        for p_name in param_names:
            for other_func_name, other_params in self.function_params.items():
                if p_name in other_params:
                    self.err(f"Parameter '{p_name}' is already used in heart function '{other_func_name}'", line)
                    self.ok = False
                    return

        self.function_table[name] = {
            "params": len(param_types),
            "param_types": param_types,
            "return": return_type
        }
        
        # Store function parameters for cross-function duplicate detection
        self.function_params[name] = set(param_names)
        # Store the line number where this function was declared
        self.function_decl_lines[name] = line

        self.scope_stack.append({})
        self.block_context_stack.append("heart")
        current = self.scope_stack[-1]
        for pt, pn in zip(param_types, param_names):
            current[pn] = {"type": pt, "fixed": False, "initialized": True}
            self.variable_usage[pn] = {"declared_line": line, "used": True, "type": "param"}

        self.function_context_stack.append({
            "type": "heart",
            "closure_type": return_type,
            "func_name": name
        })

        if func.get("stmt"):
            self.visit(func["stmt"])

        closure_node = func.get("closureCon")
        closure_line = closure_node.get("line", line) if closure_node else line
        self._handle_closure(closure_node, closure_line)

        if len(self.scope_stack) > 1:
            popped = self.scope_stack.pop()
            if self.block_context_stack:
                self.block_context_stack.pop()
            current_sd  = len(self.scope_stack)
            # Heart (function) scopes are not conditional branches; use cid=None
            # so their vars always conflict on depth alone.
            current_cid = None
            for v in popped:
                if not str(v).startswith("__"):
                    entry = (current_sd, current_cid)
                    if v not in self.popped_block_vars:
                        self.popped_block_vars[v] = [entry]
                    else:
                        self.popped_block_vars[v].append(entry)

        if self.function_context_stack:
            self.function_context_stack.pop()

# =========================  closure / return ==================================                                            
    def _handle_closure(self, closure_con_node, line):
        if not self.function_context_stack:
            return
        ctx = self.function_context_stack[-1]

        has_value = closure_con_node is not None and closure_con_node.get("value") is not None
        closure_tokens = []
        if has_value:
            closure_tokens = [t for t in flatten_expr(closure_con_node["value"]) if t != ";"]
            for tok in closure_tokens:
                if tok in self.variable_usage:
                    self.variable_usage[tok]["used"] = True

        if ctx["type"] == "brain":
            in_control = any(c in ("hope", "despair", "while", "desire", "do-while")
                             for c in self.block_context_stack)
            if not in_control:
                # Top-level brain body: only one closure allowed, and value must be 0
                if ctx.get("top_level_closure_seen"):
                    self.err("Brain function cannot have more than one top-level closure", line)
                    return
                ctx["top_level_closure_seen"] = True
                if not has_value:
                    self.err("Brain closure must be 0", line)
                else:
                    stripped = [t for t in closure_tokens if t not in ("(", ")")]
                    if stripped != ["0"]:
                        self.err("Brain closure must be 0", line)
            else:
                # Closure inside a control structure within brain: value must evaluate to int
                if not has_value:
                    self.err("Brain closure inside control structure must return an int value", line)
                else:
                    value_type = resolve_expression_type(closure_tokens, self.scope_stack, self.function_table)
                    if value_type != "int":
                        self.err(f"Brain closure must evaluate to 'int', got '{value_type}'", line)

        elif ctx["type"] == "heart":
            expected = ctx.get("closure_type")
            if expected == "void":
                if has_value:
                    self.err("Void heart function cannot return a value", line)
            else:
                if not has_value:
                    self.err(f"Heart function must return a '{expected}' value", line)
                else:
                    # First, validate any echo calls in the closure
                    if closure_tokens and "echo" in closure_tokens:
                        self._validate_echo_calls_in_tokens(closure_tokens, line, skip_void_check=False)
                    
                    value_type = None
                    is_array_element_access = False
                    
                    # Check if closure contains a direct echo call (for return type validation)
                    if closure_tokens and closure_tokens[0] == "echo" and len(closure_tokens) > 1:
                        echo_func_name = closure_tokens[1]
                        if echo_func_name in self.function_table:
                            echo_return_type = self.function_table[echo_func_name].get("return", "void")
                            value_type = echo_return_type
                    
                    # Helper function to check for eleIndex in parse tree
                    def has_element_index(node):
                        """Recursively check if node contains eleIndex (array indexing)"""
                        if isinstance(node, dict):
                            if node.get("type") == "eleIndex":
                                return True
                            for val in node.values():
                                if has_element_index(val):
                                    return True
                        elif isinstance(node, list):
                            for item in node:
                                if has_element_index(item):
                                    return True
                        return False
                    
                    if closure_tokens:
                        first_tok = closure_tokens[0]
                        
                        # Check if first token is a simple identifier (no operators)
                        is_simple_id = (first_tok.isidentifier() and 
                                       first_tok not in {"echo", "read", "spill", "core", "hope", "nope", "desire", "down",
                                                        "despair", "memory", "default", "brain", "heart", "closure",
                                                        "fixed", "int", "float", "char", "str", "bool", "trust", "betray"})
                        
                        if is_simple_id:
                            # Look up the variable in all scopes
                            var_entry = lookup(first_tok, self.scope_stack)
                            
                            # Check if array element access is being used on undeclared array
                            has_bracket_access = (len(closure_tokens) >= 3 and 
                                                 closure_tokens[1] == "[" and 
                                                 "]" in closure_tokens)
                            
                            if has_bracket_access and var_entry is None:
                                # Array element access on undeclared array
                                self.err(f"Undeclared array '{first_tok}' used in closure", line)
                                return
                            
                            if var_entry:
                                var_type = var_entry.get("type")
                                
                                # Check if this variable is declared as an array
                                # Arrays have "size" key in their scope entry
                                is_declared_array = "size" in var_entry
                                
                                if is_declared_array:
                                    # Get the actual value node, drilling through wrapper nodes
                                    value_node = closure_con_node.get("value") if closure_con_node else None
                                    
                                    # Drill into exprDec and similar single-value wrappers
                                    while value_node and isinstance(value_node, dict):
                                        if value_node.get("type") == "exprDec" and "value" in value_node:
                                            value_node = value_node.get("value")
                                        elif value_node.get("type") == "assVal" and "value" in value_node:
                                            value_node = value_node.get("value")
                                        else:
                                            break
                                    
                                    # Check multiple ways to detect array indexing
                                    # Method 1: Check if brackets present in token list
                                    has_brackets_in_tokens = "[" in closure_tokens and "]" in closure_tokens
                                    
                                    # Method 2: Simple positional check - if second token is "[", we have indexing
                                    has_brackets_positional = (len(closure_tokens) >= 3 and 
                                                              closure_tokens[0] == first_tok and 
                                                              closure_tokens[1] == "[")
                                    
                                    # Method 3: Check parse tree for eleIndex node
                                    has_index_in_tree = has_element_index(value_node) if value_node else False
                                    
                                    # Method 4: Check if value node itself has an index field
                                    has_index_direct = False
                                    if value_node and isinstance(value_node, dict):
                                        # Check recursively for 'index' key with non-None value
                                        def has_index_field(node):
                                            if isinstance(node, dict):
                                                if "index" in node and node["index"] is not None:
                                                    return True
                                                for val in node.values():
                                                    if has_index_field(val):
                                                        return True
                                            elif isinstance(node, list):
                                                for item in node:
                                                    if has_index_field(item):
                                                        return True
                                            return False
                                        has_index_direct = has_index_field(value_node)
                                    
                                    # Array has indexing if ANY method detects it
                                    has_index = (has_brackets_in_tokens or  
                                                has_brackets_positional or 
                                                has_index_in_tree or 
                                                has_index_direct)
                                    
                                    # Array without indexing 
                                    if not has_index:
                                        self.err(f"Cannot return whole array '{first_tok}' in closure;" , line)
                                        return
                                    
                                    # Array with indexing
                                    value_type = var_type
                                    is_array_element_access = True

                    for idx, et in enumerate(closure_tokens):
                        if et == "echo" and idx + 1 < len(closure_tokens):
                            vfunc = closure_tokens[idx + 1]
                            if vfunc in self.function_table and self.function_table[vfunc].get("return") == "void":
                                self.err("Void heart cannot be used in closure", line)
                                return

                    # Check if str is used in an expression within closure
                    if contains_expression(closure_tokens):
                        unary_ops = {"++", "--"}
                        for idx, tok in enumerate(closure_tokens):
                            # Check str literal (e.g. "hello") in an expression
                            if (tok.startswith('"') and tok.endswith('"')) or (tok.isidentifier() and resolve_type(tok, self.scope_stack) == "str"):
                                self.err(f"str value cannot be used in an expression", line)
                                self.ok = False
                                return
                            # Check ++ / -- applied to a str identifier
                            if tok in unary_ops:
                                # prefix: tok at i, identifier at i+1
                                if idx + 1 < len(closure_tokens) and closure_tokens[idx + 1].isidentifier():
                                    candidate = closure_tokens[idx + 1]
                                    if resolve_type(candidate, self.scope_stack) == "str":
                                        self.err(f"str variable cannot be used with unary operator", line)
                                        self.ok = False
                                        return
                                # postfix: tok at i, identifier at i-1
                                if idx > 0 and closure_tokens[idx - 1].isidentifier():
                                    candidate = closure_tokens[idx - 1]
                                    if resolve_type(candidate, self.scope_stack) == "str":
                                        self.err(f"str variable cannot be used with unary operator", line)
                                        self.ok = False
                                        return

                    # Only resolve expression type if not already determined from array element access or echo call
                    if value_type is None:
                        value_type = resolve_expression_type(closure_tokens, self.scope_stack, self.function_table)
                    
                    # For echo calls, don't treat as expression for type coercion
                    has_echo = closure_tokens and closure_tokens[0] == "echo"
                    # Array element access is not considered an expression for type coercion purposes
                    is_expr = (contains_expression(closure_tokens) or (len(closure_tokens) > 1 and not is_array_element_access)) and not has_echo

                    if is_expr:
                        allowed = (
                            (value_type == "int"   and expected == "float") or
                            (value_type == "float" and expected == "int")   or
                            (value_type == "char"  and expected == "int")   or
                            (value_type == "int"   and expected == "char")  or
                            (value_type == "float" and expected == "char")  or
                            (value_type == "char"  and expected == "float") or
                            (value_type == "int"   and expected == "bool")  or
                            (value_type == "bool"  and expected == "int")   or
                            (value_type == "float" and expected == "bool")  or
                            (value_type == "bool"  and expected == "float") or
                            (value_type == expected)
                        )
                        if not allowed:
                            self.err(f"Closure type mismatch - expected '{expected}', got '{value_type}'", line)
                    else:
                        # Allow implicit char <-> int conversion per General Rule §15.a
                        char_int_allowed = (
                            (value_type == "char" and expected == "int") or
                            (value_type == "int"  and expected == "char")
                        )
                        if value_type != expected and not char_int_allowed:
                            self.err(f"Closure type mismatch - expected '{expected}', got '{value_type}'", line)


# ======================= visit stmt / stmtOp =====================================                                              
    def visit_stmt(self, node):
        for stmt in node.get("stmts", []):
            self.visit(stmt)

    def visit_stmtOp(self, node):
        line = node.get("line", 0)
        kind = node.get("kind", "")
        
        # local variable declarations 
        if kind in ("str", "dtype1"):
            dtype = "str" if kind == "str" else node.get("dtype", "")
            name  = node.get("name", "")
            
            # RHS for int/float/char/bool: locDec -> locDecOp -> value (exprDec node)
            # RHS for str: strTail -> strTail1 -> value
            loc_dec    = node.get("locDec",  {}) or {}

            # local array declaration 
            if loc_dec.get("index") is not None:
                size_token = loc_dec.get("index")
                if str(size_token).lstrip("-").isdigit():
                    declared_size = int(str(size_token))
                else:
                    var_entry = lookup(size_token, self.scope_stack)
                    if not var_entry:
                        self.err(f"Array size '{size_token}' is not declared", line)
                        return
                    if var_entry["type"] != "int":
                        self.err(f"Array size must be 'int' type, but '{size_token}' is '{var_entry['type']}'", line)
                        return
                    if size_token in self.variable_usage:
                        self.variable_usage[size_token]["used"] = True
                    stored = var_entry.get("value")
                    declared_size = int(stored) if stored and str(stored).lstrip("-").isdigit() else 1

                ar_opt = loc_dec.get("arOpt") or {}

                # ── 2D array: int ARR[2][3] ──────────────────────────────
                if ar_opt.get("size2") is not None:
                    num_cols = int(str(ar_opt.get("size2", 1)))
                    num_rows = declared_size
                    two_d_node = ar_opt.get("2dArray") or {}
                    raw_rows   = two_d_node.get("rows", [])
                    has_init   = bool(raw_rows)
                    if has_init and len(raw_rows) > num_rows:
                        self.err(f"2D array '{name}' has too many rows: expected {num_rows}, got {len(raw_rows)}", line)
                        self.ok = False
                    elif has_init and len(raw_rows) < num_rows:
                        missing = num_rows - len(raw_rows)
                        self.terminal.log(f"WARNING: 2D array '{name}' is missing {missing} row(s) at line {line}. Missing rows will default to 0.")
                    final_rows = []
                    for ri, row_node in enumerate(raw_rows):
                        row_lits = [str(e) for e in (row_node.get("literals") or []) if e is not None]
                        if len(row_lits) > num_cols:
                            self.err(f"2D array '{name}' row {ri} has too many elements: expected {num_cols}, got {len(row_lits)}", line)
                            self.ok = False
                        elif len(row_lits) < num_cols:
                            missing_cols = num_cols - len(row_lits)
                            self.terminal.log(f"WARNING: 2D array '{name}' row {ri} partially initialized at line {line}. {missing_cols} element(s) default to 0.")
                        for elem in row_lits:
                            if not strict_type_check_array(dtype, str(elem), self.scope_stack):
                                self.terminal.log(f"Semantic Error: 2D array '{name}' element '{elem}' does not match type '{dtype}' at line {line}")
                                self.ok = False
                        final_rows.append(row_lits)
                    if self.exists_in_any_scope(name):
                        self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                        return
                    if self._popped_is_conflict(name):
                        self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                        return
                    self.current_scope()[name] = {
                        "type": dtype, "size": num_rows, "size2": num_cols,
                        "rows": final_rows, "fixed": False,
                        "is_2d": True, "initialized": has_init,
                    }
                    if self.core_declared_names_stack:
                        try: self.core_declared_names_stack[-1].add(name)
                        except Exception: pass
                    self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": has_init}
                    return
                
                elements_nodes = ar_opt.get("elements") or {}
                elements_raw = elements_nodes.get("literals", []) if isinstance(elements_nodes, dict) else []
                elements = [str(e) for e in elements_raw if e is not None]
                has_init = ar_opt.get("elements") is not None 
                final_elems, arr_had_error = semantic_array_check(name, dtype, declared_size, elements, line,
                                                                   self.terminal, has_init, self.scope_stack)
                if arr_had_error:
                    self.ok = False
                # enforce no-shadowing: ensure name is not already declared in any scope
                if self.exists_in_any_scope(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                if self._popped_is_conflict(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                self.current_scope()[name] = {
                    "type": dtype, "size": declared_size,
                    "elements": final_elems, "fixed": False,
                    "initialized": has_init,
                    "partially_initialized": has_init and len(elements) == 0
                }
                # record name in core-declared set if inside a core
                if self.core_declared_names_stack:
                    try:
                        self.core_declared_names_stack[-1].add(name)
                    except Exception:
                        pass
                
                self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": has_init}
                try:
                    current_ctx = self.block_context_stack[-1] if self.block_context_stack else None
                    if self.conditional_decl_stack and current_ctx in ("hope", "despair"):
                        self.conditional_decl_stack[-1].add(name)
                except Exception:
                    pass
                return
            
            str_tail   = node.get("strTail", {}) or {}

            
            # str local array declaration 
            if kind == "str" and str_tail.get("index") is not None:
                size_token = str_tail.get("index")
                if str(size_token).lstrip("-").isdigit():
                    declared_size = int(str(size_token))
                else:
                    var_entry = lookup(size_token, self.scope_stack)
                    if not var_entry:
                        self.err(f"Array size '{size_token}' is not declared", line)
                        return
                    if var_entry["type"] != "int":
                        self.err(f"Array size must be 'int' type, but '{size_token}' is '{var_entry['type']}'", line)
                        return
                    if size_token in self.variable_usage:
                        self.variable_usage[size_token]["used"] = True
                    stored = var_entry.get("value")
                    declared_size = int(stored) if stored and str(stored).lstrip("-").isdigit() else 1

                str_arr_tail = str_tail.get("arOpt") or {}
                elements_nodes = str_arr_tail.get("elements") or {}
                elements_raw = elements_nodes.get("literals", []) if isinstance(elements_nodes, dict) else []
                elements = [str(e) for e in elements_raw if e is not None]
                has_init = str_arr_tail.get("elements") is not None 
                final_elems, arr_had_error = semantic_array_check(name, dtype, declared_size, elements, line,
                                                                   self.terminal, has_init, self.scope_stack)
                if arr_had_error:
                    self.ok = False
                # enforce no-shadowing: ensure name is not already declared in any scope
                if self.exists_in_any_scope(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                if self._popped_is_conflict(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                self.current_scope()[name] = {
                    "type": dtype, "size": declared_size,
                    "elements": final_elems, "fixed": False,
                    "initialized": has_init,
                    "partially_initialized": has_init and len(elements) == 0
                }
                
                self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": has_init}
                return

            loc_dec_op = loc_dec.get("locDecOp", {}) or {}
            str_tail1  = str_tail.get("strTail1", {}) or {}
            
            # Check if this is an array declaration
            # Try multiple locations for size in the parse tree
            size_token = node.get("size") or loc_dec.get("size")
            if size_token is None and loc_dec_op:
                size_token = loc_dec_op.get("size")
            
            if size_token is not None and kind != "str":

                # Array declaration
                declared_size = 1
                if str(size_token).lstrip("-").isdigit():
                    declared_size = int(size_token)
                else:

                    # Size is a variable reference
                    if not resolve_type(str(size_token), self.scope_stack):
                        self.err(f"Array size reference '{size_token}' is undeclared at line {line}", line)
                        return
                
                # Check for already declared variable in the current scope or elsewhere in the same core
                if name in self.current_scope():
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                if self.core_declared_names_stack and name in self.core_declared_names_stack[-1]:
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                
                # Get initial elements if provided
                ar_opt = loc_dec_op.get("arOpt") or {}
                elements_nodes = ar_opt.get("elements", {}) or {}
                elements_raw = elements_nodes.get("literals", []) if isinstance(elements_nodes, dict) else []
                elements = [str(e) for e in elements_raw if e is not None]
                has_init = bool(elements_raw)
                
                # Semantic check for array
                final_elems = semantic_array_check(name, dtype, declared_size, elements, line,
                                                    self.terminal, has_init, self.scope_stack)
                is_partially = has_init and len(elements) == 0
                # enforce no-shadowing: ensure name is not already declared in any scope
                if self.exists_in_any_scope(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                if self._popped_is_conflict(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                self.current_scope()[name] = {
                    "type": dtype, "size": declared_size,
                    "elements": final_elems, "fixed": False,
                    "initialized": has_init,
                    "partially_initialized": is_partially
                }
                # record name in core-declared set if inside a core
                if self.core_declared_names_stack:
                    try:
                        self.core_declared_names_stack[-1].add(name)
                    except Exception:
                        pass
                self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": has_init}
                try:
                    current_ctx = self.block_context_stack[-1] if self.block_context_stack else None
                    if self.conditional_decl_stack and current_ctx in ("hope", "despair"):
                        self.conditional_decl_stack[-1].add(name)
                except Exception:
                    pass
                return
            
            # Variable declaration
            if not self.declare_var(name, dtype, False, line):
                return
            
            rhs_node   = loc_dec_op.get("value") or str_tail1.get("value")

            if rhs_node is not None:
                self.check_and_store_value(dtype, name, rhs_node, line)

            # multi-var: int A, B, C = 6  (locMV is nested recursively)
            def process_locMV(locmv_node):
                for extra in (locmv_node.get("vars") or []):
                    e_name = extra.get("name", "")
                    e_line = extra.get("line", line)
                    if not self.declare_var(e_name, dtype, False, e_line):
                        continue
                    e_loc_dec_op = extra.get("locDecOp") or {}
                    e_rhs_node = e_loc_dec_op.get("value")
                    if e_rhs_node is not None:
                        self.check_and_store_value(dtype, e_name, e_rhs_node, e_line)
                    # recurse for further chained vars (e.g. J in int E, F, J)
                    nested_mv = e_loc_dec_op.get("locMV") or {}
                    if nested_mv.get("vars"):
                        process_locMV(nested_mv)

            multi = loc_dec_op.get("locMV", {}) or {}
            process_locMV(multi)

            # multi-var str: str a="x", b="y", c="z"  (strMulti is nested recursively)
            def process_strMulti(sm_node):
                for extra in (sm_node.get("vars") or []):
                    e_name = extra.get("name", "")
                    e_line = extra.get("line", line)
                    if not self.declare_var(e_name, "str", False, e_line):
                        continue
                    e_str_tail1 = extra.get("strTail1") or {}
                    e_rhs = e_str_tail1.get("value")
                    if e_rhs is not None:
                        self.check_and_store_value("str", e_name, e_rhs, e_line)
                    nested_sm = e_str_tail1.get("strMulti") or {}
                    if nested_sm.get("vars"):
                        process_strMulti(nested_sm)

            if kind == "str":
                str_multi = str_tail1.get("strMulti") or {}
                if str_multi.get("vars"):
                    process_strMulti(str_multi)

        elif kind == "fixed":
            lf    = node.get("locFDOp", {}) or {}
            dtype = lf.get("dtype") or lf.get("kind", "")
            name  = lf.get("name", "")
       
            # Try multiple locations for size in the parse tree
            fix_loc_dec = lf.get("fixLocDec") or {}
            fix_str_tail = lf.get("fixStrTail") or {}
            size_token = fix_loc_dec.get("index") or fix_str_tail.get("index")     
            
            if size_token is not None:
                # Fixed array declaration
                declared_size = 1
                if str(size_token).lstrip("-").isdigit():
                    declared_size = int(size_token)
                else:
                    if not resolve_type(str(size_token), self.scope_stack):
                        self.err(f"Array size reference '{size_token}' is undeclared at line {line}", line)
                        return

                # Check for already declared identifier in current scope or in the same core
                if name in self.current_scope():
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                if self.core_declared_names_stack and name in self.core_declared_names_stack[-1]:
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return

                ar_opt = fix_loc_dec or {}
                f_array = ar_opt.get("fArray") or {}

                # fixed 2D array: fixed int LF_ARR1[2][3] = {{1,2,3},{4,5,6}}
                if f_array.get("size2") is not None:
                    num_cols   = int(str(f_array.get("size2", 1)))
                    num_rows   = declared_size
                    two_d_node = f_array.get("2dArray") or {}
                    raw_rows   = two_d_node.get("rows", [])
                    has_init   = bool(raw_rows)
                    if not has_init:
                        self.err(f"Fixed 2D array '{name}' must be fully initialized at declaration", line)
                        return
                    if len(raw_rows) < num_rows:
                        self.err(f"Fixed 2D array '{name}' must be fully initialized: expected {num_rows} rows, got {len(raw_rows)}", line)
                        return
                    if len(raw_rows) > num_rows:
                        self.err(f"Fixed 2D array '{name}' initialized with too many rows: expected {num_rows}", line)
                        return
                    all_ok = True
                    final_rows = []
                    for ri, row_node in enumerate(raw_rows):
                        row_lits = [str(e) for e in (row_node.get("literals") or []) if e is not None]
                        if len(row_lits) < num_cols:
                            self.err(f"Fixed 2D array '{name}' row {ri} must be fully initialized: expected {num_cols} elements, got {len(row_lits)}", line)
                            all_ok = False
                        elif len(row_lits) > num_cols:
                            self.err(f"Fixed 2D array '{name}' row {ri} has too many elements: expected {num_cols}", line)
                            all_ok = False
                        for elem in row_lits:
                            if not strict_type_check_array(dtype, str(elem), self.scope_stack):
                                self.terminal.log(f"Semantic Error: Fixed 2D array '{name}' element '{elem}' does not match type '{dtype}' at line {line}")
                                self.ok = False
                                all_ok = False
                        final_rows.append(row_lits)
                    if not all_ok:
                        self.ok = False
                        return
                    if self.exists_in_any_scope(name):
                        self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                        return
                    if self._popped_is_conflict(name):
                        self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                        return
                    self.current_scope()[name] = {
                        "type": dtype, "size": num_rows, "size2": num_cols,
                        "rows": final_rows, "fixed": True,
                        "is_2d": True, "initialized": True,
                    }
                    self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": True}
                    try:
                        current_ctx = self.block_context_stack[-1] if self.block_context_stack else None
                        if self.conditional_decl_stack and current_ctx in ("hope", "despair"):
                            self.conditional_decl_stack[-1].add(name)
                    except Exception: pass
                    return

                # fixed 1D array (original)
                elements_nodes = ar_opt.get("elements", {}) or {}
                elements_raw = elements_nodes.get("literals", []) if isinstance(elements_nodes, dict) else []
                if not elements_raw:
                    elements_raw = ar_opt.get("literals", []) or []
                if not elements_raw:
                    elements_raw = fix_str_tail.get("literals", []) or []
                if not elements_raw:
                    elements_raw = f_array.get("literals", []) or []
                # Must be AFTER all fallbacks
                elements = [str(e) for e in elements_raw if e is not None]
                has_init = bool(elements_raw)

                # fixed arrays must be fully initialized
                if not has_init:
                    self.err(f"Fixed array '{name}' must be fully initialized at declaration", line)
                    return
                if len(elements) < declared_size:
                    self.err(f"Fixed array '{name}' must be fully initialized: expected {declared_size} elements", line)
                    return
                if len(elements) > declared_size:
                    self.err(f"Fixed array '{name}' initialized with too many elements: expected {declared_size}", line)
                    return

                final_elems, arr_had_error = semantic_array_check(name, dtype, declared_size, elements, line,
                                                                   self.terminal, has_init, self.scope_stack)
                if arr_had_error:
                    self.ok = False
                    return
                
                # enforce no-shadowing: ensure name is not already declared in any scope
                if self.exists_in_any_scope(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                if self._popped_is_conflict(name):
                    self.err(f"Variable '{name}' already declared in this scope. Error found", line)
                    return
                self.current_scope()[name] = {
                    "type": dtype, "size": declared_size,
                    "elements": final_elems, "fixed": True,
                    "initialized": has_init,
                    "partially_initialized": False
                }

                self.variable_usage[name] = {"declared_line": line, "used": False, "type": "array", "initialized": has_init}
                try:
                    current_ctx = self.block_context_stack[-1] if self.block_context_stack else None
                    if self.conditional_decl_stack and current_ctx in ("hope", "despair"):
                        self.conditional_decl_stack[-1].add(name)
                except Exception:
                    pass
                return
            
            # Non-array fixed variable declaration
            if not self.declare_var(name, dtype, True, line):
                return
            rhs_node = lf.get("value")
            if rhs_node is None:
                fix_loc_dec_op = lf.get("fixLocDec") or {}
                rhs_node = fix_loc_dec_op.get("value")
            if rhs_node is None:
                fix_str_tail_op = lf.get("fixStrTail") or {}   
                rhs_node = fix_str_tail_op.get("value")         
            if rhs_node is None:
                loc_dec_op_inner = lf.get("locDecOp") or {}
                rhs_node = loc_dec_op_inner.get("value")
            if rhs_node:
                self.check_and_store_value(dtype, name, rhs_node, line, fixed=True)

            # chained fixed non-str local vars: fixed int A=1, B=2, C=3;
            multi_fix = fix_loc_dec.get("multiFix") or {}
            for extra in (multi_fix.get("vars") or []):
                e_name = extra.get("name", "")
                e_line = extra.get("line", line)
                if not self.declare_var(e_name, dtype, True, e_line):
                    continue
                e_val = extra.get("value")
                if e_val is not None:
                    self.check_and_store_value(dtype, e_name, e_val, e_line, fixed=True)

            # chained fixed str local vars: fixed str A="x", B="y";
            fix_str_multi = fix_str_tail.get("fixStrMulti") or {}
            for extra in (fix_str_multi.get("vars") or []):
                e_name = extra.get("name", "")
                e_line = extra.get("line", line)
                if not self.declare_var(e_name, dtype, True, e_line):
                    continue
                e_val = extra.get("value")
                if e_val is not None:
                    self.check_and_store_value(dtype, e_name, e_val, e_line, fixed=True)

        elif kind == "ID":
            var    = node.get("name", "")
            idExpr = node.get("idExpr", {}) or {}
            self._handle_id_stmt(var, idExpr, line)

        elif kind == "read":
            var   = node.get("id", "")
            entry = lookup(var, self.scope_stack)
            if not entry:
                if var in self.popped_block_vars:
                    self.err("Variable from another scope cannot be accessed. Error found", line)
                else:
                    self.err(f"Variable '{var}' used before declaration", line)
                return
            if entry.get("fixed"):
                self.err(f"Cannot read into fixed variable '{var}'", line)
                return
            if var in self.variable_usage:
                self.variable_usage[var]["used"] = True
            # mark array as initialized via read
            if entry and "size" in entry:
                entry["initialized"] = True
            # Check the array index variable (if present) against scope/popped vars
            ele_index = node.get("eleIndex") or {}
            idx_var = ele_index.get("index", "") if isinstance(ele_index, dict) else ""
            if idx_var and isinstance(idx_var, str) and idx_var.isidentifier():
                idx_entry = lookup(idx_var, self.scope_stack)
                if not idx_entry:
                    if idx_var in self.popped_block_vars:
                        self.err("Variable from another scope cannot be accessed. Error found", line)
                    else:
                        self.err(f"Variable '{idx_var}' used before declaration", line)
                    self.ok = False

        elif kind == "spill":
            self._handle_spill(node, line)

        elif kind == "echo":
            fname = node.get("name", "")
            self._check_echo_call(fname, node.get("echOp"), line)

        elif kind == "desire":
            self._handle_desire(node, line)

        elif kind == "while":
            self._handle_while(node, line)

        elif kind == "do":
            self._handle_do_while(node, line)

        elif kind == "una":
            op  = node.get("op", "")
            var = node.get("name", "")
            self._check_inc_dec(op, var, line)

        elif kind == "closure":
            closure_node = node.get("closureCon")
            self._handle_closure(closure_node, line)

        elif kind == "hope":
            # hope/despair can appear inside loop bodies (loopStmt context)
            # dispatch to visit_hope which now handles both stmt and loopStmt keys
            self.visit_hope(node)

        elif kind == "core":
            # core can appear inside loop bodies
            self.visit_core(node)


    def _handle_id_stmt(self, var, idExpr, line):
        entry      = lookup(var, self.scope_stack)
        idExpr_type = idExpr.get("type", "") if idExpr else ""

        # function call
        if idExpr_type == "idCallExpr":
            if var not in self.function_table:
                self.err(f"Function called before declaration: `{var}()`", line)
                return
            self._validate_call_args(var, idExpr.get("echOp"), line)
            return

        # ARRAY ELEMENT ACCESS / ASSIGNMENT
        if idExpr_type == "idExpr" and idExpr.get("index") is not None: 
            if not entry:
                if var in self.popped_block_vars:
                    self.err("Variable from another scope cannot be accessed. Error found", line)
                else:
                    self.err(f"'{var}' used before declaration", line)
                return
            
            # check if used variable 
            if var in self.variable_usage:
                self.variable_usage[var]["used"] = True

            # fixed no reassignment 
            if entry.get("fixed"):
                self.err(f"Fixed array '{var}' cannot have its elements reassigned", line)
                return
            
            # ── 2D array assignment: ARR[r][c] = val ─────────────────────
            if entry.get("is_2d"):
                idx2_node = idExpr.get("index2") or {}
                col_index = idx2_node.get("index")
                if col_index is None:
                    self.err(f"2D array '{var}' requires two indices (row and column)", line)
                    self.ok = False
                    return
                row_tokens = flatten_expr(idExpr.get("index"))
                if row_tokens and row_tokens[0].lstrip("-").isdigit():
                    row_val = int(row_tokens[0])
                    if row_val < 0 or row_val >= entry.get("size", 0):
                        self.err(f"2D array '{var}' row index {row_val} out of bounds (rows={entry.get('size',0)})", line)
                        self.ok = False
                        return
                col_tokens = flatten_expr(col_index) if isinstance(col_index, dict) else [str(col_index)]
                if col_tokens and col_tokens[0].lstrip("-").isdigit():
                    col_val = int(col_tokens[0])
                    if col_val < 0 or col_val >= entry.get("size2", 0):
                        self.err(f"2D array '{var}' column index {col_val} out of bounds (cols={entry.get('size2',0)})", line)
                        self.ok = False
                        return
                arr_id_tail = idExpr.get("arrIDTail") or {}
                ass_val = arr_id_tail.get("assVal") or {}
                rhs_node = ass_val if ass_val.get("kind") == "STRLIT" else ass_val.get("exprDec") or None
                if rhs_node is not None:
                    value = get_rhs_value_from_node(rhs_node, self.function_table, self.scope_stack)
                    ok, reason = type_check(entry.get("type", ""), value, self.scope_stack)
                    if not ok:
                        log_type_error(entry.get("type", ""), value, var, line, self.terminal, reason)
                        self.ok = False
                    elif reason:
                        log_warning(entry.get("type", ""), value, var, line, self.terminal, reason)
                entry["initialized"] = True
                return
            
            # 1D array (original)
            idx_node   = idExpr.get("index")
            idx_tokens = flatten_expr(idx_node)
            if idx_tokens:
                idx_tok = idx_tokens[0]
                if idx_tok.lstrip("-").isdigit():
                    idx_val = int(idx_tok)
                    size = entry.get("size", 0)

                    # array index out of bounds 
                    if idx_val < 0 or idx_val >= size:
                        self.err(f"Array index {idx_val} out of bounds for '{var}'", line)
                        return
                else:
                    # array index must be an int
                    ie = lookup(idx_tok, self.scope_stack)
                    if not ie or ie["type"] != "int":
                        self.err(f"Array index '{idx_tok}' must be an integer", line)
                        return
                    if idx_tok in self.variable_usage:
                        self.variable_usage[idx_tok]["used"] = True

            arr_id_tail = (idExpr.get("arrIDTail") or {})
            ass_val = arr_id_tail.get("assVal") or {}
            rhs_node = ass_val if ass_val.get("kind") == "STRLIT" else ass_val.get("exprDec") or None

            if rhs_node is not None:
                # type check ng value assigned sa array element
                value = get_rhs_value_from_node(rhs_node, self.function_table, self.scope_stack)
                arr_dtype = entry.get("type", "")
                ok, reason = type_check(arr_dtype, value, self.scope_stack)
                if not ok:
                    log_type_error(arr_dtype, value, var, line, self.terminal, reason)
                    self.ok = False
                elif reason:
                    log_warning(arr_dtype, value, var, line, self.terminal, reason)

            if idExpr.get("rhs") or rhs_node:
                entry["initialized"] = True
                # mark if assigned via variable index (likely inside a loop)
                idx_node = idExpr.get("index")
                idx_tokens = flatten_expr(idx_node)
                if idx_tokens and not idx_tokens[0].lstrip("-").isdigit():
                    entry["assigned_in_loop"] = True
            return

        # postfix ++ / --
        if idExpr_type in ("postInc", "postDec"):
            op = "++" if idExpr_type == "postInc" else "--"
            self._check_inc_dec(op, var, line)
            return

        # assignment or compound assignment
        # compound ops (+=, -=, etc.) store: idExpr["op"] + idExpr["exprDec"]
        # simple = stores via:  idExpr -> arrIDTail -> assVal -> exprDec
        op          = idExpr.get("op", "=") if idExpr else "="
        arr_id_tail = (idExpr.get("arrIDTail") or {}) if idExpr else {}

        # postfix ++ / -- may arrive here when parser sets idExpr["op"] = "++" / "--"
        if op in ("++", "--"):
            self._check_inc_dec(op, var, line)
            return
        
        #  postfix ++ / -- stored on arrIDTail (e.g. A++)
        arr_tail_op = arr_id_tail.get("op", "")
        if arr_tail_op in ("++", "--"):
            self._check_inc_dec(arr_tail_op, var, line)
            return

        if op in ("+=", "-=", "*=", "/=", "//=", "%=", "^="):
            rhs_node = idExpr.get("exprDec") if idExpr else None
        else:
            ass_val  = arr_id_tail.get("assVal") or {}
            if ass_val.get("kind") == "STRLIT":
                rhs_node = ass_val
            else:
                rhs_node = ass_val.get("exprDec") or None
            op = "="

        if not entry:
            if var in self.popped_block_vars:
                self.err("Variable from another scope cannot be accessed. Error found", line)
            else:
                self.err(f"Variable '{var}' used before declaration", line)
            return

        if var in self.variable_usage:
            self.variable_usage[var]["used"] = True

        # fixed variable reassignment 
        if entry.get("fixed"):
            self.err(f"Fixed variable '{var}' cannot be reassigned or modified", line)
            return

        # expressions in global scope 
        if self.is_global() and rhs_node and contains_expression(flatten_expr(rhs_node)):
            self.err("Expressions are not allowed in global scope", line)
            return

        # division by zero check for compound /=, //=, %=
        if op in ("/=", "//=", "%=") and rhs_node:
            inside_loop_or_cond = any(
                ctx in ("desire", "while", "do-while", "hope", "despair")
                for ctx in self.block_context_stack
            )
            if not inside_loop_or_cond:
                rhs_toks = flatten_expr(rhs_node)
                _, is_zero = evaluate_expression(rhs_toks, self.scope_stack)
                if is_zero:
                    self.err("Division by zero", line)
                    return

                # Uninitialized numeric variable defaults to 0 — also division by zero
                if len(rhs_toks) == 1 and rhs_toks[0].isidentifier():
                    rhs_entry = lookup(rhs_toks[0], self.scope_stack)
                    if rhs_entry and rhs_entry.get("type") in ("int", "float", "char"):
                        if "value" not in rhs_entry or rhs_entry.get("value") is None:
                            self.err("Division by zero", line)
                            return

        if rhs_node:
            rhs_toks = flatten_expr(rhs_node)

            # str cannot be in an expression (including ++ / -- on str variables or str literals)
            if contains_expression(rhs_toks):
                _unary_ops = {"++", "--"}
                for _idx, tok in enumerate(rhs_toks):
                    if (tok.startswith('"') and tok.endswith('"')) or (tok.isidentifier() and resolve_type(tok, self.scope_stack) == "str"):
                        self.err(f"str value cannot be used in an expression", line)
                        self.ok = False
                        return
                    if tok in _unary_ops:
                        if _idx + 1 < len(rhs_toks) and rhs_toks[_idx + 1].isidentifier():
                            _cand = rhs_toks[_idx + 1]
                            if resolve_type(_cand, self.scope_stack) == "str":
                                self.err(f"str variable cannot be used with unary operator", line)
                                self.ok = False
                                return
                        if _idx > 0 and rhs_toks[_idx - 1].isidentifier():
                            _cand = rhs_toks[_idx - 1]
                            if resolve_type(_cand, self.scope_stack) == "str":
                                self.err(f"str variable cannot be used with unary operator", line)
                                self.ok = False
                                return

            # Validate echo calls in RHS
            self._validate_echo_calls_in_tokens(rhs_toks, line)

            # Check if void heart is being assigned to a variable 
            if op == "=" and len(rhs_toks) >= 2 and rhs_toks[0] == "echo":
                echo_func_name = rhs_toks[1]
                if echo_func_name in self.function_table:
                    func_return_type = self.function_table[echo_func_name].get("return", "void")
                    if func_return_type == "void":
                        self.err(f"Void heart '{echo_func_name}' cannot be assigned to variable '{var}'", line)
                        self.ok = False
                        return

            # mark all RHS identifiers as used
            for tok in rhs_toks:
                if tok in self.variable_usage:
                    self.variable_usage[tok]["used"] = True

            # check array out of bounds in RHS of assignment
            for idx, tok in enumerate(rhs_toks):
                if tok == "[" and idx > 0 and idx + 1 < len(rhs_toks):
                    arr_name = rhs_toks[idx - 1]
                    idx_tok = rhs_toks[idx + 1]
                    arr_entry = lookup(arr_name, self.scope_stack)
                    if arr_entry and "size" in arr_entry and idx_tok.lstrip("-").isdigit():
                        idx_val = int(idx_tok)
                        size = arr_entry.get("size", 0)
                        if idx_val < 0 or idx_val >= size:
                            self.err(f"Array index {idx_val} out of bounds for '{arr_name}'", line)
                            self.ok = False
                            return

            if not validate_expression_and_operators(rhs_toks, self.scope_stack, self.terminal, line,
                                                      check_standalone=False,
                                                      variable_usage=self.variable_usage,
                                                      popped_block_vars=self.popped_block_vars):
                self.ok = False
                return

            # type check
            if op == "=":
                value = get_rhs_value_from_node(rhs_node, self.function_table, self.scope_stack)
                ok, reason = type_check(entry["type"], value, self.scope_stack)
                if not ok:
                    log_type_error(entry["type"], value, var, line, self.terminal, reason)
                    self.ok = False
                elif reason:
                    log_warning(entry["type"], value, var, line, self.terminal, reason)

            elif op in ("+=", "-=", "*=", "/=", "//=", "%=", "^="):
                lhs_type = entry["type"]
                rhs_type = resolve_expression_type(rhs_toks, self.scope_stack, self.function_table)
                if op == "+=":
                    if lhs_type == "str" and rhs_type != "str":
                        self.err(f"Invalid operand for operator '+=', cannot concatenate str with '{rhs_type}'", line)
                    elif lhs_type != "str" and rhs_type == "str":
                        self.err(f"Invalid operand for operator '+=', str not allowed with non-str", line)
                else:
                    if lhs_type == "str":
                        self.err(f"Invalid operand for operator '{op}', str not allowed", line)
                    elif lhs_type == "bool":
                        self.err(f"Invalid operand for operator '{op}', bool not allowed", line)
                    elif rhs_type == "str":
                        self.err(f"Invalid operand for operator '{op}', str not allowed", line)
                    elif rhs_type == "bool":
                        self.err(f"Invalid operand for operator '{op}', bool not allowed", line)

        # Mark variable as initialized after successful assignment
        if op in ("=", "+=", "-=", "*=", "/=", "//=", "%=", "^="):
            self.mark_initialized(var)
            # Mark variable as runtime-modified if assigned inside a desire/hope block
            if entry and any(ctx in ("desire", "while", "do-while", "hope", "despair")
                             for ctx in self.block_context_stack):
                entry["modified_in_loop"] = True

    def _check_inc_dec(self, op, var, line):
        reserved = {
            "read", "spill", "core", "hope", "nope", "echo", "desire", "down",
            "despair", "memory", "default", "brain", "heart", "closure",
            "fixed", "int", "float", "char", "str", "bool", "trust", "betray"
        }
        if var in reserved:
            return
        entry = lookup(var, self.scope_stack)
        if not entry:
            if var in self.popped_block_vars:
                self.err("Variable from another scope cannot be accessed. Error found", line)
            else:
                self.err(f"Variable '{var}' used before declaration", line)
            return
        if entry.get("fixed"):
            self.err(f"Fixed variable '{var}' cannot be modified at", line)
            return
        if entry.get("type") == "str":
            self.err(f"str variable cannot be used with unary operator", line)
            return
        if var in self.variable_usage:
            self.variable_usage[var]["used"] = True
        # Mark variable as initialized after ++ / -- operation
        self.mark_initialized(var)


# ------------------- visit HOPE / DESPAIR -------------------    
#                                          
    def visit_hope(self, node):
        line       = node.get("line", 0)
        cond_node  = node.get("condition")
        cond_tokens = flatten_expr(cond_node)

        # Validate echo calls in condition (skip void-in-expression check, use condition check instead)
        self._validate_echo_calls_in_tokens(cond_tokens, line, skip_void_check=True)

        for i, ct in enumerate(cond_tokens):
            if ct == "echo" and i + 1 < len(cond_tokens):
                pf = cond_tokens[i + 1]
                if pf in self.function_table and self.function_table[pf].get("return") == "void":
                    self.err(f"Void heart '{pf}' cannot be used in a condition", line)

        if not validate_expression_and_operators(cond_tokens, self.scope_stack, self.terminal, line,
                                           check_standalone=False,
                                           variable_usage=self.variable_usage,
                                           popped_block_vars=self.popped_block_vars):
            self.ok = False
        for ct in cond_tokens:
            if ct in self.variable_usage:
                self.variable_usage[ct]["used"] = True

        try:
            self.conditional_decl_stack.append(set())
        except Exception:
            pass

        # Assign a unique conditional chain ID for this hope/despair structure.
        # The ID stays on the stack throughout both the hope body AND all sibling despair
        # branches, so that vars declared inside this chain get the correct cond_id,
        # and sibling branches can detect each other's vars as conflicts.
        self._cond_id_counter += 1
        _my_cond_id = self._cond_id_counter
        self._cond_id_stack.append(_my_cond_id)

        self.push_scope("hope")
        body = node.get("stmt") or node.get("loopStmt")
        if body:
            self.visit(body)
        if node.get("stmtOpTail"):
            self.visit(node["stmtOpTail"])
        self.pop_scope(line)

        tail        = node.get("hopeTail") or node.get("hopeTailLoop") or {}
        despair_opt = tail.get("despairOpt") or tail.get("despairOptLoop") or {}
        if despair_opt:
            self._handle_despair_opt(despair_opt, line)

        # Pop the cond_id AFTER the entire hope+despair chain is done.
        self._cond_id_stack.pop()

        # Finished processing this conditional structure; discard the tracking set
        try:
            if self.conditional_decl_stack:
                self.conditional_decl_stack.pop()
        except Exception:
            pass

    def _handle_despair_opt(self, node, parent_line):
        line = node.get("line", parent_line)
        if node.get("condition"):
            cond_tokens = flatten_expr(node["condition"])
            
            # Validate echo calls in condition (skip void-in-expression check, use condition check instead)
            self._validate_echo_calls_in_tokens(cond_tokens, line, skip_void_check=True)
            
            for i, ct in enumerate(cond_tokens):
                if ct == "echo" and i + 1 < len(cond_tokens):
                    pf = cond_tokens[i + 1]
                    if pf in self.function_table and self.function_table[pf].get("return") == "void":
                        self.err(f"Void heart '{pf}' cannot be used in a condition", line)
            if not validate_expression_and_operators(cond_tokens, self.scope_stack, self.terminal, line,
                                               check_standalone=False,
                                               variable_usage=self.variable_usage,
                                               popped_block_vars=self.popped_block_vars):
                self.ok = False
            for ct in cond_tokens:
                if ct in self.variable_usage:
                    self.variable_usage[ct]["used"] = True

        # The despair body runs with the SAME cond_id as the sibling hope
        # (the parent hope's ID is still on _cond_id_stack). This ensures that
        # vars declared in the hope body correctly conflict with redeclarations here.
        self.push_scope("despair")
        body = node.get("stmt") or node.get("loopStmt")
        if body:
            self.visit(body)
        if node.get("stmtOpTail"):
            self.visit(node["stmtOpTail"])
        self.pop_scope(line)

        inner_tail    = node.get("hopeTail") or node.get("hopeTailLoop") or {}
        inner_despair = inner_tail.get("despairOpt") or inner_tail.get("despairOptLoop") or {}
        if inner_despair:
            self._handle_despair_opt(inner_despair, line)


# ------------------  visit CORE ------------------------     
#                                          
    def visit_core(self, node):
        line = node.get("line", 0)
        self.default_seen = False
        self.memory_labels_stack.append(set(self.memory_labels))
        self.memory_labels.clear()

        cond_node = node.get("condition") or {}
        core_value = ""
        cond_tokens = []
        resolved = None

        # Prefer explicit coreOp structure when available in the AST (safer than relying on flatten_expr)
        core_op = cond_node.get("coreOp") if isinstance(cond_node, dict) else None
        
        # Handle echo function calls as core value
        if core_op and isinstance(core_op, dict) and core_op.get("kind") == "echo":
            # Echo call detected in coreOp
            echo_func = core_op.get("name", "")
            echo_tokens = ["echo", echo_func]
            
            # Build full token list for echo call validation
            if core_op.get("echOp"):
                echo_args_tokens = flatten_expr(core_op.get("echOp"))
                echo_tokens.extend(["("])
                echo_tokens.extend(echo_args_tokens)
                echo_tokens.extend([")"])
            
            # Validate echo calls in core value
            self._validate_echo_calls_in_tokens(echo_tokens, line, skip_void_check=False)
            
            if echo_func in self.function_table:
                resolved = self.function_table[echo_func].get("return")
                core_value = echo_func  # for marking as used
                
                # Strict type checking: echo in core must return int or char
                if resolved not in ("int", "char"):
                    self.err(f"Heart '{echo_func}' returns '{resolved}', core only allows int or char ", line)
                    resolved = None
            else:
                self.err(f"Function called before declaration: `{echo_func}()`", line)
                resolved = None
        
        # Handle regular identifiers or other core values
        elif core_op and isinstance(core_op, dict) and core_op.get("name"):
            core_value = core_op.get("name")
            
            # If the core value is an identifier, ensure it was declared in some scope
            try:
                if core_value and isinstance(core_value, str) and core_value.isidentifier():
                    entry = lookup(core_value, self.scope_stack)
                    if not entry:
                        if core_value in self.popped_block_vars:
                            self.err("Variable from another scope cannot be accessed. Error found", line)
                        else:
                            self.err("Using undeclared variable as core value. Error found", line)
            except Exception:
                # Be defensive: don't crash semantic analysis if lookup fails unexpectedly
                pass

            resolved = resolve_type(core_value, self.scope_stack)

            if resolved and resolved != "char":
                entry = lookup(core_value, self.scope_stack)
                if entry and entry.get("value") is not None:
                    val = str(entry["value"])
                    if val.startswith("'") and val.endswith("'"):
                        resolved = "char"
                    elif val.lstrip("-").isdigit():
                        resolved = "int"

            if core_value in self.variable_usage:
                self.variable_usage[core_value]["used"] = True
        
        # Fallback: flatten expression if no coreOp
        else:
            cond_tokens = flatten_expr(cond_node)
            core_value = cond_tokens[0] if cond_tokens else ""
            
            # Check for echo in flattened tokens
            if core_value == "echo" and cond_tokens and len(cond_tokens) > 1:
                # Validate echo calls in core value
                self._validate_echo_calls_in_tokens(cond_tokens, line, skip_void_check=False)
                
                echo_func = cond_tokens[1]
                if echo_func in self.function_table:
                    resolved = self.function_table[echo_func].get("return")
                    
                    # Strict type checking: echo in core must return int or char
                    if resolved not in ("int", "char"):
                        self.err(f"Heart '{echo_func}' returns '{resolved}', core only allows int or char ", line)
                        resolved = None
                else:
                    self.err(f"Function called before declaration: `{echo_func}()`", line)
                    resolved = None
            else:
                # Regular identifier/variable
                try:
                    if core_value and isinstance(core_value, str) and core_value.isidentifier():
                        entry = lookup(core_value, self.scope_stack)
                        if not entry:
                            if core_value in self.popped_block_vars:
                                self.err("Variable from another scope cannot be accessed. Error found", line)
                            else:
                                self.err("Using undeclared variable as core value. Error found", line)
                except Exception:
                    pass

                resolved = resolve_type(core_value, self.scope_stack)

                if resolved and resolved != "char":
                    entry = lookup(core_value, self.scope_stack)
                    if entry and entry.get("value") is not None:
                        val = str(entry["value"])
                        if val.startswith("'") and val.endswith("'"):
                            resolved = "char"
                        elif val.lstrip("-").isdigit():
                            resolved = "int"

                if core_value in self.variable_usage:
                    self.variable_usage[core_value]["used"] = True

        self.core_type = resolved

        # start tracking declared names for this core to detect redeclarations across memory blocks
        try:
            self.core_declared_names_stack.append(set())
        except Exception:
            pass
        self.push_scope("core")
        self.core_type_stack.append(self.core_type)

        body = node.get("body", {}) or {}
        self._visit_core_body(body)
        self.pop_scope(line)

    def _visit_core_body(self, node):
        if not node:
            return
        for case in node.get("cases", []):
            self._visit_memory_case(case)
        if "default" in node:
            self._visit_default_case(node["default"], node.get("line", 0))

    def _visit_memory_case(self, case):
        line  = case.get("line", 0)
        label = str(case.get("memVal", ""))

        pushed = False
        if "{" in str(case):
            self.push_scope("memory")
            pushed = True
            # Tag this memory scope so we can deduplicate warnings reliably
            try:
                self._memory_id_counter += 1
                self.scope_stack[-1]["__memory_id__"] = self._memory_id_counter
                self.scope_stack[-1]["__mem_key__"] = (label, line)
                # initialize over flag explicitly
                self.scope_stack[-1]["__over_seen__"] = False
            except Exception:
                pass

        # Error on duplicate memory labels within the same core: same label used
        if label in self.memory_labels:
            self.err(f"Duplicate memory label '{label}'. Error found at line", line)
        else:
            self.memory_labels.add(label)

        label_type = resolve_type(label, self.scope_stack)
        is_direct  = False
        if self.block_context_stack:
            search = self.block_context_stack[:-1]
            if "core" in search:
                core_idx = max(i for i, v in enumerate(search) if v == "core")
                between  = search[core_idx + 1:]
                if not any(v == "memory" for v in between):
                    is_direct = True

        if self.core_type and label_type != self.core_type and is_direct:
            self.err("Memory label should match the data type of core. Error found at line", line)

        # The parser/syntax layer enforces that 'default' must be the last
        stmt_node = case.get("loopStmt") or case.get("coreStmt") or case.get("stmt")
        if stmt_node:
            self.visit(stmt_node)

        # Determine end-of-memory line: prefer the maximum line found inside the memory
        end_line = line
        if stmt_node:
            mx = self._max_line_in_node(stmt_node)
            if mx:
                end_line = mx

        # If AST doesn't include an explicit 'over', try to detect an 'over' that
        # belongs to this memory block. We match braces to ensure we only count
        # 'over' tokens that are at this block's top level (so nested 'over'
        # doesn't suppress the parent's warning). Also accept an 'over' placed
        # immediately after the closing brace.
        try:
            tokens = getattr(self, "tokens", None)
            found_over = False
            close_line = None
            if tokens:
                # Find an opening brace for this memory block. Prefer a brace after
                # the memory label's line; fallback to the first '{' on/after the line.
                open_idx = None
                for idx, (val, t_type, t_line, _) in enumerate(tokens):
                    if t_line >= line and val == "{":
                        open_idx = idx
                        break

                if open_idx is not None:
                    # Find matching closing brace
                    depth = 0
                    close_idx = None
                    for idx in range(open_idx, len(tokens)):
                        v, t_type, t_line, _ = tokens[idx]
                        if v == "{":
                            depth += 1
                        elif v == "}":
                            depth -= 1
                            if depth == 0:
                                close_idx = idx
                                close_line = t_line
                                break

                    if close_idx is not None:
                        # Search for 'over' at the block's top nesting level
                        rel_depth = 0
                        for idx in range(open_idx + 1, close_idx):
                            v, t_type, t_line, _ = tokens[idx]
                            if v == "{":
                                rel_depth += 1
                            elif v == "}":
                                rel_depth -= 1
                            elif v == "over" and rel_depth == 0:
                                found_over = True
                                break

                        # If not found inside, accept an 'over' immediately after the close
                        if not found_over:
                            next_idx = close_idx + 1
                            # skip whitespace/comments
                            while next_idx < len(tokens) and tokens[next_idx][1] in ("space", "tab", "newline", "ocmt", "mcmt"):
                                next_idx += 1
                            if next_idx < len(tokens):
                                nv, nt, nt_line, _ = tokens[next_idx]
                                if nv == "over" and (close_line is None or close_line < nt_line <= (close_line + 2)):
                                    found_over = True

            if found_over and pushed:
                # mark current top-of-stack memory scope so pop_scope won't warn
                top = self.scope_stack[-1] if self.scope_stack else {}
                top["__over_seen__"] = True
        except Exception:
            pass

        # pop_scope will emit the missing-'over' warning for this memory (once)
        if pushed:
            self.pop_scope(close_line or end_line)

    def _visit_default_case(self, stmt_node, line):
        self.default_seen = True
        self.push_scope("memory")
        if stmt_node:
            self.visit(stmt_node)
        end_line = line
        if stmt_node:
            mx = self._max_line_in_node(stmt_node)
            if mx:
                end_line = mx
        self.pop_scope(end_line)

 # ---------------------- LOOPS ---------------------------
                                                       
    def _handle_desire(self, node, line):
        din           = node.get("din", {}) or {}
        cond_node     = node.get("condition")
        dup           = node.get("dup")
        loop_var_type = din.get("dtype", "")
        loop_var_name = din.get("name", "")

        # Validate echo calls in initialization (din)
        din_tail = din.get("dinTail", {}) or {}
        init_value_node = din_tail.get("value")
        if init_value_node:
            init_tokens = flatten_expr(init_value_node)
            self._validate_echo_calls_in_tokens(init_tokens, line)
            if not validate_expression_and_operators(init_tokens, self.scope_stack, self.terminal, line,
                                                      check_standalone=False,
                                                      variable_usage=self.variable_usage,
                                                      popped_block_vars=self.popped_block_vars):
                self.ok = False

        cond_tokens = flatten_expr(cond_node)
        
        # Validate echo calls in condition (skip void-in-expression check, use condition check instead)
        self._validate_echo_calls_in_tokens(cond_tokens, line, skip_void_check=True)
        
        for i, ct in enumerate(cond_tokens):
            if ct == "echo" and i + 1 < len(cond_tokens):
                pf = cond_tokens[i + 1]
                if pf in self.function_table and self.function_table[pf].get("return") == "void":
                    self.err(f"Void heart '{pf}' cannot be used in a desire loop condition", line)

        # Determine whether the loop initialization declares a new variable
        is_declaration = bool(loop_var_type)

        if is_declaration:
            loop_var_redecl_error = False

            # Check active scopes
            for scope in self.scope_stack:
                if loop_var_name in scope:
                    self.terminal.log(f"Semantic Error: Identifier '{loop_var_name}' is already declared in the outer scope. Error found at line {line}")
                    self.ok = False
                    loop_var_redecl_error = True
                    break

            # Check core-declared names (covers redecls across memory blocks / sibling control blocks)
            if not loop_var_redecl_error:
                try:
                    if self.core_declared_names_stack and loop_var_name in self.core_declared_names_stack[-1]:
                        self.terminal.log(f"Semantic Error: Identifier '{loop_var_name}' is already declared in this core. Error found at line {line}")
                        self.ok = False
                        loop_var_redecl_error = True
                except Exception:
                    pass

            # Check conditional-declaration stack (hope/despair structure)
            if not loop_var_redecl_error:
                try:
                    current_ctx = self.block_context_stack[-1] if self.block_context_stack else None
                    if self.conditional_decl_stack and current_ctx in ("hope", "despair"):
                        if loop_var_name in self.conditional_decl_stack[-1]:
                            self.terminal.log(f"Semantic Error: Identifier '{loop_var_name}' is already declared in this conditional structure. Error found at line {line}")
                            self.ok = False
                            loop_var_redecl_error = True
                except Exception:
                    pass

            # Check popped_block_vars
            if not loop_var_redecl_error and self._popped_is_conflict(loop_var_name):
                self.terminal.log(f"Semantic Error: Identifier '{loop_var_name}' is already declared in this scope. Error found at line {line}")
                self.ok = False
                loop_var_redecl_error = True

            if loop_var_redecl_error:
                # Even though the loop variable is invalid, still visit the body
                # so errors inside (e.g. accessing the bad var as an array index) are reported.
                # Temporarily reset self.ok so validators inside the body (spill, read)
                # are not skipped by the early-exit "if self.ok" guards.
                saved_ok = self.ok
                self.ok = True
                self.push_scope("desire")
                loop_body = node.get("loopStmt")
                if loop_body:
                    self.visit(loop_body)
                self.pop_scope(line)
                # Restore ok: keep False (errors were found), merge any new errors
                self.ok = False
                return

            # New loop-local declaration: push a new scope and declare it
            current_ctx = self.block_context_stack[-1] if self.block_context_stack else None
            self.push_scope("desire")
            self.scope_stack[-1][loop_var_name] = {"type": loop_var_type, "fixed": False}
            self.variable_usage[loop_var_name]  = {"declared_line": line, "used": True, "type": "loop_var"}

            # Record this name in core/conditional registries so sibling blocks
            # cannot redeclare it later (even after this scope is popped).
            try:
                if self.core_declared_names_stack:
                    self.core_declared_names_stack[-1].add(loop_var_name)
            except Exception:
                pass
            try:
                if self.conditional_decl_stack and current_ctx in ("hope", "despair"):
                    self.conditional_decl_stack[-1].add(loop_var_name)
            except Exception:
                pass
        else:
            # Using an existing variable as the loop iterator (no type keyword present)
            # Ensure the identifier exists in some outer scope
            entry = lookup(loop_var_name, self.scope_stack)
            if not entry:
                if loop_var_name in self.popped_block_vars:
                    self.terminal.log(f"Variable from another scope cannot be accessed. Error found at line {line}")
                else:
                    self.terminal.log(f"Identifier '{loop_var_name}' used before declaration. Error found at line {line}")
                self.ok = False
                return

            # Push a new loop scope but DO NOT redeclare the variable (use the outer binding)
            self.push_scope("desire")
            # mark as used
            if loop_var_name in self.variable_usage:
                self.variable_usage[loop_var_name]["used"] = True
        
        # Perform type checking on initialization value
        if init_value_node:
            init_value = get_rhs_value_from_node(init_value_node, self.function_table, self.scope_stack)
            ok, reason = type_check(loop_var_type, init_value, self.scope_stack)
            if not ok:
                log_type_error(loop_var_type, init_value, loop_var_name, line, self.terminal, reason)
                self.ok = False
            elif reason:
                log_warning(loop_var_type, init_value, loop_var_name, line, self.terminal, reason)

         # so we can catch array out-of-bounds when index is a loop variable
        if cond_tokens:
            for ci, ct in enumerate(cond_tokens):
                if ct in ("<=", "<") and ci + 1 < len(cond_tokens):
                    bound_tok = cond_tokens[ci + 1]
                    if bound_tok.lstrip("-").isdigit():
                        bound_val = int(bound_tok)
                        if ct == "<=":
                            bound_val += 1  # I <= 5 means max index is 5, so upper = 6
                        # Try to set max_value on the loop-local entry if present, otherwise update the outer binding
                        if loop_var_name in self.scope_stack[-1]:
                            self.scope_stack[-1][loop_var_name]["max_value"] = bound_val
                        else:
                            outer_entry = lookup(loop_var_name, self.scope_stack)
                            if outer_entry:
                                outer_entry["max_value"] = bound_val
                    break

        # Validate the condition expression now that the loop variable is in scope.
        # This ensures undeclared identifiers (e.g., 'B' in 'B <= 10') are caught.
        if cond_tokens:
            if not validate_expression_and_operators(cond_tokens, self.scope_stack, self.terminal, line,
                                                      check_standalone=False,
                                                      variable_usage=self.variable_usage,
                                                      popped_block_vars=self.popped_block_vars):
                self.ok = False
            for ct in cond_tokens:
                if ct in self.variable_usage:
                    self.variable_usage[ct]["used"] = True

        if dup:
            dup_tokens = flatten_expr(dup)
            
            # Validate echo calls in increment/update (skip void-in-expression check, use increment check instead)
            self._validate_echo_calls_in_tokens(dup_tokens, line, skip_void_check=True)
            
            # Validate expressions in increment
            if not validate_expression_and_operators(dup_tokens, self.scope_stack, self.terminal, line,
                                                      check_standalone=False,
                                                      variable_usage=self.variable_usage,
                                                      popped_block_vars=self.popped_block_vars):
                self.ok = False
            
            inc_var = None

            # Prefer detecting ++/-- pattern: variable ++ or ++ variable
            for i, t in enumerate(dup_tokens):
                if t in ("++", "--"):
                    # prefer previous token if it's a real identifier name (not the literal 'ID')
                    if i > 0 and dup_tokens[i - 1].isidentifier() and dup_tokens[i - 1] != 'ID':
                        inc_var = dup_tokens[i - 1]
                    elif i + 1 < len(dup_tokens) and dup_tokens[i + 1].isidentifier() and dup_tokens[i + 1] != 'ID':
                        inc_var = dup_tokens[i + 1]
                    break

            # Fallback: find the first actual identifier name token (skip placeholder 'ID')
            if inc_var is None:
                for t in dup_tokens:
                    if isinstance(t, str) and t.isidentifier() and t != 'ID':
                        inc_var = t
                        break

            if inc_var and inc_var != loop_var_name:
                self.err("Loop iteration variable mismatch with initializer at line", line)

        loop_body = node.get("loopStmt")
        if loop_body:
            self.visit(loop_body)
        self.pop_scope(line)

    def _handle_while(self, node, line):
        cond_node   = node.get("condition")
        cond_tokens = flatten_expr(cond_node)

        # Validate echo calls in condition (skip void-in-expression check, use condition check instead)
        self._validate_echo_calls_in_tokens(cond_tokens, line, skip_void_check=True)

        for i, ct in enumerate(cond_tokens):
            if ct == "echo" and i + 1 < len(cond_tokens):
                pf = cond_tokens[i + 1]
                if pf in self.function_table and self.function_table[pf].get("return") == "void":
                    self.err(f"Void heart '{pf}' cannot be used in a condition", line)

        if not validate_expression_and_operators(cond_tokens, self.scope_stack, self.terminal, line,
                                           check_standalone=False,
                                           variable_usage=self.variable_usage,
                                           popped_block_vars=self.popped_block_vars):
            self.ok = False
        for ct in cond_tokens:
            if ct in self.variable_usage:
                self.variable_usage[ct]["used"] = True

        self.push_scope("while")
        loop_body = node.get("loopStmt")
        if loop_body:
            self.visit(loop_body)
        self.pop_scope(line)

    def _handle_do_while(self, node, line):
        self.push_scope("do-while")
        loop_body = node.get("loopStmt")
        if loop_body:
            self.visit(loop_body)

        cond_node   = node.get("condition")
        cond_tokens = flatten_expr(cond_node)
        # Use the condition's own line number so errors point to the `while (...)` line,
        # not to the `do {` line which is the node's line.
        cond_line = (cond_node.get("line") if isinstance(cond_node, dict) else None) or line

        # Validate echo calls in condition (skip void-in-expression check, use condition check instead)
        self._validate_echo_calls_in_tokens(cond_tokens, cond_line, skip_void_check=True)

        for i, ct in enumerate(cond_tokens):
            if ct == "echo" and i + 1 < len(cond_tokens):
                pf = cond_tokens[i + 1]
                if pf in self.function_table and self.function_table[pf].get("return") == "void":
                    self.err(f"Void heart '{pf}' cannot be used in a do-while condition", cond_line)

        if not validate_expression_and_operators(cond_tokens, self.scope_stack, self.terminal, cond_line,
                                           check_standalone=False,
                                           variable_usage=self.variable_usage,
                                           popped_block_vars=self.popped_block_vars):
            self.ok = False
        for ct in cond_tokens:
            if ct in self.variable_usage:
                self.variable_usage[ct]["used"] = True

        self.pop_scope(line)

#-------------------- SPILL / ECHO ---------------------------                                                    
    def _handle_spill(self, node, line):
        spill_opt    = node.get("spillOpt", {}) or {}
        inner_tokens = flatten_expr(spill_opt)
    
        _spill_ok = validate_expression_and_operators(inner_tokens, self.scope_stack, self.terminal, line,
                                                check_standalone=False,
                                                variable_usage=self.variable_usage,
                                                popped_block_vars=self.popped_block_vars,
                                                in_spill=True)
        if not _spill_ok:
            self.ok = False
            return

        for k, t in enumerate(inner_tokens):
            if t in self.variable_usage:
                self.variable_usage[t]["used"] = True

            if k + 1 < len(inner_tokens) and inner_tokens[k + 1] == "[":
                arr_entry = lookup(t, self.scope_stack)
                if arr_entry and "size" in arr_entry and not arr_entry.get("initialized", False) and not arr_entry.get("assigned_in_loop", False):
                    inside_control = any(ctx in ("desire", "while", "do-while", "hope", "despair")
                                         for ctx in self.block_context_stack)
                    if not inside_control:
                        self.err(f"Array '{t}' at line {line} is used before any element has been assigned.", line)

        for arg in spill_opt.get("args", []):
            if not isinstance(arg, dict):
                continue
            if arg.get("kind") == "ID":
                arr_name = arg.get("name", "")
                arr_entry = lookup(arr_name, self.scope_stack)

                # Check undeclared variable 
                if arr_entry is None and arr_name not in self.function_table:
                    if arr_name in self.popped_block_vars:
                        self.err("Variable from another scope cannot be accessed. Error found", line)
                    else:
                        self.err(f"Variable '{arr_name}' used before declaration", line)

    def _check_echo_call(self, fname, ech_op_node, line):
        if fname not in self.function_table:
            self.err(f"Function called before declaration: `{fname}()`", line)
            return
        # Mark function as called
        self.called_functions.add(fname)
        self._validate_call_args(fname, ech_op_node, line)

    def _validate_call_args(self, func_name, ech_op_node, line):
        ft = self.function_table.get(func_name)
        if not ft:
            return
        # Mark function as called
        self.called_functions.add(func_name)
        expected_count = ft["params"]
        expected_types = ft.get("param_types", [])
        current_func   = None
        if self.function_context_stack:
            ctx = self.function_context_stack[-1]
            if ctx["type"] == "heart":
                current_func = ctx.get("func_name")

        args = []
        if ech_op_node and isinstance(ech_op_node, dict):
            for arg in ech_op_node.get("args", []):
                args.append(flatten_expr(arg))

        actual = len(args)
        if actual != expected_count:
            self.err(f"Function '{func_name}' requires {expected_count} arguments, but received {actual}", line)
            return

        for idx, arg_tokens in enumerate(args):
            if idx >= len(expected_types):
                break
            expected_type = expected_types[idx]
            if arg_tokens and arg_tokens[0] == "echo" and len(arg_tokens) > 1:
                nested_func = arg_tokens[1]
                if nested_func in self.function_table:
                    arg_type = self.function_table[nested_func].get("return")
                else:
                    arg_type = resolve_type(arg_tokens[0], self.scope_stack)
            else:
                arg_type = resolve_expression_type(arg_tokens, self.scope_stack, self.function_table)
                if not arg_type:
                    arg_type = resolve_type(arg_tokens[0], self.scope_stack) if arg_tokens else None

            if arg_type and arg_type != expected_type:
                is_expr = contains_expression(arg_tokens) or len(arg_tokens) > 1
                if is_expr:
                    allowed = (
                        (arg_type == "int"   and expected_type == "float") or
                        (arg_type == "float" and expected_type == "int")   or
                        (arg_type == "char"  and expected_type == "int")   or
                        (arg_type == "int"   and expected_type == "char")  or
                        (arg_type == "float" and expected_type == "char")  or
                        (arg_type == "char"  and expected_type == "float") or
                        (arg_type == "int"   and expected_type == "bool")  or
                        (arg_type == "bool"  and expected_type == "int")   or
                        (arg_type == "float" and expected_type == "bool")  or
                        (arg_type == "bool"  and expected_type == "float")
                    )
                    if not allowed:
                        self.err(f"Parameter type mismatch: Expected '{expected_type}', got '{arg_type}' for argument {idx + 1}", line)
                else:
                    self.err(f"Parameter type mismatch: Expected '{expected_type}', got '{arg_type}' for argument {idx + 1}", line)

            for tok in arg_tokens:
                if tok not in ("echo", "(", ")", ",", ";") and tok in self.variable_usage:
                    self.variable_usage[tok]["used"] = True

        if func_name == current_func:
            inside_conditional = any(ctx in ("hope", "despair") for ctx in self.block_context_stack)
            if not inside_conditional:
                self.terminal.log(f"WARNING!: Recursive echo without base case: Infinite recursion detection at line {line}")

# ------------------  visit loopStmt / coreStmt visitors ---------------------------                                     
   
    def visit_loopStmt(self, node):
        if node.get("return") is not None:
            self._handle_closure(node.get("return"), node.get("line", 0))
            return
        for stmt in node.get("stmts", []):
            self.visit(stmt)
        if node.get("over"):
            top = self.scope_stack[-1] if self.scope_stack else {}
            top["__over_seen__"] = True

    def visit_coreStmt(self, node):
        if node.get("continue") == "over":
            top = self.scope_stack[-1] if self.scope_stack else {}
            top["__over_seen__"] = True
            return
        if node.get("return") is not None:
            self._handle_closure(node.get("return"), node.get("line", 0))
            return
        for stmt in node.get("stmts", []):
            self.visit(stmt)

    def visit_stmtOpt1(self, node):
        if node.get("return") is not None:
            self._handle_closure(node.get("return"), node.get("line", 0))
        body = node.get("stmt") or node.get("loopStmt")
        if body:
            self.visit(body)
        if node.get("stmtOpTail"):
            self.visit(node["stmtOpTail"])

    def visit_stmtOpTail(self, node):
        if node.get("return") is not None:
            self._handle_closure(node.get("return"), node.get("line", 0))


# ----------------- ENTRY POINT FOR SEMANTIC ANALYSIS -------------------
                                         
class _TrackingTerminal:
    # semantic error logging in the terminal 
    def __init__(self, real_terminal):
        self._real = real_terminal
        self.has_error = False
    def log(self, msg):
        if msg.startswith("Semantic Error"):
            self.has_error = True
        self._real.log(msg)


def perform_semantic_analysis(tokens, terminal, parse_tree=None):
    global _token_type_map
    _token_type_map = _build_token_type_map(tokens)

    tracked = _TrackingTerminal(terminal)

    if parse_tree is None:
        tracked.log("Semantic Error: No parse tree provided.")
        return False, None                          # <-- changed

    visitor = SemanticVisitor(tracked)
    # Expose raw token stream to the visitor so it can detect tokens not present in the AST
    visitor.tokens = tokens
    visitor.visit(parse_tree)

    for var_name, info in visitor.variable_usage.items():
       if not info["used"] and not is_literal(var_name) and not info.get("initialized", False):
            if info.get("type") == "array":
                tracked.log(f"WARNING: Unused array '{var_name}' declared at line {info['declared_line']}")
            else:
                tracked.log(f"WARNING: Unused variable '{var_name}' declared at line {info['declared_line']}")
    
    # Guard: catch errors logged by standalone helpers that bypass visitor.ok
    no_errors = visitor.ok and not tracked.has_error
    if no_errors:
        terminal.log("No semantic errors found.")

    # Build annotated data package for downstream phases (ICG, optimization, code generation)
    semantic_data = {                              
        "scope_stack":    visitor.scope_stack,
        "function_table": visitor.function_table,
        "variable_usage": visitor.variable_usage,
        "parse_tree":     parse_tree,
        "token_type_map": _token_type_map,
        "no_errors":      no_errors,
    }

    return no_errors, semantic_data                 