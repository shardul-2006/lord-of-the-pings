import pytest

from rag_shield.rag.llm import MockLLM

TASK = "Score this candidate for a software engineer role"


class RecordingLLM(MockLLM):
    """MockLLM that records the tools flag at every call."""

    def __init__(self):
        super().__init__()
        self.tools_enabled = True  # as an agent would have outside the check
        self.seen_tools: list[bool] = []
        self.prompts: list[str] = []

    def generate(self, prompt):
        self.seen_tools.append(self.tools_enabled)
        self.prompts.append(prompt)
        return super().generate(prompt)


@pytest.fixture
def recording_llm():
    return RecordingLLM()
