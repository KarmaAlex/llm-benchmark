"""
Compare the SonarQube findings of a patched project against the pristine
baseline for the same case.

Two questions, both answered here and nowhere else:

  1. Did the model actually resolve the issue the case is about?
  2. Did it introduce anything new on the way?

Both comparisons are deliberately line-independent. Any patch shifts line
numbers, so matching on lines would report the whole file as "new". What
identifies a finding here is (rule, file, message); lines are carried along
for the report but never participate in matching.

No server access, no I/O - everything in this module is a pure function of
the two finding lists, which is what makes it testable without podman.
"""

from collections import Counter
from dataclasses import dataclass, field

# Keys we keep from a raw SonarQube finding. The API returns a great deal
# more (hashes, effort, debt, changelog) that would only bloat report.json.
_REPORTED_FIELDS = ("rule", "file", "line", "message", "severity", "type", "status")


@dataclass(frozen=True)
class SonarComparison:
    target_resolved: bool
    remaining_target: list[dict] = field(default_factory=list)
    new_issues: list[dict] = field(default_factory=list)
    resolved_incidental: int = 0
    baseline_count: int = 0
    after_count: int = 0


def normalize(finding: dict, project_key: str) -> dict:
    """Flatten one raw API finding into the shape stored in report.json.

    SonarQube reports components as "<projectKey>:<path>"; the project key
    differs between the baseline analysis and every run's analysis, so it has
    to go before anything can be compared."""
    component = finding.get("component", "")
    prefix = f"{project_key}:"
    path = component[len(prefix):] if component.startswith(prefix) else component

    normalized = {
        "rule": finding.get("rule") or finding.get("ruleKey", ""),
        "file": path,
        "line": finding.get("line"),
        "message": finding.get("message", ""),
        "severity": finding.get("severity") or finding.get("vulnerabilityProbability"),
        "type": finding.get("type", "SECURITY_HOTSPOT" if "vulnerabilityProbability" in finding else None),
        "status": finding.get("status"),
    }
    result = {key: normalized[key] for key in _REPORTED_FIELDS}

    # Some rules point at a line other than the one a reader would call "the
    # problem" and put that one in a flow (S2259 blames the dereference and
    # flows back to the null assignment). Only recorded when present, so it
    # doesn't bloat every entry in report.json.
    secondary = secondary_lines(finding)
    if secondary:
        result["secondary_lines"] = secondary
    return result


def secondary_lines(finding: dict) -> list[int]:
    lines = {
        location.get("textRange", {}).get("startLine")
        for flow in finding.get("flows", [])
        for location in flow.get("locations", [])
    }
    return sorted(line for line in lines if line is not None)


def normalize_all(findings: list[dict], project_key: str) -> list[dict]:
    return [normalize(finding, project_key) for finding in findings]


def _identity(finding: dict) -> tuple[str, str, str]:
    """What makes two findings "the same finding" across an edit."""
    return (finding.get("rule", ""), finding.get("file", ""), finding.get("message", ""))


def compare(expected: dict, baseline: list[dict], after: list[dict]) -> SonarComparison:
    """`expected` is the case's issue.json: {rule, file, line, message}.

    Resolution is judged per (rule, file) rather than per exact issue: each
    fixture plants exactly one defect of that rule in that file, and a fix
    that merely moves the same violation a few lines down should not count."""
    rule = expected["rule"]
    expected_file = expected["file"]

    remaining_target = [
        finding for finding in after
        if finding.get("rule") == rule and finding.get("file") == expected_file
    ]

    baseline_counts = Counter(_identity(finding) for finding in baseline)
    seen: Counter = Counter()
    new_issues: list[dict] = []
    for finding in after:
        identity = _identity(finding)
        seen[identity] += 1
        # Only the occurrences beyond what the pristine project already had
        # are new - a rule that fired twice before and twice after is not a
        # regression, but twice before and three times after is.
        if seen[identity] > baseline_counts[identity]:
            new_issues.append(finding)

    resolved_incidental = sum(
        max(0, count - seen[identity])
        for identity, count in baseline_counts.items()
        if not (identity[0] == rule and identity[1] == expected_file)
    )

    return SonarComparison(
        target_resolved=not remaining_target,
        remaining_target=remaining_target,
        new_issues=new_issues,
        resolved_incidental=resolved_incidental,
        baseline_count=len(baseline),
        after_count=len(after),
    )
