"""
chart.py
Generates a revenue bar chart (last 3 years) as a PNG file.
Matches the style visible in the TCS slide template.
"""

import os
import tempfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


def generate_revenue_chart(data: dict, company_name: str) -> str:
    """
    Generates a bar chart of revenue (USD Billions) for last 3 years.
    Saves to a temp PNG file and returns the path.
    """
    revenue_data = data.get("revenue_usd_billions", {})
    cagr = data.get("revenue_cagr_3yr_pct", None)

    if not revenue_data:
        return None

    # Filter out years where value is None (Groq returned null)
    filtered = {k: v for k, v in revenue_data.items() if v is not None}
    if not filtered:
        return None

    years = sorted(filtered.keys())
    values = [float(filtered[y]) for y in years]

    # ── Chart style ────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 4.5))
    fig.patch.set_facecolor("#f5f7fa")
    ax.set_facecolor("#f5f7fa")

    bar_color = "#1a5ca8"       # TCS deep blue
    accent_color = "#2e8bce"    # lighter blue highlight

    colors = [bar_color] * len(years)
    if colors:
        colors[-1] = accent_color  # highlight latest year

    bars = ax.bar(years, values, color=colors, width=0.45, zorder=3,
                  edgecolor="white", linewidth=0.8)

    # Value labels on top of bars
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.3,
            f"{val:.2f}",
            ha="center", va="bottom",
            fontsize=11, fontweight="bold", color="#1a1a2e"
        )

    # ── Axes formatting ────────────────────────────────────────────────────
    y_min = max(0, min(values) * 0.92)
    y_max = max(values) * 1.12
    ax.set_ylim(y_min, y_max)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
    ax.set_xlabel("Fiscal Year", fontsize=11, color="#444", labelpad=8)
    ax.set_ylabel("Revenue (USD Billions)", fontsize=11, color="#444", labelpad=8)
    ax.tick_params(colors="#555", labelsize=10)

    # Grid
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, color="#cccccc", zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # ── Title ──────────────────────────────────────────────────────────────
    title = f"{company_name} — Revenue (USD Billions)"
    ax.set_title(title, fontsize=13, fontweight="bold", color="#1a1a2e", pad=14)

    # ── CAGR annotation ────────────────────────────────────────────────────
    if cagr is not None:
        try:
            cagr_val = float(cagr)
            ax.annotate(
                f"3-yr CAGR: {cagr_val:.2f}%",
                xy=(1, 1), xycoords="axes fraction",
                xytext=(-10, -10), textcoords="offset points",
                ha="right", va="top",
                fontsize=10, fontweight="bold",
                color="white",
                bbox=dict(boxstyle="round,pad=0.4", facecolor=bar_color, alpha=0.85, edgecolor="none")
            )
        except (TypeError, ValueError):
            pass

    plt.tight_layout()

    # ── Save ───────────────────────────────────────────────────────────────
    safe_name = company_name.replace(" ", "_").replace("/", "_")
    output_dir = tempfile.gettempdir()
    chart_path = os.path.join(output_dir, f"{safe_name}_revenue_chart.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return chart_path
