# Agent correction record inspector

[Open the browser inspector](https://kausha3.github.io/repeated-mistake-replay/). Paste a redacted JSON record or open a local file. The inspection runs in your browser tab. No trace is uploaded, and there are no model calls, analytics or browser storage. Loading the hosted page contacts GitHub Pages. You can also download `docs/index.html` and open it offline.

This free tool from [Hebbrix](https://hebbrix.com) checks a supplied record of two attempts and a correction. It flags missing outcome labels, changed context fields, unknown task comparability and declared correction visibility. It can check an action against a supplied allowlist. It does not run an agent, test Hebbrix, read raw vendor traces automatically, or establish why a failure happened.

The bundled records are explicitly synthetic teaching examples. They are not customer reports, founder experience, model runs or performance measurements. Output depends on your input fields and the published rules. Case names and fixture IDs do not select a result.

## Record format

Copy a JSON example from `cases/` and replace its contents using an authorized, redacted record. Set `provenance` to `user_supplied`. Keep unknowns unknown.

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer literal `1`. |
| `id`, `title` | Nonempty labels for your record. |
| `provenance` | `synthetic` or `user_supplied`. This is self-declared. |
| `initial`, `later` | Each has a distinct `decision_id`, action string, context object and outcome object. |
| `context` | 1 to 30 named string fields chosen for your workflow. Include parameters or task conditions needed for comparison. No fixed domain fields. |
| `outcome` | `status` is `failure`, `success` or `unknown`. `evidence` describes the result source or why it is unknown. This tool cannot verify the description. |
| `correction` | `after_decision_id` must match the initial ID. Include `content`, `intended_action` and an explicit `visible_to_later` boolean or `null` for unknown. |
| `comparison` (optional) | `comparable` is `true`, `false` or `null`; `basis` explains that judgment. Omission means unknown. Equal context text alone does not establish comparable task conditions. |
| `guard` (optional) | An explicit `allowed_actions` list and `basis`. Omit this unless there is an independently justified rule. A past failure alone is not grounds for banning an action. |

Unknown fields, duplicate JSON keys and invalid types are rejected rather than silently ignored. Input is limited to 100,000 UTF-8 bytes, including an optional single leading UTF-8 byte-order mark. The browser and CLI accept that mark consistently. Text values have a 12,000-character limit. Actions and context values use exact, case-sensitive strings. The tool does not normalize spacing, infer synonyms, interpret corrections, resolve contradictory prose or verify causal claims. Structured action parameters must be represented explicitly in the action string and context. Review these limits before interpreting a result.

A record can report two failures without establishing that the tasks were equivalent. Even with declared comparability and visibility, a repeated action does not prove the correction was ignored. The rules expose a next investigation step, not a root cause. In JSON, `declared_comparable_repeat_failure: false` means this pattern is not established by the supplied declarations; it does not prove that no repeat occurred.

## Python CLI

Python 3.10 or newer. No package dependencies or credentials.

```sh
python3 replay.py
python3 replay.py --case ignored-correction
python3 replay.py --input path/to/your-case.json --output path/to/private-report
```

Open `output/report.html`, or read `report.json` and `report.md`. Custom output directories receive the same three filenames. Existing report files are replaced. Input paths must be regular files; named pipes and devices are rejected. The tool refuses to overwrite any selected input file, including a selected bundled case, or write through report-file symlinks. On POSIX systems, new report files allow only owner read/write; existing stricter owner permissions and rollback file modes are preserved. This does not audit filesystem ACLs or network mounts. Reports contain the complete supplied record. Keep private reports private. Browser file selection clears the previous editor and report before reading. Inspect stays disabled during the current load; a failed read cannot silently reuse the previous record. Errors thrown while preparing or starting a download appear in the page.

Trace text is escaped in HTML and fenced as inert JSON in Markdown. The browser displays trace content using text nodes. Trace strings are never executed. No agent, shell command or external tool is invoked from a record.

## Where Hebbrix fits

An application records a decision and attaches the result when it becomes known. Hebbrix uses those results to guide later decisions. We call this outcome-based learning. Developers connect through Python, TypeScript or MCP. Hebbrix is in private beta.

This inspector is a separate evidence checklist. A useful Hebbrix evaluation would need a defined workflow, a matched baseline, permitted data, integration limits and recorded results. This tool does not include such an evaluation or reproduce Hebbrix's internal methods.

If you maintain a workflow where a corrected mistake repeats, [describe it to the Hebbrix founders](https://github.com/Kausha3/repeated-mistake-replay/issues/new?template=workflow-discussion.yml). GitHub issues are public and require an account. Share a brief non-sensitive description. Keep logs, customer information and credentials private. We can agree on a private route before inspecting a trace. A discussion is not an evaluation agreement or appointment. For a high-level inquiry without a public issue, use [Hebbrix's contact page](https://hebbrix.com/contact). Keep the trace private until a suitable route is agreed.

## Inspect and test

```sh
python3 -m unittest -v
python3 build_site.py
node test_web_state.cjs
```

`replay.py` owns the ordered diagnosis rule table. `build_site.py` embeds that same table and the synthetic fixtures in the standalone browser page. `web.js` implements browser parsing and field comparison. Cross-runtime tests compare JavaScript and Python outputs for the same inputs. Node.js is needed for those checks and the browser-state suite; Node-dependent checks are skipped or omitted when Node is unavailable. The browser-state suite uses a small mock DOM to test file-load event order, invalidation and download failure recovery. It does not replace actual browser or accessibility testing. There is no fixture-specific result lookup. Limits, schema rules and actual project links are explicit constants, not test results.

Tests cover malformed input, duplicate keys, Unicode, output preservation, absent comparison evidence, successful and unknown outcomes, identical intended actions, changed context, text escaping and browser/Python agreement. Passing checks establish only those tested behaviors. They do not establish product effectiveness, acquisition or the truth of supplied records.

The [GitHub verification workflow](.github/workflows/verify.yml) rebuilds the page and runs regressions on Ubuntu with Python 3.10 and 3.14 plus Node 24. Its checks cover code and generated files. Real browser testing remains a separate check.

## Reuse

Source, bundled synthetic fixtures and synthetic reports use the MIT license in `LICENSE`. Use and disclose real traces only when authorized.
