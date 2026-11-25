"""Stat Sheet: the brand's chart template. Colours, fonts, layout and mark shapes (brand-identity.md).

Every chart goes through three calls, so the brand is applied by construction, not by memory:

    import chart_style as cs
    cs.use_stat_sheet("light")                          # "dark" for video frames
    fig, ax = cs.frame(kicker="VAR UNDER THE MICROSCOPE",
                       headline="The claim, in one line",
                       subtitle="What the chart shows",
                       source="Data: Premier League KMI panel · 25 Nov 2026",
                       preset="x")                      # "x", "video" or "vertical"
    ...draw on ax (cs.bar, cs.block, cs.dot, cs.legend help with brand marks)...
    cs.save(fig, "charts/my_chart")                     # fits the plot into the frame, writes a PNG

The figure is built without pyplot, so no window ever opens and nothing needs closing.
"""
from pathlib import Path

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.axis import Axis
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path as MplPath
from matplotlib.transforms import Bbox, IdentityTransform

FONTS = Path(__file__).parent / "fonts"
HANDLE = ""   # your social handle, e.g. "@yourname". Once set, it goes bottom-right on every chart.

# --- Colour tokens (brand-identity.md section 1). Purple and red are a diverging pair with
#     meaning (correct/incorrect, over/under), neutral is the midpoint. Never use them as two
#     random series: two unrelated series get pole_a + neutral.
TOKENS = {
    "light": dict(bg="#ffffff", ink="#1a1333", muted="#6f6a85", grid="#ece9f4",
                  pole_a="#7445c4", pole_b="#e0243c", neutral="#7d7889"),
    "dark": dict(bg="#15111f", ink="#efecf7", muted="#9a94ad", grid="#27213a",
                 pole_a="#9d7ee0", pole_b="#f4455c", neutral="#908ba1"),
}

# --- Export presets: canvas size in inches and dots per inch. Pixels = inches x dpi.
#     "x" and "video" share the same 16:9 layout in inches, so a chart looks identical in both and
#     only the sharpness changes. "vertical" is narrower, so the same type sizes read bigger: good
#     for phones.
PRESETS = {
    "x": ((16, 9), 200),         # 3200 x 1800 = 1600 x 900 at 2x: X posts, articles
    "video": ((16, 9), 240),     # 3840 x 2160: 4K video frame
    "vertical": ((9, 11.25), 120),  # 1080 x 1350: Instagram portrait
}

# --- Type sizes in points.
SIZE = dict(kicker=12, headline=30, subtitle=15, source=10.5, tick=11.5, label=13, legend=12.5)

# --- Mark sizes in points (1 screen pixel = 0.75 pt), from the dataviz mark specs.
BAR = 18        # 24px: the thickest an ordinary bar may be
BLOCK = 21      # 28px: a part of a tall segmented bar
RADIUS = 3      # 4px rounded data end
LINE = 1.5      # 2px lines
GAP = 1.5       # 2px surface gap between touching marks
DOT = 6         # 8px end dots
HAIRLINE = 0.75  # 1px gridlines

# --- Layout in inches.
SIDE, TOP, BOTTOM = 0.6, 0.55, 0.42

_FONT_FILES = {
    "kicker": "Inter-SemiBold.ttf",
    "headline": "SpaceGrotesk-Bold.ttf",
    "body": "Inter-Regular.ttf",
    "body-medium": "Inter-Medium.ttf",
    "body-strong": "Inter-SemiBold.ttf",
    "number": "IBMPlexMono-Medium.ttf",
    "number-strong": "IBMPlexMono-Bold.ttf",
}
_tokens = TOKENS["light"]


def font(role, size=None):
    """The exact font file for a role, e.g. font("number", 12). Roles: see _FONT_FILES."""
    return font_manager.FontProperties(fname=FONTS / _FONT_FILES[role], size=size)


