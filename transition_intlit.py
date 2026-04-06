from delim import intEme 

def identify_intlit(number, next_char):
    if not number or (not number[0].isdigit() and number[0] != '-'):
        return None

    state = 244  # Start state
    i = 0

    while i < len(number):
        char = number[i]
        
        if state == 244:
            if char.isdigit():
                state = 246
                i += 1
            elif char == '-':
                state = 245
                i += 1
            else:
                return None
                
        elif state == 245:
            if char.isdigit():
                state = 246
                i += 1
            else:
                return None

        elif state == 246:
            if char.isdigit():
                state = 247
                i += 1
            else:
                break
                
        elif state == 247:
            if char.isdigit():
                state = 248
                i += 1
            else:
                break
                
        elif state == 248:
            if char.isdigit():
                state = 249
                i += 1
            else:
                break
                
        elif state == 249:
            if char.isdigit():
                state = 250
                i += 1
            else:
                break
                
        elif state == 250:
            if char.isdigit():
                state = 251
                i += 1
            else:
                break
                
        elif state == 251:
            if char.isdigit():
                state = 252
                i += 1
            else:
                break
                
        elif state == 252:
            if char.isdigit():
                state = 253
                i += 1
            else:
                break
                
        elif state == 253:
            if char.isdigit():
                state = 254
                i += 1
            else:
                break
                
        elif state == 254:
            if char.isdigit():
                state = 255
                i += 1
            else:
                break
                
        elif state == 255:
            if char.isdigit():
                state = 256
                i += 1
            else:
                break
                
        elif state == 256:
            if char.isdigit():
                state = 257
                i += 1
            else:
                break
                
        elif state == 257:
            if char.isdigit():
                state = 258
                i += 1
            else:
                break
                
        elif state == 258:
            if char.isdigit():
                state = 259
                i += 1
            else:
                break
                
        elif state == 259:
            if char.isdigit():
                state = 260
                i += 1
            else:
                break
                
        elif state == 260:
            if char.isdigit():
                state = 261
                i += 1
            else:
                break
                
        elif state == 261:
            if char.isdigit():
                state = 262
                i += 1
            else:
                break
                
        elif state == 262:
            if char.isdigit():
                state = 263
                i += 1
            else:
                break
                
        elif state == 263:
            if char.isdigit():
                state = 264
                i += 1
            else:
                break
                
        elif state == 264:
            if char.isdigit():
                state = 265
                i += 1
            else:
                break
                
        elif state == 265:
            if char.isdigit():
                state = 266
                i += 1
            else:
                break
                
        elif state == 266:
            if char.isdigit():
                state = 267
                i += 1
            else:
                break
                
        elif state == 267:
            if char.isdigit():
                i += 1
            else:
                break
        else:
            break

    # Check if we're in an accepting state
    if state >= 245 and state <= 267:
        if next_char and next_char.isalpha():
            return None
        return ("INTLIT",)
    
    return None