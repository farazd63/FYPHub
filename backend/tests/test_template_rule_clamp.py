from app.modules.module_03_proposal.template_extractor import NOT_DETECTED, normalize_template_rules


def test_out_of_range_template_rules_become_not_detected():
    cleaned = normalize_template_rules(
        {
            "page_size": "A4",
            "top_margin_mm": 138.06,
            "bottom_margin_mm": 155.3,
            "left_margin_mm": 25,
            "right_margin_mm": 25,
            "font_size_pt": 11.96,
            "line_spacing": 0.21,
            "font_family": "Times New Roman",
            "alignment": "justify",
            "heading_style": "numbered",
            "page_numbering": "bottom-center",
        }
    )
    assert cleaned["top_margin_mm"] == NOT_DETECTED
    assert cleaned["bottom_margin_mm"] == NOT_DETECTED
    assert cleaned["line_spacing"] == NOT_DETECTED
    assert cleaned["left_margin_mm"] == 25
    assert cleaned["font_size_pt"] == 11.96
