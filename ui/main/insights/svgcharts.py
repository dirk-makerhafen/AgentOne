"""Server-rendered SVG chart helpers for the analytics views.

The pyHtmlGui framework re-renders views by replacing their innerHTML, so
inline JS does not re-run after an update. Rendering charts as inline SVG in
Python keeps graphs working after any filter change without extra JS.
"""
from __future__ import annotations

import math
from typing import Sequence


def _escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_num(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return f"{value:.0f}"


def _nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    if high <= low:
        return [low]
    span = high - low
    step = span / count
    magnitude = 10 ** int(math.log10(step))
    norm = step / magnitude
    if norm < 1.5:
        norm = 1
    elif norm < 3:
        norm = 2
    elif norm < 7:
        norm = 5
    else:
        norm = 10
    step = norm * magnitude
    start = math.floor(low / step) * step
    ticks = []
    value = start
    while value <= high + 1e-9:
        ticks.append(value)
        value += step
    return ticks


# ---------------------------------------------------------------------------
# Line / area chart
# ---------------------------------------------------------------------------


def line_chart(
    series: dict[str, list[float | None]],
    labels: Sequence[str],
    width: int = 640,
    height: int = 220,
    colors: dict[str, str] | None = None,
    stacked: bool = False,
    area: bool = True,
    empty_text: str = "No data",
) -> str:
    """Render a multi-series line/area chart.

    Args:
        series: Mapping of series name -> per-bucket values (None = gap).
        labels: X-axis bucket labels (one per bucket).
        width/height: SVG canvas size in px.
        colors: Optional per-series CSS color overrides.
        stacked: Stack series on top of each other (area chart).
        area: Fill under lines.
        empty_text: Text shown when all values are empty/zero.

    Returns:
        An SVG string.
    """
    margin = {"top": 10, "right": 14, "bottom": 28, "left": 52}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    plot_top = margin["top"]
    plot_bottom = margin["top"] + plot_h

    n = len(labels)
    series_names = [name for name, vals in series.items() if any(v is not None for v in vals)]
    if not series_names or n == 0:
        return _empty_svg(width, height, empty_text)

    default_colors = [
        "var(--accent)",
        "var(--accent-2, #7c8cf8)",
        "var(--success)",
        "var(--warning)",
        "var(--info)",
        "#e05",
    ]
    palette = {
        name: (colors or {}).get(name, default_colors[i % len(default_colors)])
        for i, name in enumerate(series_names)
    }

    # Compute y-domain. For stacked, total per bucket.
    y_max = 0.0
    y_min = 0.0
    if stacked:
        for i in range(n):
            total = sum(v for name in series_names if (v := series[name][i]) is not None and v > 0)
            y_max = max(y_max, total)
    else:
        for name in series_names:
            for v in series[name]:
                if v is None:
                    continue
                if v < y_min:
                    y_min = v
                if v > y_max:
                    y_max = v
    if y_max <= y_min:
        y_max = y_min + 1
    pad = (y_max - y_min) * 0.1
    y_max += pad
    y_min -= pad

    def x_pos(i: int) -> float:
        if n == 1:
            return margin["left"] + plot_w / 2
        return margin["left"] + plot_w * i / (n - 1)

    def y_pos(v: float) -> float:
        return plot_bottom - plot_h * (v - y_min) / (y_max - y_min)

    parts: list[str] = []

    # Gridlines + y labels
    for tick in _nice_ticks(y_min, y_max, 4):
        y = y_pos(tick)
        parts.append(
            f'<line x1="{margin["left"]}" y1="{y:.1f}" x2="{width - margin["right"]}" y2="{y:.1f}" '
            f'stroke="var(--border)" stroke-width="1" opacity="0.5"/>'
        )
        parts.append(
            f'<text x="{margin["left"] - 6}" y="{y + 3:.1f}" text-anchor="end" '
            f'font-size="10" fill="var(--muted)">{_fmt_num(tick)}</text>'
        )

    # X labels (thin out if too many)
    step = max(1, math.ceil(n / max(6, plot_w // 70)))
    for i in range(0, n, step):
        x = x_pos(i)
        parts.append(
            f'<text x="{x:.1f}" y="{height - 8}" text-anchor="middle" '
            f'font-size="10" fill="var(--muted)">{_escape(labels[i])}</text>'
        )

    if stacked:
        # Render stack: reverse order so first series is on top.
        for name in reversed(series_names):
            points: list[float] = []
            stack: list[float] = []
            for i in range(n):
                base = 0.0
                for other in series_names:
                    if other == name:
                        break
                    v = series[other][i]
                    base += v if v is not None else 0
                v = series[name][i]
                stack.append(base + (v if v is not None else 0))
                points.append(y_pos(base + (v if v is not None else 0)))
            poly = " ".join(f"{x_pos(i):.1f},{p:.1f}" for i, p in enumerate(points))
            bottom = " ".join(f"{x_pos(i):.1f},{plot_bottom:.1f}" for i in range(n))
            parts.append(
                f'<polygon points="{poly} {bottom}" fill="{palette[name]}" opacity="0.55"/>'
            )
        # Stack lines on top
        for name in series_names:
            points: list[float] = []
            for i in range(n):
                base = 0.0
                for other in series_names:
                    if other == name:
                        break
                    v = series[other][i]
                    base += v if v is not None else 0
                v = series[name][i]
                points.append(y_pos(base + (v if v is not None else 0)))
            poly = " ".join(f"{x_pos(i):.1f},{points[i]:.1f}" for i in range(n))
            parts.append(
                f'<polyline points="{poly}" fill="none" stroke="{palette[name]}" '
                f'stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>'
            )
    else:
        for name in series_names:
            vals = series[name]
            xs = [x_pos(i) for i in range(n)]
            ys = [y_pos(v) if v is not None else None for v in vals]
            seg_points: list[tuple[float, float]] = []
            segments: list[list[tuple[float, float]]] = []
            for x, y in zip(xs, ys):
                if y is None:
                    if len(seg_points) > 1:
                        segments.append(seg_points)
                    seg_points = []
                else:
                    seg_points.append((x, y))
            if len(seg_points) > 1:
                segments.append(seg_points)

            for seg in segments:
                poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in seg)
                if area:
                    bottom_y = plot_bottom
                    poly_area = f"{poly} {seg[-1][0]:.1f},{bottom_y:.1f} {seg[0][0]:.1f},{bottom_y:.1f}"
                    parts.append(
                        f'<polygon points="{poly_area}" fill="{palette[name]}" opacity="0.18"/>'
                    )
                parts.append(
                    f'<polyline points="{poly}" fill="none" stroke="{palette[name]}" '
                    f'stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>'
                )

    return _wrap_svg(width, height, parts, legend=series_names, colors=palette)


# ---------------------------------------------------------------------------
# Scatter chart
# ---------------------------------------------------------------------------


def scatter_chart(
    points: Sequence[tuple[float, float]],
    width: int = 640,
    height: int = 220,
    x_label: str = "",
    y_label: str = "",
    color: str = "var(--accent)",
    max_points: int = 400,
    empty_text: str = "No data",
) -> str:
    """Render an XY scatter plot.

    Args:
        points: Sequence of (x, y) tuples.
        width/height: SVG canvas size in px.
        x_label/y_label: Optional axis captions.
        color: Point fill color.
        max_points: Downsample to at most this many points.
        empty_text: Text shown when there is nothing to plot.

    Returns:
        An SVG string.
    """
    margin = {"top": 10, "right": 14, "bottom": 34, "left": 56}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    plot_top = margin["top"]
    plot_bottom = margin["top"] + plot_h

    clean = [(x, y) for x, y in points if x is not None and y is not None]
    if not clean:
        return _empty_svg(width, height, empty_text)

    if len(clean) > max_points:
        # Uniform downsampling keeps the overall shape while bounding the SVG.
        idxs = sorted(set(round(i * (len(clean) - 1) / (max_points - 1)) for i in range(max_points)))
        clean = [clean[i] for i in idxs]

    xs = [p[0] for p in clean]
    ys = [p[1] for p in clean]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if x_max <= x_min:
        x_max = x_min + 1
    if y_max <= y_min:
        y_max = y_min + 1
    x_pad = (x_max - x_min) * 0.05 or 1
    y_pad = (y_max - y_min) * 0.08 or 1
    x_lo, x_hi = x_min - x_pad, x_max + x_pad
    y_lo, y_hi = y_min - y_pad, y_max + y_pad

    def x_pos(v: float) -> float:
        return margin["left"] + plot_w * (v - x_lo) / (x_hi - x_lo)

    def y_pos(v: float) -> float:
        return plot_bottom - plot_h * (v - y_lo) / (y_hi - y_lo)

    parts: list[str] = []

    for tick in _nice_ticks(y_lo, y_hi, 4):
        y = y_pos(tick)
        parts.append(
            f'<line x1="{margin["left"]}" y1="{y:.1f}" x2="{width - margin["right"]}" y2="{y:.1f}" '
            f'stroke="var(--border)" stroke-width="1" opacity="0.5"/>'
        )
        parts.append(
            f'<text x="{margin["left"] - 6}" y="{y + 3:.1f}" text-anchor="end" '
            f'font-size="10" fill="var(--muted)">{_fmt_num(tick)}</text>'
        )

    for tick in _nice_ticks(x_lo, x_hi, 5):
        x = x_pos(tick)
        parts.append(
            f'<text x="{x:.1f}" y="{height - 14}" text-anchor="middle" '
            f'font-size="10" fill="var(--muted)">{_fmt_num(tick)}</text>'
        )

    r = 2.6
    for x, y in clean:
        parts.append(
            f'<circle cx="{x_pos(x):.1f}" cy="{y_pos(y):.1f}" r="{r}" fill="{color}" opacity="0.55"/>'
        )

    if x_label:
        parts.append(
            f'<text x="{margin["left"] + plot_w / 2:.1f}" y="{height - 2}" text-anchor="middle" '
            f'font-size="10" fill="var(--muted)">{_escape(x_label)}</text>'
        )
    if y_label:
        parts.append(
            f'<text x="12" y="{plot_top + plot_h / 2:.1f}" text-anchor="middle" '
            f'font-size="10" fill="var(--muted)" transform="rotate(-90 12 {plot_top + plot_h / 2:.1f})">'
            f'{_escape(y_label)}</text>'
        )

    return _wrap_svg(width, height, parts)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _wrap_svg(
    width: int,
    height: int,
    parts: Sequence[str],
    legend: Sequence[str] | None = None,
    colors: dict[str, str] | None = None,
) -> str:
    body = "\n".join(parts)
    legend_html = ""
    if legend:
        items = "".join(
            f'<span class="analytics-legend-item"><i style="background:{colors.get(name, "var(--accent)")}"></i>{_escape(name)}</span>'
            for name in legend
        )
        legend_html = f'<div class="analytics-legend">{items}</div>'
    return (
        f'<div class="analytics-chart-wrap">'
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'preserveAspectRatio="none" class="analytics-svg">{body}</svg>{legend_html}</div>'
    )


def _empty_svg(width: int, height: int, text: str) -> str:
    return (
        f'<div class="analytics-empty">{_escape(text)}</div>'
    )