def use_stat_sheet(mode="light"):
    """Switch every chart drawn after this to the Stat Sheet look. Returns the colour tokens."""
    global _tokens
    for f in FONTS.glob("*.ttf"):            # make the fonts known to matplotlib by family name
        font_manager.fontManager.addfont(f)
    t = _tokens = TOKENS[mode]
    mpl.rcParams.update({
        "font.family": ["Inter", "DejaVu Sans"],   # DejaVu catches any glyph Inter lacks
        "font.size": SIZE["tick"],
        "text.color": t["ink"],
        "figure.facecolor": t["bg"], "axes.facecolor": t["bg"], "savefig.facecolor": t["bg"],
        "axes.edgecolor": t["grid"], "axes.labelcolor": t["muted"],
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": False,   # no boxes around plots
        "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
        "grid.color": t["grid"], "grid.linewidth": HAIRLINE, "grid.linestyle": "-",
        "xtick.color": t["muted"], "ytick.color": t["muted"],
        "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 6, "ytick.major.pad": 6,
        "lines.linewidth": LINE, "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
        "axes.prop_cycle": mpl.cycler(color=[t["pole_a"], t["neutral"]]),
        "legend.frameon": False, "legend.labelcolor": t["ink"],
        "pdf.fonttype": 42, "svg.fonttype": "none",   # keep text as real text in vector exports
    })
    return t


def frame(kicker, headline, subtitle, source, preset="x"):
    """A new figure with the brand skeleton: kicker, headline, subtitle, chart area, source line."""
    t = _tokens
    (w, h), dpi = PRESETS[preset]
    fig = Figure(figsize=(w, h), dpi=dpi)
    FigureCanvasAgg(fig)                        # gives the figure a renderer to measure text with
    width_in = w - 2 * SIDE
    y = h - TOP                                 # running position, in inches from the bottom

    def put(text, role, size, color, gap_after, spacing=1.15):
        nonlocal y
        lines = _wrap(fig, text, font(role, size), width_in)
        block = fig.text(SIDE / w, y / h, "\n".join(lines), fontproperties=font(role, size), color=color,
                         va="top", ha="left", linespacing=spacing)
        # Step down by the block's real rendered height: each font has its own line metrics, so
        # estimating from the point size lets wrapped headlines collide with the subtitle.
        y -= block.get_window_extent(fig.canvas.get_renderer()).height / fig.dpi + gap_after / 72

    put(_letterspace(kicker.upper()), "kicker", SIZE["kicker"], t["pole_b"], gap_after=8)
    put(headline, "headline", SIZE["headline"], t["ink"], gap_after=8, spacing=0.95)
    put(subtitle, "body", SIZE["subtitle"], t["muted"], gap_after=26)

    fig.text(SIDE / w, BOTTOM / h, source, fontproperties=font("body", SIZE["source"]),
             color=t["muted"], va="baseline", ha="left")
    if HANDLE:
        fig.text(1 - SIDE / w, BOTTOM / h, HANDLE, fontproperties=font("body-strong", SIZE["source"]),
                 color=t["muted"], va="baseline", ha="right")
    body_bottom = BOTTOM + (SIZE["source"] + 22) / 72

    # The chart area. save() later moves the axes so that tick labels and direct labels also fit.
    body = Bbox.from_extents(SIDE / w, body_bottom / h, 1 - SIDE / w, y / h)
    ax = fig.add_axes(body.bounds)
    fig._stat_sheet = dict(body=body, ax=ax)
    return fig, ax


def save(fig, path):
    """Fit the plot into the frame and write a PNG at the preset's resolution. Returns the path."""
    _fit(fig)
    path = Path(path).with_suffix(".png")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=fig.dpi)
    return path


# --- Brand marks --------------------------------------------------------------------------------

def bar(ax, start, end, at, color, thickness=BAR, horizontal=True, **kwargs):
    """An ordinary bar from the baseline (start) to the value (end): rounded at the value end,
    square at the baseline. `at` is the bar's position on the other axis (its category)."""
    return _add_bar(ax, start, end, at, color, thickness, horizontal, round_start=False, **kwargs)


def block(ax, start, end, at, color, thickness=BLOCK, horizontal=True, **kwargs):
    """One part of a segmented bar: all corners rounded, a 2px surface gap trimmed off each end."""
    return _add_bar(ax, start, end, at, color, thickness, horizontal, round_start=True, gap=GAP, **kwargs)


