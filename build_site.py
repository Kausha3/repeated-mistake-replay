#!/usr/bin/env python3
"""Build the browser inspector with the Python classifier's rule table and fixtures."""
import base64
import hashlib
import html
import json
from pathlib import Path
import replay

ROOT = Path(__file__).resolve().parent
CSS = replay.CSS + '''
main{padding-top:28px}h1{font-size:clamp(32px,5vw,52px);margin:18px 0;max-width:900px}
td{overflow-wrap:anywhere}textarea{width:100%;min-height:280px;font:13px/1.5 ui-monospace,monospace;padding:16px;border:1px solid #7b8c7b;border-radius:8px;background:#fff;color:#182b29}label{display:block;font-weight:650;margin:15px 0 6px}select,input,button{font:inherit;max-width:100%}select{width:100%;padding:10px}button{padding:10px 18px;border:1px solid #476b3e;border-radius:6px;background:#e4edda;color:#182b29;cursor:pointer;margin:12px 5px 0 0}button.primary{background:#23453a;color:white}button:disabled{opacity:.5;cursor:default}#error{color:#8d2117;overflow-wrap:anywhere}#result:empty{display:none}#result{background:#fff;border:1px solid #a4b8a1;border-radius:10px;padding:24px;margin-top:22px}a:focus-visible,button:focus-visible,textarea:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #42896e;outline-offset:3px}
'''

def build():
    cases = [replay.load_case(p) for p in sorted((ROOT / 'cases').glob('*.json'))]
    data = json.dumps({'rules':replay.RULES,'cases':cases}, ensure_ascii=True).replace('<','\\u003c')
    script = 'window.REPLAY_DATA = ' + data + ';\n' + (ROOT / 'web.js').read_text()
    def digest(s):
        return base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()
    csp = f"default-src 'none'; script-src 'sha256-{digest(script)}'; style-src 'sha256-{digest(CSS)}'; connect-src 'none'; base-uri 'none'; form-action 'none'"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{html.escape(csp,quote=True)}">
<meta name="description" content="Inspect a redacted agent decision record in your browser. Check reported results, correction visibility and comparison gaps. A free tool from Hebbrix.">
<title>Agent correction record inspector | Hebbrix</title><style>{CSS}</style></head>
<body><main><div class="brand">Hebbrix / free record inspector</div>
<h1>Did the same agent mistake happen again?</h1>
<p>Inspect a redacted record of two attempts and a correction. Get a checklist of missing results, changed context and declared correction visibility before deciding what to investigate.</p>
<p><strong>Use your own JSON record below, or choose a synthetic example.</strong> This tool compares the fields you supply. It cannot determine whether an agent understood a correction or whether memory would fix the problem.</p>
<div class="note"><strong>Your record stays in this browser tab.</strong> No record is sent to Hebbrix, no model runs, and the tool stores nothing in browser storage. Loading this hosted page contacts GitHub Pages. Downloaded reports contain your input. Use only authorized, redacted data.</div>
<nav aria-label="Resources"><a href="https://github.com/Kausha3/repeated-mistake-replay#record-format">Record format and Python CLI</a><a href="#hebbrix">How Hebbrix fits</a></nav>
<label for="examples">Load an explicitly synthetic example</label><select id="examples"><option value="">Choose an example, or supply your own record</option></select>
<label for="file">Or open a local UTF-8 JSON file (100 KB limit)</label><input id="file" type="file" accept=".json,application/json">
<label for="input">Record JSON</label><textarea id="input" spellcheck="false" autocomplete="off" autocapitalize="off" aria-describedby="format-help"></textarea>
<p id="format-help" class="muted">Use named string fields for your task context. Actions are compared as exact strings, including case, spacing and parameters. Omit comparison when task equivalence is unknown. Raw vendor trace exports need mapping to the documented record format.</p>
<button id="analyze" class="primary" type="button">Inspect record</button><button id="clear" type="button">Clear record</button><button id="download" type="button" disabled>Download report with input</button>
<p id="error" role="alert"></p><section id="result" aria-live="polite" aria-label="Inspection result"></section>
<noscript><p>This browser inspector needs JavaScript. Use the dependency-free Python CLI from the source repository, or enable JavaScript.</p></noscript>
<article id="hebbrix"><h2>Where Hebbrix fits</h2>
<p>An application records a decision and attaches the result when it becomes known. <a href="https://hebbrix.com">Hebbrix</a> uses those results to guide later decisions. We call this outcome-based learning. Developers connect through Python, TypeScript or MCP. Hebbrix is in private beta.</p>
<p>This inspector is a separate, open-source evidence checklist. It does not call Hebbrix or measure product performance.</p>
<p>If you maintain a workflow where a corrected mistake repeats, <a href="https://github.com/Kausha3/repeated-mistake-replay/issues/new?template=workflow-discussion.yml">describe it to the Hebbrix founders</a>. The GitHub issue is public and requires a GitHub account. Keep logs, customer data and credentials private. A discussion does not book an appointment or establish an evaluation agreement.</p><p>For a high-level inquiry without a public issue, use <a href="https://hebbrix.com/contact">Hebbrix's contact page</a>. Keep the trace private until a suitable route is agreed.</p></article>
<footer>Examples are authored synthetic records. User-supplied records are declarations, not independently verified evidence. Read the <a href="https://github.com/Kausha3/repeated-mistake-replay">source, limitations and tests</a>. No analytics or third-party assets are included.</footer>
</main><script>{script}</script></body></html>'''

if __name__ == '__main__':
    target=ROOT/'docs'/'index.html'
    target.write_text(build(),encoding='utf-8')
    print(target)
