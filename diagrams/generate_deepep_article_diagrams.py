from __future__ import annotations

import shutil
import subprocess
from html import escape
from pathlib import Path


OUT_DIR = Path(__file__).resolve().parent
SCALE = 2

FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Arial, "
    "'PingFang SC', 'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif"
)

COLORS = {
    "ink": "#111827",
    "muted": "#6b7280",
    "line": "#d1d5db",
    "soft": "#f8fafc",
    "blue": "#2563eb",
    "blue_soft": "#eff6ff",
    "blue_line": "#bfdbfe",
    "green": "#16a34a",
    "green_soft": "#f0fdf4",
    "green_line": "#bbf7d0",
    "orange": "#ea580c",
    "orange_soft": "#fff7ed",
    "orange_line": "#fed7aa",
    "purple": "#7c3aed",
    "purple_soft": "#faf5ff",
    "purple_line": "#ddd6fe",
    "red": "#dc2626",
    "red_soft": "#fef2f2",
    "red_line": "#fecaca",
    "teal": "#0d9488",
    "teal_soft": "#f0fdfa",
    "teal_line": "#99f6e4",
    "yellow": "#d97706",
    "yellow_soft": "#fffbeb",
    "yellow_line": "#fde68a",
}


def q(value: object) -> str:
    return escape(str(value), quote=True)


def base_svg(width: int, height: int) -> list[str]:
    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
    )
    lines.append("<style>")
    lines.append(f"text {{ font-family: {FONT_STACK}; fill: {COLORS['ink']}; }}")
    lines.append(".title { font-size: 28px; font-weight: 700; }")
    lines.append(".subtitle { font-size: 15px; fill: #6b7280; }")
    lines.append(".section { font-size: 17px; font-weight: 700; }")
    lines.append(".label { font-size: 15px; font-weight: 650; }")
    lines.append(".body { font-size: 14px; fill: #374151; }")
    lines.append(".small { font-size: 12px; fill: #6b7280; }")
    lines.append(".tiny { font-size: 11px; fill: #6b7280; }")
    lines.append(".mono { font-size: 13px; fill: #374151; }")
    lines.append("</style>")
    lines.append("<defs>")
    for name in ["blue", "green", "orange", "purple", "red", "teal"]:
        lines.append(
            f'<marker id="arrow-{name}" markerWidth="10" markerHeight="8" '
            f'refX="9" refY="4" orient="auto" markerUnits="strokeWidth">'
            f'<path d="M0,0 L10,4 L0,8 Z" fill="{COLORS[name]}"/></marker>'
        )
    lines.append(
        '<marker id="arrow-gray" markerWidth="10" markerHeight="8" refX="9" '
        'refY="4" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L10,4 L0,8 Z" fill="#6b7280"/></marker>'
    )
    lines.append(
        '<marker id="arrow-gray-start" markerWidth="10" markerHeight="8" refX="1" '
        'refY="4" orient="auto" markerUnits="strokeWidth">'
        '<path d="M10,0 L0,4 L10,8 Z" fill="#6b7280"/></marker>'
    )
    lines.append(
        '<marker id="arrow-green-start" markerWidth="10" markerHeight="8" refX="1" '
        'refY="4" orient="auto" markerUnits="strokeWidth">'
        f'<path d="M10,0 L0,4 L10,8 Z" fill="{COLORS["green"]}"/></marker>'
    )
    lines.append(
        '<marker id="arrow-purple-start" markerWidth="10" markerHeight="8" refX="1" '
        'refY="4" orient="auto" markerUnits="strokeWidth">'
        f'<path d="M10,0 L0,4 L10,8 Z" fill="{COLORS["purple"]}"/></marker>'
    )
    lines.append("</defs>")
    rect(lines, 0, 0, width, height, fill="#ffffff", stroke="none", rx=0)
    rect(lines, 18, 18, width - 36, height - 36, fill="#ffffff", stroke="#e5e7eb", rx=18)
    return lines


def save_svg(name: str, width: int, height: int, lines: list[str]) -> None:
    lines.append("</svg>")
    path = OUT_DIR / f"{name}.svg"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {path.name}")


def render_png(name: str, width: int, height: int) -> None:
    converter = shutil.which("rsvg-convert")
    if not converter:
        print("rsvg-convert not found; SVG written, PNG skipped")
        return
    svg = OUT_DIR / f"{name}.svg"
    png = OUT_DIR / f"{name}.png"
    subprocess.run(
        [
            converter,
            "-w",
            str(width * SCALE),
            "-h",
            str(height * SCALE),
            "--background-color",
            "white",
            str(svg),
            "-o",
            str(png),
        ],
        check=True,
    )
    print(f"rendered {png.name}")


def finish(name: str, width: int, height: int, lines: list[str]) -> None:
    save_svg(name, width, height, lines)
    render_png(name, width, height)


