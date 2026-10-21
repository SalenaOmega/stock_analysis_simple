"""
宏观指标月度跟踪

覆盖指标：CPI（同比）、PPI（同比）、PMI（制造业，指数水平）、M2（同比）
数据来源：AKShare 公开接口，统一整理为月度频率（2015-01 至今）

用法（在项目 venv 里）：
    python macro_tracker.py              # 联网抓数并缓存到 ./macro_cache/
    python macro_tracker.py --offline    # 只用缓存
输出：macro_monthly.csv + macro_charts.png
"""
import argparse, os, sys
import numpy as np
import pandas as pd

CACHE = "macro_cache"
START = "2015-01-01"


# ───────────────────────── 缓存工具 ─────────────────────────
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


# ───────────────────────── 数据抓取 ─────────────────────────
def load_cpi(offline):
    def fetch():
        import akshare as ak
        raw = ak.macro_china_cpi()
        raw["date"] = pd.to_datetime(raw["月份"].str.replace("年", "-").str.replace("月份", ""),
                                     format="%Y-%m")
        df = pd.DataFrame({
            "date": raw["date"],
            "cpi_yoy": pd.to_numeric(raw["全国-同比增长"], errors="coerce"),
        })
        return df.dropna()
    return _cached("cpi", fetch, offline)


def load_ppi(offline):
    def fetch():
        import akshare as ak
        raw = ak.macro_china_ppi()
        raw["date"] = pd.to_datetime(raw["月份"].str.replace("年", "-").str.replace("月份", ""),
                                     format="%Y-%m")
        df = pd.DataFrame({
            "date": raw["date"],
            "ppi_yoy": pd.to_numeric(raw["当月同比增长"], errors="coerce"),
        })
        return df.dropna()
    return _cached("ppi", fetch, offline)


def load_pmi(offline):
    def fetch():
        import akshare as ak
        raw = ak.macro_china_pmi()
        # 列：月份（如 "2026年09月份"）、制造业-指数
        raw["date"] = pd.to_datetime(raw["月份"].str.replace("年", "-").str.replace("月份", ""),
                                     format="%Y-%m")
        df = pd.DataFrame({
            "date": raw["date"],
            "pmi_mfg": pd.to_numeric(raw["制造业-指数"], errors="coerce"),
        })
        return df.dropna()
    return _cached("pmi", fetch, offline)


def load_m2(offline):
    def fetch():
        import akshare as ak
        raw = ak.macro_china_money_supply()
        raw["date"] = pd.to_datetime(raw["月份"].str.replace("年", "-").str.replace("月份", ""),
                                     format="%Y-%m")
        df = pd.DataFrame({
            "date": raw["date"],
            "m2_yoy": pd.to_numeric(raw["货币和准货币(M2)-同比增长"], errors="coerce"),
        })
        return df.dropna()
    return _cached("m2", fetch, offline)


# ───────────────────────── 合并与整理 ─────────────────────────
def build_monthly(offline=False):
    loaders = [
        ("cpi", load_cpi),
        ("ppi", load_ppi),
        ("pmi", load_pmi),
        ("m2",  load_m2),
    ]
    frames = {}
    for name, fn in loaders:
        df = fn(offline)
        df = df[df["date"] >= START].copy()
        # 取月末最后一个有效值
        df = df.dropna().set_index("date").sort_index()
        df = df.groupby(df.index.to_period("M")).last()
        df.index = df.index.to_timestamp(how="end").normalize()
        frames[name] = df
        print(f"  {name:5s} {df.index.min().date()} → {df.index.max().date()}  {len(df)} 行")

    out = None
    for df in frames.values():
        out = df if out is None else out.join(df, how="outer")
    return out.sort_index()


# ───────────────────────── 图表 ─────────────────────────
def plot_charts(m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("宏观指标月度跟踪（2015 年至今）", fontsize=14, y=0.99)

    cfg = [
        ("cpi_yoy", "CPI 同比（%）",     "#d6604d", axes[0, 0], 0),
        ("ppi_yoy", "PPI 同比（%）",     "#4393c3", axes[0, 1], 0),
        ("pmi_mfg", "制造业 PMI（指数）", "#74c476", axes[1, 0], 50),
        ("m2_yoy",  "M2 同比（%）",      "#9970ab", axes[1, 1], None),
    ]

    for col, title, color, ax, hline in cfg:
        s = m[col].dropna()
        ax.plot(s.index, s.values, color=color, linewidth=1.4)
        ax.fill_between(s.index, s.values,
                        hline if hline is not None else s.mean(),
                        alpha=0.12, color=color)
        if hline is not None:
            ax.axhline(hline, color="gray", linewidth=0.8, linestyle="--")
        ax.set_title(title)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.tick_params(axis="x", labelsize=8)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig("macro_charts.png", dpi=150)
    plt.close(fig)


# ───────────────────────── 热力图 ─────────────────────────
def plot_heatmap(m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    cols = ["cpi_yoy", "ppi_yoy", "pmi_mfg", "m2_yoy"]
    labels = ["CPI 同比", "PPI 同比", "PMI 制造业", "M2 同比"]
    # 最近60个月月度热力图
    sub = m[cols].tail(60).copy()
    norm = sub.apply(lambda x: (x - x.mean()) / x.std(), axis=0)

    xticklabels = [d.strftime("%Y-%m") for d in norm.index]
    # 每隔6个月标注一次
    xtick_pos = list(range(0, len(norm), 6))

    fig, ax = plt.subplots(figsize=(16, 4))
    im = ax.imshow(norm.T.values, aspect="auto", cmap="RdYlGn", vmin=-2.5, vmax=2.5)
    ax.set_xticks(xtick_pos)
    ax.set_xticklabels([xticklabels[i] for i in xtick_pos], rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    # 标注缺失值
    for row in range(len(cols)):
        for col in range(len(norm)):
            if pd.isna(sub.iloc[col, row]):
                ax.text(col, row, "NA", ha="center", va="center", fontsize=6, color="gray")
    ax.set_title("宏观指标标准化热力图（最近60个月，绿=偏高，红=偏低）")
    fig.colorbar(im, ax=ax, label="z-score", fraction=0.03, pad=0.04)
    fig.tight_layout()
    fig.savefig("macro_heatmap.png", dpi=150)
    plt.close(fig)


# ───────────────────────── 主程序 ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    print("加载宏观数据 ...")
    m = build_monthly(args.offline)

    m.to_csv("macro_monthly.csv", encoding="utf-8-sig")
    print("已写出 macro_monthly.csv")

    plot_charts(m)
    print("已写出 macro_charts.png")

    plot_heatmap(m)
    print("已写出 macro_heatmap.png")

    # 终端摘要
    print("\n── 最新数据一览 ──")
    latest = m.dropna(how="all").iloc[-1]
    for col, label in [("cpi_yoy", "CPI 同比"), ("ppi_yoy", "PPI 同比"),
                       ("pmi_mfg", "PMI 制造业"), ("m2_yoy", "M2 同比")]:
        val = latest.get(col, float("nan"))
        suffix = "%" if col != "pmi_mfg" else ""
        print(f"  {label:12s} {val:.2f}{suffix}  （{latest.name.date()}）")


if __name__ == "__main__":
    main()
