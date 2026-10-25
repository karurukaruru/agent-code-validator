"""ASM-derived, version-scoped observations. Reuse never skips verification."""
from pathlib import Path
from .evidence import digest, now, read_json, sanitize, write_json


class KnowledgeStore:
    def __init__(self, root):
        self.root = Path(root)

    def save(self, identity, evidence):
        if not all(identity.get(k) for k in ("software", "version", "boundary", "source_sha256", "environment")):
            raise ValueError("Knowledge requires complete version, source and environment scope")
        if evidence.get("status") not in {"PASS", "FAIL"} or evidence.get("execution") is not True:
            raise ValueError("Only executed determinate observations may enter verified knowledge")
        record = {"identity": identity, "evidence_level": "verified", "scope": "this exact execution environment only", "verified_at": now(), "evidence": evidence, "revalidation_triggers": ["source hash", "dependency version", "environment", "contract change"]}
        key = digest(identity)
        record = sanitize(record)
        record["integrity"] = digest(record)
        write_json(self.root / (key + ".json"), record)
        return key

    def lookup(self, identity):
        path = self.root / (digest(identity) + ".json")
        if not path.exists():
            return None
        record = read_json(path)
        checksum = record.pop("integrity", None)
        if checksum != digest(record) or record.get("identity") != identity:
            raise ValueError("Knowledge evidence integrity failure")
        record["integrity"] = checksum
        record["reuse_policy"] = "Prior observation only; execute contract again before current PASS"
        return record

    def export_markdown(self, identity):
        record = self.lookup(identity)
        if not record:
            return "# Compatibility ASM\n\nEvidence: unknown. No matching scoped observation.\n"
        return "# Compatibility ASM\n\n" + "\n".join(f"- {k}: {v}" for k, v in identity.items()) + "\n\nEvidence: verified for the recorded local execution only.\n\n" + record["reuse_policy"] + "\n\nRecovery: reproduce the contract and verify a repair before adoption.\n"
