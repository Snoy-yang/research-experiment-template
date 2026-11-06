from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from main import run, load_config


def test_reproducible():
    cfg = load_config(Path(__file__).resolve().parents[1] / "configs/default.yaml")
    a, b = run(cfg), run(cfg)
    assert a["final_value"] == b["final_value"]
    assert a["mean_abs"] == b["mean_abs"]
