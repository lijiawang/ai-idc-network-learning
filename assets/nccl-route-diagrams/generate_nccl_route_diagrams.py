from pathlib import Path
from xml.sax.saxutils import escape


OUT = Path(__file__).resolve().parent
W = 1600
H = 900

NAVY = "#07143d"
BLUE = "#0b55d9"
LIGHT_BLUE = "#eff6ff"
GREEN = "#159438"
LIGHT_GREEN = "#f0fdf4"
RED = "#dc2626"
LIGHT_RED = "#fff5f5"
ORANGE = "#f97316"
LIGHT_ORANGE = "#fff7ed"
GRAY = "#5f6680"
LIGHT_GRAY = "#f8fafc"


def attr(**kwargs):
    return " ".join(f'{k.replace("_", "-")}="{escape(str(v))}"' for k, v in kwargs.items() if v is not None)


def text(lines, x, y, value, size=24, fill=NAVY, weight=600, anchor="middle"):
    lines.append(
        f'<text {attr(x=x, y=y, fill=fill, font_size=size, font_weight=weight, text_anchor=anchor)}>{escape(value)}</text>'
    )


def multiline(lines, x, y, values, size=22, fill=BLUE, weight=600, anchor="middle", gap=30):
    for i, value in enumerate(values):
        text(lines, x, y + i * gap, value, size=size, fill=fill, weight=weight, anchor=anchor)


def rect(lines, x, y, w, h, rx=18, fill="#ffffff", stroke=BLUE, sw=3, dash=None):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    lines.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{extra}/>'
    )


def circle(lines, cx, cy, r, fill=BLUE, stroke=None, sw=2):
    stroke_attrs = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{stroke_attrs}/>')


def line(lines, x1, y1, x2, y2, color=BLUE, width=4, marker=True, dash=None):
    marker_attr = f' marker-end="url(#arrow-{color_name(color)})"' if marker else ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    lines.append(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"{dash_attr}{marker_attr}/>'
    )


def path(lines, d, color=BLUE, width=4, marker=True, dash=None, fill="none"):
    marker_attr = f' marker-end="url(#arrow-{color_name(color)})"' if marker else ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    lines.append(
        f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"{dash_attr}{marker_attr}/>'
    )


def color_name(color):
    return {
        BLUE: "blue",
        GREEN: "green",
        RED: "red",
        ORANGE: "orange",
        GRAY: "gray",
    }.get(color, "blue")


def base(title, subtitle=None):
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        "<style>",
        "text { font-family: 'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif; }",
        "</style>",
        "<defs>",
    ]
    for name, color in [
        ("blue", BLUE),
        ("green", GREEN),
        ("red", RED),
        ("orange", ORANGE),
        ("gray", GRAY),
    ]:
        lines.extend(
            [
                f'<marker id="arrow-{name}" markerWidth="12" markerHeight="8" refX="11" refY="4" orient="auto" markerUnits="userSpaceOnUse">',
                f'<polygon points="0 0, 12 4, 0 8" fill="{color}"/>',
                "</marker>",
            ]
        )
    lines.extend(
        [
            "</defs>",
            f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
        ]
    )
    text(lines, W / 2, 72, title, size=58, fill=NAVY, weight=800)
    if subtitle:
        text(lines, W / 2, 122, subtitle, size=30, fill=GRAY, weight=600)
    return lines


def finish(lines, name, footer=None):
    if footer:
        line(lines, 360, 846, 470, 846, color=GRAY, width=2, marker=False)
        text(lines, 800, 854, footer, size=24, fill=GRAY, weight=600)
        line(lines, 1130, 846, 1240, 846, color=GRAY, width=2, marker=False)
    lines.append("</svg>")
    (OUT / f"{name}.svg").write_text("\n".join(lines), encoding="utf-8")


