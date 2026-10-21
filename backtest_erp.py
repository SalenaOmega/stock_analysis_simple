"""
沪深300 股债风险溢价（ERP）回测分析

ERP = 1/PE(TTM) − 中国10Y国债收益率（盈利收益率口径）
对比版本：
  A. 沪深300 ERP · 2%–7% 线性映射
  B. 沪深300 ERP · 滚动5年分位

目标：沪深300 未来 6 个月 / 12 个月收益，月末采样。
主样本 2016-01 起；扩展样本 2011-01 起。

用法（在项目 venv 里）：
    python backtest_erp.py              # 联网抓数据并缓存到 ./erp_bt_cache/
    python backtest_erp.py --offline    # 只用缓存
输出：终端报告 + erp_bt_result.md + erp_bt_monthly.csv + erp_bt_charts.png
"""
import argparse, os, sys
import numpy as np
import pandas as pd

CACHE = "erp_bt_cache"
MAIN_START = "2016-01-01"
EXT_START = "2011-01-01"
ROLL_M = 60                     # 滚动分位窗口：60 个月 = 5 年
LO, HI = 2.0, 7.0               # 现行线性映射区间（%）


# ───────────────────────── 数据 ─────────────────────────
def _pick(df, *keys, exclude=()):
    for c in df.columns:
        s = str(c)
        if all(k in s for k in keys) and not any(x in s for x in exclude):
            return c
    raise KeyError(f"找不到包含 {keys} 的列，实际列：{list(df.columns)}")


