from delim import idEme

def identify_identifier(identifier, next_char=None):
    state = 204  # Start state

  
    if not identifier:  # Empty identifier check
        return None

    for char in identifier:
        # === Initial character transitions ===
        if state == 204:
            if char.isupper():
                state = 205
            else:
                return None

        # === DFA transitions ===
        elif state == 205:
            if char.isupper() or char.isdigit() or char == '_':
                state = 205  # Stay in accepting state
            else:
                return None

    # Final state checks using length and delimiter validation
    final_states = {
        205: ("IDENTIFIER", "idEme") 
    }

    delim_sets = {
        "idEme": idEme
    }

    # Check length constraint (1-19 characters)
    if not (1 <= len(identifier) <= 20):
        return None

    if state in final_states and next_char is not None:
        token_name, delim_type = final_states[state]
        if next_char in delim_sets[delim_type] or next_char.isspace():
            return token_name, delim_type

    return None