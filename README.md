# Repeated mistake replay

A small local tool for inspecting what happened after an agent received a correction. It separates an unavailable correction, a supplied correction that did not prevent a repeat, a changed task context, and a missing later result.

The four bundled cases are synthetic authored traces. They are teaching examples, not founder experience, customer reports, model runs, or Hebbrix performance results.

## Try it

Python 3.10 or newer is sufficient. There are no package dependencies, credentials, model calls, or network requests.

```sh
python3 replay.py
```

Open `output/report.html` in a browser. The same results are available in `output/report.json` and `output/report.md`. Each case includes its entire input so the conclusion can be inspected.

Choose one case:

```sh
python3 replay.py --case ignored-correction
```

Inspect your own authorized, redacted trace locally:

```sh
python3 replay.py --input path/to/your-case.json --output path/to/local-report
```

No content is uploaded. Generated reports contain the supplied trace. Keep reports private when they contain private information.

## What the controls mean

The written-correction control exposes the action stated in the correction and the record's declared correction visibility. It does not run a model or establish that a model will follow the correction.

The deterministic-check control checks the observed action against an explicit allowlist supplied in the fixture. It illustrates where an execution check can reject a known invalid action. It does not select another action, execute the task, or establish success.

There are no success percentages, comparative performance scores, token measurements, or counterfactual task results.

## Use a real case

Copy one JSON file in `cases/` and set `provenance` to `user_supplied`. Supply an initial decision, an observed result, the correction, and a later decision with its own result. Use `unknown` for an outcome that has not arrived. Use `null` for correction visibility when the trace does not establish it.

The four required context fields are `workflow`, `environment`, `task_family`, and `condition`. The tool compares these exact strings. It does not infer semantic equivalence, causality, or whether a description is true.

A correction must reference the initial decision ID. The two decision IDs must differ. Outcomes accept `failure`, `success`, or `unknown`, together with an evidence description. Omit `guard` if there is no independently justified precondition. Do not add an allowlist simply because an action previously failed.

The tool treats JSON as data. It executes no commands supplied in traces. The HTML report escapes trace content and has no scripts or external assets.

## Where Hebbrix fits

Applications record a decision and attach its later result. [Hebbrix](https://hebbrix.com) uses those results to guide later decisions. We call this outcome-based learning. Hebbrix is in private beta.

This replay helps decide what evidence a real evaluation would need. It does not call Hebbrix or reproduce its internal methods. A live comparison would require a separately agreed workflow, matched baseline, permitted data, supported integration, resource limits, and recorded outcomes. No live integration adapter is included here.

A repeated failure with a visible correction may require stronger execution constraints. A changed context may make an earlier correction inappropriate. A missing result should remain unknown. Those findings are useful even when adding memory is not the next step.

## Check the tool

```sh
python3 -m unittest -v
```

Checks cover missing outcomes, changed contexts, mismatched decision IDs, strict visibility fields, the absence of invented guard results, HTML escaping, the input size limit, and local report generation.

## Reuse

The source, bundled synthetic fixtures, and generated synthetic reports in this package are available under the MIT license in `LICENSE`. Replace synthetic examples with real traces only when you have the right to use and disclose them.


## Discuss a workflow

If you own an agent workflow where a corrected mistake repeats, you can [start a workflow discussion](https://github.com/Kausha3/repeated-mistake-replay/issues/new?template=workflow-discussion.yml). Share only a brief, non-sensitive description. Keep logs, customer information and credentials private. We can agree on a suitable private route before inspecting any trace. A discussion is not an agreed evaluation or appointment.
