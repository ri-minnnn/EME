from delim import *
from transition_reserved import identify_reserved_word
from transition_symbol import identify_symbol
from transition_id import identify_identifier, idEme
from transition_floatlit import identify_floatlit
from transition_charlit import identify_charlit, charEme
from transition_strlit import identify_strlit, strEme
from transition_intlit import identify_intlit, intEme
from transition_com import identify_comment


def perform_lexical_analysis(code, terminal=None):
    symbol_chars = set('+-*/%=^&|!><=(){}[]:,; \t\n')
    default_delim = "whiteEme"  # Default delimiter if last token has no next_char
    lexeme_list = []
    i = 0
    length = len(code)
    line, col = 1, 1
    id_counter = 1
    
    def validate_int(number_str):
        """Returns (is_valid, is_overflow)"""
        if not number_str:
            return False, False
        
        if number_str[0] == '-':
            if len(number_str) == 1 or not number_str[1:].isdigit():
                return False, False
            digits_part = number_str[1:]
        elif number_str.isdigit():
            digits_part = number_str
        else:
            return False, False
        
        stripped = digits_part.lstrip('0')
        digit_count = 1 if stripped == '' else len(stripped)
        
        if digit_count > 12:
            return False, True
        
        try:
            value = int(number_str)
            if value < -999999999999 or value > 999999999999:
                return False, True
        except ValueError:
            return False, False
        
        return True, False

    def validate_float(float_str):
        """Returns (is_valid, is_overflow)"""
        if not float_str:
            return False, False
        
        parts = float_str.split('.')
        if len(parts) != 2:
            return False, False
        
        int_part, dec_part = parts
        if len(int_part) == 0 or len(dec_part) == 0:
            return False, False
        
        is_negative = False
        if int_part and int_part[0] == '-':
            is_negative = True
            int_part = int_part[1:]
        
        if not int_part.isdigit() or not dec_part.isdigit():
            return False, False
        
        if len(int_part) > 12 or len(dec_part) > 11 or len(int_part) + len(dec_part) > 23:
            return False, True
        
        try:
            value = float(float_str)
            if abs(value) > 999999999999.99999999999:
                return False, True
        except ValueError:
            return False, False
        
        return True, False

    while i < length:
        ch = code[i]

        # === COMMENTS ===
        result = identify_comment(code[i:])
        if result is not None:
            comment_token = result
            if comment_token.startswith(':>>') and comment_token.endswith(':<'):
                token_type = "mcmt"
            elif comment_token.startswith(':>') and comment_token.endswith('\n'):
                token_type = "ocmt"
            else:
                # If comment doesn't end with newline (e.g., at EOF), still classify as ocmt
                if comment_token.startswith(':>') and not comment_token.startswith(':>>'):
                    token_type = "ocmt"
                else:
                    continue  # Invalid comment format, skip it

            lexeme_list.append((comment_token, token_type, line, col))
            newline_count = comment_token.count('\n')
            if newline_count > 0:
                line += newline_count
                last_newline_pos = comment_token.rfind('\n')
                col = len(comment_token) - last_newline_pos
            else:
                col += len(comment_token)

            i += len(comment_token)
            continue
            
        # === CHARACTER LITERALS ===
        result = identify_charlit(code[i:])
        if result is not None:
            charlit_token = result
            is_valid_length = (
                (charlit_token.startswith("'") and charlit_token.endswith("'") and
                 (len(charlit_token) == 3 or (len(charlit_token) == 4 and charlit_token[1] == '\\'))) or
                (charlit_token.startswith("‘") and charlit_token.endswith("’") and
                 (len(charlit_token) == 3 or (len(charlit_token) == 4 and charlit_token[1] == '\\')))
            )
            is_valid_escape = True
            if len(charlit_token) == 4 and charlit_token[1] == '\\':
                escaped_char = charlit_token[2]
                if escaped_char not in ['t', 'n', "'", '"', '\\']:
                    is_valid_escape = False

            if is_valid_length and is_valid_escape:
                next_char_index = i + len(charlit_token)
                if next_char_index < len(code):
                    next_part = code[next_char_index:]
                    has_valid_delimiter = False
                    for op in operator:
                        if next_part.startswith(op):
                            has_valid_delimiter = True
                            break
                    if not has_valid_delimiter and (next_part[0] in strEme or next_part[0] == ':'):
                        has_valid_delimiter = True
                    if has_valid_delimiter:
                        lexeme_list.append((charlit_token, "CHARLIT", line, col))
                    else:
                        lexeme_list.append((charlit_token, "UNKNOWN", line, col))
                        if terminal:
                            terminal.log(f"ERROR: invalid {charlit_token} at line {line}, column {col}")

                    i += len(charlit_token)
                    col += len(charlit_token)
                    continue
            else:
                lexeme_list.append((charlit_token, "UNKNOWN", line, col))
                if terminal:
                    terminal.log(f"ERROR: invalid {charlit_token} at line {line}, column {col}")
                i += len(charlit_token)
                col += len(charlit_token)
                continue

        # === STRING LITERALS ===
        result = identify_strlit(code[i:])
        if result is not None:
            strlit_token = result
            next_char_index = i + len(strlit_token)
            next_char = code[next_char_index] if next_char_index < length else None
            if next_char is None:
                next_char_type = default_delim
            else:
                next_char_type = next_char
            if next_char_type in strEme or next_char_type == default_delim:
                lexeme_list.append((strlit_token, "STRLIT", line, col))
            else:
                lexeme_list.append((strlit_token, "UNKNOWN", line, col))
                if terminal:
                    terminal.log(f"ERROR: invalid {strlit_token} at line {line}, column {col}")
            i += len(strlit_token)
            col += len(strlit_token)
            continue

        # === Numbers ===
        if (ch.isdigit() or 
            (ch == '-' and i + 1 < length and (code[i + 1].isdigit() or code[i + 1] == '.') and
             (i == 0 or code[i-1].isspace() or code[i-1] in '(+*/=,{[:')) or 
            ch == '.'):
            
            start = i
            start_col = col
            is_negative = (ch == '-')
            if ch == '-':
                i += 1
                col += 1
            while i < length and (code[i].isdigit() or code[i] == '.'):
                i += 1
                col += 1
            full_sequence = code[start:i]
            number_part = full_sequence[1:] if is_negative else full_sequence
            next_char = code[i] if i < length else None
            has_decimal = '.' in number_part

            # Default delimiter if last token
            if next_char is None:
                next_char_type = default_delim
            else:
                next_char_type = next_char

            if not has_decimal:
                result = identify_intlit(full_sequence, next_char_type)
                is_valid, is_overflow = validate_int(full_sequence)
                if result is not None and is_valid and not is_overflow:
                    lexeme_list.append((full_sequence, "INTLIT", line, start_col))
                else:
                    lexeme_list.append((full_sequence, "UNKNOWN", line, start_col))
            else:
                result = identify_floatlit(full_sequence, next_char_type)
                is_valid, is_overflow = validate_float(full_sequence)
                if result is not None and is_valid and not is_overflow:
                    lexeme_list.append((full_sequence, "FLOATLIT", line, start_col))
                else:
                    lexeme_list.append((full_sequence, "UNKNOWN", line, start_col))
            continue

        # === Identifiers (UPPERCASE) ===
        if ch.isupper():
            start = i
            start_col = col
            while i < length and (code[i].isupper() or code[i].isdigit() or code[i] == '_'):
                i += 1
                col += 1
            identifier = code[start:i]
            next_char = code[i] if i < length else None
            next_char_type = default_delim if next_char is None else next_char
            result = identify_identifier(identifier, next_char_type)
            if result is not None:
                lexeme_list.append((identifier, f"ID{id_counter}", line, start_col))
                id_counter += 1
            else:
                lexeme_list.append((identifier, "UNKNOWN", line, start_col))
            continue

        # === Reserved Words (lowercase) ===
        if ch.islower():
            start = i
            start_col = col
            while i < length and code[i].isalpha():
                i += 1
                col += 1
            word = code[start:i]
            next_char = code[i] if i < length else None
            next_char_type = default_delim if next_char is None else next_char
            result = identify_reserved_word(word, next_char_type)
            if result is not None:
                lexeme_list.append((word, result, line, start_col))
            else:
                for idx, char in enumerate(word):
                    lexeme_list.append((char, "UNKNOWN", line, start_col + idx))
                    if terminal:
                        terminal.log(f"ERROR: invalid {char} at line {line}, column {start_col + idx}")
            continue

        # === Symbols ===
        if ch in symbol_chars:
            result = identify_symbol(code[i:])
            if result is not None:
                symbol_token, delimiter_type = result
                next_index = i + len(symbol_token)
                next_char = code[next_index] if next_index < length else None
                valid_delims = delim_sets.get(delimiter_type, set())
                next_char_type = default_delim if next_char is None else next_char
                if delimiter_type == "whiteEme" or next_char_type in valid_delims or next_char_type == default_delim:
                    if symbol_token == ' ':
                        lexeme_list.append(('⎵', 'space', line, col))
                    elif symbol_token == '\t':
                        lexeme_list.append(('\t', 'tab', line, col))
                    elif symbol_token == '\n':
                        lexeme_list.append(('\n', 'newline', line, col))
                        line += 1
                        col = 1
                    else:
                        lexeme_list.append((symbol_token, symbol_token, line, col))
                    i += len(symbol_token)
                    if symbol_token != '\n':
                        col += len(symbol_token)
                    continue
                else:
                    lexeme_list.append((symbol_token, "UNKNOWN", line, col))
                    i += len(symbol_token)
                    col += len(symbol_token)
                    continue
            else:
                i += 1
                col += 1
                continue

        # === Unknown Character ===
        lexeme_list.append((ch, "UNKNOWN", line, col))
        i += 1
        col += 1

    return lexeme_list
