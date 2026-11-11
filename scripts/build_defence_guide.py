"""Build a source-backed defence guide. Database inspection is read-only.

Run locally: python scripts/build_defence_guide.py --inspect
Run locally: python scripts/build_defence_guide.py --build
Run renderer in backend container: python build_defence_guide.py --render DIRECTORY
"""
import argparse
import ast
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TITLE = "FYPHub — Complete Technical Defence Guide"
LIVE_SCRIPT = r'''
import json, inspect as pyinspect
from sqlalchemy import inspect, text
from app.database import Base, engine
from app.main import app
from app import models
def column(c):
    return {'name': c.name, 'type': str(c.type.compile(dialect=engine.dialect)), 'nullable': c.nullable, 'primary_key': c.primary_key, 'foreign_keys': [str(f.target_fullname) for f in c.foreign_keys], 'server_default': str(c.server_default.arg) if c.server_default else None}
def deps(d, depth=0):
    if depth > 3: return []
    result=[]
    for x in d.dependencies:
        call=x.call
        name=getattr(call,'__name__',str(type(call)))
        roles=[]
        if name=='role_guard':
            roles=[getattr(r,'value',str(r)) for r in pyinspect.getclosurevars(call).nonlocals.get('roles',())]
        result.append(name + (': '+', '.join(roles) if roles else ''))
        result.extend(deps(x,depth+1))
    return list(dict.fromkeys(result))
routes=[]
def route_entries(router):
    for route in router.routes:
        if hasattr(route,'original_router'):
            yield from route_entries(route.original_router)
        else:
            yield route
for r in route_entries(app):
    if not hasattr(r,'endpoint') or not hasattr(r,'methods'): continue
    f=r.endpoint
    if not hasattr(f,'__code__'): continue
    path=pyinspect.getsourcefile(f) or ''
    if '/app/app/' in path: path='backend/app/'+path.split('/app/app/',1)[1]
    routes.append({'methods':sorted(r.methods), 'path':r.path,'function':f.__name__,'file':path,'line':f.__code__.co_firstlineno,'guards':deps(r.dependant) if hasattr(r,'dependant') else [],'description':(pyinspect.getdoc(f) or '').split('\n')[0], 'body_type':str(getattr(getattr(getattr(r,'body_field',None),'field_info',None),'annotation',None)), 'response_type':str(getattr(r,'response_model',None)), 'query_params':[{'name':p.name,'required':p.field_info.is_required()} for p in r.dependant.query_params] if hasattr(r,'dependant') else []})
model_tables=[]
for table in Base.metadata.sorted_tables:
    model_tables.append({'name':table.name,'columns':[column(c) for c in table.columns], 'constraints':[str(c.sqltext) for c in table.constraints if c.__class__.__name__=='CheckConstraint']})
with engine.connect() as conn:
    conn.execute(text('SET TRANSACTION READ ONLY'))
    i=inspect(conn)
    tables=[]
    for name in i.get_table_names(schema='public'):
        cols=[{'name':c['name'],'type':str(c['type'].compile(dialect=engine.dialect)),'nullable':c['nullable'],'default':c.get('default')} for c in i.get_columns(name,schema='public')]
        tables.append({'name':name,'columns':cols,'primary_key':i.get_pk_constraint(name,schema='public'),'foreign_keys':i.get_foreign_keys(name,schema='public'),'unique_constraints':i.get_unique_constraints(name,schema='public'),'checks':i.get_check_constraints(name,schema='public'),'indexes':i.get_indexes(name,schema='public')})
    version=conn.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    ext=conn.execute(text('SELECT extname, extversion FROM pg_extension ORDER BY extname')).mappings().all()
    database=conn.execute(text('SELECT current_database()')).scalar_one()
    conn.rollback()
print(json.dumps({'database':database,'migration_versions':version,'extensions':[dict(x) for x in ext],'tables':tables,'model_tables':model_tables,'routes':routes},default=str))
'''


