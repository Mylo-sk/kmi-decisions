"""Charts for the VAR video and social posts, drawn with the Stat Sheet template (chart_style.py).

Every number is computed live from the KMI data, so after each weekly update a re-run refreshes
every chart.

Run:  py charts.py      (writes PNGs into charts/)
"""
import sys
from datetime import date
from pathlib import Path

from matplotlib.transforms import offset_copy

import chart_style as cs
from history import this_season

sys.stdout.reconfigure(encoding="utf-8")   # Windows terminals choke on some characters otherwise

OUT = Path(__file__).parent / "charts"


def var_97_vs_93(mode="light", preset="x"):
    """One bar of every key decision, split three ways, with the two ways of counting 'correct'."""
    rnd, now = this_season()
    n = int(now["incidents"])
    stood = int(now["decisions_stood_correct"])               # right in the end
    left_alone = int(now["onfield_errors_not_for_var"])       # wrong, 'not clear and obvious'
    other_wrong = n - stood - left_alone                      # wrong and stood
    pl_pct, stood_pct = 100 * (stood + left_alone) / n, 100 * stood / n

    t = cs.use_stat_sheet(mode)
    fig, ax = cs.frame(
        kicker=f"VAR under the microscope · rounds 1–{rnd}",
        headline=f"The Premier League’s {pl_pct:.0f}% counts {left_alone} wrong calls as correct",
        subtitle=(f"All {n} key decisions of 2026-27 so far, judged by the Premier League’s own panel. "
                  f"The {left_alone} were wrong on the pitch, but not ‘clear and obvious’ errors, so VAR left them."),
        source=f"Data: Premier League Key Match Incidents panel, rounds 1–{rnd} · {_today()}",
        preset=preset)
    ax.axis("off")
    ax.set_xlim(0, n)
    ax.set_ylim(-1, 1)                # save() centres the finished block vertically

    # The bar: three blocks, each part's count printed inside it when it fits (otherwise the
    # legend carries it).
    parts = [(stood, t["pole_a"], "Right on the pitch, or put right by VAR"),
             (left_alone, t["neutral"], "Wrong, but not ‘clear and obvious’, so VAR left it"),
             (other_wrong, t["pole_b"], "Wrong and stood: VAR’s own errors, and calls VAR can’t review")]
    x = 0
    for value, color, _ in parts:
        cs.block(ax, x, x + value, 0, color)
        cs.block_label(ax, x, x + value, 0, str(value), color)
        x += value

    # The two ways of counting, as brackets: above = the PL's figure, below = what actually stood.
    def bracket(x1, dy, big, text):
        line = offset_copy(ax.transData, fig=fig, y=dy, units="points")
        ax.plot([0, x1], [0, 0], transform=line, color=t["ink"], lw=cs.HAIRLINE * 1.5,
                marker="|", markersize=9, markeredgewidth=cs.LINE, solid_capstyle="butt")
        # Number and text share one baseline: 12pt clear of the bracket above it, or a cap height
        # (about 0.7 x 34pt) plus 12pt clear below it.
        baseline = dy + 12 if dy > 0 else dy - 12 - 0.7 * 34
        big_font = cs.font("number-strong", 34)
        ax.annotate(big, (0, 0), xytext=(0, baseline), textcoords="offset points",
                    fontproperties=big_font, color=t["ink"], va="baseline", ha="left")
        ax.annotate(text, (0, 0), xytext=(_width_pt(fig, big, big_font) + 12, baseline),
                    textcoords="offset points", fontproperties=cs.font("body-medium", cs.SIZE["label"]),
                    color=t["ink"], va="baseline", ha="left")

    bracket(stood + left_alone, 24, f"{pl_pct:.0f}%",
            f"The Premier League’s figure: counts the {left_alone} as correct")
    bracket(stood, -24, f"{stood_pct:.0f}%", "The decisions that actually stood that were right")

    leg = cs.legend(ax, [(c, f"{label} ({v})") for v, c, label in parts],
                    loc="upper left", bbox_to_anchor=(0, 0),
                    bbox_transform=offset_copy(ax.transData, fig=fig, y=-100, units="points"))
    return fig


def _today():
    d = date.today()
    return f"{d.day} {d:%b %Y}"        # "25 Nov 2026" (no leading zero, works on Windows too)


def _width_pt(fig, text, prop):
    w, _, _ = fig.canvas.get_renderer().get_text_width_height_descent(text, prop, ismath=False)
    return w * 72 / fig.dpi


def main():
    for mode, preset in [("light", "x"), ("dark", "x"), ("light", "vertical")]:
        path = cs.save(var_97_vs_93(mode, preset), OUT / f"var_97_vs_93_{preset}_{mode}")
        print("wrote", path.relative_to(Path(__file__).parent))


if __name__ == "__main__":
    main()
