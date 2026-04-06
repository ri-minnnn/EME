def identify_symbol(code):
    if not code:
        return None

    state = 129
    token = ''
    delimiter_type = None
    i = 0
    length = len(code)

    while i < length and state != -1:
        char = code[i]

        # === Initial state ===
        if state == 129:
            if char == '+':
                state = 130
                token += char
            elif char == '-':
                state = 135
                token += char
            elif char == '*':
                state = 141
                token += char
            elif char == '/':
                state = 145
                token += char
            elif char == '%':
                state = 153
                token += char
            elif char == '^':
                state = 157
                token += char
            elif char == '&':
                state = 161
                token += char
            elif char == '|':
                state = 164
                token += char
            elif char == '!':
                state = 167
                token += char
            elif char == '>':
                state = 171
                token += char
            elif char == '<':
                state = 175
                token += char
            elif char == '=':
                state = 179
                token += char
            elif char == '{':
                return '{', "incurlbraEme"
            elif char == '}':
                return '}', "clcurlEme"
            elif char == '[':
                return '[', "sqrbraEme"
            elif char == ']':
                return ']', "clbraEme"
            elif char == '(':
                return '(', "inparEme"
            elif char == ')':
                return ')', "clparEme"
            elif char == ',':
                return ',', "comEme"
            elif char == ':':
                return ':', "colonEme"
            elif char == ';':
                return ';', "termEme"
            elif char in ' \n\t':
                return char, "whiteEme"
            else:
                return None
            i += 1

        # ==== + ====
        elif state == 130:

            if i < length and code[i] == '+':        # ++
                token += code[i]
                delimiter_type = "unaEme"
                i += 1
            elif i < length and code[i] == '=':      # +=
                token += '='
                delimiter_type = "opEme"
                i += 1
            else:                                    # single '+'
                delimiter_type = "opEme"
            break
        
        # ==== - ====
        elif state == 135:
            if i < length and code[i] == '-':        # --
                token += code[i]
                delimiter_type = "unaEme"
                i += 1
            elif i < length and code[i] == '=':      # -=
                token += '='
                delimiter_type = "opEme"
                i += 1
            else:                                   # single '-'
                delimiter_type = "opEme"

            break

        # ==== * ====
        elif state == 141:
            if i < length and code[i] == '=':       # *=
                token += '='
                delimiter_type = "opEme"
                i += 1
            else:                                   # single '*'
                delimiter_type = "opEme"
            break

        # ==== / ====
        elif state == 145:
            if i < length and code[i] == '/':        # //
                token += '/'
                i += 1
                if i < length and code[i] == '=':    # //=
                    token += '='
                    i += 1
                delimiter_type = "divEme"
            elif i < length and code[i] == '=':      # /=
                token += '='
                delimiter_type = "divEme"
                i += 1
            else:                                    # single '/'
                delimiter_type = "divEme"
            break

        # ==== % ====
        elif state == 153:
            if i < length and code[i] == '=':        # %=
                token += '='
                delimiter_type = "divEme"
                i += 1
            else:                                    # single '%'
                delimiter_type = "divEme"
            break

        # ==== ^ ====
        elif state == 157:
            if i < length and code[i] == '=':        # ^=
                token += '='
                delimiter_type = "opEme"
                i += 1
            else:                                    # single '^'
                delimiter_type = "opEme"
            break

        # ==== & ====
        elif state == 161:
            if i < length and code[i] == '&':        # &&
                token += '&'
                delimiter_type = "relogEme"
                i += 1
            else:                                    # single '&'
                delimiter_type = "relogEme"
            break

        # ==== | ====
        elif state == 164:
            if i < length and code[i] == '|':        # ||
                token += '|'
                delimiter_type = "relogEme"
                i += 1
            else:                                    # single '|'
                delimiter_type = "relogEme"
            break

        # ==== ! ====
        elif state == 167:
            if i < length and code[i] == '=':        # !=
                token += '='
                delimiter_type = "relogEme"
                i += 1
            else:                                    # single '!'
                delimiter_type = "relogEme"
            break

        # ==== > ====
        elif state == 171:
            if i < length and code[i] == '=':        # >=
                token += '='
                delimiter_type = "relogEme"
                i += 1
            else:                                    # single '>'
                delimiter_type = "relogEme"
            break

        # ==== < ====
        elif state == 175:
            if i < length and code[i] == '=':        # <=
                token += '='
                delimiter_type = "relogEme"
                i += 1
            else:                                    # single '<'
                delimiter_type = "relogEme"
            break

        # ==== = ====
        elif state == 179:
            if i < length and code[i] == '=':        # ==
                token += '='
                delimiter_type = "relogEme"
                i += 1
            else:                                    # single '='
                delimiter_type = "eqEme"
            break


    if delimiter_type is None:
        if state == 129:
            delimiter_type = "opEme"
        elif state == 135:
            delimiter_type = "opEme"
        elif state == 141:
            delimiter_type = "opEme"
        elif state == 145:
            delimiter_type = "divEme"
        elif state == 153:
            delimiter_type = "divEme"
        elif state == 157:
            delimiter_type = "opEme"
        elif state == 161:
            delimiter_type = "relogEme"
        elif state == 164:
            delimiter_type = "relogEme"
        elif state == 167:
            delimiter_type = "relogEme"
        elif state == 171:
            delimiter_type = "relogEme"
        elif state == 175:
            delimiter_type = "relogEme"
        elif state == 179:
            delimiter_type = "eqEme"

    if token and delimiter_type:
        return token, delimiter_type
    return None