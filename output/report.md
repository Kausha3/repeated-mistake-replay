# Repeated mistake replay

Local inspection only. The bundled cases are synthetic authored traces.
No model, Hebbrix API, network, or external tools were called.

## A correction was not available on the later attempt

Provenance: synthetic.
Diagnosis: correction_unavailable.

The same failed action repeated while the correction was declared unavailable.

Next check: Inspect how the correction is scoped, retrieved, and included in the later decision.

Recorded actions: read-replica -> read-replica.
Written correction control: intended action is read-primary.
The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured.

Deterministic check control: the later action is rejected by the declared precondition.
Basis: Authored teaching precondition: this export requires the primary source for current data.
This checks a declared allowlist. It does not execute an agent, choose a repair, or prove task success.

This is evidence bookkeeping, not a Hebbrix evaluation or a comparison of model or product performance.

## The correction was supplied, but the same action repeated

Provenance: synthetic.
Diagnosis: correction_available.

The same failed action repeated despite declared correction visibility.

Next check: Inspect adherence and execution constraints. Better retrieval alone may not solve this.

Recorded actions: test --all -> test --all.
Written correction control: intended action is test --project demo-app.
The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured.

Deterministic check control: the later action is rejected by the declared precondition.
Basis: Authored teaching precondition: only the project-scoped invocation is allowed in this toy runner.
This checks a declared allowlist. It does not execute an agent, choose a repair, or prove task success.

This is evidence bookkeeping, not a Hebbrix evaluation or a comparison of model or product performance.

## The same action occurred in a different context

Provenance: synthetic.
Diagnosis: context_changed.

These attempts are not comparable under the declared context.

Next check: Review whether the old correction applies. Repeating an action in a different task can be appropriate.

Recorded actions: read-replica -> read-replica.
Written correction control: intended action is read-primary.
The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured.

Deterministic check control: the later action is allowed by the declared precondition.
Basis: Authored teaching precondition for the later task: historical analysis uses a frozen snapshot.
This checks a declared allowlist. It does not execute an agent, choose a repair, or prove task success.

This is evidence bookkeeping, not a Hebbrix evaluation or a comparison of model or product performance.

## A later action has no observed result yet

Provenance: synthetic.
Diagnosis: insufficient_outcome_evidence.

The recorded outcomes do not establish a repeated failure.

Next check: Collect the missing independently observed result. Missing feedback is not failure.

Recorded actions: test --all -> test --all.
Written correction control: intended action is test --project demo-app.
The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured.

No explicit precondition was supplied. No guard result is inferred.

This is evidence bookkeeping, not a Hebbrix evaluation or a comparison of model or product performance.

