#!/usr/bin/env python3
"""
paired.py —— 配对分析：同一批种子，两档参数，判「能不能下结论」

用法：
    python scripts/paired.py results/sweep.csv
    python scripts/paired.py results/sweep.csv --lv1 0.10 --lv2 0.20
    python scripts/paired.py results/sweep.csv --metrics final_value,mean_abs

它回答三个问题（顺序不能颠倒）：

  1. 这个指标能不能用来比均值？      看 CV = 组内标准差 / 均值
     CV > 1 → 组内波动比均值还大，均值本身不可靠，后面全部免谈

  2. 差值显著吗？                     看 t = 差值均值 / 差值标准误
     t <= 2 → 差值淹没在噪声里，不能写进结论

  3. 该报差值还是比值？               看比值这一路稳不稳
     同 seed 下比值几乎恒定 → 说明效应是乘性的，报倍数，别报差值

为什么配对：
    同一个 seed 跑两档参数，两组共享同一段随机序列（CRN）。
    逐个种子先做差/做比，再对差值序列求均值和标准误 ——
    随机成分在「配对内部」被扣掉一部分，剩下的是真正的效应。

    注意：配对不是万能的。本例 final_value 的效应是纯乘性的，
    配对差值里仍带着随机量 z（差值 = 0.10 · z），所以 t 依旧过不了 2。
    真正救场的是指标选择（见 lesson05 第四节），不是配对本身。

输出：终端表格 + 可选 --out 落盘 CSV
"""

import argparse
import csv
import statistics as st
import sys
from pathlib import Path


def load(csv_path: Path) -> list[dict]:
    with csv_path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def group(rows: list[dict], level: float, metric: str) -> dict[int, float]:
    """按 seed 取出某档参数下某指标的取值：{seed: value}"""
    out = {}
    for r in rows:
        if abs(float(r["noise_std"]) - level) < 1e-9:
            out[int(r["seed"])] = float(r[metric])
    return out


def cv(values: list[float]) -> float:
    """变异系数：标准差 / |均值|。跨零的指标不要算 CV（分母会失真）。"""
    if len(values) < 2:
        return float("nan")
    m = st.mean(values)
    if abs(m) < 1e-12:
        return float("inf")          # 均值≈0，CV 无意义，按「不可用」处理
    return st.stdev(values) / abs(m)


def paired_stats(a: dict[int, float], b: dict[int, float]) -> dict:
    """只取两档都跑过的 seed，逐个配对。"""
    seeds = sorted(set(a) & set(b))
    diffs = [b[s] - a[s] for s in seeds]
    ratios = [b[s] / a[s] for s in seeds if abs(a[s]) > 1e-12]
    n = len(diffs)
    mean_d = st.mean(diffs)
    sd_d = st.stdev(diffs) if n > 1 else 0.0
    se_d = sd_d / n ** 0.5 if n > 1 else float("nan")
    t = mean_d / se_d if se_d and se_d == se_d and se_d > 0 else float("inf")
    return {
        "seeds": seeds, "diffs": diffs, "ratios": ratios, "n": n,
        "mean_d": mean_d, "sd_d": sd_d, "se_d": se_d, "t": t,
        "mean_r": st.mean(ratios) if ratios else float("nan"),
        "min_r": min(ratios) if ratios else float("nan"),
        "max_r": max(ratios) if ratios else float("nan"),
        "rng_r": (max(ratios) - min(ratios)) if ratios else float("nan"),
    }