def command(args):
    result = subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Command failed: {' '.join(args[:5])}\n{result.stderr[-1500:]}")
    return result.stdout


def source_index():
    files = []
    imports = {}
    frontend = ROOT / "frontend/src"
    for base in (ROOT / "backend/app", frontend, ROOT / "backend/alembic", ROOT / "backend/tests", ROOT / "frontend/tests", ROOT / "scripts", ROOT / "database", ROOT / "ai", ROOT / "modules", ROOT / "tests"):
        for p in sorted(base.rglob("*")):
            if not p.is_file() or any(x in p.parts for x in ("__pycache__", "node_modules", ".venv")) or p.suffix not in (".py", ".ts", ".tsx", ".css", ".sql", ".json", ".mjs"):
                continue
            text = p.read_text(encoding="utf-8-sig", errors="replace")
            entry = {"path":p.relative_to(ROOT).as_posix(),"lines":len(text.splitlines()),"symbols":[],"description":"","tables":[],"test_names":[],"schema_fields":{}}
            if p.suffix == ".py":
                try:
                    tree = ast.parse(text)
                    entry["description"] = (ast.get_docstring(tree) or "").split("\n")[0]
                    for node in tree.body:
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            entry["symbols"].append({"name":node.name,"line":node.lineno,"kind":type(node).__name__,"description":(ast.get_docstring(node) or "").split("\n")[0]})
                            if isinstance(node, ast.ClassDef):
                                if '/schemas/' in entry['path']:
                                    entry['schema_fields'][node.name] = [{'name': child.target.id, 'annotation': ast.unparse(child.annotation), 'validation': ast.unparse(child.value) if child.value else 'Required'} for child in node.body if isinstance(child,ast.AnnAssign) and isinstance(child.target,ast.Name)]
                                for child in node.body:
                                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                                        entry["test_names"].append(child.name)
                                    if isinstance(child, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in child.targets):
                                        entry["tables"].append(ast.literal_eval(child.value))
                        if isinstance(node, (ast.Assign, ast.AnnAssign)) and "alembic/versions" in entry["path"]:
                            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                            for target in targets:
                                if isinstance(target, ast.Name) and target.id in ("revision", "down_revision"):
                                    entry[target.id] = ast.literal_eval(node.value)
                except (SyntaxError, ValueError) as error:
                    entry["parse_error"] = str(error)
            elif p.suffix in (".tsx", ".ts", ".mjs"):
                text = re.sub(r"/\*[\s\S]*?\*/", lambda match: "\n" * match.group(0).count("\n"), text)
                text = re.sub(r"^\s*//[^\n]*", "", text, flags=re.MULTILINE)
                entry["symbols"] = [{"name":m.group(1),"line":text[:m.start()].count("\n")+1,"kind":"export","description":""} for m in re.finditer(r"export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class)\s+(\w+)",text)]
                entry["api_references"] = sorted(set(re.findall(r"/api/v1/[A-Za-z0-9_{}$?./:-]+",text)))
                entry["imports"] = re.findall(r"(?:from\s*|import\s*)[\"']([^\"']+)[\"']",text)
                if p.is_relative_to(frontend):
                    resolved=[]
                    for imp in entry["imports"]:
                        if not imp.startswith("."): continue
                        candidate=p.parent/imp
                        for item in [candidate, *[Path(str(candidate)+s) for s in (".tsx", ".ts", ".css")], candidate/"index.tsx", candidate/"index.ts"]:
                            if item.is_file():
                                resolved.append(item.resolve().relative_to(ROOT).as_posix()); break
                    imports[entry["path"]]=resolved
            files.append(entry)
    reachable=set()
    pending=["frontend/src/main.tsx"]
    while pending:
        p=pending.pop()
        if p in reachable: continue
        reachable.add(p); pending.extend(imports.get(p,[]))
    for item in files:
        if item["path"].startswith("frontend/src/"): item["reachable_from_entry"] = item["path"] in reachable
    for path, description in {
        'docker-compose.yml':'Service topology, initialization jobs, ports, volumes, networks and health checks.',
        'backend/Dockerfile':'Python runtime image, dependency installation and Uvicorn launch command.',
        'frontend/Dockerfile':'Frontend build stage and Nginx static runtime image.',
        'frontend/nginx.conf':'SPA fallback and reverse proxy routes for API and health endpoints.',
        'frontend/vite.config.ts':'Vite React/Tailwind plugins, development host/port and API proxy.',
        'frontend/package.json':'Frontend dependency declarations and dev/build/lint commands.',
        'frontend/package-lock.json':'Exact resolved npm dependency graph for reproducible installs.',
        'frontend/tsconfig.json':'TypeScript project-reference configuration.',
        'frontend/tsconfig.app.json':'Browser TypeScript compiler rules.',
        'frontend/tsconfig.node.json':'Node/toolchain TypeScript compiler rules.',
        'frontend/eslint.config.js':'Lint rules and React hooks checks.',
        'backend/requirements.txt':'Pinned Python runtime dependency versions.',
        'backend/alembic.ini':'Migration tool configuration; environment builds the effective connection.',
        'frontend/index.html':'HTML shell containing the React root and module entry script.',
        '.gitignore':'Excludes environment files, dependencies, caches and runtime uploads from Git.',
        '.env.example':'Environment-variable template; real private values are intentionally not inspected or exported.',
    }.items():
        p=ROOT/path
        if p.is_file():
            files.append({'path':path,'lines':len(p.read_text(encoding='utf-8-sig').splitlines()),'description':description,'symbols':[],'tables':[],'test_names':[]})
    return files


