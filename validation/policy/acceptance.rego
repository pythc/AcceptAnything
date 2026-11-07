package acceptance

import rego.v1

# Research policy: input must come from a trusted collector, never from an LLM.
default allow := false

allow if {
    is_object(data.baseline)
    is_object(input)
    count(deny) == 0
}

deny contains "baseline_missing" if {
    not data.baseline
}
deny contains "baseline_not_object" if {
    not is_object(data.baseline)
}
deny contains "input_not_object" if {
    not is_object(input)
}
deny contains "missing_or_unapproved_baseline" if {
    object.get(data.baseline, "approved", false) != true
}
deny contains "no_required_checks" if {
    count(object.get(data.baseline, "required_checks", [])) == 0
}
deny contains "spec_changed" if {
    object.get(input, "spec_digest", "") != data.baseline.spec_digest
}
deny contains "test_suite_changed" if {
    object.get(input, "suite_digest", "") != data.baseline.suite_digest
}
deny contains "wrong_target" if {
    object.get(input, "target_digest", "") != data.baseline.target_digest
}
deny contains "run_incomplete" if {
    object.get(input, "complete", false) != true
}
deny contains "evidence_not_verified" if {
    object.get(input, "evidence_verified", false) != true
}
deny contains "collector_not_verified" if {
    object.get(input, "collector_verified", false) != true
}
deny contains "blocking_security_finding" if {
    object.get(input, "blocking_findings", 0) > 0
}
deny contains "check_missing_or_duplicated" if {
    some id in data.baseline.required_checks
    matches := [r | some r in object.get(input, "results", []); r.check_id == id]
    count(matches) != 1
}
deny contains "mandatory_check_not_passed" if {
    some r in object.get(input, "results", [])
    r.check_id in data.baseline.required_checks
    object.get(r, "status", "") != "passed"
}
deny contains "mandatory_check_has_no_evidence" if {
    some r in object.get(input, "results", [])
    r.check_id in data.baseline.required_checks
    count(object.get(r, "evidence_refs", [])) == 0
}
