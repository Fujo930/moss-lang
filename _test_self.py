from mosslang.parser import parse_source
from mosslang.compiler import compile_program
from mosslang.vm import VM
from pathlib import Path
from io import StringIO

f = Path('examples/self_host/project_check.moss')
source = f.read_text(encoding='utf-8-sig')
program = parse_source(source)
mod = compile_program(program, source_path=str(f.resolve()))
vm = VM(base_path=str(f.parent))
buf = StringIO()
vm.output = buf.write
vm.load_module(mod)
vm.run()
out = buf.getvalue()
for line in out.split('\n')[:20]:
    print(line)
