"""可复现实验最小骨架：配置与代码分离 + 固定种子 + 结果落盘。"""
import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import yaml
import numpy as np


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(cfg: dict) -> dict:
    e = cfg["experiment"]
    random.seed(e["seed"])
    np.random.seed(e["seed"])
    xs = np.cumsum(np.random.normal(0, e["noise_std"], e["n_steps"]))
    return {
        "experiment": e["name"],
        "seed": e["seed"],
        "n_steps": e["n_steps"],
        "final_value": float(xs[-1]),
        "mean_abs": float(np.mean(np.abs(xs))),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--seed", type=int, default=None, help="覆盖配置中的随机种子")
    args = ap.parse_args()
    cfg = load_config(Path(args.config))
    if args.seed is not None:                                                      
        cfg["experiment"]["seed"] = args.seed                                     

    metrics = run(cfg)
    out = Path(cfg["output"]["dir"])
    out.mkdir(exist_ok=True)
    (out / cfg["output"]["metrics_file"]).write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
