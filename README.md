# 可复现实验模板（阶段 1 教具）

一次实验必须满足四条，才算「可复现」：

1. 参数不在代码里，在 `configs/` 的 YAML 里
2. 随机种子写进配置并固定
3. 一次实验一条命令：`bash run.sh`
4. 结果落到 `results/`，日志落到 `logs/`，两者都不进版本库

目录约定：
- `configs/` 参数快照（每次实验复制一份，带日期）
- `src/` 代码
- `tests/` 最小自测
- `results/` 指标与产物（被 .gitignore 忽略）
- `logs/` 运行日志（被 .gitignore 忽略）

判据：连跑两次 `bash run.sh`，两次 `results/metrics.json` 内容完全一致（时间戳字段除外）。
