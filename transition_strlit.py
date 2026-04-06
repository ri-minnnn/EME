from delim import strEme

asciistr = set(chr(i) for i in range(32, 126) if chr(i) not in ['"', '“', '”', '\n', '\r', '\t'])

def identify_strlit(code):
    if not code or (code[0] != '"' and code[0] != '“'):
        return None

    state = 291
    i = 0
    length = len(code)
    token = ""
    opening_quote = code[0]

    token += opening_quote
    state = 292
    i += 1

    while i < length:
        char = code[i]

        if state == 292:  # Inside string
            if char == '\\':  # Escape character found
                token += char
                i += 1
                if i < length:  
                    token += code[i]
                    i += 1
                else:
                    # Incomplete escape sequence - wait for more input
                    return None
            elif (opening_quote == '"' and char == '"') or (opening_quote == '“' and char == '”'):  # Closing quote found
                token += char
                state = 293  # Found closing quote
                i += 1
                break
            elif char in asciistr or char == ' ':
                token += char
                i += 1
            else:  # Invalid character in string
                token += char
                i += 1
                # Continue reading to find closing quote
                found_quote = False
                while i < length:
                    next_char = code[i]
                    if next_char == '\\':  
                        token += next_char
                        i += 1
                        if i < length:
                            token += code[i]
                            i += 1
                        else:
                            return None
                    elif (opening_quote == '"' and next_char == '"') or (opening_quote == '“' and next_char == '”'):
                        token += next_char
                        i += 1
                        state = 293
                        found_quote = True
                        break
                    else:
                        token += next_char
                        i += 1
                
                if found_quote:
                    break
                else:
                    # No closing quote found yet - wait for more inputz
                    return None

    if state == 293:  
        # We have a complete string literal - return JUST the token
        return token
    else:  
        # Never found closing quote - wait for more input
        return None