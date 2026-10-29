"""Deterministic mock "LLM" used when no API key is available.

It scores each criterion by looking for positive and negative signals in the supplier
document, quotes the sentence that triggered the strongest signal as evidence, and
returns the same JSON shape a real model would. It is not intelligent; it exists so the
pipeline can be demonstrated and tested reproducibly.

Fault injection: when `fault_target` names a supplier, the first reply for that supplier
is not JSON and the retry contains a missing criterion, an out-of-range score, a text
score, an unknown criterion id and fabricated evidence - exercising every validation rule.
"""
from __future__ import annotations

import json
import re

# (label, regex) pairs. Matched case-insensitively against the document text.
# Fraction of the positive signals needed for a full score (per criterion bucket).
TARGET_RATIO = {"security": 1.0, "commercial": 0.85, "technical": 0.9}
DEFAULT_TARGET_RATIO = 0.75
NEGATIVE_PENALTY = 0.75
BASE_SCORE = 2.0
SIGNAL_RANGE = 7.5
MAX_MOCK_SCORE_RATIO = 0.9   # the mock never awards a perfect score

LEXICON: dict[str, dict[str, list[tuple[str, str]]]] = {
    "technical": {
        "pos": [
            ("microservices / service-oriented architecture", r"microservice|service-oriented"),
            ("container orchestration", r"kubernetes"),
            ("API gateway", r"api gateway"),
            ("REST APIs", r"rest apis?"),
            ("event-driven integration", r"event bus|kafka"),
            ("pre-built connectors", r"connectors? for"),
            ("SAP integration detail", r"s/4hana"),
            ("telephony integration", r"genesys"),
            ("documented integration specification", r"integration specification"),
            ("autoscaling", r"autoscal"),
            ("horizontal scalability", r"horizontal"),
            ("evidence of scale", r"concurrent agents"),
            ("latency figures", r"latency"),
            ("availability SLA", r"99\.9"),
            ("high-availability failover", r"active-active|failover"),
            ("load testing", r"load test"),
            ("omnichannel coverage", r"omnichannel|live chat"),
            ("cloud hosting", r"cloud"),
            ("CRM integration", r"salesforce"),
        ],
        "neg": [
            ("integration approach not yet defined", r"to be confirmed|finalised during discovery"),
            ("connectors only 'as needed'", r"as needed"),
            ("key integrations deferred to the project", r"can be built during the project"),
            ("limited feature set", r"\bbasic\b"),
        ],
    },
    "implementation": {
        "pos": [
            ("phased plan", r"phase \d|phases?:|in (four|five) phases"),
            ("week-level timeline", r"weeks? \d+-\d+"),
            ("numbered milestones", r"\bm[1-6]\b"),
            ("named team roles", r"delivery manager|solution architect"),
            ("integration lead", r"integration lead"),
            ("risk register", r"risk register"),
            ("named risk mitigations", r"mitigation:"),
            ("UAT", r"user acceptance testing|\buat\b"),
            ("performance testing", r"performance testing"),
            ("pilot before rollout", r"\bpilot\b"),
            ("hypercare", r"hypercare"),
            ("RACI matrix", r"\braci\b"),
            ("rollback plan", r"rollback"),
            ("change management", r"change manager|change management"),
            ("iterative sprints", r"sprint"),
            ("defined go-live point", r"week \d+ go-live|go-live \(week"),
        ],
        "neg": [
            ("plan to be agreed after contract", r"after contract signature"),
            ("approximate timeline", r"approximately \d+ weeks"),
            ("milestone dates undefined", r"exact dates will be agreed"),
        ],
    },
    "commercial": {
        "pos": [
            ("itemised price table", r"total contract value"),
            ("fixed-price implementation", r"fixed price"),
            ("stated assumptions", r"exclude (applicable )?taxes"),
            ("payment milestones", r"payment milestones?|payment:"),
            ("total cost of ownership", r"total cost of ownership|total cost"),
            ("no hidden fees", r"no hidden fees|no additional mandatory fees|all-inclusive"),
            ("change rates published", r"day rate|per agent per year"),
            ("competitive price point", r"lowest total cost"),
        ],
        "neg": [
            ("cost items are estimates", r"estimate"),
            ("price may change", r"may change"),
            ("premium pricing acknowledged", r"not the lowest-cost"),
        ],
    },
    "security": {
        "pos": [
            ("ISO 27001", r"iso/iec 27001|iso 27001 certif"),
            ("SOC 2 attestation", r"soc 2"),
            ("SOC 2 Type II report", r"soc 2 type ii report"),
            ("encryption at rest", r"aes-256|encrypted at rest"),
            ("encryption in transit", r"tls 1\."),
            ("SSO / SAML", r"saml"),
            ("role-based access control", r"role-based access control|rbac"),
            ("multi-factor authentication", r"multi-factor"),
            ("audit logs", r"audit logs?"),
            ("GDPR", r"gdpr"),
            ("DPDP Act 2023", r"dpdp"),
            ("data residency", r"data residency|host data in india"),
            ("penetration testing", r"penetration test"),
            ("incident response", r"incident response"),
            ("key management", r"kms|key rotation"),
        ],
        "neg": [
            ("certification only planned", r"planning to begin"),
            ("relies on generic 'best practices'", r"best practices"),
            ("relies on hosting provider's controls", r"its own certifications"),
            ("security detail only on request", r"questionnaire can be completed on request"),
        ],
    },
    "support": {
        "pos": [
            ("24x7 support", r"24x7"),
            ("tiered support model", r"l1/l2/l3"),
            ("defined response times", r"p1 \d+ minutes"),
            ("service credits", r"service credits"),
            ("dedicated account / success manager", r"customer success manager|account manager"),
            ("service reviews", r"service reviews"),
            ("knowledge base", r"knowledge base"),
            ("relevant retail experience", r"for retail|for retailers"),
            ("substantial track record", r"more than 40|seven contact-centre|\b(12|three) (for|omnichannel)"),
            ("named references", r"references:"),
            ("multiple references", r"\(c[a-z]o\)|\(head of"),
        ],
        "neg": [
            ("business-hours-only support", r"business hours, monday"),
            ("recently founded / limited track record", r"founded in 202"),
            ("references not provided", r"references are available on request"),
        ],
    },
}


