from pathlib import Path
c = Path('src/mosslang/vm.py').read_text(encoding='utf-8')
old = '            elif op == Opcode.LOAD_LOCAL:\n                val = frame.locals[arg]\n                if val is None and arg < len(frame.locals):\n                    raise MossRuntimeError(f"undefined local at index {arg}")\n                frame.stack.append(val)'
new = '            elif op == Opcode.LOAD_LOCAL:\n                frame.stack.append(frame.locals[arg])'
c = c.replace(old, new)
Path('src/mosslang/vm.py').write_text(c, encoding='utf-8')
print('Fixed')
