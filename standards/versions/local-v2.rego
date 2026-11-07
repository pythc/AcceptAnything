package release

import rego.v1

default decision := "inconclusive"

valid if {
    input.integrity == true
    input.validation.valid == true
    input.complete == true
    count(input.required) > 0
    every id in input.required {
        matches := [r | some r in input.results; r.criterion_id == id]
        count(matches) == 1
        matches[0].status in {"passed", "failed"}
        matches[0].verified == true
        count(matches[0].evidence_refs) > 0
    }
}

failed if {
    some r in input.results
    r.criterion_id in input.required
    r.status == "failed"
}

decision := "reject" if { valid; failed }
decision := "allow" if { valid; not failed }