def block_label(ax, start, end, at, text, fill, size=None, pad=6):
    """Print text inside a block, but only if it fits with `pad` points either side: never clipped.
    Ink is white or near-black, whichever contrasts more with the fill (same pair in both modes).
    Returns False when it didn't fit, so the caller can put the value elsewhere."""
    prop = font("number-strong", size or SIZE["label"])
    fig = ax.get_figure()
    (x0, _), (x1, _) = ax.transData.transform([(start, at), (end, at)])
    w, _, _ = fig.canvas.get_renderer().get_text_width_height_descent(text, prop, ismath=False)
    if w + 2 * pad * fig.dpi / 72 > abs(x1 - x0):
        return False
    ink = max(["#ffffff", TOKENS["light"]["ink"]], key=lambda c: _contrast(c, fill))
    ax.annotate(text, (start, at), xytext=(pad, 0), textcoords="offset points",
                fontproperties=prop, color=ink, va="center", ha="left")
    return True


def dot(ax, x, y, color, **kwargs):
    """An 8px dot with a 2px ring in the background colour, so it stays legible over lines."""
    return ax.scatter(x, y, s=DOT ** 2, color=color, edgecolors=_tokens["bg"],
                      linewidths=GAP, zorder=3, **kwargs)


def legend(ax, items, **kwargs):
    """A legend from (colour, label) pairs: swatches beside text in ink, never coloured text."""
    handles = [Patch(facecolor=c, edgecolor="none", label=label) for c, label in items]
    options = dict(prop=font("body", SIZE["legend"]), handlelength=1.0, handleheight=1.0,
                   handletextpad=0.6, borderaxespad=0, borderpad=0, labelspacing=0.55, frameon=False)
    options.update(kwargs)
    return ax.legend(handles=handles, **options)


# --- Internals ----------------------------------------------------------------------------------

class _RoundedBar(PathPatch):
    """A bar whose thickness and corner radius are in points, whatever the axis scales.

    Its outline is worked out in screen pixels every time it's drawn: data coordinates say where
    the bar starts and ends, points say how thick it is and how round its corners are. That keeps
    corners circular (not squashed ovals) and the 24px cap exact at any export size.
    """

    def __init__(self, start, end, at, thickness, radius, horizontal, round_start, gap, **kwargs):
        super().__init__(MplPath([(0, 0)]), transform=IdentityTransform(), **kwargs)
        self._geometry = (start, end, at, thickness, radius, horizontal, round_start, gap)

    def get_path(self):
        start, end, at, thickness, radius, horizontal, round_start, gap = self._geometry
        px = self.figure.dpi / 72                      # points -> pixels at the current dpi
        to_px = self.axes.transData.transform
        if horizontal:
            (a, c), (b, _) = to_px([(start, at), (end, at)])
        else:
            (c, a), (_, b) = to_px([(at, start), (at, end)])
        s = 1 if b >= a else -1                         # bars can point either way (negatives)
        a, b = a + s * gap * px / 2, b - s * gap * px / 2
        length, half = abs(b - a), thickness * px / 2
        if length <= 0:
            return MplPath([(c, c)])                    # zero value: draw nothing
        r = min(radius * px, half, length / 2 if round_start else length)
        rs = r if round_start else 0
        # Walk round the outline in (along, across) coordinates; curves are the rounded corners.
        pts = [(a + s * rs, c - half), (b - s * r, c - half),
               (b, c - half), (b, c - half + r),       # rounded corner at the value end
               (b, c + half - r),
               (b, c + half), (b - s * r, c + half),   # rounded corner at the value end
               (a + s * rs, c + half)]
        codes = [MplPath.MOVETO, MplPath.LINETO, MplPath.CURVE3, MplPath.CURVE3,
                 MplPath.LINETO, MplPath.CURVE3, MplPath.CURVE3, MplPath.LINETO]
        if rs:
            pts += [(a, c + half), (a, c + half - rs), (a, c - half + rs), (a, c - half), (a + s * rs, c - half)]
            codes += [MplPath.CURVE3, MplPath.CURVE3, MplPath.LINETO, MplPath.CURVE3, MplPath.CURVE3]
        else:
            pts += [(a, c + half), (a, c - half)]
            codes += [MplPath.LINETO, MplPath.LINETO]
        pts.append((0, 0))
        codes.append(MplPath.CLOSEPOLY)
        if not horizontal:
            pts = [(v, u) for u, v in pts]
        return MplPath(pts, codes)


