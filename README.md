# 宏观指标跟踪与股债性价比分析（个人研究）

## 项目说明

本项目基于公开宏观数据，做一定分析，未来可能会进一步深入：

1. **股债风险溢价（ERP）回测** — 以沪深300盈利收益率（1/PE_TTM）与10年期国债收益率之差衡量股债相对性价比，统计5年滚动历史分位，检验其与未来6个月股指收益的相关性。
2. **宏观指标月度跟踪** — 整理 CPI、PPI、PMI、M2 四项指标为2015年至今的月度跟踪表，用折线图与热力图观察增长与通胀组合的切换。



## 运行方式

```bash
# 首次运行（联网抓数并缓存）
.\.venv\Scripts\python.exe backtest_erp.py
.\.venv\Scripts\python.exe macro_tracker.py

# 后续运行（仅用缓存，不联网）
.\.venv\Scripts\python.exe backtest_erp.py --offline
.\.venv\Scripts\python.exe macro_tracker.py --offline
```

## 环境配置

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe akshare pandas numpy tabulate matplotlib
```

依赖版本（本次运行所用）：

| 包 | 版本 |
|---|---|
| akshare | 1.19.1 |
| pandas | 3.0.6 |
| numpy | 2.4.6 |
| matplotlib | 3.11.2 |
| tabulate | 0.10.0 |
| Python | 3.11.15 |

## 输出文件

| 文件 | 说明 |
|---|---|
| `erp_bt_result.md` | ERP 回测文字报告 |
| `erp_bt_monthly.csv` | ERP 月度数据宽表 |
| `erp_bt_charts.png` | ERP 三联图（时序、滚动分位、散点） |
| `macro_monthly.csv` | 宏观指标月度宽表 |
| `macro_charts.png` | CPI/PPI/PMI/M2 折线图 |
| `macro_heatmap.png` | 最近60个月标准化热力图 |
| `erp_bt_cache/` | ERP 数据缓存 |
| `macro_cache/` | 宏观数据缓存 |

## 主要发现

### ERP 回测

以2016年1月起的主样本为例：

- 线性映射版本（2%–7%区间）与未来6个月收益的 Spearman 相关约为 0.31，5年滚动分位版本约为 0.12。
- 分段结果显示，线性映射版本在2011–2015、2016–2020、2021至今三个子区间的 IC6m 均为正（0.69/0.48/0.63），方向一致。
- 5年滚动分位在这段主样本中没有表现得更强，可能是因为分位改变了跨时期比较的参照，在不同市场阶段对信号的强弱有不同影响。
- 分组检验中，最便宜组6个月平均收益约 9.1%，最贵组约 -1.9%，多空差约 11 个百分点。

### 宏观跟踪

- 四项指标均更新至2026年9月（截至本次运行）。
- PMI 保留指数水平（非同比），以50为荣枯线参考。
- 热力图展示最近60个月的标准化值，可观察增长与通胀组合的月度切换。