def snapshot():
    raw=command(["docker","exec","fyphub-p1-backend-1","python","-c",LIVE_SCRIPT])
    live=json.loads(raw[raw.index('{'):])
    live["files"]=source_index()
    live["git_commit"]=command(["git","rev-parse","HEAD"]).strip()
    live["git_status"]=command(["git","status","--short"])
    live["migration_heads"]=command(["docker","exec","fyphub-p1-backend-1","alembic","heads"]).strip().splitlines()
    live["services"]=command(["docker","compose","ps","-a"])
    live["inspection_date"]="2026-11-11 (Asia/Karachi)"
    out=ROOT/"docs/defence"
    out.mkdir(parents=True,exist_ok=True)
    (out/"technical-inventory.json").write_text(json.dumps(live,indent=2,ensure_ascii=False),encoding="utf-8")
    return live


def cell(value):
    return str(value).replace("|","/").replace("\n"," ")


def build(live):
    parts=[(ROOT/"docs/FYPHub_Defence_Guide_Source.md").read_text(encoding="utf-8")]
    add=parts.append
    add("\n# Appendix A — Inspection evidence and counts\n")
    add(f"Inspection: {live['inspection_date']}. Git snapshot: `{live['git_commit']}`. The guide describes source and the running database as inspected, not a claim that every feature was tested during this documentation task.\n")
    add(f"Inspected source/configuration files in the generated inventory: {len(live['files'])}. Live public tables: {len(live['tables'])}. ORM tables: {len(live['model_tables'])}. Registered application route entries: {len(live['routes'])}. Multiple methods/aliases can share one handler.\n")
    add("Database migration version(s): " + ", ".join(f"`{v}`" for v in live["migration_versions"]) + ".\n")
    add("Migration repository heads: " + ", ".join(f"`{v}`" for v in live["migration_heads"]) + ".\n")
    add("Extensions: " + ", ".join(f"{x['extname']} {x['extversion']}" for x in live['extensions']) + ".\n")
    model_names={x['name'] for x in live['model_tables']}; live_names={x['name'] for x in live['tables']}
    add("Tables present in database but absent from current ORM metadata: " + (", ".join(sorted(live_names-model_names)) or "None") + ". Historical/retired tables are not proof of active features.\n")
    add("ORM tables absent from the live database: " + (", ".join(sorted(model_names-live_names)) or "None") + ".\n")
    add("\n# Appendix B — Complete feature database dictionary\n")
    add("This is generated from the running PostgreSQL catalog. No user rows, passwords, tokens, uploaded content or secrets are included. Locate the model file beside each table; the model declares the intended structure, while the catalog describes the actual installed database.\n")
    for table in sorted(live['tables'],key=lambda item:item['name']):
        add(f"\n## Table: {table['name']}\n")
        models=[f for f in live['files'] if table['name'] in f.get('tables',[])]
        add("Model source: " + (", ".join(f"`{f['path']}`" for f in models) or "No current ORM class; migration/legacy infrastructure table") + ".\n")
        pk=table['primary_key'].get('constrained_columns',[])
        add("Primary key: " + (", ".join(pk) or "None reported") + ".\n")
        model = next((m for m in live['model_tables'] if m['name']==table['name']), None)
        if model:
            model_cols={c['name'] for c in model['columns']}; catalog_cols={c['name'] for c in table['columns']}
            if model_cols != catalog_cols:
                add(f"Column-name drift: model-only {sorted(model_cols-catalog_cols)}; database-only {sorted(catalog_cols-model_cols)}.\n")
        add("| Column | PostgreSQL type | Nullable | Default |\n|---|---|---|---|\n")
        for c in table['columns']: add(f"| {c['name']} | {cell(c['type'])} | {'Yes' if c['nullable'] else 'No'} | {cell(c.get('default') or '—')} |\n")
        for fk in table['foreign_keys']:
            add(f"- Foreign key `{', '.join(fk['constrained_columns'])}` → `{fk['referred_table']}({', '.join(fk['referred_columns'])})`; options: `{cell(fk.get('options',{}))}`.\n")
        for c in table['unique_constraints']: add(f"- Unique constraint `{c.get('name')}`: `{', '.join(c.get('column_names',[]))}`.\n")
        for c in table['checks']: add(f"- Check `{c.get('name')}`: `{cell(c['sqltext'])}`.\n")
        for i in table['indexes']:
            add(f"- Index `{i.get('name')}`; unique={i.get('unique')}; columns/expressions `{cell(i.get('column_names') or i.get('expressions'))}`; options `{cell(i.get('dialect_options',{}))}`.\n")
    add("\n# Appendix C — Complete registered backend API map\n")
    add("Routes come from the running FastAPI application. Guards show dependency-based checks; ownership, state and transaction checks also occur inside handlers and helpers. A route with no listed guard may be public or perform authorization internally. Use the source reference to explain it. Browser page URLs and these API URLs are different layers.\n")
    for file in sorted({r['file'] for r in live['routes']}):
        add(f"\n## {file}\n\n| Method | API path | Handler / line | Dependency guards |\n|---|---|---|---|\n")
        for r in live['routes']:
            if r['file'] != file: continue
            add(f"| {', '.join(r['methods'])} | `{r['path']}` | `{r['function']}` line {r['line']} | {cell('; '.join(r['guards']) or 'See handler')} |\n")
        for r in live['routes']:
            if r['file'] != file: continue
            add(f"- `{','.join(r['methods'])} {r['path']}`: body `{cell(r['body_type'])}`; response `{cell(r['response_type'])}`; query parameters `{cell(r['query_params'])}`. {r['description']}\n")
    add("\n# Appendix D — Complete source-file navigation atlas\n")
    add("Every discovered application, migration, test and script source file is listed below. Line numbers refer to this snapshot. Frontend reachability means an import path exists from main.tsx; a reachable module may still have conditional or inaccessible branches. A file not reachable through static relative imports is an alternative/helper candidate, not automatically safe to delete.\n")
    for f in live['files']:
        add(f"\n## {f['path']}\n")
        add(f"Lines: {f['lines']}. "+f.get('description','')+"\n")
        if 'reachable_from_entry' in f: add("Frontend entry import graph: " + ("reachable" if f['reachable_from_entry'] else "not reached by static imports") + ".\n")
        if f.get('imports'): add("Imports: " + ", ".join(f"`{i}`" for i in f['imports']) + ".\n")
        if f.get('tables'): add("Tables declared: " + ", ".join(f['tables']) + ".\n")
        if f.get('api_references'): add("API references found in source (dynamic expressions may be partial): " + ", ".join(f"`{i}`" for i in f['api_references']) + ".\n")
        if f.get('symbols'):
            add("| Symbol | Line | Purpose / source docstring |\n|---|---|---|\n")
            for s in f['symbols']: add(f"| `{s['name']}` | {s['line']} | {cell(s['description'] or 'Implementation entry; inspect this symbol for details')} |\n")
        if f.get('test_names'): add("Test cases: " + ", ".join(f"`{n}`" for n in f['test_names']) + ".\n")
        for name, fields in f.get('schema_fields',{}).items():
            if not fields: continue
            add(f"\n### API contract: {name}\n\n| Field | Type | Default / validation declaration |\n|---|---|---|\n")
            for field in fields: add(f"| `{field['name']}` | `{cell(field['annotation'])}` | `{cell(field['validation'])}` |\n")
    add("\n# Appendix E — Migration revision graph\n\n| Revision | Parent(s) | File |\n|---|---|---|\n")
    for f in live['files']:
        if 'revision' in f: add(f"| `{f['revision']}` | `{cell(f.get('down_revision'))}` | `{f['path']}` |\n")
    add("\n# Appendix F — Reproducibility and evidence files\n")
    add("The machine-readable companion `technical-inventory.json` contains the full inspected schema, ORM metadata, endpoint ownership, source symbols, frontend imports and test names. `scripts/build_defence_guide.py` rebuilds it using read-only database catalog queries. `FYPHub_Defence_Guide_Source.md` is the authored explanatory part. Generated documents are snapshots and should be regenerated after code/schema changes.\n")
    out=ROOT/"docs/defence"
    md=out/"FYPHub_Complete_Defence_Guide.md"
    md.write_text("".join(parts),encoding="utf-8")
    return md