def step_card(lines, n, y, title, detail, icon="chip", tag=None, tag_color=ORANGE):
    x, w, h = 230, 1140, 106
    rect(lines, x, y, w, h, rx=20, fill="#ffffff", stroke=BLUE, sw=3)
    circle(lines, x + 50, y + 53, 26, fill=BLUE)
    text(lines, x + 50, y + 64, str(n), size=34, fill="#ffffff", weight=800)
    draw_icon(lines, x + 190, y + 53, icon)
    text(lines, x + 560, y + 45, title, size=40, fill=NAVY, weight=800)
    text(lines, x + 560, y + 78, detail, size=24, fill=BLUE, weight=600)
    if tag:
        rect(lines, x + w - 215, y + 33, 170, 44, rx=20, fill="#ffffff", stroke=tag_color, sw=2)
        text(lines, x + w - 130, y + 64, tag, size=22, fill=tag_color, weight=700)


def draw_icon(lines, cx, cy, kind, color=BLUE):
    if kind == "chip":
        rect(lines, cx - 30, cy - 30, 60, 60, rx=8, fill=LIGHT_BLUE, stroke=color, sw=4)
        rect(lines, cx - 17, cy - 17, 34, 34, rx=4, fill="#ffffff", stroke=color, sw=4)
        for dx in [-44, -38, 38, 44]:
            line(lines, cx + dx, cy - 20, cx + dx, cy + 20, color=color, width=3, marker=False)
        for dy in [-44, -38, 38, 44]:
            line(lines, cx - 20, cy + dy, cx + 20, cy + dy, color=color, width=3, marker=False)
    elif kind == "graph":
        pts = [(cx - 35, cy - 12), (cx + 28, cy - 28), (cx + 48, cy + 22), (cx - 32, cy + 35)]
        for a, b in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]:
            line(lines, *pts[a], *pts[b], color=color, width=3, marker=False)
        for px, py in pts:
            circle(lines, px, py, 10, fill=color)
    elif kind == "decision":
        path(lines, f"M {cx} {cy-38} L {cx+28} {cy-10} L {cx} {cy+18} L {cx-28} {cy-10} Z", color=ORANGE, width=4, marker=False)
        line(lines, cx, cy + 18, cx, cy + 28, color=ORANGE, width=3, marker=False)
        for dx in [-48, 0, 48]:
            line(lines, cx, cy + 28, cx + dx, cy + 28, color=ORANGE, width=3, marker=False)
            line(lines, cx + dx, cy + 28, cx + dx, cy + 36, color=ORANGE, width=3, marker=False)
            circle(lines, cx + dx, cy + 43, 8, fill=ORANGE)
    elif kind == "ringtree":
        for a in range(4):
            import math
            px = cx - 45 + 35 * math.cos(a * 1.5708)
            py = cy + 2 + 35 * math.sin(a * 1.5708)
            circle(lines, px, py, 8, fill=color)
        path(lines, f"M {cx-10} {cy-32} C {cx+25} {cy-30} {cx+25} {cy+36} {cx-10} {cy+34}", color=color, width=3, marker=True)
        circle(lines, cx + 50, cy - 35, 8, fill=color)
        line(lines, cx + 50, cy - 27, cx + 50, cy + 10, color=color, width=3, marker=False)
        line(lines, cx + 50, cy + 10, cx + 24, cy + 38, color=color, width=3, marker=False)
        line(lines, cx + 50, cy + 10, cx + 76, cy + 38, color=color, width=3, marker=False)
        circle(lines, cx + 24, cy + 42, 8, fill=color)
        circle(lines, cx + 76, cy + 42, 8, fill=color)
    elif kind == "collective":
        line(lines, cx - 55, cy - 15, cx + 40, cy - 15, color=color, width=5, marker=True)
        line(lines, cx + 55, cy + 20, cx - 40, cy + 20, color=color, width=5, marker=True)


def diagram_01():
    lines = base("NCCL 不是逐包路由，而是先生成通信图")
    rows = [
        (1, 120, "硬件拓扑探测", "GPU / NVLink / PCIe / CPU / NIC", "chip", None),
        (2, 245, "路径距离判断", "NVL / PIX / PXB / PHB / SYS", "graph", None),
        (3, 370, "传输方式选择", "P2P / SHM / NET（NET 可启用 GDRDMA）", "decision", "选择 / 决策"),
        (4, 495, "生成通信图", "Ring / Tree / Channel", "ringtree", None),
        (5, 620, "执行 Collective", "AllReduce / AllGather / ReduceScatter", "collective", None),
    ]
    for i, (n, y, title, detail, icon, tag) in enumerate(rows):
        step_card(lines, n, y, title, detail, icon, tag)
        if i < len(rows) - 1:
            line(lines, 800, y + 106, 800, y + 128, color=BLUE, width=8, marker=True)
    finish(lines, "01-nccl-flow", "这张放在文章前半部分，让读者先建立全局框架。")


