from pathlib import Path

# Fix tokens.py properly: TWO_CHAR_TOKENS for |>
f = Path('src/mosslang/tokens.py')
c = f.read_text(encoding='utf-8')

# Fix TWO_CHAR_TOKENS: add |>
c = c.replace('"<=": "OP",\n}', '"<=": "OP",\n    "|>": "OP",\n}')

# Remove the incorrectly placed |> from SINGLE_CHAR_TOKENS
c = c.replace('    "|>": "OP",\n', '')

f.write_text(c, encoding='utf-8')
print('Fixed TWO_CHAR_TOKENS for |>')
