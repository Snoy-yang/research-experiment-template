#!/usr/bin/env python3
"""
sweep.py —— 参数 × 随机种子的网格实验

用法：
    python scripts/sweep.py
    python scripts/sweep.py --noise 0.10,0.20,0.30 --seeds 1,2,3,4,5
    python scripts/sweep.py --out results/sweep.csv

产出：
    results/sweep.csv          每行一次运行的原始结果
    终端打印汇总表             每个参数档位的均值/标准差/最值

为什么需要它：
    一次实验只能得到一个数。而同一个参数下，换个随机种子结果就会变。
    如果你只跑一次就下结论「A 比 B 好」，你比较的其实是两次随机波动，
    不是两个参数 —— 这不是实验，是抽签。

    这个脚本做三件事：
    1. 同一配置跑多个种子，得到分布而不是单点
    2. 同一配置同一 seed 跑两次，验证真的可复现
    3. 输出 CSV，让结论可被复查
"""

import argparse
import csv
import importlib.util
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    """按路径加载 src/main.py，避免要求它是个包。"""
    spec = importlib.util.spec_from_file_location("exp_main", ROOT / "src" / "main.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"加载失败：{ROOT / 'src' / 'main.py'}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description="参数 × 种子网格实验")
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--noise", default="0.10,0.20", help="逗号分隔的 noise_std 取值")
    ap.add_argument("--seeds", default="1,2,3,4,5", help="逗号分隔的随机种子")
    ap.add_argument("--out", default="results/sweep.csv")
    ap.add_argument("--repeat-check", action="store_true", default=True,
                    help="额外做一次同种子重复运行的可复现性校验")
    args = ap.parse_args()

    import copy
    import yaml

    cfg_path = ROOT / args.config
    with cfg_path.open("r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f)

    mod = load_runner()
    noises = [float(x) for x in args.noise.split(",") if x.strip()]
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]

    rows = []
    print(f"配置：{cfg_path.relative_to(ROOT)}")
    print(f"网格：{len(noises)} 个 noise_std × {len(seeds)} 个种子 = {len(noises) * len(seeds)} 次运行\n")

    for noise in noises:
        for seed in seeds:
            cfg = copy.deepcopy(base_cfg)
            cfg["experiment"]["noise_std"] = noise
            cfg["experiment"]["seed"] = seed
            m = mod.run(cfg)
            rows.append({
                "noise_std": noise,
                "seed": seed,
                "final_value": round(m["final_value"], 6),
                "mean_abs": round(m["mean_abs"], 6),
            })

    # ---- 可复现性校验：同参数同种子跑两次，结果必须按位相同 ----
    repro_ok = True
    if args.repeat_check:
        cfg = copy.deepcopy(base_cfg)
        cfg["experiment"]["noise_std"] = noises[0]
        cfg["experiment"]["seed"] = seeds[0]
        a = mod.run(cfg)
        b = mod.run(cfg)
        repro_ok = (a["final_value"] == b["final_value"] and a["mean_abs"] == b["mean_abs"])
        print("【可复现性】同配置同种子跑两次：", "一致 ✓" if repro_ok else "不一致 × 严重问题")
        print(f"  final_value 第一次 = {a['final_value']}")
        print(f"  final_value 第二次 = {b['final_value']}\n")

    # ---- 汇总：每档参数一组统计 ----
    print("【分布】同一个参数档位，换种子后的结果")
    print(f"{'noise_std':>10} {'n':>3} {'均值':>14} {'标准差':>12} {'最小':>14} {'最大':>14} {'极差':>12}")
    print("-" * 88)
    for noise in noises:
        vals = [r["final_value"] for r in rows if r["noise_std"] == noise]
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        rng = max(vals) - min(vals)
        print(f"{noise:>10.2f} {len(vals):>3} {mean:>14.6f} {sd:>12.6f} "
              f"{min(vals):>14.6f} {max(vals):>14.6f} {rng:>12.6f}")

    # ---- 两档之间的比较：差多少，够不够大 ----
    if len(noises) >= 2:
        g1 = [r["final_value"] for r in rows if r["noise_std"] == noises[0]]
        g2 = [r["final_value"] for r in rows if r["noise_std"] == noises[1]]
        diff = statistics.mean(g2) - statistics.mean(g1)
        pooled = (statistics.stdev(g1) + statistics.stdev(g2)) / 2 if len(g1) > 1 else 0.0
        print("\n【对照】noise_std %.2f → %.2f" % (noises[0], noises[1]))
        print(f"  均值差   = {diff:+.6f}")
        print(f"  组内波动 = {pooled:.6f}（两档标准差的平均）")
        if pooled > 0:
            ratio = abs(diff) / pooled
            verdict = "信号明显强于噪声" if ratio > 2 else "信号与噪声同量级，不能据此下结论"
            print(f"  信噪比   = {ratio:.2f}  → {verdict}")

    # ---- 单次会骗你多少 ----
    first = [r for r in rows if r["noise_std"] == noises[0]]
    if len(first) > 1:
        vals = [r["final_value"] for r in first]
        mean = statistics.mean(vals)
        worst = max(vals, key=lambda v: abs(v - mean))
        print("\n【单次的陷阱】拿 noise_std=%.2f 这一组举例" % noises[0])
        print(f"  均值        = {mean:.6f}")
        print(f"  最偏的一次  = {worst:.6f}（偏离均值 {abs(worst - mean):.6f}）")
        print(f"  → 如果你只跑了这一次就写进报告，读者拿到的不是 {noises[0]} 的表现，是这一次抽签的结果")

    # ---- 落盘 ----
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["noise_std", "seed", "final_value", "mean_abs"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n原始数据已写入：{out_path.relative_to(ROOT)}（{len(rows)} 行）")

    return 0 if repro_ok else 1


if __name__ == "__main__":
    sys.exit(main())