def gpu_node(lines, x, y, label, w=180, h=76):
    rect(lines, x, y, w, h, rx=12, fill="#ffffff", stroke=BLUE, sw=3)
    rect(lines, x + 16, y + 18, 44, 40, rx=6, fill=LIGHT_BLUE, stroke=BLUE, sw=3)
    circle(lines, x + 38, y + 38, 13, fill="#ffffff", stroke=BLUE, sw=3)
    text(lines, x + w * 0.66, y + 48, label, size=24, fill=NAVY, weight=800)


def small_box(lines, x, y, w, h, label, fill="#ffffff", stroke=BLUE):
    rect(lines, x, y, w, h, rx=10, fill=fill, stroke=stroke, sw=3)
    text(lines, x + w / 2, y + h / 2 + 8, label, size=22, fill=BLUE, weight=800)


def diagram_02():
    lines = base("GPU 之间的路，并不是一样近")
    text(lines, 145, 210, "GPU 层", size=24, fill=BLUE, weight=800)
    text(lines, 145, 330, "PCIe 交换层", size=24, fill=BLUE, weight=800)
    text(lines, 145, 462, "CPU 层", size=24, fill=BLUE, weight=800)
    text(lines, 145, 570, "互连层", size=24, fill=BLUE, weight=800)
    text(lines, 145, 690, "GPU 层", size=24, fill=BLUE, weight=800)
    for y in [270, 390, 525, 615]:
        line(lines, 70, y, 1110, y, color="#8bb6ff", width=2, marker=False, dash="8 10")
    rect(lines, 250, 140, 850, 640, rx=18, fill="#ffffff", stroke=BLUE, sw=3)
    gpu_node(lines, 310, 175, "GPU0")
    gpu_node(lines, 760, 175, "GPU1")
    line(lines, 490, 213, 760, 213, color=GREEN, width=8, marker=True)
    line(lines, 760, 213, 490, 213, color=GREEN, width=8, marker=True)
    text(lines, 625, 195, "NVLink", size=24, fill=GREEN, weight=800)
    small_box(lines, 520, 305, 220, 72, "PCIe Switch A")
    line(lines, 400, 251, 590, 305, color=BLUE, width=4, marker=True)
    line(lines, 850, 251, 670, 305, color=BLUE, width=4, marker=True)
    small_box(lines, 540, 430, 180, 70, "CPU0")
    line(lines, 630, 377, 630, 430, color=BLUE, width=4, marker=True)
    small_box(lines, 540, 545, 180, 64, "UPI")
    line(lines, 630, 500, 630, 545, color=BLUE, width=4, marker=True)
    small_box(lines, 540, 640, 180, 66, "CPU1")
    line(lines, 630, 609, 630, 640, color=BLUE, width=4, marker=True)
    small_box(lines, 450, 715, 200, 54, "PCIe Switch B")
    small_box(lines, 700, 715, 200, 54, "PCIe Switch C")
    line(lines, 585, 706, 548, 715, color=BLUE, width=4, marker=True)
    line(lines, 675, 706, 802, 715, color=BLUE, width=4, marker=True)
    gpu_node(lines, 280, 708, "GPU2", w=145, h=62)
    gpu_node(lines, 925, 708, "GPU3", w=145, h=62)
    line(lines, 425, 739, 450, 739, color=BLUE, width=4, marker=True)
    line(lines, 900, 739, 925, 739, color=BLUE, width=4, marker=True)

    text(lines, 1170, 188, "近", size=28, fill=GREEN, weight=800)
    line(lines, 1170, 210, 1170, 770, color=GREEN, width=5, marker=False)
    line(lines, 1170, 770, 1170, 800, color=RED, width=5, marker=True)
    text(lines, 1170, 825, "远", size=28, fill=RED, weight=800)
    text(lines, 1340, 230, "从快到慢", size=30, fill=NAVY, weight=800)
    items = [
        (1, "NVL：NVLink / NVSwitch，最快", GREEN, LIGHT_GREEN),
        (2, "PIX：同一个 PCIe Switch", BLUE, "#ffffff"),
        (3, "PXB：跨 PCIe Switch", BLUE, "#ffffff"),
        (4, "PHB：经过 CPU Root Complex", BLUE, "#ffffff"),
        (5, "SYS：跨 NUMA，最远", RED, LIGHT_RED),
    ]
    for idx, (n, label, color, fill) in enumerate(items):
        y = 285 + idx * 95
        rect(lines, 1220, y, 330, 64, rx=12, fill=fill, stroke=color, sw=2)
        circle(lines, 1255, y + 32, 20, fill=color)
        text(lines, 1255, y + 40, str(n), size=24, fill="#ffffff", weight=800)
        text(lines, 1295, y + 40, label, size=20, fill=color, weight=800, anchor="start")
    finish(lines, "02-gpu-distance-levels", "这张解释 NVL/PIX/PXB/PHB/SYS，重点是 GPU-GPU 路径距离。")


