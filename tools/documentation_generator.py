
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]

def tree(path, prefix=""):
    lines=[]
    items=sorted([p for p in path.iterdir() if p.name not in {".git","__pycache__",".venv","venv"}], key=lambda p:(p.is_file(),p.name.lower()))
    for i,p in enumerate(items):
        last=i==len(items)-1
        branch="└── " if last else "├── "
        lines.append(prefix+branch+p.name)
        if p.is_dir():
            ext="    " if last else "│   "
            lines.extend(tree(p,prefix+ext))
    return lines

def discover_api():
    apis=[]
    api_dir=ROOT/'api'/'routers'
    if not api_dir.exists():
        return apis
    for f in api_dir.glob('*.py'):
        txt=f.read_text(encoding='utf-8')
        try:
            mod=ast.parse(txt)
        except:
            continue
        for node in ast.walk(mod):
            if isinstance(node,ast.FunctionDef):
                for dec in node.decorator_list:
                    if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute):
                        if dec.func.attr in ('get','post','put','delete','patch'):
                            if dec.args and isinstance(dec.args[0],ast.Constant):
                                apis.append((dec.func.attr.upper(),dec.args[0].value))
    return apis

def env_keys():
    env=ROOT/'.env.example'
    keys=[]
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if line and not line.startswith('#') and '=' in line:
                keys.append(line.split('=')[0])
    return keys

def main():
    md=[]
    md.append('# Auto Generated Project Documentation')
    md.append('')
    md.append('## Project Tree')
    md.append('```text')
    md.extend(tree(ROOT))
    md.append('```')
    md.append('')
    md.append('## API')
    md.append('|Method|Path|')
    md.append('|---|---|')
    for m,p in discover_api():
        md.append(f'|{m}|{p}|')
    md.append('')
    md.append('## Environment')
    for k in env_keys():
        md.append(f'- {k}')
    out=ROOT/'docs'
    out.mkdir(exist_ok=True)
    (out/'AUTO_GENERATED_DOCUMENTATION.md').write_text("\n".join(md),encoding='utf-8')
    print("Generated docs/AUTO_GENERATED_DOCUMENTATION.md")

if __name__=="__main__":
    main()
