import json
import sys

d = json.load(sys.stdin)
expr = sys.argv[1]
ok = eval(expr, {"__builtins__": {"len": len, "any": any, "all": all, "set": set, "sorted": sorted}}, {"d": d})  # noqa: E501, S307
if not ok:
    print("ASSERT FAILED:", expr)
    print(json.dumps(d, indent=2)[:2000])
    sys.exit(1)
print("ok:", expr)