def diagram_03():
    lines = base("跨节点通信，GPU 要找离自己最近的网卡")
    text(lines, 355, 160, "服务器 A", size=32, fill=BLUE, weight=800)
    text(lines, 1245, 160, "服务器 B", size=32, fill=BLUE, weight=800)
    rect(lines, 110, 180, 490, 620, rx=18, fill="#ffffff", stroke=BLUE, sw=3)
    rect(lines, 1000, 180, 490, 620, rx=18, fill="#ffffff", stroke=BLUE, sw=3)
    text(lines, 800, 185, "IB / RoCE 网络", size=34, fill=BLUE, weight=800)
    path(lines, "M 760 260 C 690 260 690 340 750 350 C 690 390 710 470 760 470 C 695 520 725 610 800 595 C 875 615 910 520 845 470 C 910 450 900 370 845 350 C 900 305 850 245 800 275 C 790 265 775 260 760 260 Z", color=BLUE, width=3, marker=False, fill="#ffffff")
    for row in range(4):
        y = 245 + row * 130
        text(lines, 175, y + 20, f"GPU{row}", size=24, fill=NAVY, weight=700)
        gpu_node(lines, 230, y - 30, f"GPU{row}", w=140, h=70)
        small_box(lines, 445, y - 25, 110, 60, f"NIC{row}")
        line(lines, 370, y + 5, 445, y + 5, color=GREEN, width=4, marker=False)
        text(lines, 1425, y + 20, f"GPU{row}", size=24, fill=NAVY, weight=700)
        gpu_node(lines, 1245, y - 30, f"GPU{row}", w=140, h=70)
        small_box(lines, 1045, y - 25, 110, 60, f"NIC{row}")
        line(lines, 1155, y + 5, 1245, y + 5, color=GREEN, width=4, marker=False)
        line(lines, 555, y + 5, 1045, y + 5, color=GREEN, width=5, marker=True)
    path(lines, "M 220 275 C 165 330 165 600 220 660 L 430 660", color=RED, width=4, marker=True, dash="12 12")
    rect(lines, 138, 705, 260, 80, rx=16, fill=LIGHT_RED, stroke=RED, sw=2)
    text(lines, 268, 740, "低效路径", size=24, fill=RED, weight=800)
    text(lines, 268, 770, "跨 PCIe / 跨 NUMA / 绕远路", size=18, fill=RED, weight=700)
    rect(lines, 715, 720, 170, 58, rx=16, fill=LIGHT_GREEN, stroke=GREEN, sw=3)
    text(lines, 800, 757, "最佳路径", size=26, fill=GREEN, weight=800)
    text(lines, 800, 845, "绿色实线表示合理亲缘路径，红色虚线表示错误或低效路径。", size=24, fill=GRAY, weight=600)
    finish(lines, "03-gpu-nic-affinity")


