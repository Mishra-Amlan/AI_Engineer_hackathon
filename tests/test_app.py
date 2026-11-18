from streamlit.testing.v1 import AppTest

def test_workbench_renders_all_tabs_without_exception():
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 6

def test_tier3_hitl_flow_in_ui():
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    next(b for b in at.button if "Submit sample Tier-3" in b.label).click().run()
    assert not at.exception and any("Approve" == b.label for b in at.button)
