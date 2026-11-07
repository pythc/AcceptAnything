package acceptance_test

import rego.v1
import data.acceptance

baseline := {"approved":true,"spec_digest":"spec-1","suite_digest":"suite-1","target_digest":"image-1","required_checks":["SEC-1"]}
good := {"spec_digest":"spec-1","suite_digest":"suite-1","target_digest":"image-1","complete":true,"evidence_verified":true,"collector_verified":true,"blocking_findings":0,"results":[{"check_id":"SEC-1","status":"passed","evidence_refs":["sha256:artifact-1"]}]}

test_good_passes if { acceptance.allow with input as good with data.baseline as baseline }
test_absent_baseline_fails if { not acceptance.allow with input as good }
test_null_baseline_fails if { not acceptance.allow with input as good with data.baseline as null }
test_null_input_fails if { not acceptance.allow with input as null with data.baseline as baseline }
test_missing_input_fails if { not acceptance.allow with input as {} with data.baseline as baseline }
test_unapproved_baseline_fails if { not acceptance.allow with input as good with data.baseline as object.union(baseline,{"approved":false}) }
test_no_checks_fails if { not acceptance.allow with input as good with data.baseline as object.union(baseline,{"required_checks":[]}) }
test_changed_spec_fails if { not acceptance.allow with input as object.union(good,{"spec_digest":"other"}) with data.baseline as baseline }
test_changed_test_fails if { not acceptance.allow with input as object.union(good,{"suite_digest":"other"}) with data.baseline as baseline }
test_wrong_target_fails if { not acceptance.allow with input as object.union(good,{"target_digest":"other"}) with data.baseline as baseline }
test_timeout_fails if { not acceptance.allow with input as object.union(good,{"complete":false}) with data.baseline as baseline }
test_corrupt_evidence_fails if { not acceptance.allow with input as object.union(good,{"evidence_verified":false}) with data.baseline as baseline }
test_untrusted_collector_fails if { not acceptance.allow with input as object.union(good,{"collector_verified":false}) with data.baseline as baseline }
test_critical_finding_fails if { not acceptance.allow with input as object.union(good,{"blocking_findings":1}) with data.baseline as baseline }
test_missing_check_fails if { not acceptance.allow with input as object.union(good,{"results":[]}) with data.baseline as baseline }
test_duplicate_check_fails if { not acceptance.allow with input as object.union(good,{"results":[good.results[0],good.results[0]]}) with data.baseline as baseline }
test_failed_check_fails if { not acceptance.allow with input as object.union(good,{"results":[object.union(good.results[0],{"status":"failed"})]}) with data.baseline as baseline }
test_skipped_check_fails if { not acceptance.allow with input as object.union(good,{"results":[object.union(good.results[0],{"status":"skipped"})]}) with data.baseline as baseline }
test_blocked_check_fails if { not acceptance.allow with input as object.union(good,{"results":[object.union(good.results[0],{"status":"blocked"})]}) with data.baseline as baseline }
test_unsupported_check_fails if { not acceptance.allow with input as object.union(good,{"results":[object.union(good.results[0],{"status":"unsupported"})]}) with data.baseline as baseline }
test_missing_evidence_fails if { not acceptance.allow with input as object.union(good,{"results":[object.union(good.results[0],{"evidence_refs":[]})]}) with data.baseline as baseline }
