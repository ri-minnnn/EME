from delim import whiteEme, singcmtEme

asciicmt = set(chr(i) for i in range(32, 127))

def identify_comment(code_from_i):
    if not code_from_i or code_from_i[0] != ':':
        return None

    state = 299  # Start state - found ':'
    i = 0
    length = len(code_from_i)
    token = ""

    if len(code_from_i) >= 2 and code_from_i[0] == ':' and code_from_i[1] == '>':
        if len(code_from_i) >= 3 and code_from_i[2] == '>':
            # Multi-line comment: :>> ... :<
            state = 301  # Multi-line comment content (aciicmt loop)
            token = ":>>"
            i = 3
            found_end = False
            
            while i < length:
                # Check for closing :<
                if code_from_i[i] == ':' and i + 1 < length and code_from_i[i + 1] == '<':
                    token += ":<"
                    state = 303  # Found closing :<
                    i += 2
                    found_end = True
                    break
                elif code_from_i[i] not in asciicmt and code_from_i[i] != '\n':  # Allow newlines in multi-line
                    return None
                else:
                    token += code_from_i[i]
                i += 1
            
            if found_end:
                return token  # Just return the token, no type
        else:
            # Single-line comment - read until newline
            state = 302  # Single-line comment content (aciicmt loop)
            token = ":>"
            i = 2
            while i < length and code_from_i[i] != '\n':
                if code_from_i[i] not in asciicmt:
                    return None
                token += code_from_i[i]
                i += 1
            if i < length and code_from_i[i] == '\n':
                token += '\n'
                state = 304  # Found newline delimiter
                i += 1
                return token  # Just return the token, no type

    return None