def decision_box(lines, x, y, w, h, label, color=BLUE, fill="#ffffff"):
    rect(lines, x, y, w, h, rx=14, fill=fill, stroke=color, sw=3)
    text(lines, x + w / 2, y + h / 2 + 9, label, size=28, fill=color if color != BLUE else NAVY, weight=800)


def badge(lines, x, y, label, color=BLUE):
    circle(lines, x, y, 26, fill="#ffffff", stroke=color, sw=3)
    text(lines, x, y + 9, label, size=24, fill=color, weight=800)


def diagram_04():
    lines = base("NCCL 到底走哪种传输方式？")
    decision_box(lines, 520, 135, 560, 70, "两张 GPU 在同一台机器？", color=BLUE)
    line(lines, 800, 205, 800, 250, color=BLUE, width=4, marker=False)
    path(lines, "M 800 250 L 520 250 L 520 300", color=BLUE, width=4, marker=True)
    path(lines, "M 800 250 L 1135 250 L 1135 300", color=BLUE, width=4, marker=True)
    badge(lines, 485, 250, "是", BLUE)
    badge(lines, 1115, 250, "否", BLUE)

    decision_box(lines, 360, 300, 360, 68, "是否支持 P2P？", color=ORANGE, fill=LIGHT_ORANGE)
    path(lines, "M 520 368 L 520 430 L 330 430 L 330 475", color=BLUE, width=4, marker=True)
    path(lines, "M 520 368 L 520 430 L 765 430 L 765 475", color=BLUE, width=4, marker=True)
    badge(lines, 335, 430, "是", BLUE)
    badge(lines, 765, 430, "否", BLUE)
    decision_box(lines, 175, 475, 310, 72, "NVLink / PCIe P2P", color=BLUE)
    decision_box(lines, 610, 475, 310, 72, "SHM / CPU 中转", color=BLUE)

    decision_box(lines, 1010, 300, 250, 72, "走 NET", color=BLUE)
    decision_box(lines, 955, 455, 360, 72, "IB / RoCE / TCP", color=BLUE)
    line(lines, 1135, 372, 1135, 455, color=BLUE, width=4, marker=True)
    decision_box(lines, 935, 605, 400, 68, "IB/RoCE 是否启用 GDRDMA？", color=ORANGE, fill=LIGHT_ORANGE)
    line(lines, 1135, 527, 1135, 605, color=BLUE, width=4, marker=True)
    path(lines, "M 1135 673 L 1135 720 L 915 720 L 915 750", color=GREEN, width=4, marker=True)
    path(lines, "M 1135 673 L 1135 720 L 1375 720 L 1375 750", color=BLUE, width=4, marker=True)
    badge(lines, 945, 720, "是", GREEN)
    badge(lines, 1325, 720, "否", ORANGE)
    decision_box(lines, 720, 750, 390, 78, "GPU ↔ NIC 直通", color=GREEN, fill=LIGHT_GREEN)
    decision_box(lines, 1180, 750, 390, 78, "GPU ↔ CPU ↔ NIC", color=BLUE)
    text(lines, 1135, 560, "GDRDMA 属于跨节点 NET 路径能力，不和 NET 平级", size=22, fill=GRAY, weight=600)
    finish(lines, "04-transport-decision", "修正版：GDRDMA 放在 NET / IB / RoCE 分支下面。")