def _bucket(name: str, description: str) -> str | None:
    n = name.lower()
    for key in LEXICON:
        if key in n:
            return key
    if "price" in n or "cost" in n:
        return "commercial"
    return None


_NON_SENTENCE_LINE = re.compile(r"^(\d+\.\s.{3,90}|page \d+|.*\| response to .*)$", re.IGNORECASE)


def _sentences(text: str) -> list[str]:
    """Split into sentences, skipping section headings and page headers/footers."""
    lines = [ln for ln in text.splitlines() if not _NON_SENTENCE_LINE.match(ln.strip())]
    flat = re.sub(r"\s+", " ", " ".join(lines))
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if len(s.strip()) > 20]


def _first_sentence(sentences: list[str], pattern: str) -> str:
    rx = re.compile(pattern, re.IGNORECASE)
    for s in sentences:
        if rx.search(s):
            return s[:300]
    return ""


def score_criterion(crit: dict, text: str, sentences: list[str]) -> dict:
    max_score = int(crit["max_score"])
    text = re.sub(r"\s+", " ", text)
    bucket = _bucket(crit["name"], crit.get("description", ""))
    if bucket:
        pos, neg = LEXICON[bucket]["pos"], LEXICON[bucket]["neg"]
    else:  # unknown criterion: use long words from its description as weak signals
        words = sorted({w for w in re.findall(r"[a-z]{6,}", crit.get("description", "").lower())})
        pos, neg = [(w, re.escape(w)) for w in words], []
    hits = [(label, rx) for label, rx in pos if re.search(rx, text, re.IGNORECASE)]
    misses = [(label, rx) for label, rx in neg if re.search(rx, text, re.IGNORECASE)]
    target = max(len(pos), 1) * TARGET_RATIO.get(bucket or "", DEFAULT_TARGET_RATIO)
    coverage = min(1.0, len(hits) / target)
    raw = min(BASE_SCORE + SIGNAL_RANGE * coverage, MAX_MOCK_SCORE_RATIO * 10)   # on a 10-point scale
    raw = max(raw - NEGATIVE_PENALTY * len(misses), 1.0)
    score = int(round(raw / 10 * max_score))

    evidence = ""
    for _, rx in (misses if score <= max_score * 0.4 and misses else []) + hits + misses:
        evidence = _first_sentence(sentences, rx)
        if evidence:
            break
    parts = []
    if hits:
        extra = f" and {len(hits) - 5} more" if len(hits) > 5 else ""
        parts.append("Strengths: " + ", ".join(l for l, _ in hits[:5]) + extra)
    if misses:
        parts.append("Concerns: " + ", ".join(l for l, _ in misses))
    if not parts:
        parts.append("The document contains little information relevant to this criterion.")
    return {
        "criterion_id": crit["criterion_id"], "score": score, "max_score": max_score,
        "justification": ". ".join(parts) + ".", "evidence": evidence,
        "_concerns": [l for l, _ in misses],
    }


class MockLLM:
    provider = "Mock (no API key)"
    model = "mock-keyword-v1"

    def __init__(self, fault_target: str | None = None):
        self.fault_target = fault_target

    def complete(self, messages: list[dict], context: dict) -> str:
        supplier = context["supplier_name"]
        criteria = context["criteria"]
        text = context["document_text"]
        attempt = context.get("attempt", 1)
        faulty = bool(self.fault_target) and supplier == self.fault_target

        if faulty and attempt == 1:
            return "Sure! Here is my evaluation of the supplier:\n{criteria: [oops this is not json"

        sentences = _sentences(text)
        results = [score_criterion(c, text, sentences) for c in criteria]
        risks = sorted({c for r in results for c in r.pop("_concerns")})
        best = max(results, key=lambda r: r["score"] / r["max_score"])
        worst = min(results, key=lambda r: r["score"] / r["max_score"])
        name_of = {c["criterion_id"]: c["name"] for c in criteria}
        out = {
            "supplier_name": supplier,
            "criteria": results,
            "risks": [r[0].upper() + r[1:] for r in risks],
            "overall_summary": (f"Keyword-based mock assessment. Strongest area: {name_of[best['criterion_id']]}; "
                                f"weakest area: {name_of[worst['criterion_id']]}."),
        }
        if faulty:  # deliberately broken but parseable second reply
            crit = out["criteria"]
            if len(crit) >= 1:
                crit[0]["score"] = crit[0]["max_score"] + 4                  # out of range
            if len(crit) >= 2:
                crit[1]["score"] = f"{crit[1]['score']}/{crit[1]['max_score']}"  # text score
            if len(crit) >= 3:
                crit[2]["evidence"] = "We guarantee a 70% cost reduction in year one."  # not in document
            if len(crit) >= 4:
                crit.pop()                                                    # missing criterion
            crit.append({"criterion_id": 99, "score": 10, "max_score": 10,
                         "justification": "Extra", "evidence": ""})            # unknown id
        return "```json\n" + json.dumps(out, indent=2) + "\n```"
