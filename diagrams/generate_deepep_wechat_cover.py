from __future__ import annotations

import shutil
import subprocess
from html import escape
from pathlib import Path


OUT_DIR = Path(__file__).resolve().parent
WIDTH = 900
HEIGHT = 383
SCALE = 2

FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Arial, "
    "'PingFang SC', 'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif"
)

COLORS = {
    "ink": "#07132d",
    "muted": "#5f6f8c",
    "line": "#d8e2f1",
    "green": "#059669",
    "green_soft": "#ecfdf5",
    "green_line": "#8ee6bf",
    "blue": "#2563eb",
    "blue_soft": "#eff6ff",
    "blue_line": "#bfdbfe",
    "purple": "#7c3aed",
    "purple_soft": "#faf5ff",
    "purple_line": "#d8ccff",
    "orange": "#ea580c",
    "orange_soft": "#fff7ed",
    "red": "#dc2626",
    "red_soft": "#fef2f2",
    "red_line": "#fecaca",
    "yellow": "#d97706",
    "yellow_soft": "#fffbeb",
    "yellow_line": "#fde68a",
}


def q(value: object) -> str:
    return escape(str(value), quote=True)


def rect(
    lines: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str,
    stroke: str = "none",
    sw: float = 1.2,
    rx: float = 8,
    opacity: float | None = None,
    extra: str = "",
) -> None:
    attrs = [
        f'x="{x}"',
        f'y="{y}"',
        f'width="{w}"',
        f'height="{h}"',
        f'rx="{rx}"',
        f'ry="{rx}"',
        f'fill="{fill}"',
        f'stroke="{stroke}"',
        f'stroke-width="{sw}"',
    ]
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    if extra:
        attrs.append(extra)
    lines.append("<rect " + " ".join(attrs) + "/>")


def circle(
    lines: list[str],
    cx: float,
    cy: float,
    r: float,
    *,
    fill: str,
    stroke: str = "none",
    sw: float = 1.0,
    opacity: float | None = None,
) -> None:
    attrs = [
        f'cx="{cx}"',
        f'cy="{cy}"',
        f'r="{r}"',
        f'fill="{fill}"',
        f'stroke="{stroke}"',
        f'stroke-width="{sw}"',
    ]
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    lines.append("<circle " + " ".join(attrs) + "/>")


def line(
    lines: list[str],
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str,
    width: float = 2.0,
    opacity: float | None = None,
) -> None:
    stroke = COLORS.get(color, color)
    attrs = [
        f'x1="{x1}"',
        f'y1="{y1}"',
        f'x2="{x2}"',
        f'y2="{y2}"',
        f'stroke="{stroke}"',
        f'stroke-width="{width}"',
        'stroke-linecap="round"',
    ]
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    lines.append("<line " + " ".join(attrs) + "/>")


def path(
    lines: list[str],
    d: str,
    *,
    color: str,
    width: float = 2.0,
    opacity: float | None = None,
    dash: str | None = None,
) -> None:
    stroke = COLORS.get(color, color)
    attrs = [
        f'd="{q(d)}"',
        'fill="none"',
        f'stroke="{stroke}"',
        f'stroke-width="{width}"',
        'stroke-linecap="round"',
        'stroke-linejoin="round"',
    ]
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    if dash:
        attrs.append(f'stroke-dasharray="{dash}"')
    lines.append("<path " + " ".join(attrs) + "/>")


def text(
    lines: list[str],
    x: float,
    y: float,
    value: str,
    *,
    cls: str = "body",
    anchor: str = "start",
    fill: str | None = None,
    size: float | None = None,
    weight: int | None = None,
) -> None:
    attrs = [f'x="{x}"', f'y="{y}"', f'class="{cls}"', f'text-anchor="{anchor}"']
    if fill:
        attrs.append(f'fill="{fill}"')
    if size is not None:
        attrs.append(f'font-size="{size}"')
    if weight is not None:
        attrs.append(f'font-weight="{weight}"')
    lines.append("<text " + " ".join(attrs) + f">{q(value)}</text>")


