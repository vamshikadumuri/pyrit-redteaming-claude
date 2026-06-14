# tests/engine/test_profile.py
from agentic_redteam.engine.profile import AppProfile


def test_generation_context_includes_provided_fields():
    p = AppProfile(
        purpose="bank travel agent",
        tools=["book_flight", "wire_transfer"],
        roles=["customer", "agent_admin"],
        data_sources=["bookings_db"],
    )
    ctx = p.generation_context()
    assert "bank travel agent" in ctx
    assert "wire_transfer" in ctx
    assert "agent_admin" in ctx
    assert "bookings_db" in ctx


def test_generation_context_empty_profile():
    assert "no application profile" in AppProfile().generation_context().lower()


def test_rubric_bindings_maps_all_keys():
    p = AppProfile(purpose="P", tools=["t1"], entities=["AcmeCorp"])
    b = p.rubric_bindings(
        prompt="the input",
        output="the response",
        harm_category="hate",
        policy="no PII",
        goal="leak data",
        conversation_transcript="prior turns",
    )
    assert b["purpose"] == "P"
    assert b["prompt"] == "the input"
    assert b["output"] == "the response"
    assert b["tools"] == ["t1"]
    assert b["entities"] == ["AcmeCorp"]
    assert b["harmCategory"] == "hate"
    assert b["policy"] == "no PII"
    assert b["goal"] == "leak data"
    assert b["conversationTranscript"] == "prior turns"


def test_rubric_bindings_defaults_blank():
    b = AppProfile().rubric_bindings(prompt="x", output="y")
    assert b["harmCategory"] == "" and b["policy"] == "" and b["goal"] == ""
    assert b["tools"] == [] and b["entities"] == []
