# Supplied record inspection

No model or Hebbrix API calls were made. All trace fields are supplied declarations.

```json
{
  "reports": [
    {
      "id": "changed-context",
      "title": "The same action occurred in a different context",
      "provenance": "synthetic",
      "diagnosis": "context_changed",
      "conclusion": "The supplied context fields differ. Their relevance needs review.",
      "next_check": "Decide whether these differences change the task or the correction's applicability. A text difference alone does not establish that.",
      "scope_differences": [
        "condition",
        "task_family"
      ],
      "same_action": true,
      "declared_comparable_repeat_failure": false,
      "reported_failure_pattern": false,
      "comparison_declared": false,
      "evidence_limit": "All fields are supplied declarations. This tool cannot verify their truth, causal explanation, action equivalence or outcome quality.",
      "recorded_correction": {
        "intended_action": "read-primary",
        "visible_in_recorded_later_attempt": true,
        "limit": "The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured."
      },
      "declared_allowlist_check": {
        "available": true,
        "later_action_allowed": true,
        "correction_action_allowed": false,
        "allowed_actions": [
          "read-replica"
        ],
        "basis": "Authored teaching precondition for the later task: historical analysis uses a frozen snapshot.",
        "limit": "This checks a declared allowlist. It does not execute an agent, choose a repair, or prove task success."
      },
      "claim_boundary": "This inspects a supplied record. It does not run an agent, test Hebbrix, establish causality, or compare model or product performance.",
      "case": {
        "schema_version": 1,
        "id": "changed-context",
        "title": "The same action occurred in a different context",
        "provenance": "synthetic",
        "initial": {
          "decision_id": "query-1",
          "context": {
            "workflow": "billing-export",
            "environment": "demo",
            "task_family": "month-close",
            "condition": "must-read-current-data"
          },
          "action": "read-replica",
          "outcome": {
            "status": "failure",
            "evidence": "Authored fixture: close report required current data."
          }
        },
        "correction": {
          "after_decision_id": "query-1",
          "content": "For month-close exports, use the primary source.",
          "intended_action": "read-primary",
          "visible_to_later": true
        },
        "later": {
          "decision_id": "query-2",
          "context": {
            "workflow": "billing-export",
            "environment": "demo",
            "task_family": "historical-analysis",
            "condition": "frozen-snapshot-required"
          },
          "action": "read-replica",
          "outcome": {
            "status": "success",
            "evidence": "Authored fixture: this historical analysis explicitly required the frozen snapshot."
          }
        },
        "guard": {
          "allowed_actions": [
            "read-replica"
          ],
          "basis": "Authored teaching precondition for the later task: historical analysis uses a frozen snapshot."
        },
        "comparison": {
          "comparable": false,
          "basis": "Authored synthetic comparison: task purpose and condition differ."
        }
      }
    },
    {
      "id": "ignored-correction",
      "title": "The correction was supplied, but the same action repeated",
      "provenance": "synthetic",
      "diagnosis": "correction_available",
      "conclusion": "The record reports the same action failing twice and declares the correction visible.",
      "next_check": "Check the actual supplied context, interpretation and execution. Visibility does not prove the correction was understood or applicable.",
      "scope_differences": [],
      "same_action": true,
      "declared_comparable_repeat_failure": true,
      "reported_failure_pattern": true,
      "comparison_declared": true,
      "evidence_limit": "All fields are supplied declarations. This tool cannot verify their truth, causal explanation, action equivalence or outcome quality.",
      "recorded_correction": {
        "intended_action": "test --project demo-app",
        "visible_in_recorded_later_attempt": true,
        "limit": "The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured."
      },
      "declared_allowlist_check": {
        "available": true,
        "later_action_allowed": false,
        "correction_action_allowed": true,
        "allowed_actions": [
          "test --project demo-app"
        ],
        "basis": "Authored teaching precondition: only the project-scoped invocation is allowed in this toy runner.",
        "limit": "This checks a declared allowlist. It does not execute an agent, choose a repair, or prove task success."
      },
      "claim_boundary": "This inspects a supplied record. It does not run an agent, test Hebbrix, establish causality, or compare model or product performance.",
      "case": {
        "schema_version": 1,
        "id": "ignored-correction",
        "title": "The correction was supplied, but the same action repeated",
        "provenance": "synthetic",
        "initial": {
          "decision_id": "repair-1",
          "context": {
            "workflow": "build-repair",
            "environment": "demo",
            "task_family": "test-command",
            "condition": "runner-requires-project-argument"
          },
          "action": "test --all",
          "outcome": {
            "status": "failure",
            "evidence": "Authored fixture: the tool rejected this invocation because the project argument was absent."
          }
        },
        "correction": {
          "after_decision_id": "repair-1",
          "content": "This runner requires test --project demo-app.",
          "intended_action": "test --project demo-app",
          "visible_to_later": true
        },
        "later": {
          "decision_id": "repair-2",
          "context": {
            "workflow": "build-repair",
            "environment": "demo",
            "task_family": "test-command",
            "condition": "runner-requires-project-argument"
          },
          "action": "test --all",
          "outcome": {
            "status": "failure",
            "evidence": "Authored fixture: the same invocation was rejected again."
          }
        },
        "guard": {
          "allowed_actions": [
            "test --project demo-app"
          ],
          "basis": "Authored teaching precondition: only the project-scoped invocation is allowed in this toy runner."
        },
        "comparison": {
          "comparable": true,
          "basis": "Authored synthetic comparison: these toy attempts declare the same task conditions. This is not independent evidence."
        }
      }
    },
    {
      "id": "missing-history",
      "title": "A correction was not available on the later attempt",
      "provenance": "synthetic",
      "diagnosis": "correction_unavailable",
      "conclusion": "The record reports the same action failing twice and declares the correction unavailable.",
      "next_check": "Inspect how the correction is scoped, retrieved, and included in the later decision.",
      "scope_differences": [],
      "same_action": true,
      "declared_comparable_repeat_failure": true,
      "reported_failure_pattern": true,
      "comparison_declared": true,
      "evidence_limit": "All fields are supplied declarations. This tool cannot verify their truth, causal explanation, action equivalence or outcome quality.",
      "recorded_correction": {
        "intended_action": "read-primary",
        "visible_in_recorded_later_attempt": false,
        "limit": "The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured."
      },
      "declared_allowlist_check": {
        "available": true,
        "later_action_allowed": false,
        "correction_action_allowed": true,
        "allowed_actions": [
          "read-primary"
        ],
        "basis": "Authored teaching precondition: this export requires the primary source for current data.",
        "limit": "This checks a declared allowlist. It does not execute an agent, choose a repair, or prove task success."
      },
      "claim_boundary": "This inspects a supplied record. It does not run an agent, test Hebbrix, establish causality, or compare model or product performance.",
      "case": {
        "schema_version": 1,
        "id": "missing-history",
        "title": "A correction was not available on the later attempt",
        "provenance": "synthetic",
        "initial": {
          "decision_id": "export-1",
          "context": {
            "workflow": "billing-export",
            "environment": "demo",
            "task_family": "month-close",
            "condition": "must-read-current-data"
          },
          "action": "read-replica",
          "outcome": {
            "status": "failure",
            "evidence": "Authored fixture: export used a snapshot older than the requested reporting period."
          }
        },
        "correction": {
          "after_decision_id": "export-1",
          "content": "For this month-close export, use the primary data source.",
          "intended_action": "read-primary",
          "visible_to_later": false
        },
        "later": {
          "decision_id": "export-2",
          "context": {
            "workflow": "billing-export",
            "environment": "demo",
            "task_family": "month-close",
            "condition": "must-read-current-data"
          },
          "action": "read-replica",
          "outcome": {
            "status": "failure",
            "evidence": "Authored fixture: the later export used the same old snapshot."
          }
        },
        "guard": {
          "allowed_actions": [
            "read-primary"
          ],
          "basis": "Authored teaching precondition: this export requires the primary source for current data."
        },
        "comparison": {
          "comparable": true,
          "basis": "Authored synthetic comparison: these toy attempts declare the same task conditions. This is not independent evidence."
        }
      }
    },
    {
      "id": "missing-outcome",
      "title": "A later action has no observed result yet",
      "provenance": "synthetic",
      "diagnosis": "insufficient_outcome_evidence",
      "conclusion": "The recorded outcomes do not establish a repeated failure.",
      "next_check": "Record the missing result and its source. Missing feedback is not failure.",
      "scope_differences": [],
      "same_action": true,
      "declared_comparable_repeat_failure": false,
      "reported_failure_pattern": false,
      "comparison_declared": true,
      "evidence_limit": "All fields are supplied declarations. This tool cannot verify their truth, causal explanation, action equivalence or outcome quality.",
      "recorded_correction": {
        "intended_action": "test --project demo-app",
        "visible_in_recorded_later_attempt": null,
        "limit": "The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured."
      },
      "declared_allowlist_check": {
        "available": false,
        "limit": "No allowlist was supplied. No rule result is inferred."
      },
      "claim_boundary": "This inspects a supplied record. It does not run an agent, test Hebbrix, establish causality, or compare model or product performance.",
      "case": {
        "schema_version": 1,
        "id": "missing-outcome",
        "title": "A later action has no observed result yet",
        "provenance": "synthetic",
        "initial": {
          "decision_id": "job-1",
          "context": {
            "workflow": "build-repair",
            "environment": "demo",
            "task_family": "test-command",
            "condition": "runner-requires-project-argument"
          },
          "action": "test --all",
          "outcome": {
            "status": "failure",
            "evidence": "Authored fixture: tool rejected missing project argument."
          }
        },
        "correction": {
          "after_decision_id": "job-1",
          "content": "Supply the project argument.",
          "intended_action": "test --project demo-app",
          "visible_to_later": null
        },
        "later": {
          "decision_id": "job-2",
          "context": {
            "workflow": "build-repair",
            "environment": "demo",
            "task_family": "test-command",
            "condition": "runner-requires-project-argument"
          },
          "action": "test --all",
          "outcome": {
            "status": "unknown",
            "evidence": "No result is recorded in this authored fixture."
          }
        },
        "comparison": {
          "comparable": true,
          "basis": "Authored synthetic comparison: these toy attempts declare the same task conditions. This is not independent evidence."
        }
      }
    }
  ]
}
```