def _add_bar(ax, start, end, at, color, thickness, horizontal, round_start, gap=0, **kwargs):
    patch = _RoundedBar(start, end, at, thickness, RADIUS, horizontal, round_start, gap,
                        facecolor=color, edgecolor="none", **kwargs)
    ax.add_patch(patch)
    # The bar lives in screen pixels, so tell the axes about its data extent ourselves.
    ax.update_datalim([(start, at), (end, at)] if horizontal else [(at, start), (at, end)])
    ax.autoscale_view()
    return patch


def _wrap(fig, text, prop, max_width_in):
    """Break text into lines that fit max_width_in, by measuring the real rendered width."""
    renderer = fig.canvas.get_renderer()
    limit = max_width_in * fig.dpi
    lines, line = [], ""
    # split(" "), not split(): Python counts the kicker's hair spaces as whitespace too.
    for word in filter(None, text.split(" ")):
        trial = f"{line} {word}".strip()
        w, _, _ = renderer.get_text_width_height_descent(trial, prop, ismath=False)
        if w > limit and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines


def _contrast(a, b):
    """WCAG contrast ratio between two colours (1 to 21; 4.5+ is comfortable for text)."""
    def luminance(c):
        rgb = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in mpl.colors.to_rgb(c)]
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    hi, lo = sorted([luminance(a), luminance(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _letterspace(text):
    """Caps kickers read better spaced out. Matplotlib has no letter-spacing, so put a hair space
    (U+200A, which Inter has) between characters."""
    return " ".join(text)


def _content_box(ax, renderer):
    """The box around everything visible in the plot, in pixels. matplotlib's own get_tightbbox
    always includes the axes rectangle, so with hidden axes it reports the whole chart area even
    when the content is smaller. Then measure the visible pieces instead."""
    if ax.axison:
        return ax.get_tightbbox(renderer)
    boxes = []
    for artist in ax.get_children():
        # Skip the background, and the x/y axes: hidden, but they still report their tick labels.
        if artist is ax.patch or isinstance(artist, Axis) or not artist.get_visible() or not artist.get_in_layout():
            continue
        box = artist.get_tightbbox(renderer)
        if box is not None and box.width > 0 and box.height > 0:   # skips empty titles
            boxes.append(box)
    return Bbox.union(boxes)


def _fit(fig):
    """Move the axes so the whole plot, tick labels and direct labels included, sits inside the
    chart area. Axes positions ignore tick labels; this measures them and makes room."""
    info = getattr(fig, "_stat_sheet", None)
    if not info:
        return
    body, ax = info["body"], info["ax"]
    number = font("number", SIZE["tick"])
    for _ in range(3):                         # moving the axes can change its ticks: settle it
        fig.canvas.draw()
        # Numbers wear the mono font, including tick labels.
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            if label.get_text().replace(",", "").replace(".", "").replace("%", "").lstrip("-−").isdigit():
                label.set_fontproperties(number)
        tight = _content_box(ax, fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
        pos = ax.get_position()
        left, right = max(0, pos.x0 - tight.x0), max(0, tight.x1 - pos.x1)
        below, above = max(0, pos.y0 - tight.y0), max(0, tight.y1 - pos.y1)
        ax.set_position([body.x0 + left, body.y0 + below,
                         body.width - left - right, body.height - below - above])
    # A chart with hidden axes (e.g. one segmented bar plus labels) can be shorter than the chart
    # area: centre it vertically rather than leave a gap underneath. Ordinary charts already fill
    # the area exactly, so they don't move.
    fig.canvas.draw()
    tight = _content_box(ax, fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    if tight.height < body.height - 1e-3:
        pos = ax.get_position()
        shift = (body.y0 + body.y1) / 2 - (tight.y0 + tight.y1) / 2
        ax.set_position([pos.x0, pos.y0 + shift, pos.width, pos.height])