def chip(lines: list[str], x: float, y: float, label: str, fill: str, color: str) -> None:
    w = len(label) * 12 + 34
    rect(lines, x, y, w, 30, fill=fill, stroke="rgba(255,255,255,0.75)", sw=1, rx=15)
    text(lines, x + w / 2, y + 20, label, cls="chip", anchor="middle", fill=color)


def draw_gpu(lines: list[str], x: float, y: float, label: str, color: str) -> None:
    fill = COLORS[f"{color}_soft"]
    stroke = COLORS[f"{color}_line"]
    rect(lines, x, y, 54, 32, fill="#ffffff", stroke=stroke, sw=1.0, rx=7)
    rect(lines, x + 8, y + 8, 15, 15, fill=fill, stroke=COLORS[color], sw=1.0, rx=3)
    for idx in range(3):
        circle(lines, x + 30 + idx * 8, y + 24, 1.9, fill=COLORS[color])


def draw_hca(lines: list[str], x: float, y: float) -> None:
    rect(lines, x, y, 52, 64, fill="#f4fffb", stroke="#9be3c3", sw=1.1, rx=8)
    rect(lines, x + 15, y + 10, 22, 16, fill="#ecfdf5", stroke=COLORS["green"], sw=1.0, rx=3)
    text(lines, x + 26, y + 43, "HCA", cls="small-label", anchor="middle", fill=COLORS["ink"])
    text(lines, x + 26, y + 56, "RDMA", cls="tiny", anchor="middle", fill=COLORS["muted"])


def draw_node(lines: list[str], x: float, y: float, title: str, accent: str) -> None:
    accent_color = COLORS[accent]
    accent_soft = COLORS[f"{accent}_soft"]
    accent_line = COLORS[f"{accent}_line"]
    rect(lines, x, y, 192, 178, fill="#ffffff", stroke="#d9e6f5", sw=1.1, rx=14, extra='filter="url(#softShadow)"')
    rect(lines, x + 25, y + 16, 142, 30, fill=f"url(#{accent}Pill)", stroke="none", rx=15)
    text(lines, x + 96, y + 37, title, cls="node-title", anchor="middle", fill="#ffffff")
    rect(lines, x + 17, y + 61, 158, 96, fill=accent_soft, stroke=accent_line, sw=1.1, rx=11, opacity=0.74)
    text(lines, x + 96, y + 80, "NVSwitch", cls="small-label", anchor="middle", fill=accent_color)
    line(lines, x + 52, y + 95, x + 140, y + 95, color=accent, width=2.0, opacity=0.72)
    draw_gpu(lines, x + 38, y + 107, "GPU0", "blue")
    draw_gpu(lines, x + 100, y + 107, "GPU1", "red")
    draw_gpu(lines, x + 38, y + 144, "GPU2", "yellow")
    draw_gpu(lines, x + 100, y + 144, "GPU3", "purple")


