from delim import *

# MOVE final_states to MODULE LEVEL (outside the function)
final_states = {
    5: ("heart", "whiteEme"), 9: ("hope", "funcEme"), 15: ("brain", "funcEme"),
    19: ("bool", "whiteEme"), 25: ("betray", "boolEme"), 29: ("int", "whiteEme"),
    35: ("float", "whiteEme"), 40: ("fixed", "whiteEme"), 44: ("str", "whiteEme"),
    49: ("spill", "funcEme"), 54: ("char", "whiteEme"), 61: ("closure", "cloEme"),
    65: ("core", "funcEme"), 70: ("read", "funcEme"), 73: ("do", "blockEme"),
    76: ("down", "overEme"), 84: ("default", "defEme"), 89: ("despair", "blockEme"),
    93: ("desire", "funcEme"), 98: ("echo", "whiteEme"), 105: ("memory", "whiteEme"),
    111: ("while", "funcEme"), 116: ("over", "overEme"), 121: ("void", "whiteEme"),
    127: ("trust", "boolEme")
}

def identify_reserved_word(word, next_char=None):
    state = 0

    if not word.islower():
        return None

    for char in word:
        # === Initial character transitions ===
        if state == 0:
            if char == 'h': state = 1
            elif char == 'b': state = 11
            elif char == 'i': state = 27
            elif char == 'f': state = 31
            elif char == 's': state = 42
            elif char == 'c': state = 51
            elif char == 'r': state = 67
            elif char == 'd': state = 72
            elif char == 'e': state = 95
            elif char == 'm': state = 100
            elif char == 'w': state = 107
            elif char == 'o': state = 113
            elif char == 'v': state = 118
            elif char == 't': state = 123
            else:
                return None

        # === DFA transitions ===
        # heart
        elif state == 1 and char == 'e': state = 2
        elif state == 2 and char == 'a': state = 3
        elif state == 3 and char == 'r': state = 4
        elif state == 4 and char == 't': state = 5

        # hope
        elif state == 1 and char == 'o': state = 7
        elif state == 7 and char == 'p': state = 8
        elif state == 8 and char == 'e': state = 9

        # brain
        elif state == 11 and char == 'r': state = 12
        elif state == 12 and char == 'a': state = 13
        elif state == 13 and char == 'i': state = 14
        elif state == 14 and char == 'n': state = 15

        # bool
        elif state == 11 and char == 'o': state = 17
        elif state == 17 and char == 'o': state = 18
        elif state == 18 and char == 'l': state = 19

        # betray
        elif state == 11 and char == 'e': state = 21
        elif state == 21 and char == 't': state = 22
        elif state == 22 and char == 'r': state = 23
        elif state == 23 and char == 'a': state = 24
        elif state == 24 and char == 'y': state = 25

        # int
        elif state == 27 and char == 'n': state = 28
        elif state == 28 and char == 't': state = 29

        # float
        elif state == 31 and char == 'l': state = 32
        elif state == 32 and char == 'o': state = 33
        elif state == 33 and char == 'a': state = 34
        elif state == 34 and char == 't': state = 35

        # fixed
        elif state == 31 and char == 'i': state = 37
        elif state == 37 and char == 'x': state = 38
        elif state == 38 and char == 'e': state = 39
        elif state == 39 and char == 'd': state = 40

        # str
        elif state == 42 and char == 't': state = 43
        elif state == 43 and char == 'r': state = 44

        # spill
        elif state == 42 and char == 'p': state = 46
        elif state == 46 and char == 'i': state = 47
        elif state == 47 and char == 'l': state = 48
        elif state == 48 and char == 'l': state = 49

        # char
        elif state == 51 and char == 'h': state = 52
        elif state == 52 and char == 'a': state = 53
        elif state == 53 and char == 'r': state = 54

        # closure
        elif state == 51 and char == 'l': state = 56
        elif state == 56 and char == 'o': state = 57
        elif state == 57 and char == 's': state = 58
        elif state == 58 and char == 'u': state = 59
        elif state == 59 and char == 'r': state = 60
        elif state == 60 and char == 'e': state = 61

        # core
        elif state == 51 and char == 'o': state = 63
        elif state == 63 and char == 'r': state = 64
        elif state == 64 and char == 'e': state = 65

        # read
        elif state == 67 and char == 'e': state = 68
        elif state == 68 and char == 'a': state = 69
        elif state == 69 and char == 'd': state = 70

        # do
        elif state == 72 and char == 'o': state = 73

        # down
        elif state == 73 and char == 'w': state = 75
        elif state == 75 and char == 'n': state = 76

        # default
        elif state == 72 and char == 'e': state = 78
        elif state == 78 and char == 'f': state = 79
        elif state == 79 and char == 'a': state = 81
        elif state == 81 and char == 'u': state = 82
        elif state == 82 and char == 'l': state = 83
        elif state == 83 and char == 't': state = 84

        # despair
        elif state == 78 and char == 's': state = 85
        elif state == 85 and char == 'p': state = 86
        elif state == 86 and char == 'a': state = 87
        elif state == 87 and char == 'i': state = 88
        elif state == 88 and char == 'r': state = 89

        # desire
        elif state == 85 and char == 'i': state = 91
        elif state == 91 and char == 'r': state = 92
        elif state == 92 and char == 'e': state = 93

        # echo
        elif state == 95 and char == 'c': state = 96
        elif state == 96 and char == 'h': state = 97
        elif state == 97 and char == 'o': state = 98

        # memory
        elif state == 100 and char == 'e': state = 101
        elif state == 101 and char == 'm': state = 102
        elif state == 102 and char == 'o': state = 103
        elif state == 103 and char == 'r': state = 104
        elif state == 104 and char == 'y': state = 105

        # while
        elif state == 107 and char == 'h': state = 108
        elif state == 108 and char == 'i': state = 109
        elif state == 109 and char == 'l': state = 110
        elif state == 110 and char == 'e': state = 111

        # over
        elif state == 113 and char == 'v': state = 114
        elif state == 114 and char == 'e': state = 115
        elif state == 115 and char == 'r': state = 116

        # void
        elif state == 118 and char == 'o': state = 119
        elif state == 119 and char == 'i': state = 120
        elif state == 120 and char == 'd': state = 121

        # trust
        elif state == 123 and char == 'r': state = 124
        elif state == 124 and char == 'u': state = 125
        elif state == 125 and char == 's': state = 126
        elif state == 126 and char == 't': state = 127

        else:
            return None

    # Create delim_sets locally
    delim_sets = {
        "whiteEme": whiteEme, "funcEme": funcEme, "boolEme": boolEme,
        "blockEme": blockEme, "defEme": defEme, "overEme": overEme, "cloEme": cloEme
    }

    if state in final_states and next_char is not None:
        keyword, delim_type = final_states[state]
        valid_delims = delim_sets[delim_type]
        
        # FIX: Handle multi-character delimiter sets for reserved words
        def is_valid_delimiter(char, delim_set):
            if char is None:
                return True
            if char in delim_set:
                return True
            # Check if char could be start of any multi-character delimiter
            for item in delim_set:
                if len(item) > 1 and item.startswith(char):
                    return True
            return char.isspace()

        if is_valid_delimiter(next_char, valid_delims):
            return keyword 

    return None