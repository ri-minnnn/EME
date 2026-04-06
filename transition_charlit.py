from delim import charEme

asciichar = set(chr(i) for i in range(32, 127) if chr(i) not in ["'", "‘", "’"])

def identify_charlit(code):
    if not code or (code[0] != "'" and code[0] != "‘"):
        return None

    state = 295  # Opening quote '
    i = 0
    length = len(code)
    token = ""
    opening_quote = code[0]

    token += opening_quote
    state = 296  # asciichar
    i += 1

    char_count = 0
    
    while i < length:
        char = code[i]

        if state == 296:  # Inside char - expecting asciichar
            if char == '\\':  # Escape character found
                token += char
                i += 1
                if i < length:  
                    token += code[i]
                    i += 1
                    char_count = 1
                else:
                    return token
            elif (opening_quote == "'" and char == "'") or (opening_quote == "‘" and char == "’"):  # Closing quote found
                if char_count == 0:
                    # Empty char literal - return as invalid
                    token += char
                    return token
                else:
                    token += char
                    i += 1
                    break
            elif char in asciichar:
                token += char
                i += 1
                char_count += 1
                if char_count > 1:
                    # Multiple characters - return immediately as invalid
                    return token
            else:  # Invalid character in char
                token += char
                i += 1
                return token

    return token