def rect(
    lines: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = "#ffffff",
    stroke: str = "#d1d5db",
    sw: float = 1.5,
    rx: float = 8,
    dash: str | None = None,
    opacity: float | None = None,
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
    if dash:
        attrs.append(f'stroke-dasharray="{dash}"')
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    lines.append("<rect " + " ".join(attrs) + "/>")


def circle(
    lines: list[str],
    cx: float,
    cy: float,
    r: float,
    *,
    fill: str = "#ffffff",
    stroke: str = "#d1d5db",
    sw: float = 1.5,
) -> None:
    lines.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}"/>'
    )


def line(
    lines: list[str],
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = "blue",
    width: float = 2,
    arrow: bool = True,
    start: bool = False,
    dash: str | None = None,
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
    if arrow:
        attrs.append(f'marker-end="url(#arrow-{color})"')
    if start:
        attrs.append(f'marker-start="url(#arrow-{color}-start)"')
    if dash:
        attrs.append(f'stroke-dasharray="{dash}"')
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    lines.append("<line " + " ".join(attrs) + "/>")


def path(
    lines: list[str],
    d: str,
    *,
    color: str = "blue",
    width: float = 2,
    arrow: bool = True,
    start: bool = False,
    dash: str | None = None,
    opacity: float | None = None,
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
    if arrow:
        attrs.append(f'marker-end="url(#arrow-{color})"')
    if start:
        attrs.append(f'marker-start="url(#arrow-{color}-start)"')
    if dash:
        attrs.append(f'stroke-dasharray="{dash}"')
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    lines.append("<path " + " ".join(attrs) + "/>")


def text(
    lines: list[str],
    x: float,
    y: float,
    value: str,
    *,
    cls: str = "body",
    anchor: str = "middle",
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


def multiline(
    lines: list[str],
    x: float,
    y: float,
    values: list[str],
    *,
    cls: str = "small",
    anchor: str = "middle",
    line_h: float = 19,
    fill: str | None = None,
) -> None:
    for idx, value in enumerate(values):
        text(lines, x, y + idx * line_h, value, cls=cls, anchor=anchor, fill=fill)


def title(lines: list[str], width: int, title_value: str, subtitle_value: str) -> None:
    text(lines, width / 2, 56, title_value, cls="title")
    text(lines, width / 2, 86, subtitle_value, cls="subtitle")


def chip(
    lines: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    *,
    fill: str,
    stroke: str,
    color: str,
    sub: str | None = None,
) -> None:
    rect(lines, x, y, w, h, fill=fill, stroke=stroke, sw=1.4, rx=8)
    text(lines, x + w / 2, y + (h / 2 - 2 if sub else h / 2 + 5), label, cls="label", fill=color)
    if sub:
        text(lines, x + w / 2, y + h / 2 + 20, sub, cls="tiny")


def icon_all_to_all(lines: list[str], cx: float, cy: float) -> None:
    pts = [(cx - 24, cy - 20), (cx + 24, cy - 20), (cx - 24, cy + 20), (cx + 24, cy + 20)]
    for a, b in [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]:
        line(lines, pts[a][0], pts[a][1], pts[b][0], pts[b][1], color="blue", width=1.4, arrow=False, opacity=0.45)
    for x, y in pts:
        circle(lines, x, y, 7, fill="#eff6ff", stroke="#2563eb", sw=1.6)


def icon_nccl(lines: list[str], cx: float, cy: float) -> None:
    rect(lines, cx - 30, cy - 24, 60, 48, fill="#f0fdfa", stroke="#99f6e4", sw=1.5, rx=8)
    for yy in [cy - 10, cy + 3, cy + 16]:
        line(lines, cx - 18, yy, cx + 18, yy, color="teal", width=1.8, arrow=False)
    circle(lines, cx - 20, cy - 10, 3, fill="#0d9488", stroke="#0d9488", sw=1)
    circle(lines, cx + 20, cy + 16, 3, fill="#0d9488", stroke="#0d9488", sw=1)


def icon_deepep(lines: list[str], cx: float, cy: float) -> None:
    rect(lines, cx - 34, cy - 26, 68, 52, fill="#fff7ed", stroke="#fed7aa", sw=1.5, rx=10)
    for yy in [cy - 15, cy, cy + 15]:
        line(lines, cx - 22, yy, cx + 20, yy, color="orange", width=1.8, arrow=True)
    circle(lines, cx - 24, cy - 15, 4, fill="#ffffff", stroke="#ea580c", sw=1.5)
    circle(lines, cx - 24, cy, 4, fill="#ffffff", stroke="#ea580c", sw=1.5)
    circle(lines, cx - 24, cy + 15, 4, fill="#ffffff", stroke="#ea580c", sw=1.5)


def diagram_three_layers() -> None:
    width, height = 1280, 720
    lines = base_svg(width, height)
    title(lines, width, "All-to-All / NCCL / DeepEP 三层关系", "先分清：通信模式、通用通信工具、MoE 专用通信库不是同一层东西")

    cards = [
        (
            126,
            136,
            "All-to-All",
            "通信模式",
            "大家互相发货",
            ["描述通信形状", "不是某一个库"],
            "blue",
            "#eff6ff",
            "#bfdbfe",
            icon_all_to_all,
        ),
        (
            126,
            306,
            "NCCL",
            "通用通信工具",
            "通用货车，负责搬 GPU 内存",
            ["能做多种集合通信", "也可以承载 All-to-All 能力"],
            "teal",
            "#f0fdfa",
            "#99f6e4",
            icon_nccl,
        ),
        (
            126,
            476,
            "DeepEP",
            "MoE 专用通信库",
            "自动分拣中心 + 专用运输流水线",
            ["把 MoE dispatch / combine 做快", "底层可借用 NCCL Gin backend"],
            "orange",
            "#fff7ed",
            "#fed7aa",
            icon_deepep,
        ),
    ]

    for x, y, name, tag, big, details, color, fill, stroke, icon_fn in cards:
        rect(lines, x, y, 1028, 122, fill=fill, stroke=stroke, sw=1.6, rx=16)
        rect(lines, x + 24, y + 25, 82, 72, fill="#ffffff", stroke=stroke, sw=1.4, rx=12)
        icon_fn(lines, x + 65, y + 61)
        text(lines, x + 144, y + 48, name, cls="section", anchor="start", fill=COLORS[color])
        text(lines, x + 144, y + 76, tag, cls="body", anchor="start")
        text(lines, x + 498, y + 52, big, cls="section", fill=COLORS["ink"])
        multiline(lines, x + 848, y + 43, details, cls="small", anchor="start", line_h=22)

    path(lines, "M640,258 L640,292", color="gray", width=2.2, arrow=True)
    path(lines, "M640,428 L640,462", color="gray", width=2.2, arrow=True)
    text(lines, 668, 281, "可以用工具实现", cls="tiny", anchor="start")
    text(lines, 668, 451, "面向 MoE 做专用化", cls="tiny", anchor="start")

    rect(lines, 238, 633, 804, 42, fill="#f8fafc", stroke="#e5e7eb", sw=1.2, rx=10)
    text(lines, 640, 660, "用了 DeepEP，不是没有 All-to-All；而是 MoE 的 All-to-All 由 dispatch / combine 高效完成", cls="body")
    finish("deepep-three-layers", width, height, lines)


def diagram_router_to_buffer() -> None:
    width, height = 1280, 720
    lines = base_svg(width, height)
    title(lines, width, "Router 结果如何变成 All-to-All 发送块", "router 解决“发给谁”，DeepEP 解决“怎么摆成高效能发的连续数据”")

    rect(lines, 56, 126, 350, 500, fill="#faf5ff", stroke="#ddd6fe", sw=1.6, rx=16)
    rect(lines, 466, 126, 320, 500, fill="#fff7ed", stroke="#fed7aa", sw=1.6, rx=16)
    rect(lines, 846, 126, 378, 500, fill="#eff6ff", stroke="#bfdbfe", sw=1.6, rx=16)
    text(lines, 86, 160, "1  Router 结果", cls="section", anchor="start", fill=COLORS["purple"])
    text(lines, 496, 160, "2  分桶 / 打包 / 重排", cls="section", anchor="start", fill=COLORS["orange"])
    text(lines, 876, 160, "3  发送 buffer", cls="section", anchor="start", fill=COLORS["blue"])

    rows = [
        ("T0", "expert 5", "GPU2", "yellow"),
        ("T1", "expert 1", "GPU0", "blue"),
        ("T2", "expert 7", "GPU3", "purple"),
        ("T3", "expert 4", "GPU2", "yellow"),
        ("T4", "expert 2", "GPU1", "red"),
        ("T5", "expert 6", "GPU3", "purple"),
    ]
    color_map = {
        "blue": ("#eff6ff", "#bfdbfe", "#2563eb"),
        "yellow": ("#fffbeb", "#fde68a", "#d97706"),
        "purple": ("#faf5ff", "#ddd6fe", "#7c3aed"),
        "red": ("#fef2f2", "#fecaca", "#dc2626"),
    }
    for idx, (tok, exp, gpu, cname) in enumerate(rows):
        y = 200 + idx * 62
        fill, stroke, color = color_map[cname]
        rect(lines, 92, y, 278, 44, fill="#ffffff", stroke=stroke, sw=1.4, rx=8)
        text(lines, 116, y + 28, tok, cls="label", anchor="start", fill=color)
        text(lines, 204, y + 28, "-> " + exp, cls="body", anchor="start")
        text(lines, 318, y + 28, gpu, cls="label", fill=color)

    line(lines, 406, 376, 458, 376, color="orange", width=2.8)
    line(lines, 786, 376, 838, 376, color="blue", width=2.8)

    rect(lines, 512, 210, 228, 116, fill="#ffffff", stroke="#fdba74", sw=1.5, rx=12)
    text(lines, 626, 252, "按目标 GPU 分组", cls="section")
    text(lines, 626, 284, "同一目的地的 token", cls="small")
    text(lines, 626, 306, "排成连续块", cls="small")
    for i, (label, fill, stroke, color) in enumerate(
        [
            ("GPU0", "#eff6ff", "#bfdbfe", "#2563eb"),
            ("GPU1", "#fef2f2", "#fecaca", "#dc2626"),
            ("GPU2", "#fffbeb", "#fde68a", "#d97706"),
            ("GPU3", "#faf5ff", "#ddd6fe", "#7c3aed"),
        ]
    ):
        y = 366 + i * 48
        rect(lines, 528, y, 196, 34, fill=fill, stroke=stroke, sw=1.2, rx=7)
        text(lines, 552, y + 22, label, cls="small", anchor="start", fill=color)
        text(lines, 690, y + 22, "bucket", cls="tiny", fill=color)

    buffers = [
        ("GPU0 块", ["T1"], "#eff6ff", "#bfdbfe", "#2563eb"),
        ("GPU1 块", ["T4"], "#fef2f2", "#fecaca", "#dc2626"),
        ("GPU2 块", ["T0", "T3"], "#fffbeb", "#fde68a", "#d97706"),
        ("GPU3 块", ["T2", "T5"], "#faf5ff", "#ddd6fe", "#7c3aed"),
    ]
    for idx, (label, toks, fill, stroke, color) in enumerate(buffers):
        y = 204 + idx * 92
        rect(lines, 892, y, 286, 66, fill="#ffffff", stroke=stroke, sw=1.6, rx=10)
        rect(lines, 892, y, 16, 66, fill=color, stroke=color, sw=0, rx=8)
        text(lines, 928, y + 40, label, cls="label", anchor="start", fill=color)
        x0 = 1060
        for j, tok in enumerate(toks):
            chip(lines, x0 + j * 48, y + 19, 38, 28, tok, fill=fill, stroke=stroke, color=color)

    rect(lines, 250, 656, 780, 34, fill="#f8fafc", stroke="#e5e7eb", sw=1.1, rx=9)
    text(lines, 640, 678, "中间这一步不是玄学：就是把 token 按目的地重新排队，减少通信前后的折腾", cls="small")
    finish("deepep-router-to-buffer", width, height, lines)


def diagram_plain_pipeline() -> None:
    width, height = 1280, 720
    lines = base_svg(width, height)
    title(lines, width, "不用 DeepEP 的普通 MoE All-to-All 11 步", "真正的网络传输只占其中几步，很多时间花在分桶、拷贝、重排、等待和合并")

    steps = [
        ("1", "router", "算 token 去哪", "blue"),
        ("2", "查位置", "expert 在哪张 GPU", "blue"),
        ("3", "分桶", "按目标 GPU 分组", "orange"),
        ("4", "拷贝", "写入 send buffer", "orange"),
        ("5", "All-to-All", "第一次发送", "purple"),
        ("6", "接收整理", "按 expert 排", "orange"),
        ("7", "expert 计算", "矩阵计算", "green"),
        ("8", "结果打包", "准备回传", "orange"),
        ("9", "All-to-All", "第二次发送", "purple"),
        ("10", "恢复顺序", "回原 token 位", "orange"),
        ("11", "top-k 合并", "按权重合并", "green"),
    ]
    positions: list[tuple[float, float]] = []
    for i in range(6):
        positions.append((74 + i * 190, 166))
    for i in range(5):
        positions.append((1024 - i * 190, 390))

    for idx in range(len(positions) - 1):
        x1, y1 = positions[idx]
        x2, y2 = positions[idx + 1]
        if idx == 5:
            path(lines, f"M{x1 + 144},{y1 + 54} C1196,260 1196,360 {x2 + 144},{y2 + 24}", color="gray", width=2.1)
        elif idx < 5:
            line(lines, x1 + 144, y1 + 54, x2 - 12, y2 + 54, color="gray", width=2.1)
        else:
            line(lines, x1, y1 + 54, x2 + 156, y2 + 54, color="gray", width=2.1)

    for (num, label, sub, cname), (x, y) in zip(steps, positions):
        fill = COLORS[f"{cname}_soft"] if f"{cname}_soft" in COLORS else "#f8fafc"
        stroke = COLORS[f"{cname}_line"] if f"{cname}_line" in COLORS else "#d1d5db"
        rect(lines, x, y, 148, 108, fill="#ffffff", stroke=stroke, sw=1.5, rx=12)
        circle(lines, x + 25, y + 28, 15, fill=fill, stroke=stroke, sw=1.3)
        text(lines, x + 25, y + 33, num, cls="small", fill=COLORS[cname], weight=700)
        text(lines, x + 74, y + 59, label, cls="label", fill=COLORS[cname])
        text(lines, x + 74, y + 84, sub, cls="tiny")

    rect(lines, 90, 566, 1100, 68, fill="#f8fafc", stroke="#e5e7eb", sw=1.3, rx=14)
    text(lines, 132, 596, "慢的高发区", cls="label", anchor="start", fill=COLORS["orange"])
    for i, label in enumerate(["分桶", "拷贝", "重排", "同步等待", "回传整理", "合并"]):
        chip(
            lines,
            252 + i * 142,
            578,
            94 if label != "同步等待" else 112,
            34,
            label,
            fill="#fff7ed",
            stroke="#fed7aa",
            color="#ea580c",
        )
    text(lines, 640, 666, "DeepEP 快在把这些零散动作收进 MoE 专用高速流水线", cls="small")
    finish("deepep-plain-pipeline-11steps", width, height, lines)


def diagram_plain_vs_deepep() -> None:
    width, height = 1280, 760
    lines = base_svg(width, height)
    title(lines, width, "普通方案 vs DeepEP：差别在整条链路怎么组织", "DeepEP 不是比 router 更懂目的地，而是把 dispatch / combine 周边动作做成专用路径")

    rect(lines, 62, 126, 1156, 252, fill="#fff7ed", stroke="#fed7aa", sw=1.6, rx=16)
    rect(lines, 62, 424, 1156, 230, fill="#f0fdf4", stroke="#bbf7d0", sw=1.6, rx=16)
    text(lines, 96, 162, "普通 MoE All-to-All", cls="section", anchor="start", fill=COLORS["orange"])
    text(lines, 96, 460, "DeepEP 思路", cls="section", anchor="start", fill=COLORS["green"])

    top_nodes = [
        ("router", "目的地表", 112),
        ("分桶/拷贝", "send buffer", 282),
        ("通用通信", "All-to-All", 452),
        ("接收整理", "expert 布局", 622),
        ("expert", "矩阵计算", 792),
        ("回传/恢复", "combine", 962),
    ]
    for i, (label, sub, x) in enumerate(top_nodes):
        rect(lines, x, 206, 128, 82, fill="#ffffff", stroke="#fdba74", sw=1.4, rx=10)
        text(lines, x + 64, 238, label, cls="label")
        text(lines, x + 64, 262, sub, cls="small")
        if i < len(top_nodes) - 1:
            line(lines, x + 128, 247, top_nodes[i + 1][2] - 14, 247, color="orange", width=2.1)
    text(lines, 640, 330, "容易把时间花在：多次搬运、临时重排、等待同步、通信和计算互相抢资源", cls="small", fill="#9a3412")

    deep_nodes = [
        ("router", "目的地表", 112, 132),
        ("DeepEP dispatch", "分桶 + 打包 + 传输 + 接收布局", 312, 260),
        ("expert 计算", "直接吃更合适的布局", 642, 190),
        ("DeepEP combine", "按 handle 回来并 top-k 合并", 890, 260),
    ]
    for i, (label, sub, x, w) in enumerate(deep_nodes):
        rect(lines, x, 502, w, 84, fill="#ffffff", stroke="#86efac", sw=1.4, rx=10)
        text(lines, x + w / 2, 535, label, cls="label", fill=COLORS["green"])
        text(lines, x + w / 2, 560, sub, cls="small")
        if i < len(deep_nodes) - 1:
            nx = deep_nodes[i + 1][2]
            line(lines, x + w, 544, nx - 16, 544, color="green", width=2.5)

    rect(lines, 395, 618, 490, 34, fill="#ecfdf5", stroke="#86efac", sw=1.2, rx=9)
    text(lines, 640, 641, "少拷贝 · 少重排 · 少等待 · 少占 GPU SM", cls="label", fill="#15803d")
    finish("deepep-plain-vs-deepep", width, height, lines)


def diagram_dispatch_combine_handle() -> None:
    width, height = 1280, 760
    lines = base_svg(width, height)
    title(lines, width, "DeepEP dispatch / combine 与 handle", "dispatch 保存本次派送路线图；combine 按同一张路线图把结果送回原 token 位置")

    rect(lines, 70, 150, 260, 430, fill="#faf5ff", stroke="#ddd6fe", sw=1.6, rx=16)
    text(lines, 100, 186, "原 token 顺序", cls="section", anchor="start", fill=COLORS["purple"])
    for idx, (tok, expert, gpu, cname) in enumerate(
        [
            ("T0", "E5", "GPU2", "yellow"),
            ("T1", "E1", "GPU0", "blue"),
            ("T2", "E7", "GPU3", "purple"),
            ("T3", "E4", "GPU2", "yellow"),
            ("T4", "E2", "GPU1", "red"),
        ]
    ):
        fill = COLORS[f"{cname}_soft"] if f"{cname}_soft" in COLORS else "#fffbeb"
        stroke = COLORS[f"{cname}_line"] if f"{cname}_line" in COLORS else "#fde68a"
        color = COLORS[cname] if cname in COLORS else "#d97706"
        y = 224 + idx * 58
        rect(lines, 108, y, 184, 40, fill="#ffffff", stroke=stroke, sw=1.3, rx=8)
        text(lines, 128, y + 26, tok, cls="label", anchor="start", fill=color)
        text(lines, 188, y + 26, f"{expert} / {gpu}", cls="small", anchor="start")

    rect(lines, 430, 234, 190, 112, fill="#eff6ff", stroke="#bfdbfe", sw=1.6, rx=14)
    text(lines, 525, 277, "dispatch", cls="section", fill=COLORS["blue"])
    text(lines, 525, 304, "派送到 expert", cls="small")
    rect(lines, 472, 316, 106, 22, fill="#fff7ed", stroke="#fed7aa", sw=1.0, rx=7)
    text(lines, 525, 331, "生成 handle", cls="tiny", fill=COLORS["orange"])
    line(lines, 330, 360, 420, 292, color="blue", width=2.4)

    rect(lines, 430, 438, 190, 112, fill="#f0fdf4", stroke="#bbf7d0", sw=1.6, rx=14)
    text(lines, 525, 481, "combine", cls="section", fill=COLORS["green"])
    text(lines, 525, 508, "回原位并合并", cls="small")
    rect(lines, 472, 520, 106, 22, fill="#fff7ed", stroke="#fed7aa", sw=1.0, rx=7)
    text(lines, 525, 535, "复用 handle", cls="tiny", fill=COLORS["orange"])
    line(lines, 420, 494, 330, 446, color="green", width=2.4)

    rect(lines, 438, 140, 318, 58, fill="#fff7ed", stroke="#fed7aa", sw=1.4, rx=12)
    text(lines, 464, 174, "handle", cls="label", anchor="start", fill=COLORS["orange"])
    text(lines, 548, 174, "路线图 / 偏移 / 合并信息", cls="body", anchor="start")

    rect(lines, 760, 150, 430, 430, fill="#f8fafc", stroke="#e5e7eb", sw=1.6, rx=16)
    text(lines, 790, 186, "expert 所在 GPU", cls="section", anchor="start")
    experts = [
        ("GPU0", "E1", ["T1"], "#eff6ff", "#bfdbfe", "#2563eb", 212),
        ("GPU1", "E2", ["T4"], "#fef2f2", "#fecaca", "#dc2626", 296),
        ("GPU2", "E4 / E5", ["T0", "T3"], "#fffbeb", "#fde68a", "#d97706", 380),
        ("GPU3", "E7", ["T2"], "#faf5ff", "#ddd6fe", "#7c3aed", 464),
    ]
    for gpu, exp, toks, fill, stroke, color, y in experts:
        rect(lines, 804, y, 340, 58, fill="#ffffff", stroke=stroke, sw=1.4, rx=9)
        text(lines, 828, y + 36, gpu, cls="label", anchor="start", fill=color)
        text(lines, 930, y + 36, exp, cls="small", anchor="start")
        for j, tok in enumerate(toks):
            chip(lines, 1048 + j * 42, y + 15, 32, 28, tok, fill=fill, stroke=stroke, color=color)
        line(lines, 620, 290, 794, y + 29, color="blue", width=1.8, opacity=0.78)
        line(lines, 794, y + 29, 620, 494, color="green", width=1.8, dash="5 4", opacity=0.78)

    rect(lines, 310, 634, 660, 42, fill="#f8fafc", stroke="#e5e7eb", sw=1.2, rx=10)
    text(lines, 640, 661, "handle 让 combine 不必重新猜路线：发出去怎么走，回来就怎么还原", cls="body")
    finish("deepep-dispatch-combine-handle", width, height, lines)


def diagram_dispatch_combine_flow() -> None:
    width, height = 1280, 760
    lines = base_svg(width, height)
    title(lines, width, "DeepEP dispatch / combine 数据流", "MoE 的 All-to-All 被拆成发出去和收回来两条专用路径，中间保留 handle")

    stages = [
        ("router 输出", ["token -> expert", "expert -> GPU"], 72, 190, 158, "purple"),
        ("发送布局", ["按目标 GPU 分组", "整理成连续块"], 270, 190, 178, "orange"),
        ("dispatch 通信", ["发到目标 GPU", "生成 handle"], 490, 190, 178, "blue"),
        ("expert 布局", ["收到即适合计算", "减少再整理"], 710, 190, 178, "teal"),
        ("expert 计算", ["MLP / GEMM", "输出结果"], 930, 190, 158, "green"),
    ]
    for i, (label, subs, x, y, w, cname) in enumerate(stages):
        fill = COLORS[f"{cname}_soft"] if f"{cname}_soft" in COLORS else "#f8fafc"
        stroke = COLORS[f"{cname}_line"] if f"{cname}_line" in COLORS else "#d1d5db"
        rect(lines, x, y, w, 116, fill="#ffffff", stroke=stroke, sw=1.5, rx=12)
        text(lines, x + w / 2, y + 43, label, cls="label", fill=COLORS[cname])
        multiline(lines, x + w / 2, y + 70, subs, cls="small", line_h=20)
        if i < len(stages) - 1:
            line(lines, x + w, y + 58, stages[i + 1][2] - 14, y + 58, color="blue", width=2.2)

    rect(lines, 480, 354, 330, 58, fill="#fff7ed", stroke="#fed7aa", sw=1.4, rx=12)
    text(lines, 506, 389, "handle", cls="label", anchor="start", fill=COLORS["orange"])
    text(lines, 590, 389, "记录 token 路线、偏移、合并信息", cls="body", anchor="start")
    line(lines, 579, 306, 604, 354, color="orange", width=2, dash="5 5")

    return_stages = [
        ("结果打包", ["expert 输出", "准备回传"], 930, 486, 158, "orange"),
        ("combine 回传", ["按 handle 返程", "跨 GPU 收回"], 710, 486, 178, "green"),
        ("恢复原位", ["回到原 token 顺序", "对齐 batch"], 490, 486, 178, "purple"),
        ("top-k 合并", ["多个 expert 输出", "按 weight 加权"], 270, 486, 178, "teal"),
        ("MoE 输出", ["继续后续层计算"], 72, 486, 158, "blue"),
    ]
    for i, (label, subs, x, y, w, cname) in enumerate(return_stages):
        fill = COLORS[f"{cname}_soft"] if f"{cname}_soft" in COLORS else "#f8fafc"
        stroke = COLORS[f"{cname}_line"] if f"{cname}_line" in COLORS else "#d1d5db"
        rect(lines, x, y, w, 116, fill="#ffffff", stroke=stroke, sw=1.5, rx=12)
        text(lines, x + w / 2, y + 43, label, cls="label", fill=COLORS[cname])
        multiline(lines, x + w / 2, y + 70, subs, cls="small", line_h=20)
        if i < len(return_stages) - 1:
            line(lines, x, y + 58, return_stages[i + 1][2] + return_stages[i + 1][4] + 14, y + 58, color="green", width=2.2)

    path(lines, "M1010,306 C1148,354 1148,440 1010,486", color="green", width=2.2)
    line(lines, 646, 412, 800, 486, color="orange", width=2, dash="5 5")

    rect(lines, 240, 668, 800, 36, fill="#f8fafc", stroke="#e5e7eb", sw=1.1, rx=10)
    text(lines, 640, 692, "dispatch 负责发得快，combine 负责回得准；这两步一起替代普通 MoE 周边的大量手工搬运", cls="small")
    finish("deepep-dispatch-combine-flow", width, height, lines)


def draw_gpu(lines: list[str], x: float, y: float, label: str, color: str) -> None:
    fill = COLORS[f"{color}_soft"] if f"{color}_soft" in COLORS else "#f8fafc"
    stroke = COLORS[f"{color}_line"] if f"{color}_line" in COLORS else "#d1d5db"
    rect(lines, x, y, 130, 78, fill="#ffffff", stroke=stroke, sw=1.5, rx=10)
    rect(lines, x + 12, y + 12, 106, 20, fill=fill, stroke=stroke, sw=1.0, rx=5)
    text(lines, x + 65, y + 55, label, cls="label", fill=COLORS[color])
    for i in range(4):
        circle(lines, x + 24 + i * 28, y + 68, 3.4, fill=COLORS[color], stroke=COLORS[color], sw=1)


def diagram_intra_inter_node() -> None:
    width, height = 1280, 720
    lines = base_svg(width, height)
    title(lines, width, "DeepEP：机内 NVLink 与跨机 RDMA 分开优化", "节点内走 NVLink / NVSwitch；节点间走 IB / RDMA，瓶颈路径按拓扑分别处理")

    def gpu_module(x: float, y: float, label: str, color: str) -> None:
        fill = COLORS[f"{color}_soft"]
        stroke = COLORS[f"{color}_line"]
        rect(lines, x, y, 120, 72, fill="#ffffff", stroke=stroke, sw=1.5, rx=10)
        rect(lines, x + 14, y + 13, 92, 17, fill=fill, stroke=stroke, sw=1.0, rx=5)
        text(lines, x + 60, y + 52, label, cls="label", fill=COLORS[color])
        for i in range(3):
            circle(lines, x + 43 + i * 17, y + 63, 3.2, fill=COLORS[color], stroke=COLORS[color], sw=1)

    def nic_module(x: float, y: float, port_side: str) -> tuple[float, float]:
        rect(lines, x, y, 76, 104, fill="#faf5ff", stroke="#ddd6fe", sw=1.6, rx=12)
        rect(lines, x + 16, y + 14, 44, 20, fill="#ffffff", stroke="#ddd6fe", sw=1.0, rx=5)
        text(lines, x + 38, y + 54, "HCA", cls="label", fill=COLORS["purple"])
        text(lines, x + 38, y + 78, "RDMA 出口", cls="tiny")
        if port_side == "right":
            circle(lines, x + 76, y + 52, 4.2, fill=COLORS["purple"], stroke=COLORS["purple"], sw=1)
            return (x + 76, y + 52)
        circle(lines, x, y + 52, 4.2, fill=COLORS["purple"], stroke=COLORS["purple"], sw=1)
        return (x, y + 52)

    node_specs = [
        (52, "节点 1  (Node 1)", "right"),
        (728, "节点 2  (Node 2)", "left"),
    ]
    hca_ports: list[tuple[float, float]] = []
    for x, label, nic_side in node_specs:
        rect(lines, x, 144, 500, 440, fill="#f8fafc", stroke="#d1d5db", sw=1.7, rx=18)
        rect(lines, x + 24, 170, 452, 46, fill="#ffffff", stroke="#e5e7eb", sw=1.2, rx=10)
        text(lines, x + 250, 200, label, cls="section")

        domain_x = x + 44 if nic_side == "right" else x + 116
        domain_y = 246
        rect(lines, domain_x, domain_y, 340, 294, fill="#f0fdf4", stroke="#bbf7d0", sw=1.6, rx=16)
        text(lines, domain_x + 22, domain_y + 30, "NVLink / NVSwitch 域", cls="small", anchor="start")

        rect(lines, domain_x + 36, 276, 268, 64, fill="#ecfdf5", stroke="#86efac", sw=1.5, rx=13)
        text(lines, domain_x + 170, 306, "NVSwitch Fabric", cls="label", fill="#15803d")
        text(lines, domain_x + 170, 328, "节点内高带宽互联", cls="tiny")
        rect(lines, domain_x + 74, 356, 192, 5, fill="#16a34a", stroke="#16a34a", sw=0, rx=3, opacity=0.55)

        gpu_slots = [
            (domain_x + 38, 382, "GPU0", "blue"),
            (domain_x + 182, 382, "GPU1", "red"),
            (domain_x + 38, 466, "GPU2", "yellow"),
            (domain_x + 182, 466, "GPU3", "purple"),
        ]
        for gpu_x, gpu_y, gpu_label, gpu_color in gpu_slots:
            gpu_module(gpu_x, gpu_y, gpu_label, gpu_color)

        if nic_side == "right":
            nic_x = x + 406
            hca_ports.append(nic_module(nic_x, 388, "right"))
        else:
            nic_x = x + 18
            hca_ports.append(nic_module(nic_x, 388, "left"))

    rdma_y = 440
    left_port, right_port = hca_ports

    line(lines, left_port[0], rdma_y, 574, rdma_y, color="purple", width=3.0, arrow=False)
    line(lines, 706, rdma_y, right_port[0], rdma_y, color="purple", width=3.0, arrow=False)
    rect(lines, 574, 390, 132, 100, fill="#faf5ff", stroke="#ddd6fe", sw=1.6, rx=14)
    text(lines, 640, 424, "IB / RDMA", cls="label", fill=COLORS["purple"])
    text(lines, 640, 449, "Fabric", cls="label", fill=COLORS["purple"])
    text(lines, 640, 472, "跨节点网络", cls="tiny")
    for px in [left_port[0], 574, 706, right_port[0]]:
        circle(lines, px, rdma_y, 4, fill=COLORS["purple"], stroke=COLORS["purple"], sw=1)

    rect(lines, 244, 608, 792, 56, fill="#fff7ed", stroke="#fed7aa", sw=1.4, rx=12)
    line(lines, 308, 636, 358, 636, color="green", width=2.5, arrow=False)
    text(lines, 540, 641, "节点内 NVLink：153 / 160 GB/s ≈ 95.6%", cls="label", fill=COLORS["orange"])
    line(lines, 714, 636, 764, 636, color="purple", width=2.8, arrow=False)
    text(lines, 900, 641, "跨节点 RDMA：43 / 50 GB/s = 86%", cls="label", fill=COLORS["orange"])

    finish("deepep-intra-inter-node", width, height, lines)


def main() -> None:
    diagram_three_layers()
    diagram_router_to_buffer()
    diagram_plain_pipeline()
    diagram_plain_vs_deepep()
    diagram_dispatch_combine_handle()
    diagram_dispatch_combine_flow()
    diagram_intra_inter_node()


if __name__ == "__main__":
    main()