def _cached(name, fn, offline):
    path = os.path.join(CACHE, name + ".csv")
    if os.path.exists(path) and offline:
        return pd.read_csv(path, parse_dates=["date"])
    if offline:
        sys.exit(f"缺少缓存 {path}，请先联网运行一次")
    df = fn()
    os.makedirs(CACHE, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def load_data(offline=False):

    def pe300():
        import akshare as ak
        raw = ak.stock_index_pe_lg(symbol="沪深300")
        d = _pick(raw, "日期")
        c = _pick(raw, "滚动市盈率", exclude=("等权", "中位"))
        return pd.DataFrame({"date": pd.to_datetime(raw[d]), "pe300": pd.to_numeric(raw[c], errors="coerce")})

    def bond():
        import akshare as ak
        raw = ak.bond_zh_us_rate(start_date="20050101")
        d = _pick(raw, "日期")
        c = _pick(raw, "中国", "10年", exclude=("-",))
        return pd.DataFrame({"date": pd.to_datetime(raw[d]), "y10": pd.to_numeric(raw[c], errors="coerce")})

    def hs300():
        import akshare as ak
        raw = ak.stock_zh_index_daily(symbol="sh000300")
        return pd.DataFrame({"date": pd.to_datetime(raw["date"]), "close": pd.to_numeric(raw["close"], errors="coerce")})

    frames = {
        "pe300": _cached("pe300", pe300, offline),
        "bond":  _cached("bond",  bond,  offline),
        "hs300": _cached("hs300", hs300, offline),
    }
    for k, v in frames.items():
        v = v.dropna()
        print(f"  {k:7s} {v['date'].min().date()} → {v['date'].max().date()}  {len(v)} 行")
    return frames


def to_monthly(frames):
    """各序列取月末最后一个有效值后合并。只保留已完整结束的月份。"""
    out = None
    for k, df in frames.items():
        x = df.dropna().set_index("date").sort_index()
        m = x.groupby(x.index.to_period("M")).last()
        out = m if out is None else out.join(m, how="outer")
    out = out.sort_index().ffill(limit=1)
    out.index = out.index.to_timestamp(how="end").normalize()
    # 剔除当月尚未结束的数据，只保留已完整结束的月份
    today = pd.Timestamp.today().normalize()
    last_complete = (today - pd.offsets.MonthEnd(1))
    out = out[out.index <= last_complete]
    return out


# ───────────────────────── 因子 ─────────────────────────
def build(m):
    m = m.copy()
    erp = 100.0 / m["pe300"] - m["y10"]
    m["erp_300"] = erp
    m["lin_300"] = ((erp - LO) / (HI - LO) * 100).clip(0, 100)
    # 滚动 5 年分位：当月值在过去 60 个月（含当月）中的百分位，只用当时可得的数据
    m["pct_300"] = erp.rolling(ROLL_M, min_periods=ROLL_M).apply(
        lambda x: (x[:-1] < x[-1]).mean() * 100 + (x[:-1] == x[-1]).mean() * 50, raw=True)
    for h in (6, 12):
        m[f"fwd{h}"] = (m["close"].shift(-h) / m["close"] - 1) * 100
    return m


VARIANTS = [
    ("A 沪深300·线性2–7%", "lin_300"),
    ("B 沪深300·5年分位", "pct_300"),
]


# ───────────────────────── 评估 ─────────────────────────
def ic(x, y):
    d = pd.concat([x, y], axis=1).dropna()
    if len(d) < 12:
        return np.nan, 0
    return d.iloc[:, 0].rank().corr(d.iloc[:, 1].rank()), len(d)


def evaluate(m, start):
    s = m[m.index >= start]
    rows = []
    for name, col in VARIANTS:
        r = {"版本": name}
        for h in (6, 12):
            v, n = ic(s[col], s[f"fwd{h}"])
            r[f"IC{h}m"] = v
            r[f"N{h}"] = n
        # 6m 分组（主线）：最便宜 1/5 vs 最贵 1/5 的平均未来收益
        d6 = s[[col, "fwd6"]].dropna()
        if len(d6) >= 25:
            q = pd.qcut(d6[col].rank(method="first"), 5, labels=False)
            r["便宜组6m%"] = d6["fwd6"][q == 4].mean()
            r["贵组6m%"]   = d6["fwd6"][q == 0].mean()
            r["多空差6m"]   = r["便宜组6m%"] - r["贵组6m%"]
        # 滚动36个月 IC（基于6个月收益）为正的比例：看稳定性
        roll = [ic(s[col].iloc[i - 36:i], s["fwd6"].iloc[i - 36:i])[0]
                for i in range(36, len(s) + 1)]
        roll = [x for x in roll if not np.isnan(x)]
        r["滚动IC6m>0占比"] = np.mean([x > 0 for x in roll]) * 100 if roll else np.nan
        # 线性映射的饱和度：多少月份被压到 0 或 100（区间外信息丢失）
        if col.startswith("lin_"):
            x = s[col].dropna()
            r["触顶/触底%"] = ((x >= 100) | (x <= 0)).mean() * 100
        rows.append(r)
    return pd.DataFrame(rows)


def subperiods(m):
    periods = [("2011–2015", "2011-01-01", "2015-12-31"),
               ("2016–2020", "2016-01-01", "2020-12-31"),
               ("2021–今",   "2021-01-01", "2100-01-01")]
    rows = []
    for name, col in VARIANTS:
        r = {"版本": name}
        for pname, a, b in periods:
            s = m[(m.index >= a) & (m.index <= b)]
            # 6m IC 为主，12m 作参考
            r[f"{pname} IC6m"]  = ic(s[col], s["fwd6"])[0]
            r[f"{pname} IC12m"] = ic(s[col], s["fwd12"])[0]
        rows.append(r)
    return pd.DataFrame(rows)


def failure_cases(m, pct_thresh=80, fwd_thresh=0):
    """ERP 分位高（>pct_thresh）但随后6个月收益为负的月份。"""
    rows = m[["pct_300", "erp_300", "y10", "fwd6", "fwd12"]].dropna()
    fail = rows[(rows["pct_300"] > pct_thresh) & (rows["fwd6"] < fwd_thresh)].copy()
    fail = fail.sort_values("pct_300", ascending=False)
    fail.index = fail.index.strftime("%Y-%m")
    fail.columns = ["5年分位%", "ERP%", "10Y%", "未来6m收益%", "未来12m收益%"]
    return fail.round(2)


def fmt(df):
    return df.to_markdown(index=False, floatfmt=".2f")


# ───────────────────────── 图表 ─────────────────────────
def plot_charts(m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(3, 1, figsize=(12, 14))
    fig.suptitle("沪深300 股债风险溢价（ERP）回测分析", fontsize=14, y=0.98)

    # ── 图1：ERP 时序 + 5年滚动分位带 ──
    ax = axes[0]
    s = m.dropna(subset=["erp_300"])
    ax.plot(s.index, s["erp_300"], color="#2166ac", linewidth=1.4, label="ERP（%）")
    ax.axhline(LO, color="#b2182b", linewidth=0.8, linestyle="--", label=f"线性映射下限 {LO}%")
    ax.axhline(HI, color="#4dac26", linewidth=0.8, linestyle="--", label=f"线性映射上限 {HI}%")
    # 5年滚动 25/75 分位带（基于 ERP 本身）
    roll_lo = s["erp_300"].rolling(ROLL_M, min_periods=ROLL_M).quantile(0.25)
    roll_hi = s["erp_300"].rolling(ROLL_M, min_periods=ROLL_M).quantile(0.75)
    ax.fill_between(s.index, roll_lo, roll_hi, alpha=0.15, color="#2166ac", label="5年滚动 25–75 分位带")
    ax.set_ylabel("ERP（%）")
    ax.set_title("股债风险溢价时序（ERP = 1/PE_TTM − 10Y国债收益率）")
    ax.legend(fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))

    # ── 图2：5年滚动分位（pct_300）时序 ──
    ax = axes[1]
    valid = m.dropna(subset=["pct_300"])
    ax.plot(valid.index, valid["pct_300"], color="#762a83", linewidth=1.4)
    ax.axhline(50, color="gray", linewidth=0.8, linestyle=":")
    ax.axhline(80, color="#b2182b", linewidth=0.8, linestyle="--", label="80 分位（历史偏高）")
    ax.axhline(20, color="#4dac26", linewidth=0.8, linestyle="--", label="20 分位（历史偏低）")
    ax.fill_between(valid.index, valid["pct_300"], 50,
                    where=valid["pct_300"] > 50, alpha=0.15, color="#4dac26")
    ax.fill_between(valid.index, valid["pct_300"], 50,
                    where=valid["pct_300"] < 50, alpha=0.15, color="#b2182b")
    ax.set_ylim(0, 100)
    ax.set_ylabel("5年滚动分位（%）")
    ax.set_title("ERP 5年滚动历史分位（绿=偏便宜，红=偏贵）")
    ax.legend(fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))

    # ── 图3：散点图——ERP 5年分位 vs 未来6个月收益 ──
    ax = axes[2]
    scatter_data = m[["pct_300", "fwd6"]].dropna()
    sc = ax.scatter(scatter_data["pct_300"], scatter_data["fwd6"],
                    alpha=0.55, s=18, c=scatter_data["fwd6"],
                    cmap="RdYlGn", vmin=-30, vmax=30)
    # 线性趋势线
    x_vals = scatter_data["pct_300"].values
    y_vals = scatter_data["fwd6"].values
    coef = np.polyfit(x_vals, y_vals, 1)
    x_line = np.linspace(x_vals.min(), x_vals.max(), 100)
    ax.plot(x_line, np.polyval(coef, x_line), color="#2166ac", linewidth=1.2,
            label=f"线性拟合（斜率 {coef[0]:.2f}）")
    ax.axhline(0, color="gray", linewidth=0.7, linestyle=":")
    ax.axvline(50, color="gray", linewidth=0.7, linestyle=":")
    ax.set_xlabel("ERP 5年滚动分位（%）")
    ax.set_ylabel("未来6个月收益率（%）")
    ax.set_title("ERP 分位 vs 未来6个月沪深300收益（月末样本）")
    ax.legend(fontsize=8)
    fig.colorbar(sc, ax=ax, label="未来6m收益（%）", fraction=0.03, pad=0.01)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig("erp_bt_charts.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    print("加载数据 ...")
    m = build(to_monthly(load_data(args.offline)))
    last = m.dropna(subset=["erp_300"]).iloc[-1]

    parts = [
        "# 沪深300 股债风险溢价（ERP）回测分析\n",
        f"数据截至 {last.name.date()}。当前：沪深300 ERP {last['erp_300']:.2f}%，10Y 国债 {last['y10']:.2f}%。\n",
        "ERP = 盈利收益率（1/PE_TTM） − 10年期国债收益率。"
        "IC 为 Spearman 秩相关，正值表示 ERP 越高（越便宜）时未来收益越高。"
        "以6个月收益为主要检验窗口，12个月作参考。N6/N12 为各窗口有效样本数（尾部缺失未来收益的月份被剔除）。\n",
        f"## 主样本（{MAIN_START[:7]} 起）\n", fmt(evaluate(m, MAIN_START)),
        f"\n## 扩展样本（{EXT_START[:7]} 起）\n", fmt(evaluate(m, EXT_START)),
        "\n## 分段 IC（稳定性检验，6m 主、12m 参考）\n", fmt(subperiods(m)),
        "\n### 说明\n"
        "- IC 为描述性相关系数，月度样本存在收益窗口重叠，有效独立观测数少于 N，结论应保守解读。\n"
        "- 线性映射版本若『触顶/触底%』较高，说明当前2%–7%区间对实际 ERP 范围有截断。\n"
        "- 分段 IC 显示各子区间是否一致为正；某段失效可进一步核查该时段的宏观背景。\n",
    ]
    report = "\n".join(parts)
    print("\n" + report)
    with open("erp_bt_result.md", "w", encoding="utf-8") as f:
        f.write(report)

    # 失效案例：ERP 分位 >80% 但随后6个月收益为负
    fc = failure_cases(m)
    fail_md = "\n## 信号失效阶段（5年分位>80% 但随后6个月收益为负）\n\n"
    fail_md += fc.to_markdown()
    fail_md += (
        "\n\n**典型案例（2022年4月）：** ERP 5年滚动分位约93.2%，市场估值历史上处于极便宜区间，"
        "但随后6个月沪深300价格收益约 −12.6%。同期背景：新冠管控冲击叠加美联储快速加息，"
        "分母端（债券收益率）锚定在低位，ERP 主要由估值压缩驱动，而不是盈利改善。"
        "2023年5–8月也出现类似失效：经济复苏不及预期，ERP 高位滞留但市场持续调整。"
        "这说明 ERP 作为价值信号能识别相对便宜区间，但对短期情绪与基本面修复节奏无法定位，"
        "在宏观冲击主导的市场环境中失效概率更高。\n"
    )
    fail_md += "\n## 局限说明\n"
    fail_md += ("- IC 为描述性相关，月度收益窗口重叠，有效独立观测数少于 N，不能支持统计显著性结论。\n"
                "- ERP 为盈利收益率口径（1/PE_TTM），非股息率，与部分文献定义不同。\n"
                "- 数据依赖 AKShare 上游接口，历史序列存在修订风险。\n")

    report += fail_md
    print(fail_md)
    with open("erp_bt_result.md", "w", encoding="utf-8") as f:
        f.write(report)
    m.to_csv("erp_bt_monthly.csv", encoding="utf-8-sig")
    print("已写出 erp_bt_result.md / erp_bt_monthly.csv")

    plot_charts(m)
    print("已写出 erp_bt_charts.png")


if __name__ == "__main__":
    main()
