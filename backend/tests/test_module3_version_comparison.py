import asyncio

from app.modules.module_03_proposal.comparison import build_version_comparison, generate_comparison_summary


def _report(score, checks):
    return {
        "reportSummary": {"score": score},
        "categories": [{"name": "Structure", "checks": checks}],
    }


def _check(rule, status="FAIL", page=1, difference="old wording"):
    return {
        "id": rule,
        "name": rule.replace("_", " "),
        "status": status,
        "location": {"section": "Methodology", "page": page, "field": rule},
        "difference": difference,
    }


def test_comparison_matches_stable_issue_identity_not_wording():
    previous = _report(60, [_check("margin", difference="previous wording")])
    current = _report(82, [_check("margin", difference="updated wording")])

    result = build_version_comparison(
        previous_report=previous,
        current_report=current,
        previous_version=1,
        current_version=2,
        previous_template_version_id=4,
        current_template_version_id=4,
    )

    assert result["previousIssueCount"] == 1
    assert result["currentIssueCount"] == 1
    assert result["fixedIssues"] == []
    assert len(result["remainingIssues"]) == 1
    assert len(result["unchangedIssues"]) == 0
    assert result["scoreDifference"] == 22
    assert result["overallResult"] == "Improved"


def test_comparison_separates_fixed_remaining_new_and_unchanged():
    previous = _report(60, [_check("fixed"), _check("remaining"), _check("unchanged", difference="same")])
    current = _report(82, [_check("remaining", difference="updated"), _check("unchanged", difference="same"), _check("new")])

    result = build_version_comparison(
        previous_report=previous,
        current_report=current,
        previous_version=1,
        current_version=2,
        previous_template_version_id=4,
        current_template_version_id=5,
    )

    assert len(result["fixedIssues"]) == 1
    assert len(result["remainingIssues"]) == 2
    assert len(result["newIssues"]) == 1
    assert len(result["unchangedIssues"]) == 1
    assert result["differentTemplateVersions"] is True
    assert result["templateVersionMessage"] == "Comparison based on different template versions."


def test_ai_summary_prompt_contains_only_structured_comparison_data():
    comparison = build_version_comparison(
        previous_report=_report(60, [_check("fixed")]),
        current_report=_report(82, []),
        previous_version=1,
        current_version=2,
        previous_template_version_id=4,
        current_template_version_id=4,
    )
    calls = []

    async def runner(prompt, schema, **kwargs):
        calls.append((prompt, schema, kwargs))
        return {"status": "COMPLETED", "payload": {"summary": "Version 2 improves compliance."}, "model": "llama3.5"}

    result = asyncio.run(generate_comparison_summary(comparison, runner, rate_key="test-comparison"))
    assert result["summary"] == "Version 2 improves compliance."
    assert "fixedIssueCount" in calls[0][0]
    assert "proposal.pdf" not in calls[0][0]
    assert "student document text" not in calls[0][0]
    assert "structured_version_comparison" in result["inputScope"].lower()
