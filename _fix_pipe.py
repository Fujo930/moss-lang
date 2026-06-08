from pathlib import Path

# Fix tokens.py: add |> as OP token
f = Path('src/mosslang/tokens.py')
c = f.read_text(encoding='utf-8')

# Add multi-char operator to token kind map
c = c.replace('"|": "PUNCT",', '"|": "PUNCT",\n    "|>": "OP",')

# Add two-char handling in tokenizer for |>
# Find the tokenizer section - look for the pattern of single char handlers
old = '''        if ch == "|":
            add(TOKEN_KINDS.get(ch, "PUNCT"), ch, start_line, start_col)
            i += 1'''
if old in c:
    # Replace with two-char aware version
    new = '''        if ch == "|":
            if i + 1 < len(source) and source[i + 1] == ">":
                add("OP", "|>", start_line, start_col)
                i += 2
            else:
                add("PUNCT", ch, start_line, start_col)
                i += 1'''
    c = c.replace(old, new)
    print('Added |> tokenizer handling')
else:
    print('WARNING: could not find | handler in tokenizer')
    # Show what's around
    idx = c.find('ch ==')
    if idx > 0:
        # Find relevant section
        for line in c[idx:idx+500].split('\n'):
            if '|' in line or 'ch ==' in line:
                print(' ', line)

f.write_text(c, encoding='utf-8')
print('Done fixing tokens.py')
