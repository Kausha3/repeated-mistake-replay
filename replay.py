#!/usr/bin/env python3
"""Inspect an explicit attempt history locally. No model, network, or Hebbrix API calls."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path
import sys

CONTEXT_KEYS = ("workflow", "environment", "task_family", "condition")
STATUS = {"failure", "success", "unknown"}
MAX_INPUT_BYTES = 100_000
ROOT = Path(__file__).resolve().parent

class CaseError(ValueError):
    pass

def text_value(value, location):
    if not isinstance(value, str) or not value.strip() or len(value) > 12_000:
        raise CaseError(f"{location} must be a nonempty string of at most 12000 characters")
    return value

def validate_case(case):
    if not isinstance(case, dict) or case.get("schema_version") != 1:
        raise CaseError("Expected a case object with schema_version 1")
    for name in ("id", "title"):
        text_value(case.get(name), name)
    if case.get("provenance") not in {"synthetic", "user_supplied"}:
        raise CaseError("provenance must be synthetic or user_supplied")
    for name in ("initial", "later"):
        attempt = case.get(name)
        if not isinstance(attempt, dict):
            raise CaseError(f"{name} must be an object")
        for key in ("decision_id", "action"):
            text_value(attempt.get(key), f"{name}.{key}")
        context = attempt.get("context")
        if not isinstance(context, dict) or set(context) != set(CONTEXT_KEYS):
            raise CaseError(f"{name}.context must contain exactly {', '.join(CONTEXT_KEYS)}")
        for key in CONTEXT_KEYS:
            text_value(context[key], f"{name}.context.{key}")
        outcome = attempt.get("outcome")
        if not isinstance(outcome, dict) or outcome.get("status") not in STATUS:
            raise CaseError(f"{name}.outcome.status must be failure, success, or unknown")
        text_value(outcome.get("evidence"), f"{name}.outcome.evidence")
    if case["initial"]["decision_id"] == case["later"]["decision_id"]:
        raise CaseError("The initial and later decisions must have distinct IDs")
    correction = case.get("correction")
    if not isinstance(correction, dict):
        raise CaseError("correction must be an object")
    if correction.get("after_decision_id") != case["initial"]["decision_id"]:
        raise CaseError("Correction must refer to the initial decision ID")
    for key in ("content", "intended_action"):
        text_value(correction.get(key), f"correction.{key}")
    if correction.get("visible_to_later") is not None and type(correction.get("visible_to_later")) is not bool:
        raise CaseError("correction.visible_to_later must be true, false, or null")
    if "visible_to_later" not in correction:
        raise CaseError("Declare correction.visible_to_later explicitly, using null when unknown")
    guard = case.get("guard")
    if guard is not None:
        if not isinstance(guard, dict):
            raise CaseError("guard must be an object")
        allowed = guard.get("allowed_actions")
        if not isinstance(allowed, list) or not 1 <= len(allowed) <= 20:
            raise CaseError("guard.allowed_actions must have 1 to 20 explicit actions")
        for item in allowed:
            text_value(item, "guard.allowed_actions entry")
        text_value(guard.get("basis"), "guard.basis")
    return case

def load_case(path):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise CaseError("Input exceeds the 100 KB local case limit")
    try:
        parsed = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CaseError(f"Input is not valid UTF-8 JSON: {error}") from error
    return validate_case(parsed)

def diagnose(case):
    validate_case(case)
    first, later, correction = case["initial"], case["later"], case["correction"]
    differences = [key for key in CONTEXT_KEYS if first["context"][key] != later["context"][key]]
    same_action = first["action"] == later["action"]
    first_failure = first["outcome"]["status"] == "failure"
    later_failure = later["outcome"]["status"] == "failure"
    visible = correction["visible_to_later"]
    if differences:
        code = "context_changed"
        conclusion = "These attempts are not comparable under the declared context."
        next_check = "Review whether the old correction applies. Repeating an action in a different task can be appropriate."
    elif not first_failure or later["outcome"]["status"] == "unknown":
        code = "insufficient_outcome_evidence"
        conclusion = "The recorded outcomes do not establish a repeated failure."
        next_check = "Collect the missing independently observed result. Missing feedback is not failure."
    elif not same_action:
        code = "different_action"
        conclusion = "The later attempt used a different action."
        next_check = "Investigate its result separately. This is not an exact repetition of the first action."
    elif not later_failure:
        code = "repeat_without_repeat_failure"
        conclusion = "The action repeated, but the recorded failure did not."
        next_check = "Check whether the first failure was transient before banning the action."
    elif visible is False:
        code = "correction_unavailable"
        conclusion = "The same failed action repeated while the correction was declared unavailable."
        next_check = "Inspect how the correction is scoped, retrieved, and included in the later decision."
    elif visible is True:
        code = "correction_available"
        conclusion = "The same failed action repeated despite declared correction visibility."
        next_check = "Inspect adherence and execution constraints. Better retrieval alone may not solve this."
    else:
        code = "visibility_unknown"
        conclusion = "A repeated failure is recorded, but correction visibility is unknown."
        next_check = "Capture the evidence actually supplied to the later decision."
    guard = case.get("guard")
    guard_report = {"available": guard is not None}
    if guard:
        guard_report.update({
            "observed_action_allowed": later["action"] in guard["allowed_actions"],
            "correction_action_allowed": correction["intended_action"] in guard["allowed_actions"],
            "allowed_actions": guard["allowed_actions"],
            "basis": guard["basis"],
            "limit": "This checks a declared allowlist. It does not execute an agent, choose a repair, or prove task success.",
        })
    else:
        guard_report["limit"] = "No explicit precondition was supplied. No guard result is inferred."
    return {
        "id": case["id"], "title": case["title"], "provenance": case["provenance"],
        "diagnosis": code, "conclusion": conclusion, "next_check": next_check,
        "scope_differences": differences, "same_action": same_action,
        "observed_repeat_failure": not differences and first_failure and later_failure and same_action,
        "written_correction_control": {
            "intended_action": correction["intended_action"],
            "visible_in_recorded_later_attempt": visible,
            "limit": "The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured.",
        },
        "deterministic_check_control": guard_report,
        "claim_boundary": "This is evidence bookkeeping, not a Hebbrix evaluation or a comparison of model or product performance.",
        "case": case,
    }

def markdown_report(reports):
    lines = ["# Repeated mistake replay", "",
             "Local inspection only. The bundled cases are synthetic authored traces.",
             "No model, Hebbrix API, network, or external tools were called.", ""]
    for report in reports:
        case = report["case"]
        guard = report["deterministic_check_control"]
        lines.extend([f"## {report['title']}", "", f"Provenance: {report['provenance']}.",
            f"Diagnosis: {report['diagnosis']}.", "", report["conclusion"], "",
            "Next check: " + report["next_check"], "",
            f"Recorded actions: {case['initial']['action']} -> {case['later']['action']}.",
            "Written correction control: intended action is " + case["correction"]["intended_action"] + ".",
            report["written_correction_control"]["limit"], ""])
        if guard["available"]:
            lines.extend(["Deterministic check control: the later action is " +
                ("allowed" if guard["observed_action_allowed"] else "rejected") + " by the declared precondition.",
                "Basis: " + guard["basis"], guard["limit"], ""])
        else:
            lines.extend([guard["limit"], ""])
        lines.extend([report["claim_boundary"], ""])
    return "\n".join(lines) + "\n"

CSS = """
:root{color-scheme:light;--ink:#182b29;--muted:#50615e;--line:#dce5dc;--paper:#f4f5ed;--green:#dcebd0}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 system-ui,sans-serif}
main{max-width:1040px;margin:auto;padding:50px 28px 75px}.brand{font-size:14px;letter-spacing:.12em;text-transform:uppercase}
h1{font-size:clamp(36px,6vw,65px);line-height:1.05;max-width:800px;margin:24px 0}h2{font-size:28px;line-height:1.2}
p{max-width:76ch}.note{border-left:4px solid #476b3e;background:#e8eddf;padding:15px 20px}.muted{color:var(--muted)}
nav{display:flex;gap:8px;flex-wrap:wrap;margin:28px 0}a{color:inherit;text-underline-offset:4px}nav a{padding:8px 12px;border:1px solid var(--line);border-radius:6px;text-decoration:none;background:white}
article{background:#fff;border:1px solid var(--line);border-radius:12px;padding:26px;margin:24px 0}
.tag{font:12px/1.5 ui-monospace,monospace;padding:5px 9px;border-radius:4px;background:var(--green);display:inline-block}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.control{background:#f5f6f2;border:1px solid var(--line);padding:18px;border-radius:6px}
h3{font-size:17px;margin:0 0 8px}.control p{font-size:15px;margin:8px 0}code{background:#edf1e8;padding:2px 5px;overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;font-size:15px;margin:20px 0}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid var(--line)}th{width:22%}
details{margin-top:20px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f6f2;padding:18px;font:13px/1.5 ui-monospace,monospace}
footer{margin-top:35px;font-size:14px;color:var(--muted)}@media(max-width:700px){.grid{grid-template-columns:1fr}main{padding:30px 18px}article{padding:18px}th{width:28%}}
"""

def html_report(reports):
    esc = lambda value: html.escape(str(value), quote=True)
    sections = []
    for index, report in enumerate(reports):
        case = report["case"]
        guard = report["deterministic_check_control"]
        guard_text = ("The declared guard " + ("allows" if guard["observed_action_allowed"] else "rejects") +
            " the observed later action.") if guard["available"] else "No guard was supplied."
        guard_basis = "<p>" + esc(guard["basis"]) + "</p>" if guard["available"] else ""
        rows = []
        for label, a, b in [
            ("Decision",case["initial"]["decision_id"],case["later"]["decision_id"]),
            ("Action",case["initial"]["action"],case["later"]["action"]),
            ("Outcome",case["initial"]["outcome"]["status"],case["later"]["outcome"]["status"]),
            ("Evidence",case["initial"]["outcome"]["evidence"],case["later"]["outcome"]["evidence"]),
        ]:
            rows.append(f"<tr><th>{esc(label)}</th><td>{esc(a)}</td><td>{esc(b)}</td></tr>")
        sections.append(f"""
<article id="case-{index}"><span class="tag">{esc(report['provenance'])} case / {esc(report['diagnosis'])}</span>
<h2>{esc(report['title'])}</h2><p>{esc(report['conclusion'])}</p>
<table><thead><tr><th>Recorded trace</th><th>Initial attempt</th><th>Later attempt</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p><strong>Correction:</strong> {esc(case['correction']['content'])}</p>
<p><strong>Next check:</strong> {esc(report['next_check'])}</p>
<div class="grid"><div class="control"><h3>Written correction control</h3>
<p>Intended action: <code>{esc(case['correction']['intended_action'])}</code></p>
<p>{esc(report['written_correction_control']['limit'])}</p></div>
<div class="control"><h3>Deterministic check control</h3><p>{esc(guard_text)}</p>{guard_basis}<p>{esc(guard['limit'])}</p></div></div>
<details><summary>Inspect the complete input</summary><pre>{esc(json.dumps(case, indent=2))}</pre></details>
</article>""")
    style_hash = hashlib.sha256(CSS.encode()).digest()
    import base64
    csp = "default-src 'none'; style-src 'sha256-" + base64.b64encode(style_hash).decode() + "'; base-uri 'none'; form-action 'none'"
    nav = "".join(f'<a href="#case-{i}">{i + 1}. {esc(r["id"])}</a>' for i, r in enumerate(reports))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}"><title>Repeated mistake replay</title><style>{CSS}</style></head>
<body><main><div class="brand">Hebbrix / an inspectable teaching example</div>
<h1>What happened after the correction?</h1>
<p>Follow an attempted action, its result, a correction, and the next attempt. Separate missing evidence from an instruction that was supplied and still went unused.</p>
<div class="note"><strong>Synthetic trace replay.</strong> The bundled cases were authored for teaching.
This page is not a live agent run or a Hebbrix performance result. Controls inspect explicit fixture data; they do not demonstrate that a model follows advice.</div>
<nav aria-label="Cases">{nav}</nav>{''.join(sections)}
<footer>Everything on this page is rendered locally. No sign-up, API key, model call, or network request is required.
For a real investigation, replace the fixture with an authorized redacted trace and preserve what is known, unknown, and independently observed.
Hebbrix is in private beta. Applications record a decision and attach its later result; Hebbrix uses those results to guide later decisions.</footer>
</main></body></html>"""

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--case", default=None, help="A bundled case ID, or all (default)")
    source.add_argument("--input", type=Path, help="Inspect one local JSON case. No content is uploaded.")
    parser.add_argument("--output", type=Path, default=ROOT / "output", help="Local output directory")
    args = parser.parse_args(argv)
    try:
        if args.input:
            cases = [load_case(args.input)]
        else:
            selection = args.case or "all"
            order = {"missing-history": 0, "ignored-correction": 1, "changed-context": 2, "missing-outcome": 3}
            paths = sorted((ROOT / "cases").glob("*.json"), key=lambda path: (order.get(path.stem, 99), path.stem))
            if selection != "all":
                paths = [path for path in paths if path.stem == selection]
            if not paths:
                raise CaseError("Unknown bundled case. Choose all or a file stem under cases/.")
            cases = [load_case(path) for path in paths]
        reports = [diagnose(case) for case in cases]
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "report.json").write_text(json.dumps({"mode":"local_trace_inspection","live_calls":0,"reports":reports}, indent=2) + "\n")
        (args.output / "report.md").write_text(markdown_report(reports))
        (args.output / "report.html").write_text(html_report(reports))
        for report in reports:
            print(f"{report['id']}: {report['diagnosis']}")
            print("  " + report["next_check"])
        print(f"Local HTML: {(args.output / 'report.html').resolve()}")
        print("No model or Hebbrix API calls were made.")
        return 0
    except (CaseError, OSError) as error:
        print(f"Cannot inspect case: {error}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())