def diagram_05():
    lines = base("NCCL 最后生成的是通信图", "不是只选一条线，而是安排一整套通信计划")
    card_w = 470
    xs = [40, 565, 1090]
    titles = ["Ring", "Tree", "Multi-Channel"]
    for i, x in enumerate(xs):
        rect(lines, x, 190, card_w, 610, rx=18, fill="#ffffff", stroke=BLUE, sw=3)
        circle(lines, x + 160, 250, 26, fill=BLUE)
        text(lines, x + 160, 259, str(i + 1), size=28, fill="#ffffff", weight=800)
        text(lines, x + 270, 260, titles[i], size=36, fill=NAVY, weight=800)
    # Ring
    coords = [(275, 360), (405, 500), (275, 640), (145, 500)]
    for idx, (x, y) in enumerate(coords):
        decision_box(lines, x - 55, y - 35, 110, 70, f"GPU{idx}", color=BLUE)
    path(lines, "M 330 360 C 390 380 430 435 425 500", color=BLUE, width=4, marker=True)
    path(lines, "M 405 535 C 390 600 335 635 275 640", color=BLUE, width=4, marker=True)
    path(lines, "M 220 640 C 160 620 125 565 145 500", color=BLUE, width=4, marker=True)
    path(lines, "M 145 465 C 155 405 220 360 275 360", color=BLUE, width=4, marker=True)
    line(lines, 100, 720, 450, 720, color=GRAY, width=2, marker=False)
    text(lines, 275, 755, "环形", size=24, fill=GRAY, weight=700)
    # Tree
    decision_box(lines, 745, 325, 130, 70, "GPU0", color=BLUE)
    decision_box(lines, 630, 495, 130, 70, "GPU1", color=BLUE)
    decision_box(lines, 865, 495, 130, 70, "GPU2", color=BLUE)
    decision_box(lines, 865, 650, 130, 70, "GPU3", color=BLUE)
    line(lines, 810, 395, 695, 495, color=BLUE, width=4, marker=True)
    line(lines, 810, 395, 930, 495, color=BLUE, width=4, marker=True)
    line(lines, 930, 565, 930, 650, color=BLUE, width=4, marker=True)
    line(lines, 625, 720, 970, 720, color=GRAY, width=2, marker=False)
    text(lines, 800, 755, "树形", size=24, fill=GRAY, weight=700)
    # Channels
    channel_data = [
        ("Channel 0", ["GPU0", "GPU1", "GPU2", "GPU3"]),
        ("Channel 1", ["GPU0", "GPU2", "GPU1", "GPU3"]),
        ("Channel 2", ["GPU3", "GPU2", "GPU1", "GPU0"]),
    ]
    for idx, (label, nodes) in enumerate(channel_data):
        y = 310 + idx * 145
        rect(lines, 1110, y, 430, 100, rx=12, fill="#ffffff", stroke=BLUE, sw=2, dash="6 6")
        text(lines, 1150, y + 34, label, size=20, fill=BLUE, weight=800, anchor="start")
        for j, node in enumerate(nodes):
            x = 1150 + j * 100
            decision_box(lines, x, y + 50, 76, 38, node, color=BLUE)
            if j < 3:
                line(lines, x + 76, y + 69, x + 98, y + 69, color=BLUE, width=3, marker=True)
    line(lines, 1130, 720, 1530, 720, color=GRAY, width=2, marker=False)
    text(lines, 1330, 755, "并行多通道", size=24, fill=GRAY, weight=700)
    finish(lines, "05-communication-graph", "NCCL 不是只选一条线，而是安排一整套通信计划。")


