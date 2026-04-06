from delim import floatEme

def identify_floatlit(number, next_char):
    if not number or (not number[0].isdigit() and number[0] != '-'):
        return None

    state = 268  # Start state
    i = 0
    has_decimal = False

    # Process with if-else state machine
    while i < len(number):
        char = number[i]
        
        # === State 268: Start or after decimal ===
        if state == 268:
            if char.isdigit():
                state = 269
                i += 1
            elif char == '-':
                state = 268  # Stay for negative
                i += 1
            else:
                return None
                
        # === Individual digit states with explicit transitions ===
        elif state == 269:
            if char.isdigit():
                state = 270
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 270:
            if char.isdigit():
                state = 271
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 271:
            if char.isdigit():
                state = 272
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 272:
            if char.isdigit():
                state = 273
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 273:
            if char.isdigit():
                state = 274
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 274:
            if char.isdigit():
                state = 275
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 275:
            if char.isdigit():
                state = 276
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 276:
            if char.isdigit():
                state = 277
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 277:
            if char.isdigit():
                state = 278
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 278:
            if char.isdigit():
                state = 279
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 279:
            if char.isdigit():
                state = 280
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 280:
            if char.isdigit():
                state = 281
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 281:
            if char.isdigit():
                state = 282
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 282:
            if char.isdigit():
                state = 283
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 283:
            if char.isdigit():
                state = 284
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 284:
            if char.isdigit():
                state = 285
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 285:
            if char.isdigit():
                state = 286
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 286:
            if char.isdigit():
                state = 287
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 287:
            if char.isdigit():
                state = 288
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 288:
            if char.isdigit():
                state = 289
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 289:
            if char.isdigit():
                state = 290
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
                
        elif state == 290:
            if char.isdigit():
                i += 1
            elif char == '.' and not has_decimal:
                state = 268
                has_decimal = True
                i += 1
            else:
                break
        else:
            break

    # Check if we're in an accepting state and has decimal point
    float_accepting_states = {269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 
                             279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290}
    
    if state in float_accepting_states and has_decimal:
       
        if next_char and next_char.isalpha():
            return None
        return number, "FLOATLIT"