def render(directory):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle, PageBreak
    from xml.sax.saxutils import escape
    directory=Path(directory)
    md=(directory/"FYPHub_Complete_Defence_Guide.md").read_text(encoding="utf-8")
    doc=Document(); section=doc.sections[0]
    section.header.paragraphs[0].text="FYPHub | Technical Defence Preparation | 11 November 2026"
    section.top_margin=Inches(.7); section.bottom_margin=Inches(.7)
    normal=doc.styles['Normal']; normal.font.name='Calibri'; normal.font.size=Pt(10)
    for n in ['Title','Heading 1','Heading 2','Heading 3']:
        doc.styles[n].font.color.rgb=RGBColor.from_string('124BC4')
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='GuideBody',fontName='Helvetica',fontSize=8,leading=11,spaceAfter=5,wordWrap='CJK'))
    styles.add(ParagraphStyle(name='GuideCell',fontName='Helvetica',fontSize=6,leading=8,wordWrap='CJK'))
    for n in ('Heading1','Heading2','Heading3'): styles[n].textColor=colors.HexColor('#124BC4')
    story=[]; in_code=False; code=[]; table_lines=[]
    def clean(s): return re.sub(r'[`*]', '', s)
    def para(s, style='GuideBody'):
        plain=clean(s).translate(str.maketrans({'→':' -> ', '—':' - ', '–':'-', '’':"'", '‘':"'", '“':'"', '”':'"', '•':'-'}))
        return Paragraph(escape(plain).replace('\n','<br/>'),styles[style])
    def flush_table():
        if not table_lines: return
        rows=[[clean(v.strip()) for v in line.strip().strip('|').split('|')] for line in table_lines if not re.fullmatch(r'[| :\-]+',line)]
        table_lines.clear()
        if not rows: return
        count=max(map(len,rows)); rows=[row+['']*(count-len(row)) for row in rows]
        word_table=doc.add_table(rows=1, cols=count); word_table.style='Light Shading Accent 1'
        word_table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
        for idx,v in enumerate(rows[0]): word_table.rows[0].cells[idx].text=v
        for row in rows[1:]:
            cells=word_table.add_row().cells
            for idx,v in enumerate(row): cells[idx].text=v
        pdf_rows=[[para(v,'GuideCell') for v in row] for row in rows]
        width=A4[0]-72
        table=Table(pdf_rows,colWidths=[width/count]*count,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf2ff')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#d9e2ef')),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
        story.extend([table,Spacer(1,8)])
    for line in md.splitlines():
        if line.startswith('```'):
            flush_table()
            if in_code:
                text='\n'.join(code); p=doc.add_paragraph(text); p.style='No Spacing'
                for run in p.runs: run.font.name='Consolas'; run.font.size=Pt(8)
                # Wrap long source paths/commands to fit the printable page.
                import textwrap
                wrapped='\n'.join('\n'.join(textwrap.wrap(l,95,replace_whitespace=False,drop_whitespace=False)) or ' ' for l in code)
                story.append(Preformatted(wrapped,styles['Code'])); code=[]
            in_code=not in_code; continue
        if in_code: code.append(line); continue
        if line.startswith('|'): table_lines.append(line); continue
        flush_table()
        if not line.strip(): continue
        if line.startswith('#'):
            level=len(line)-len(line.lstrip('#')); text=line[level:].strip()
            if level==1:
                if text.startswith('Appendix'): story.append(PageBreak()); doc.add_page_break()
                doc.add_heading(clean(text),0 if text.startswith('FYPHub') else 1)
                story.append(para(text,'Title' if text.startswith('FYPHub') else 'Heading1'))
            else: doc.add_heading(clean(text),min(level,3)); story.append(para(text,'Heading2' if level==2 else 'Heading3'))
        else:
            bullet=line.startswith('- '); numbered=bool(re.match(r'^\d+\. ',line))
            text=line[2:] if bullet else re.sub(r'^\d+\. ','',line) if numbered else line
            doc.add_paragraph(clean(text),style='List Bullet' if bullet else 'List Number' if numbered else None)
            prefix='• ' if bullet else re.match(r'^\d+\. ',line).group(0) if numbered else ''
            story.append(para(prefix+text))
    flush_table()
    footer=section.footer.paragraphs[0]; footer.text="FYPHub | Source-backed defence guide | Page "
    from docx.oxml.ns import qn
    page_field=OxmlElement('w:fldSimple'); page_field.set(qn('w:instr'),'PAGE'); footer._p.append(page_field)
    doc.save(directory/'FYPHub_Complete_Defence_Guide.docx')
    def page_number(canvas, document):
        canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(36,20,'FYPHub — Technical Defence Guide'); canvas.drawRightString(A4[0]-36,20,str(document.page))
    class GuideTemplate(SimpleDocTemplate):
        outline_number=0
        def afterFlowable(self, flowable):
            if not isinstance(flowable,Paragraph): return
            levels={'Title':0,'Heading1':0,'Heading2':1,'Heading3':2}
            level=levels.get(flowable.style.name)
            if level is None: return
            self.outline_number+=1
            key=f'heading-{self.outline_number}'
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(),key,level=level,closed=True)
    GuideTemplate(str(directory/'FYPHub_Complete_Defence_Guide.pdf'),pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36,title=TITLE,author='FYPHub Technical Documentation').build(story,onFirstPage=page_number,onLaterPages=page_number)
    print('Rendered DOCX and PDF successfully.')


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--inspect',action='store_true'); parser.add_argument('--build',action='store_true'); parser.add_argument('--render')
    args=parser.parse_args()
    if args.render: render(args.render); return
    live=snapshot()
    print(json.dumps({'files':len(live['files']),'tables':len(live['tables']),'routes':len(live['routes']),'heads':live['migration_heads'],'current':live['migration_versions']},indent=2))
    if args.build: print(build(live))


if __name__=='__main__': main()