def diagram_06():
    lines = base("训练慢时，按这张图排查 NCCL", "从计算节点内部，一路查到网络交换侧")
    boxes = [
        ("GPU 拓扑", "NVLink / PCIe", "chip", False),
        ("GPU-NIC\n距离", "NUMA / PCIe\nAffinity", "nic", False),
        ("网络类型", "IB / RoCE / TCP", "net", False),
        ("GDRDMA", "是否直通 GPU 显存", "gdr", True),
        ("NCCL 图", "Ring / Tree /\nChannel", "ring", False),
        ("交换机侧", "PFC / ECN /\n拥塞 / 丢包", "switch", True),
    ]
    start_x, gap, bw, bh = 30, 280, 220, 380
    for i, (title, detail, icon, key) in enumerate(boxes):
        x = start_x + i * gap
        rect(lines, x, 270, bw, bh, rx=18, fill="#ffffff", stroke=BLUE, sw=3)
        circle(lines, x + 38, 315, 22, fill=BLUE)
        text(lines, x + 38, 323, str(i + 1), size=24, fill="#ffffff", weight=800)
        if key:
            rect(lines, x + 150, 290, 55, 34, rx=16, fill="#ffffff", stroke=ORANGE, sw=2)
            text(lines, x + 177, 314, "关键", size=18, fill=ORANGE, weight=800)
        multiline(lines, x + bw / 2, 385, title.split("\n"), size=32, fill=NAVY, weight=800, gap=42)
        multiline(lines, x + bw / 2, 470, detail.split("\n"), size=22, fill=BLUE, weight=600, gap=32)
        draw_box_icon(lines, x + bw / 2, 570, icon)
        if i < len(boxes) - 1:
            line(lines, x + bw + 10, 460, x + gap - 25, 460, color=BLUE, width=8, marker=True)
    # Legend
    line(lines, 95, 735, 210, 735, color=BLUE, width=6, marker=True)
    text(lines, 275, 744, "主数据流 / 排查链路", size=22, fill=NAVY, weight=600)
    line(lines, 500, 735, 615, 735, color=GREEN, width=5, marker=False)
    text(lines, 700, 744, "最佳路径（应达到）", size=22, fill=NAVY, weight=600)
    line(lines, 915, 735, 1030, 735, color=ORANGE, width=5, marker=False, dash="10 10")
    text(lines, 1125, 744, "控制 / 决策点", size=22, fill=NAVY, weight=600)
    line(lines, 1275, 735, 1390, 735, color=RED, width=5, marker=True, dash="10 10")
    text(lines, 1480, 744, "低效线路（待排除）", size=22, fill=NAVY, weight=600)
    finish(lines, "06-troubleshooting-map", "这张适合放在文章后半部分，读者会觉得很实用。")


def draw_box_icon(lines, cx, cy, kind):
    if kind == "chip":
        draw_icon(lines, cx, cy, "chip")
    elif kind == "nic":
        small_box(lines, cx - 62, cy - 25, 60, 50, "NIC")
        rect(lines, cx + 20, cy - 30, 54, 60, rx=8, fill=LIGHT_BLUE, stroke=BLUE, sw=3)
        line(lines, cx - 2, cy, cx + 20, cy, color=BLUE, width=4, marker=True)
    elif kind == "net":
        circle(lines, cx, cy, 45, fill="#ffffff", stroke=BLUE, sw=4)
        line(lines, cx - 45, cy, cx + 45, cy, color=BLUE, width=3, marker=False)
        line(lines, cx, cy - 45, cx, cy + 45, color=BLUE, width=3, marker=False)
        path(lines, f"M {cx-35} {cy-20} C {cx-5} {cy-5} {cx+5} {cy-5} {cx+35} {cy-20}", color=BLUE, width=3, marker=False)
        path(lines, f"M {cx-35} {cy+20} C {cx-5} {cy+5} {cx+5} {cy+5} {cx+35} {cy+20}", color=BLUE, width=3, marker=False)
    elif kind == "gdr":
        rect(lines, cx - 74, cy - 34, 55, 68, rx=6, fill=LIGHT_BLUE, stroke=BLUE, sw=3)
        text(lines, cx - 47, cy + 8, "GPU", size=18, fill=BLUE, weight=800)
        rect(lines, cx + 35, cy - 34, 55, 68, rx=6, fill=LIGHT_GREEN, stroke=GREEN, sw=3)
        text(lines, cx + 62, cy + 8, "NIC", size=18, fill=GREEN, weight=800)
        line(lines, cx - 19, cy, cx + 35, cy, color=GREEN, width=5, marker=True)
        line(lines, cx + 35, cy, cx - 19, cy, color=GREEN, width=5, marker=True)
    elif kind == "ring":
        draw_icon(lines, cx - 25, cy, "ringtree")
    elif kind == "switch":
        path(lines, f"M {cx-65} {cy-30} L {cx+65} {cy-30} L {cx+45} {cy+35} L {cx-85} {cy+35} Z", color=BLUE, width=4, marker=False, fill=LIGHT_BLUE)
        for i in range(4):
            rect(lines, cx - 60 + i * 30, cy + 5, 20, 12, rx=2, fill="#ffffff", stroke=BLUE, sw=2)


if __name__ == "__main__":
    diagram_01()
    diagram_02()
    diagram_03()
    diagram_04()
    diagram_05()
    diagram_06()
    print(f"Generated diagrams in {OUT}")
