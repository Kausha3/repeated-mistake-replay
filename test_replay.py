import json
import tempfile
from pathlib import Path
import unittest
import replay

class ReplayEvidenceTests(unittest.TestCase):
    def case(self, name):
        return replay.load_case(Path(__file__).parent / "cases" / (name + ".json"))

    def test_unavailable_correction_is_distinct_from_ignored_correction(self):
        missing = replay.diagnose(self.case("missing-history"))
        supplied = replay.diagnose(self.case("ignored-correction"))
        self.assertEqual(missing["diagnosis"], "correction_unavailable")
        self.assertEqual(supplied["diagnosis"], "correction_available")
        self.assertTrue(missing["declared_comparable_repeat_failure"])
        self.assertTrue(supplied["declared_comparable_repeat_failure"])

    def test_changed_context_does_not_become_a_repeated_failure(self):
        report = replay.diagnose(self.case("changed-context"))
        self.assertEqual(report["diagnosis"], "context_changed")
        self.assertFalse(report["declared_comparable_repeat_failure"])
        self.assertEqual(set(report["scope_differences"]), {"condition", "task_family"})
        self.assertTrue(report["declared_allowlist_check"]["later_action_allowed"])

    def test_missing_feedback_is_not_failure(self):
        report = replay.diagnose(self.case("missing-outcome"))
        self.assertEqual(report["diagnosis"], "insufficient_outcome_evidence")
        self.assertFalse(report["declared_comparable_repeat_failure"])
        self.assertFalse(report["declared_allowlist_check"]["available"])

    def test_recovered_action_is_not_reported_as_repeated_failure(self):
        case = self.case("missing-history")
        case["later"]["outcome"] = {"status":"success", "evidence":"The supplied record says the later run succeeded."}
        report = replay.diagnose(case)
        self.assertEqual(report["diagnosis"], "repeat_without_repeat_failure")
        self.assertFalse(report["declared_comparable_repeat_failure"])

    def test_different_action_is_not_an_exact_repeat(self):
        case = self.case("missing-history")
        case["later"]["action"] = "another-action"
        report = replay.diagnose(case)
        self.assertEqual(report["diagnosis"], "different_action")
        self.assertFalse(report["declared_comparable_repeat_failure"])

    def test_correction_must_link_to_original_attempt(self):
        case = self.case("missing-history")
        case["correction"]["after_decision_id"] = "another-decision"
        with self.assertRaisesRegex(replay.CaseError, "refer"):
            replay.validate_case(case)

    def test_visibility_must_be_declared_without_boolean_coercion(self):
        case = self.case("missing-history")
        case["correction"]["visible_to_later"] = "false"
        with self.assertRaisesRegex(replay.CaseError, "true, false, or null"):
            replay.validate_case(case)
        del case["correction"]["visible_to_later"]
        with self.assertRaisesRegex(replay.CaseError, "missing fields"):
            replay.validate_case(case)

    def test_html_escapes_trace_content(self):
        case = self.case("missing-history")
        case["title"] = '<script>alert("x")</script>'
        case["later"]["action"] = '<img src=x onerror=alert(1)>'
        output = replay.html_report([replay.diagnose(case)])
        self.assertNotIn("<script>", output)
        self.assertNotIn("<img src=x", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertIn("Content-Security-Policy", output)

    def test_custom_trace_has_no_guard_result_without_declared_rule(self):
        case = self.case("ignored-correction")
        case["provenance"] = "user_supplied"
        del case["guard"]
        report = replay.diagnose(case)
        self.assertFalse(report["declared_allowlist_check"]["available"])
        self.assertNotIn("later_action_allowed", report["declared_allowlist_check"])

    def test_cli_writes_only_local_inspection_results(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(replay.main(["--case","all","--output",folder]), 0)
            output = json.loads((Path(folder) / "report.json").read_text())
            self.assertEqual(output["live_calls"], 0)
            self.assertEqual(len(output["reports"]), 4)
            self.assertTrue((Path(folder) / "report.html").is_file())
            self.assertTrue((Path(folder) / "report.md").is_file())

    def test_oversize_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            path.write_bytes(b"x" * 100001)
            with self.assertRaisesRegex(replay.CaseError, "100 KB"):
                replay.load_case(path)

if __name__ == "__main__":
    unittest.main()

