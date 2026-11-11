import importlib.util
import os
import sys

PLAN = os.path.join(
    os.path.dirname(__file__),
    "..",
    "skills",
    "deploy-scheduled-tasks",
    "scripts",
    "plan.py",
)

spec = importlib.util.spec_from_file_location("plan", PLAN)
plan = importlib.util.module_from_spec(spec)
sys.modules["plan"] = plan
spec.loader.exec_module(plan)