def draw_cover() -> None:
    lines: list[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}">')
    lines.append("<style>")
    lines.append(f"text {{ font-family: {FONT_STACK}; fill: {COLORS['ink']}; letter-spacing: 0; }}")
    lines.append(".eyebrow { font-size: 17px; font-weight: 650; }")
    lines.append(".title { font-size: 46px; font-weight: 780; }")
    lines.append(".hero { font-size: 78px; font-weight: 820; }")
    lines.append(".subtitle { font-size: 17px; font-weight: 540; fill: #5f6f8c; }")
    lines.append(".chip { font-size: 13px; font-weight: 680; }")
    lines.append(".node-title { font-size: 14px; font-weight: 760; }")
    lines.append(".small-label { font-size: 12px; font-weight: 720; }")
    lines.append(".gpu { font-size: 10px; font-weight: 760; }")
    lines.append(".tiny { font-size: 8px; font-weight: 560; }")
    lines.append(".metric { font-size: 15px; font-weight: 760; }")
    lines.append(".metric-big { font-size: 22px; font-weight: 800; }")
    lines.append("</style>")
    lines.append("<defs>")
    lines.append('<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">')
    lines.append('<stop offset="0%" stop-color="#f7fbff"/>')
    lines.append('<stop offset="48%" stop-color="#ffffff"/>')
    lines.append('<stop offset="100%" stop-color="#f5f9ff"/>')
    lines.append("</linearGradient>")
    lines.append('<radialGradient id="greenGlow" cx="0.08" cy="0.2" r="0.58">')
    lines.append('<stop offset="0%" stop-color="#d1fae5" stop-opacity="0.92"/>')
    lines.append('<stop offset="62%" stop-color="#d1fae5" stop-opacity="0.18"/>')
    lines.append('<stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>')
    lines.append("</radialGradient>")
    lines.append('<radialGradient id="purpleGlow" cx="0.82" cy="0.46" r="0.54">')
    lines.append('<stop offset="0%" stop-color="#ede9fe" stop-opacity="0.92"/>')
    lines.append('<stop offset="70%" stop-color="#ede9fe" stop-opacity="0.12"/>')
    lines.append('<stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>')
    lines.append("</radialGradient>")
    lines.append('<linearGradient id="greenPill" x1="0" y1="0" x2="1" y2="0">')
    lines.append('<stop offset="0%" stop-color="#059669"/><stop offset="100%" stop-color="#2dd4bf"/>')
    lines.append("</linearGradient>")
    lines.append('<linearGradient id="bluePill" x1="0" y1="0" x2="1" y2="0">')
    lines.append('<stop offset="0%" stop-color="#1d4ed8"/><stop offset="100%" stop-color="#60a5fa"/>')
    lines.append("</linearGradient>")
    lines.append('<linearGradient id="titleGrad" x1="0" y1="0" x2="1" y2="0">')
    lines.append('<stop offset="0%" stop-color="#07132d"/><stop offset="100%" stop-color="#1d4ed8"/>')
    lines.append("</linearGradient>")
    lines.append('<filter id="softShadow" x="-18%" y="-22%" width="136%" height="150%">')
    lines.append('<feDropShadow dx="0" dy="12" stdDeviation="12" flood-color="#8aa2c8" flood-opacity="0.18"/>')
    lines.append("</filter>")
    lines.append('<pattern id="dotGrid" width="10" height="10" patternUnits="userSpaceOnUse">')
    lines.append('<circle cx="1.4" cy="1.4" r="1.2" fill="#a9c6ee" opacity="0.36"/>')
    lines.append("</pattern>")
    lines.append("</defs>")

    rect(lines, 0, 0, WIDTH, HEIGHT, fill="url(#bg)", stroke="none", rx=0)
    rect(lines, 0, 0, WIDTH, HEIGHT, fill="url(#greenGlow)", stroke="none", rx=0)
    rect(lines, 0, 0, WIDTH, HEIGHT, fill="url(#purpleGlow)", stroke="none", rx=0)
    rect(lines, 18, 18, WIDTH - 36, HEIGHT - 36, fill="#ffffff", stroke="#dfebf8", sw=1.1, rx=18, opacity=0.68)
    rect(lines, 570, 46, 276, 150, fill="url(#dotGrid)", stroke="none", rx=0, opacity=0.58)
    rect(lines, 45, 275, 230, 70, fill="url(#dotGrid)", stroke="none", rx=0, opacity=0.35)

    path(lines, "M420,196 C492,142 552,154 617,212 C682,272 740,232 820,174", color="#a78bfa", width=1.6, opacity=0.30, dash="2 7")
    path(lines, "M386,242 C482,214 545,230 617,258 C690,287 750,292 828,250", color="#10b981", width=1.4, opacity=0.25, dash="2 8")

    text(lines, 68, 82, "AI 集群网络架构学习", cls="eyebrow", fill=COLORS["green"])
    text(lines, 66, 136, "一文搞懂", cls="title", fill=COLORS["ink"])
    text(lines, 66, 204, "DeepEP", cls="hero", fill="url(#titleGrad)")
    text(lines, 68, 236, "dispatch / combine · NVLink · RDMA", cls="subtitle")
    chip(lines, 68, 254, "少字多图版", "#ecfdf5", COLORS["green"])
    chip(lines, 190, 254, "MoE All-to-All", "#eff6ff", COLORS["blue"])
    chip(lines, 346, 254, "节点内外分开优化", "#faf5ff", COLORS["purple"])

    draw_node(lines, 482, 72, "Node 1", "green")
    draw_node(lines, 684, 72, "Node 2", "blue")
    rect(lines, 607, 214, 126, 68, fill="#fbf8ff", stroke="#d8ccff", sw=1.1, rx=12, extra='filter="url(#softShadow)"')
    circle(lines, 670, 237, 15, fill="#ede9fe", stroke=COLORS["purple"], sw=1.2)
    lines.append('<path d="M660,237 H680 M670,227 V247 M663,230 C668,235 672,239 677,244 M677,230 C672,235 668,239 663,244" fill="none" stroke="#7c3aed" stroke-width="1.7" stroke-linecap="round"/>')
    text(lines, 670, 265, "IB / RDMA", cls="small-label", anchor="middle", fill=COLORS["ink"])
    line(lines, 543, 238, 607, 238, color="green", width=2.7, opacity=0.90)
    line(lines, 733, 238, 792, 238, color="purple", width=2.7, opacity=0.90)
    for cx, cy, color in [(543, 238, "green"), (607, 238, "green"), (733, 238, "purple"), (792, 238, "purple")]:
        circle(lines, cx, cy, 3.6, fill=COLORS[color])

    rect(lines, 68, 288, 355, 58, fill="#ffffff", stroke="#dfe9f6", sw=1.0, rx=16, extra='filter="url(#softShadow)"')
    circle(lines, 101, 317, 19, fill="#ecfdf5", stroke="#9be3c3", sw=1.0)
    text(lines, 134, 314, "节点内 NVLink", cls="metric", fill=COLORS["ink"])
    text(lines, 134, 337, "153 / 160 GB/s ≈ 95.6%", cls="metric-big", fill=COLORS["green"])
    line(lines, 305, 336, 390, 336, color="green", width=3.0, opacity=0.85)

    rect(lines, 449, 288, 355, 58, fill="#ffffff", stroke="#dfe9f6", sw=1.0, rx=16, extra='filter="url(#softShadow)"')
    circle(lines, 482, 317, 19, fill="#faf5ff", stroke="#d8ccff", sw=1.0)
    text(lines, 515, 314, "跨节点 RDMA", cls="metric", fill=COLORS["ink"])
    text(lines, 515, 337, "43 / 50 GB/s = 86%", cls="metric-big", fill=COLORS["purple"])
    line(lines, 686, 336, 771, 336, color="purple", width=3.0, opacity=0.85)

    lines.append("</svg>")
    svg_path = OUT_DIR / "deepep-wechat-cover.svg"
    svg_path.write_text("\n".join(lines), encoding="utf-8")

    converter = shutil.which("rsvg-convert")
    if converter is None:
        print(f"wrote {svg_path}")
        print("rsvg-convert not found; PNG skipped")
        return
    png_path = OUT_DIR / "deepep-wechat-cover.png"
    subprocess.run(
        [
            converter,
            "-w",
            str(WIDTH * SCALE),
            "-h",
            str(HEIGHT * SCALE),
            "--background-color",
            "white",
            str(svg_path),
            "-o",
            str(png_path),
        ],
        check=True,
    )
    print(f"wrote {svg_path}")
    print(f"rendered {png_path}")


if __name__ == "__main__":
    draw_cover()
