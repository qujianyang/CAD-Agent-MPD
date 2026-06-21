"""Offline tests for the shock-mount tool-use enforcement classifier.
Run: .\\mpd\\Scripts\\python.exe -m pytest tests/test_tooluse_guard.py

No LLM / API key: we only exercise _requires_tool, the gate that decides whether a
no-tool answer should trigger the retry guard in DomainAgent.stream().
"""
from agent import _requires_tool


class TestSmallTalkIsToolFree:
    def test_greetings(self):
        for q in ["hi", "Hello!", "hey there", "what can you do?",
                  "who are you", "thanks!"]:
            assert _requires_tool(q, "Hi! I can help size shock isolators.") is False


class TestGenuineClarificationIsToolFree:
    def test_asks_for_missing_mass_no_claim(self):
        q = "Select an isolator."
        a = "Sure — what is the rack mass in kg?"
        assert _requires_tool(q, a) is False

    def test_asks_for_part_number_no_claim(self):
        q = "Can you verify it?"
        a = "Which part number should I check?"
        assert _requires_tool(q, a) is False


class TestTechnicalAnswersRequireTool:
    def test_loophole_question_mark_with_claim(self):
        # The case the user flagged: has a '?' but asserts a part + verdict.
        q = "Select an isolator for 900 kg, max clearance margin."
        a = "CB1500-80 passes. Do you want the full report?"
        assert _requires_tool(q, a) is True

    def test_declarative_verification(self):
        q = "Verify CB1500-30 for a 1500 kg rack."
        a = ("CB1500-30 is suitable. Comp-Wall GT = 2.699 G vs limit 10.0 G "
             "-> 26.99% utilization (PASS).")
        assert _requires_tool(q, a) is True

    def test_empty_answer_requires_tool(self):
        # A technical question that produced no answer at all must still be caught.
        q = "What is the stiffness and rated travel of CB1400-30?"
        assert _requires_tool(q, "") is True

    def test_recommendation_without_question(self):
        q = "What mount for a 1200 kg cabinet?"
        a = "Recommendation: CB1400-60 in 6 bottom + 4 wall configuration."
        assert _requires_tool(q, a) is True
