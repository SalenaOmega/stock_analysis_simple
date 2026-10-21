# 宏观指标跟踪与股债性价比分析（个人研究）

## 项目说明

本项目基于公开宏观数据，做两件事：

1. **股债风险溢价（ERP）回测** — 以沪深300盈利收益率（1/PE_TTM）与10年期国债收益率之差衡量股债相对性价比，统计5年滚动历史分位，检验其与未来6个月股指收益的相关性。
2. **宏观指标月度跟踪** — 整理 CPI、PPI、PMI、M2 四项指标为2015年至今的月度跟踪表，用折线图与热力图观察增长与通胀组合的切换。

数据来源为 AKShare 公开接口。项目脱胎于 [zhysh3/a-share-monitor](https://github.com/zhysh3/a-share-monitor) 的 `backtest_erp.py`，在此基础上做了以下个人改动：

- 将原六种 ERP 口径简化为沪深300一种（盈利收益率口径），删除全A中位数和全A等权两种估值数据来源。
- 以6个月未来收益为主要检验窗口（原脚本以12个月为主），分组和滚动稳定性检验均围绕6个月展开，12个月保留作参考。
- 剔除未完整结束的当月数据，只保留已结束月份的月末值。
- 新增 `macro_tracker.py` 模块，抓取并整理 CPI/PPI/PMI/M2 月度数据。
- 新增 matplotlib 图表：ERP 时序与分位带、滚动分位时序、ERP 分位 vs 未来6个月收益散点图、宏观指标折线图与标准化热力图。

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

## 局限

- **相关性为描述性证据。** 月度样本的收益窗口存在重叠，有效独立观测数少于样本数 N，IC 值不能直接当作严格显著性检验的结果。
- **数据依赖上游接口。** AKShare 接口的可用性和列名可能随版本变化，脚本中的列名匹配逻辑需相应调整。
- **未覆盖简历全部目标。** 社融跟踪和风险平价资产配置尚未实现，当前版本只完成前两条。
- **ERP 口径为盈利收益率，非股息率。** 与部分文献的"股债利差"定义不同，使用时需注明。
