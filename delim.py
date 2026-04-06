# === Character ===
lowc = set('abcdefghijklmnopqrstuvwxyz')
upc = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
letters = lowc.union(upc)
zero = {'0'}
num = set('123456789')
dig = zero.union(num)
letdig = letters.union(dig)

# Operator definitions - split into single and multi-char
# Single character operators (for delimiter sets)
single_char_operators = {'+', '-', '*', '/', '%', '^', '!', '>', '<', '=', '&', '|'}

# Multi-character operators (for token recognition with lookahead)
multi_char_operators = {'&&', '||', '>=', '<=', '==', '!=', '+=', '-=', '*=', '/=', '//=', '%=', '^='}

# For backward compatibility, you can still have the full operator sets
arithop = {'+', '-', '*', '/', '%', '^'}
logop = {'&&', '||', '!'}  # These are multi-char except '!'
releqop = {'>', '<', '>=', '<=', '==', '!='}  # Mix of single and multi-char
compop = {'+=', '-=', '*=', '/=', '//=', '%=', '^='}  # All multi-char

# Full operator sets (if needed elsewhere in your code)
operator = arithop.union(compop).union(logop).union(releqop)

# Single character sets for delimiter checking
operator_chars = single_char_operators  # Use this instead of the old operator_chars
whiteEme_chars = {' ', '\n', '\t'}

# === delimiter sets === (ONLY SINGLE CHARACTERS - use single_char_operators)
whiteEme = set(whiteEme_chars)
funcEme = whiteEme.union({'('})
blockEme = whiteEme.union({'{'})
defEme = whiteEme.union({':'})
overEme = whiteEme.union({';'})
colonEme = whiteEme.union(letdig).union({'{'})
incurlbraEme = whiteEme.union({'"', "'", '-', '+', '}', '{',':'}).union(letdig)
sqrbraEme = whiteEme.union(upc).union(dig)
opEme = funcEme.union(letdig).union({'+', '-', '!', "'"})
divEme = funcEme.union(letters).union(num).union({'+', '-', '!', "'"})
cloEme = funcEme.union({";"})
comEme = opEme.union({'"', "'", '{' , '}'}).union(funcEme)
termEme = opEme.union({'}', '+', '-',':'}).union(letters).union(funcEme)
relogEme = funcEme.union(letdig).union({'+', '-', '!', "'",'{'})
inparEme = comEme.union({'+', '-', '!', ')'})
clcurlEme = overEme.union(letters).union({'}', '+', '-', ':', ','})
# Use single_char_operators instead of operator for delimiter sets
clbraEme = overEme.union({'=', ')', ',','['}).union(single_char_operators)
clparEme = overEme.union({'{', ')', ','}).union(single_char_operators)

#Added for unaEme 
una_operators = single_char_operators - {'+', '-'}
unaEme = funcEme.union(upc).union(una_operators).union({';', ')', ','})
#unaEme = funcEme.union(upc).union(single_char_operators).union({';', ')',','})
eqEme = relogEme.union({'"', '{'})
idEme = overEme.union({'=', '(', ')', '[', ']', ',', '+'}).union(single_char_operators)
strEme = overEme.union({')', '}', ','})
charEme = strEme.union({':'}).union(arithop).union(releqop).union(logop)
floatEme = overEme.union(arithop).union(logop).union(releqop).union({')', '}', ','})
intEme = floatEme.union({':', ']'})
boolEme = overEme.union({',', '}', '=', ')'}).union(arithop).union(logop).union(releqop)
singcmtEme = {'\n'}

delim_sets = {
    "incurlbraEme": incurlbraEme,
    "sqrbraEme": sqrbraEme,  
    "clcurlEme": clcurlEme,
    "clbraEme": clbraEme,
    "inparEme": inparEme,
    "clparEme": clparEme,
    "comEme": comEme,
    "colonEme": colonEme,
    "termEme": termEme,
    "opEme": opEme,
    "divEme": divEme,
    "relogEme": relogEme,
    "unaEme": unaEme,
    "eqEme": eqEme,
    "idEme": idEme,
    "strEme": strEme,
    "charEme": charEme,
    "floatEme": floatEme,
    "intEme": intEme,
    "boolEme": boolEme,
    "whiteEme": whiteEme,
    "singcmtEme": singcmtEme
}