def report(metric: str, a: dict, b: dict, lv1: float, lv2: float) -> bool:
    """打印一个指标的体检结果，返回「是否可下结论」。"""
    va, vb = list(a.values()), list(b.values())
    s = paired_stats(a, b)

    print(f"\n{'=' * 76}")
    print(f"指标：{metric}")
    print(f"{'=' * 76}")

    # ---- 1. 指标体检 ----
    cva, cvb = cv(va), cv(vb)
    print(f"[1] 指标体检（CV = 组内标准差 / 均值）")
    print(f"    lv={lv1:.2f}  均值 {st.mean(va):+12.6f}  标准差 {st.stdev(va):10.6f}  CV {cva:7.3f}")
    print(f"    lv={lv2:.2f}  均值 {st.mean(vb):+12.6f}  标准差 {st.stdev(vb):10.6f}  CV {cvb:7.3f}")
    ok_cv = cva <= 1.0 and cvb <= 1.0
    print(f"    → {'CV<=1，均值可用' if ok_cv else 'CV>1，均值本身不可靠，不能用来比大小'}")

    # ---- 2. 差值显著性 ----
    print(f"[2] 配对差值（同 seed 先做差，再求均值 ± 标准误）")
    print(f"    n = {s['n']}   差值均值 {s['mean_d']:+.6f}   标准差 {s['sd_d']:.6f}   标准误 {s['se_d']:.6f}")
    print(f"    t = {s['t']:+.2f}   （门限 2）")
    ok_t = abs(s["t"]) > 2
    print(f"    → {'差值显著，可以写进结论' if ok_t else '差值被噪声淹没，不能写进结论'}")

    # ---- 3. 比值稳不稳 ----
    print(f"[3] 配对比值（同 seed 先做比）")
    print(f"    比值均值 {s['mean_r']:.6f}   最小 {s['min_r']:.6f}   最大 {s['max_r']:.6f}   极差 {s['rng_r']:.2e}")
    stable = s["rng_r"] < 1e-3
    print(f"    → {'比值几乎恒定，效应是乘性的：报倍数' if stable else '比值不稳：效应不是纯乘性，报差值+置信区间'}")

    usable = ok_cv and ok_t
    print(f"\n    本指标能否下结论：{'能' if usable else '不能'}")
    return usable


def main() -> int:
    ap = argparse.ArgumentParser(description="配对分析：两档 × 多指标，判能不能下结论")
    ap.add_argument("csv", help="sweep.py 产出的原始结果 CSV")
    ap.add_argument("--lv1", type=float, default=None, help="对照档（默认取最小两档中小的那个）")
    ap.add_argument("--lv2", type=float, default=None, help="实验档")
    ap.add_argument("--metrics", default="", help="逗号分隔；默认分析 CSV 里除 noise_std/seed 外的所有数值列")
    args = ap.parse_args()

    path = Path(args.csv)
    if not path.exists():
        print(f"找不到文件：{path}", file=sys.stderr)
        return 2
    rows = load(path)
    if not rows:
        print("CSV 是空的", file=sys.stderr)
        return 2

    levels = sorted({float(r["noise_std"]) for r in rows})
    lv1 = args.lv1 if args.lv1 is not None else levels[0]
    lv2 = args.lv2 if args.lv2 is not None else (levels[1] if len(levels) > 1 else levels[0])
    if lv1 == lv2:
        print("只有一档参数，没有可配对的对象", file=sys.stderr)
        return 2

    if args.metrics.strip():
        metrics = [m.strip() for m in args.metrics.split(",")]
    else:
        metrics = [k for k in rows[0].keys() if k not in ("noise_std", "seed")]

    print(f"文件：{path}")
    print(f"对照：noise_std {lv1:.2f}  →  {lv2:.2f}")

    verdicts = {}
    for m in metrics:
        a = group(rows, lv1, m)
        b = group(rows, lv2, m)
        if not a or not b:
            continue
        verdicts[m] = report(m, a, b, lv1, lv2)

    # ---- 总结：哪个指标能用 ----
    print(f"\n{'=' * 76}")
    print("总结")
    for m, ok in verdicts.items():
        print(f"  {m:<14} {'✓ 可以写进结论' if ok else '× 不足以支持结论'}")
    print("  （一个都不能用时，问题不在样本量，在指标 —— 加种子救不了）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
