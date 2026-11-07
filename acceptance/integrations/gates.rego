package integrations
import rego.v1

default decision := "inconclusive"

ready if {
    object.get(input, "contract_ready", true)
    object.get(input, "recipe_complete", true)
    input.integrity == true
    count(input.tasks) > 0
    count(input.rules) > 0
    every task in input.tasks { task.state == "completed"; task.report.complete == true }
    every rule in input.rules { rule.status in {"passed", "failed"} }
}
failed if { some rule in input.rules; rule.status == "failed" }
decision := "allow" if { ready; not failed }
decision := "reject" if { ready; failed }
