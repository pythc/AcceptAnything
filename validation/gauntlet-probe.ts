import {parseReportCriteria, checkCriteriaConsistency} from '../research/upstream/gauntlet/src/agent/validators';
const requirement = ['Alice must not read Bobs private document'];
const probes = {
  missing_evidence: parseReportCriteria([{criterion: requirement[0],verdict:'pass',evidence:''}],requirement),
  unverified_artifact_reference: parseReportCriteria([{criterion:requirement[0],verdict:'pass',evidence:'screenshots/does-not-exist.png shows access denied'}],requirement),
  rewritten_criterion: parseReportCriteria([{criterion:'The home page renders',verdict:'pass',evidence:'Home page visible'}],requirement),
  contradictory_overall_pass: checkCriteriaConsistency('pass',[{criterion:requirement[0],verdict:'fail',evidence:'HTTP 200'}])
};
console.log(JSON.stringify(probes,null,2));
