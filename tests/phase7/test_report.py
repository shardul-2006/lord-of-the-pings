import json
import re

NUM = re.compile(r"\d+(?:\.\d+)?")


def _allowed_numbers(obj, acc):
    """Every way a number from the result JSON may be printed in the report."""
    if isinstance(obj, bool) or obj is None:
        return acc
    if isinstance(obj, (int, float)):
        v = float(obj)
        if v.is_integer():
            acc.add(str(int(v)))
        acc.update({f"{v:.1f}", f"{v:.2f}", f"{v * 100:.1f}"})
    elif isinstance(obj, str):
        acc.update(NUM.findall(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            acc.update(NUM.findall(str(k)))
            _allowed_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _allowed_numbers(v, acc)
    return acc


def test_report_generated(all_result):
    _, out = all_result
    text = (out / "REPORT.md").read_text(encoding="utf-8")
    for section in ("Main results", "Ablation", "Latency", "By carrier", "Proposed Target"):
        assert section in text


def test_every_number_in_report_tables_comes_from_the_result(all_result):
    d, out = all_result
    allowed = _allowed_numbers(json.loads(json.dumps(d)), set())
    text = (out / "REPORT.md").read_text(encoding="utf-8")
    checked = 0
    for line in text.splitlines():
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        for cell in cells[1:]:  # first column is a label
            for num in NUM.findall(cell):
                checked += 1
                assert num in allowed, f"{num!r} in {line!r} is not in the result file"
    assert checked > 50
