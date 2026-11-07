"""Directly exercise the downloaded evidence helper; no LLM or network."""
import copy
import json
from utils.reporting.evidence_chain import (
    ChainOfCustody, EvidenceItem, EvidencePackage, hash_content, verify_chain_integrity,
)

item = EvidenceItem(id="e1", source="fixture", category="http", timestamp="2026-10-17T00:00:00Z", content={"status":403})
package = EvidencePackage(package_id="p1",chain=ChainOfCustody(chain_id="c1").add(item),metadata={"target_digest":"image-1"}).seal()
results = {"original": verify_chain_integrity(package)["pass"]}
changed = copy.deepcopy(package)
changed.chain.items[0].content["status"] = 200
results["content_changed_without_rehash"] = verify_chain_integrity(changed)["pass"]
changed = copy.deepcopy(package)
changed.chain.items[0].timestamp = "2099-01-01T00:00:00Z"
changed.metadata["target_digest"] = "image-2"
results["timestamp_and_target_metadata_changed"] = verify_chain_integrity(changed)["pass"]
changed = copy.deepcopy(package)
changed.chain.items[0].content["status"] = 200
changed.chain.items[0].content_hash = hash_content(changed.chain.items[0].content)
changed.seal()
results["content_rehashed_and_resealed_by_same_writer"] = verify_chain_integrity(changed)["pass"]
print(json.dumps(results,indent=2))
