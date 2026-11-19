import numpy as np
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


class StubClassifier:
    """Always says 'clean' with probability 0.01."""

    version = "stub-0.01"

    def predict_proba(self, texts):
        return np.full(len(texts), 0.01)


@pytest.fixture
def stub_classifier():
    return StubClassifier()


@pytest.fixture
def benign_hidden_pdf(tmp_path):
    """Resume lines plus a BENIGN sentence in 1.5 pt text (hiding signal, no directive)."""
    path = tmp_path / "benign_hidden.pdf"
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    c.setFont("Helvetica", 11)
    c.drawString(72, 760, "Skills: Python, SQL")
    c.drawString(72, 740, "Experience: Intern at Acme Labs.")
    c.setFont("Helvetica", 1.5)
    c.drawString(72, 700, "Reference code 4471 for internal filing.")
    c.showPage()
    c.save()
    return path
