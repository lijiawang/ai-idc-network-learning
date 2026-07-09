from __future__ import annotations

import html
import subprocess
from pathlib import Path


OUT_DIR = Path(__file__).parent / "assets-drawn"
OUT_DIR.mkdir(parents=True, exist_ok=True)


FONT = "'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif"


COLORS = {
    "ink": "#111827",
    "muted": "#6b7280",
    "line": "#d1d5db",
    "soft": "#f9fafb",
    "blue": "#2563eb",
    "blue_bg": "#eff6ff",
    "blue_stroke": "#bfdbfe",
    "green": "#16a34a",
    "green_bg": "#f0fdf4",
    "green_stroke": "#bbf7d0",
    "purple": "#9333ea",
    "purple_bg": "#faf5ff",
    "purple_stroke": "#e9d5ff",
    "orange": "#ea580c",
    "orange_bg": "#fff7ed",
    "orange_stroke": "#fed7aa",
    "red": "#dc2626",
    "red_bg": "#fef2f2",
    "red_stroke": "#fecaca",
    "teal": "#0f766e",
    "teal_bg": "#f0fdfa",
    "teal_stroke": "#99f6e4",
    "slate_bg": "#f8fafc",
    "slate_stroke": "#cbd5e1",
}


def esc(value: str) -> str:
    return html.escape(value, quote=True)


class SVG:
    def __init__(self, title: str, width: int = 1440, height: int = 900):
        self.title = title
        self.width = width
        self.height = height
        self.items: list[str] = []

    def add(self, value: str) -> None:
        self.items.append(value)

    def text(
        self,
        x: float,
        y: float,
        text: str,
        *,
        size: int = 22,
        weight: int | str = 400,
        fill: str = COLORS["ink"],
        anchor: str = "start",
        opacity: float = 1,
    ) -> None:
        self.add(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" opacity="{opacity}">{esc(text)}</text>'
        )

    def multiline(
        self,
        x: float,
        y: float,
        lines: list[str],
        *,
        size: int = 20,
        weight: int | str = 400,
        fill: str = COLORS["ink"],
        anchor: str = "middle",
        line_gap: int = 24,
    ) -> None:
        self.add(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}">'
        )
        for i, line in enumerate(lines):
            dy = 0 if i == 0 else line_gap
            self.add(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
        self.add("</text>")

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        rx: int = 14,
        fill: str = "#ffffff",
        stroke: str = COLORS["line"],
        sw: float = 2,
        dash: str | None = None,
        opacity: float = 1,
    ) -> None:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"{dash_attr}/>'
        )

    def circle(
        self,
        cx: float,
        cy: float,
        r: float,
        *,
        fill: str,
        stroke: str = "none",
        sw: float = 2,
        opacity: float = 1,
    ) -> None:
        self.add(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" opacity="{opacity}"/>'
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        color: str = COLORS["blue"],
        width: float = 3,
        arrow: str | None = "blue",
        dash: str | None = None,
        opacity: float = 1,
    ) -> None:
        marker = f' marker-end="url(#arrow-{arrow})"' if arrow else ""
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="{width}" fill="none" opacity="{opacity}"{dash_attr}{marker}/>'
        )

    def path(
        self,
        d: str,
        *,
        color: str = COLORS["blue"],
        width: float = 3,
        arrow: str | None = "blue",
        dash: str | None = None,
        opacity: float = 1,
    ) -> None:
        marker = f' marker-end="url(#arrow-{arrow})"' if arrow else ""
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(
            f'<path d="{d}" stroke="{color}" stroke-width="{width}" fill="none" '
            f'opacity="{opacity}"{dash_attr}{marker}/>'
        )

    def title_block(self, subtitle: str | None = None) -> None:
        self.text(60, 58, self.title, size=30, weight=700)
        if subtitle:
            self.text(60, 92, subtitle, size=18, fill=COLORS["muted"])
        self.line(60, 118, self.width - 60, 118, color="#e5e7eb", width=2, arrow=None)

    def node(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        subtitle: str | None = None,
        *,
        fill: str = "#ffffff",
        stroke: str = COLORS["line"],
        accent: str | None = None,
        icon: str | None = None,
        title_size: int = 19,
    ) -> None:
        self.rect(x, y, w, h, fill=fill, stroke=stroke)
        if accent:
            self.rect(x, y, 10, h, rx=14, fill=accent, stroke=accent, sw=0)
        if icon:
            self.circle(x + 34, y + h / 2, 19, fill=accent or stroke, opacity=0.95)
            self.text(x + 34, y + h / 2 + 7, icon, size=15, weight=700, fill="#ffffff", anchor="middle")
            text_x = x + 64
            anchor = "start"
        else:
            text_x = x + w / 2
            anchor = "middle"
        if subtitle:
            self.text(text_x, y + h / 2 - 4, title, size=title_size, weight=700, anchor=anchor)
            self.text(text_x, y + h / 2 + 25, subtitle, size=15, fill=COLORS["muted"], anchor=anchor)
        else:
            self.text(text_x, y + h / 2 + 7, title, size=title_size, weight=700, anchor=anchor)

    def legend(self, x: float, y: float, items: list[tuple[str, str, str]]) -> None:
        self.rect(x, y, 360, 42 + len(items) * 30, fill="#ffffff", stroke="#e5e7eb", sw=1.5)
        self.text(x + 18, y + 30, "图例", size=16, weight=700)
        for idx, (label, color, key) in enumerate(items):
            yy = y + 58 + idx * 30
            self.line(x + 20, yy - 5, x + 70, yy - 5, color=color, width=3, arrow=key)
            self.text(x + 84, yy, label, size=14, fill=COLORS["muted"])

    def render(self) -> str:
        defs = f"""
<defs>
  <marker id="arrow-blue" markerWidth="12" markerHeight="8" refX="11" refY="4" orient="auto"><polygon points="0 0, 12 4, 0 8" fill="{COLORS['blue']}"/></marker>
  <marker id="arrow-green" markerWidth="12" markerHeight="8" refX="11" refY="4" orient="auto"><polygon points="0 0, 12 4, 0 8" fill="{COLORS['green']}"/></marker>
  <marker id="arrow-purple" markerWidth="12" markerHeight="8" refX="11" refY="4" orient="auto"><polygon points="0 0, 12 4, 0 8" fill="{COLORS['purple']}"/></marker>
  <marker id="arrow-orange" markerWidth="12" markerHeight="8" refX="11" refY="4" orient="auto"><polygon points="0 0, 12 4, 0 8" fill="{COLORS['orange']}"/></marker>
  <marker id="arrow-red" markerWidth="12" markerHeight="8" refX="11" refY="4" orient="auto"><polygon points="0 0, 12 4, 0 8" fill="{COLORS['red']}"/></marker>
</defs>
"""
        body = "\n".join(self.items)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}">
<style>
text {{ font-family: {FONT}; }}
.small {{ font-size: 14px; fill: {COLORS['muted']}; }}
</style>
{defs}
<rect width="{self.width}" height="{self.height}" fill="#ffffff"/>
{body}
</svg>
"""


def rack_icon(svg: SVG, x: int, y: int, w: int, h: int, label: str, fill: str = "#111827") -> None:
    svg.rect(x, y, w, h, rx=10, fill=fill, stroke="#374151", sw=2)
    for i in range(8):
        yy = y + 18 + i * ((h - 36) / 8)
        svg.rect(x + 12, yy, w - 24, 10, rx=3, fill="#374151", stroke="none", sw=0)
    svg.circle(x + w - 18, y + 18, 4, fill="#22c55e")
    svg.text(x + w / 2, y + h + 26, label, size=14, weight=700, anchor="middle")


def switch_icon(svg: SVG, x: int, y: int, w: int, h: int, label: str, *, fill: str, stroke: str) -> None:
    svg.rect(x, y, w, h, rx=8, fill=fill, stroke=stroke)
    for i in range(5):
        svg.rect(x + 18 + i * 28, y + 20, 18, 12, rx=2, fill="#ffffff", stroke=stroke, sw=1)
    svg.text(x + w / 2, y + h + 23, label, size=14, weight=700, anchor="middle")


def cloud(svg: SVG, x: int, y: int, w: int, h: int, label: str, *, fill: str = "#ffffff", stroke: str = COLORS["line"]) -> None:
    d = (
        f"M{x + w * 0.18},{y + h * 0.68} "
        f"C{x + w * 0.02},{y + h * 0.66} {x},{y + h * 0.45} {x + w * 0.16},{y + h * 0.38} "
        f"C{x + w * 0.20},{y + h * 0.14} {x + w * 0.45},{y + h * 0.08} {x + w * 0.58},{y + h * 0.24} "
        f"C{x + w * 0.78},{y + h * 0.10} {x + w},{y + h * 0.25} {x + w * 0.92},{y + h * 0.52} "
        f"C{x + w * 1.04},{y + h * 0.68} {x + w * 0.84},{y + h * 0.86} {x + w * 0.70},{y + h * 0.78} "
        f"C{x + w * 0.55},{y + h * 0.92} {x + w * 0.32},{y + h * 0.88} {x + w * 0.18},{y + h * 0.68} Z"
    )
    svg.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    svg.text(x + w / 2, y + h * 0.58, label, size=17, weight=700, anchor="middle")


def diagram_su_overview() -> SVG:
    svg = SVG("DGX GB200 SuperPOD：单个 Scalable Unit（SU）", 1440, 900)
    svg.title_block("一个 SU = 8 个 DGX GB200 NVL72 机柜，合计 576 GPU，约 1.2MW TDP")
    svg.rect(70, 170, 1300, 500, fill=COLORS["slate_bg"], stroke=COLORS["slate_stroke"], dash="10 7")
    svg.text(95, 205, "单个 SU 物理布局", size=20, weight=700)

    rack_icon(svg, 120, 355, 100, 190, "HPS", "#0f172a")
    switch_icon(svg, 260, 335, 150, 70, "IB 训练网", fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"])
    switch_icon(svg, 260, 485, 150, 70, "以太网", fill=COLORS["green_bg"], stroke=COLORS["green_stroke"])

    start_x = 455
    for i in range(8):
        rack_icon(svg, start_x + i * 82, 300, 64, 245, f"DGX{i + 1}", "#1f2937")
    svg.rect(435, 275, 700, 305, fill="none", stroke=COLORS["purple"], sw=2.5, dash="8 7")
    svg.text(785, 270, "8 × DGX GB200 NVL72 计算机柜", size=20, weight=700, anchor="middle", fill=COLORS["purple"])

    switch_icon(svg, 1160, 335, 150, 70, "管理节点", fill=COLORS["orange_bg"], stroke=COLORS["orange_stroke"])
    switch_icon(svg, 1160, 485, 150, 70, "BMS / OT", fill=COLORS["red_bg"], stroke=COLORS["red_stroke"])

    svg.path("M210 360 C300 250, 530 235, 785 275", color=COLORS["green"], arrow="green")
    svg.path("M410 370 C520 235, 830 235, 1160 370", color=COLORS["blue"], arrow="blue")
    svg.path("M410 520 C600 650, 970 650, 1160 520", color=COLORS["orange"], arrow="orange")
    svg.path("M1235 485 C1235 430, 1190 390, 1120 360", color=COLORS["red"], arrow="red", dash="9 7")

    svg.node(110, 720, 240, 90, "计算", "576 GPU / NVL72 × 8", fill=COLORS["purple_bg"], stroke=COLORS["purple_stroke"], accent=COLORS["purple"], icon="GPU")
    svg.node(410, 720, 240, 90, "网络", "InfiniBand + Ethernet", fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="NET")
    svg.node(710, 720, 240, 90, "存储", "高性能共享数据面", fill=COLORS["green_bg"], stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="IO")
    svg.node(1010, 720, 240, 90, "运维", "管理节点 + BMS/OT", fill=COLORS["orange_bg"], stroke=COLORS["orange_stroke"], accent=COLORS["orange"], icon="OPS")
    return svg


def diagram_rack_internal() -> SVG:
    svg = SVG("DGX GB200 NVL72 机柜内部结构", 1440, 900)
    svg.title_block("72 张 GPU 先在单机柜内形成一个高速 NVLink 域")
    svg.rect(95, 160, 420, 600, fill="#111827", stroke="#374151", sw=3)
    svg.text(305, 140, "DGX GB200 NVL72 Rack", size=21, weight=700, anchor="middle")

    for i in range(18):
        col = i % 2
        row = i // 2
        x = 125 + col * 190
        y = 190 + row * 48
        svg.rect(x, y, 170, 34, rx=5, fill="#374151", stroke="#64748b", sw=1)
        svg.text(x + 85, y + 23, f"Compute Tray {i + 1}", size=13, fill="#f9fafb", anchor="middle")

    for i in range(9):
        y = 190 + i * 48
        svg.rect(420, y, 68, 34, rx=5, fill="#312e81", stroke="#818cf8", sw=1)
        svg.text(454, y + 23, "NVSW", size=12, weight=700, fill="#e0e7ff", anchor="middle")

    for i in range(4):
        svg.rect(125 + i * 90, 645, 70, 35, rx=5, fill="#7c2d12", stroke="#fdba74", sw=1)
        svg.text(160 + i * 90, 668, "Power", size=12, fill="#ffedd5", anchor="middle")
    for i in range(4):
        svg.rect(125 + i * 90, 695, 70, 35, rx=5, fill="#7c2d12", stroke="#fdba74", sw=1)
        svg.text(160 + i * 90, 718, "Shelf", size=12, fill="#ffedd5", anchor="middle")

    svg.rect(585, 180, 760, 140, fill=COLORS["purple_bg"], stroke=COLORS["purple_stroke"])
    svg.multiline(965, 230, ["72 GPU NVLink 域", "机柜内 scale-up，尽量让高频通信留在本地"], size=23, weight=700)
    svg.line(515, 405, 585, 250, color=COLORS["purple"], arrow="purple", width=4)

    svg.node(605, 380, 210, 95, "18 × Compute Tray", "每个 tray = 4 GPU", fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="18")
    svg.node(870, 380, 210, 95, "9 × NVLink Switch", "18 个交换芯片", fill=COLORS["purple_bg"], stroke=COLORS["purple_stroke"], accent=COLORS["purple"], icon="SW")
    svg.node(1135, 380, 210, 95, "8 × Power Shelf", "高密供电与冗余", fill=COLORS["orange_bg"], stroke=COLORS["orange_stroke"], accent=COLORS["orange"], icon="PWR")

    svg.node(605, 560, 300, 105, "CX-7 InfiniBand", "跨 rack 训练通信：NDR 400G", fill="#ffffff", stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="IB")
    svg.node(1045, 560, 300, 105, "BlueField-3 Ethernet", "存储与带内管理：2×200G/4×200G", fill="#ffffff", stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="BF3")
    svg.path("M815 428 C870 500, 850 540, 755 560", color=COLORS["blue"], arrow="blue")
    svg.path("M1080 428 C1110 495, 1140 530, 1195 560", color=COLORS["green"], arrow="green")

    svg.legend(605, 720, [("机柜内 NVLink scale-up", COLORS["purple"], "purple"), ("跨机柜 InfiniBand scale-out", COLORS["blue"], "blue"), ("存储/管理以太网", COLORS["green"], "green")])
    return svg


def diagram_compute_tray() -> SVG:
    svg = SVG("GB200 Compute Tray：从 Superchip 到网络接口", 1440, 900)
    svg.title_block("每个 compute tray 内含 2 个 GB200 Superchip，共 4 张 B200 GPU")
    svg.rect(90, 175, 1260, 520, fill=COLORS["slate_bg"], stroke=COLORS["slate_stroke"])
    svg.text(120, 215, "Compute Tray", size=24, weight=700)

    for block, x in enumerate([170, 690]):
        svg.rect(x, 265, 420, 300, fill="#ffffff", stroke=COLORS["purple_stroke"], sw=2.5)
        svg.text(x + 210, 250, f"GB200 Superchip {block + 1}", size=21, weight=700, anchor="middle", fill=COLORS["purple"])
        svg.node(x + 35, 330, 130, 90, "Grace CPU", "控制与内存", fill=COLORS["orange_bg"], stroke=COLORS["orange_stroke"], accent=COLORS["orange"], icon="CPU", title_size=17)
        svg.node(x + 215, 300, 150, 90, "B200 GPU", "Tensor Core", fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="G1", title_size=17)
        svg.node(x + 215, 430, 150, 90, "B200 GPU", "Tensor Core", fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="G2", title_size=17)
        svg.line(x + 165, 375, x + 215, 345, color=COLORS["purple"], arrow="purple")
        svg.line(x + 165, 375, x + 215, 475, color=COLORS["purple"], arrow="purple")
        svg.text(x + 185, 398, "NVLink-C2C", size=14, fill=COLORS["purple"])

    svg.path("M590 415 C630 390, 650 390, 690 415", color=COLORS["purple"], width=4, arrow="purple")
    svg.text(640, 380, "tray 内互联", size=16, fill=COLORS["purple"], anchor="middle")

    svg.node(170, 720, 240, 95, "4 × CX-7 NIC", "InfiniBand Compute Fabric", fill="#ffffff", stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="IB")
    svg.node(500, 720, 260, 95, "2 × BlueField-3 DPU", "Storage + In-band Ethernet", fill="#ffffff", stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="BF")
    svg.node(850, 720, 220, 95, "E1.S NVMe", "本地缓存 / staging", fill="#ffffff", stroke=COLORS["orange_stroke"], accent=COLORS["orange"], icon="SSD")
    svg.node(1160, 720, 170, 95, "M.2 NVMe", "OS 镜像", fill="#ffffff", stroke=COLORS["slate_stroke"], accent="#64748b", icon="OS")

    svg.line(290, 565, 290, 720, color=COLORS["blue"], arrow="blue")
    svg.line(630, 565, 630, 720, color=COLORS["green"], arrow="green")
    svg.line(960, 565, 960, 720, color=COLORS["orange"], arrow="orange")
    svg.line(1245, 565, 1245, 720, color="#64748b", arrow=None)
    return svg


def diagram_fabric_overview() -> SVG:
    svg = SVG("DGX SuperPOD 的五张逻辑网络", 1440, 900)
    svg.title_block("逻辑上拆成 5 张网，物理上落在 4 类 fabric，避免训练、存储和管理互相干扰")

    rows = [
        ("NVLink5", "机柜内 GPU scale-up", "Multi-node NVLink Fabric", COLORS["purple"], COLORS["purple_bg"], COLORS["purple_stroke"]),
        ("Compute Fabric", "跨机柜 / 跨 SU 训练通信", "Compute InfiniBand Fabric", COLORS["blue"], COLORS["blue_bg"], COLORS["blue_stroke"]),
        ("Storage Fabric", "高性能共享存储与 RoCE", "Storage + In-band Ethernet Fabric", COLORS["green"], COLORS["green_bg"], COLORS["green_stroke"]),
        ("In-band Management", "provisioning、用户访问、服务流量", "Storage + In-band Ethernet Fabric", COLORS["orange"], COLORS["orange_bg"], COLORS["orange_stroke"]),
        ("Out-of-band Management", "BMC、PDU、交换机管理口", "Out-of-Band Network", COLORS["red"], COLORS["red_bg"], COLORS["red_stroke"]),
    ]
    svg.text(120, 170, "逻辑网络", size=22, weight=700)
    svg.text(990, 170, "物理 fabric", size=22, weight=700, anchor="middle")
    for i, (name, desc, fabric, color, bg, stroke) in enumerate(rows):
        y = 220 + i * 115
        svg.node(110, y, 370, 78, name, desc, fill=bg, stroke=stroke, accent=color, icon=str(i + 1), title_size=20)
        svg.node(930, y, 360, 78, fabric, None, fill="#ffffff", stroke=stroke, accent=color, icon="PHY", title_size=18)
        svg.line(480, y + 39, 930, y + 39, color=color, arrow={COLORS["purple"]:"purple", COLORS["blue"]:"blue", COLORS["green"]:"green", COLORS["orange"]:"orange", COLORS["red"]:"red"}[color], width=3)
    svg.rect(590, 200, 230, 620, fill="#ffffff", stroke="#e5e7eb", dash="9 7")
    svg.multiline(705, 455, ["隔离原则", "训练网", "存储网", "管理网", "硬件管理网", "不要混跑"], size=21, weight=700, line_gap=38)
    return svg


def diagram_nvlink_scaleup() -> SVG:
    svg = SVG("机柜内 NVLink scale-up：72 GPU 共享一个高速域", 1440, 900)
    svg.title_block("简化为 18 个 compute tray × 4 GPU，连接到 NVLink Switch 层")
    svg.rect(70, 170, 1300, 600, fill=COLORS["purple_bg"], stroke=COLORS["purple_stroke"], dash="12 8")
    svg.text(100, 210, "DGX GB200 NVL72 Rack", size=23, weight=700, fill=COLORS["purple"])

    tray_xs = [125, 365, 605, 845, 1085]
    for idx, x in enumerate(tray_xs):
        svg.rect(x, 270, 170, 120, fill="#ffffff", stroke=COLORS["blue_stroke"])
        svg.text(x + 85, 255, f"Tray {idx + 1}", size=16, weight=700, anchor="middle")
        for g in range(4):
            svg.rect(x + 18 + g * 36, 305, 28, 44, rx=5, fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"])
            svg.text(x + 32 + g * 36, 333, f"G{g + 1}", size=11, weight=700, anchor="middle", fill=COLORS["blue"])
    svg.text(1265, 335, "...", size=42, weight=700, fill=COLORS["muted"])
    svg.text(705, 435, "18 个 compute tray，合计 72 张 GPU", size=20, anchor="middle", fill=COLORS["muted"])

    for i in range(9):
        x = 150 + i * 130
        svg.rect(x, 555, 85, 72, rx=8, fill="#312e81", stroke="#818cf8", sw=2)
        svg.text(x + 42.5, 598, f"SW{i + 1}", size=15, weight=700, fill="#e0e7ff", anchor="middle")
    svg.text(705, 680, "9 个 NVLink Switch Tray / 18 个 NVLink Switch Chip", size=20, anchor="middle", fill=COLORS["purple"])

    for x in tray_xs:
        for sx in [190, 450, 710, 970, 1230]:
            svg.line(x + 85, 390, sx, 555, color=COLORS["purple"], arrow=None, width=1.4, opacity=0.32)
    svg.path("M125 735 C380 805, 1040 805, 1285 735", color=COLORS["purple"], arrow="purple", width=4)
    svg.text(705, 820, "目标：让 tensor/model/expert 并行中的高频通信尽量在机柜内完成", size=22, weight=700, anchor="middle")
    return svg


def diagram_ib_rail() -> SVG:
    svg = SVG("Compute Fabric：Rail-Optimized InfiniBand", 1440, 900)
    svg.title_block("同编号 NIC/GPU 进入同一条 rail，降低 hash 热点和跨 rail 抖动")

    for r in range(8):
        y = 170 + r * 72
        color = COLORS["blue"] if r % 2 == 0 else COLORS["purple"]
        svg.rect(80, y, 1240, 46, rx=8, fill="#ffffff", stroke="#e5e7eb", sw=1.4)
        svg.text(100, y + 29, f"Rail {r}", size=15, weight=700, fill=color)
        svg.rect(210, y + 8, 115, 30, rx=6, fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], sw=1)
        svg.text(267, y + 29, "Leaf", size=13, weight=700, anchor="middle", fill=COLORS["blue"])
        svg.rect(1110, y + 8, 115, 30, rx=6, fill=COLORS["purple_bg"], stroke=COLORS["purple_stroke"], sw=1)
        svg.text(1167, y + 29, "Spine", size=13, weight=700, anchor="middle", fill=COLORS["purple"])
        svg.line(325, y + 23, 1110, y + 23, color=color, arrow={COLORS["blue"]:"blue", COLORS["purple"]:"purple"}[color], width=2.6, opacity=0.65)

    for i in range(8):
        x = 220 + i * 130
        rack_icon(svg, x, 765, 70, 105, f"Rack{i + 1}", "#1f2937")
        for r in range(8):
            y = 193 + r * 72
            svg.line(x + 35, 765, 267, y, color=COLORS["blue"], arrow=None, width=0.7, opacity=0.12)

    return svg


def diagram_scaleout() -> SVG:
    svg = SVG("Compute Fabric 扩展：从 1 SU 到 16 SU", 1440, 900)
    svg.title_block("每个 SU 保持内部 rail 结构，多 SU 通过 core group 做 scale-out")

    for i, x in enumerate([110, 410, 710, 1010]):
        svg.rect(x, 510, 220, 220, fill=COLORS["slate_bg"], stroke=COLORS["slate_stroke"], dash="8 6")
        svg.text(x + 110, 545, f"SU {i + 1}", size=22, weight=700, anchor="middle")
        for r in range(4):
            svg.rect(x + 35, 575 + r * 32, 150, 20, rx=4, fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], sw=1)
            svg.text(x + 110, 590 + r * 32, f"SLG / Rail group {r + 1}", size=11, anchor="middle", fill=COLORS["blue"])
    svg.text(1235, 625, "...", size=46, weight=700, fill=COLORS["muted"])

    for i in range(6):
        x = 155 + i * 205
        switch_icon(svg, x, 280, 140, 58, f"Core Group {i + 1}", fill=COLORS["purple_bg"], stroke=COLORS["purple_stroke"])

    svg.rect(80, 185, 1280, 210, fill="#ffffff", stroke=COLORS["purple_stroke"], dash="10 8")
    svg.text(105, 220, "Core layer：预留到目标规模，扩容时保持拓扑对称", size=22, weight=700, fill=COLORS["purple"])

    for su_x in [220, 520, 820, 1120]:
        for core_x in [225, 430, 635, 840, 1045, 1250]:
            svg.line(su_x, 510, core_x, 338, color=COLORS["purple"], arrow=None, width=1.2, opacity=0.18)

    svg.node(120, 780, 250, 80, "2 SU", "1152 GPU", fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="2")
    svg.node(430, 780, 250, 80, "4 SU", "2304 GPU", fill=COLORS["green_bg"], stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="4")
    svg.node(740, 780, 250, 80, "8 SU", "4608 GPU", fill=COLORS["orange_bg"], stroke=COLORS["orange_stroke"], accent=COLORS["orange"], icon="8")
    svg.node(1050, 780, 250, 80, "16 SU", "9216 GPU", fill=COLORS["purple_bg"], stroke=COLORS["purple_stroke"], accent=COLORS["purple"], icon="16")
    return svg


def diagram_ethernet_segmentation() -> SVG:
    svg = SVG("Storage + In-band Ethernet Fabric：一套物理底座，三类逻辑网络", 1440, 900)
    svg.title_block("SN5600/SN2201 承载存储、带内管理和 OOB 汇聚，通过 VXLAN/VTEP 隔离")

    switch_icon(svg, 570, 165, 145, 62, "SN5600 Spine A", fill=COLORS["green_bg"], stroke=COLORS["green_stroke"])
    switch_icon(svg, 760, 165, 145, 62, "SN5600 Spine B", fill=COLORS["green_bg"], stroke=COLORS["green_stroke"])
    for i, (x, label) in enumerate([(165, "DGX Leaf"), (380, "Storage Leaf"), (595, "Mgmt Leaf"), (810, "OOB Leaf"), (1025, "Edge Leaf")]):
        switch_icon(svg, x, 330, 145, 62, label, fill="#ffffff", stroke=COLORS["slate_stroke"])
        svg.line(x + 72, 330, 642, 227, color=COLORS["green"], arrow=None, width=2, opacity=0.45)
        svg.line(x + 72, 330, 832, 227, color=COLORS["green"], arrow=None, width=2, opacity=0.45)

    rack_icon(svg, 150, 545, 85, 135, "DGX", "#1f2937")
    svg.node(330, 555, 190, 90, "HPS", "RoCE 存储", fill=COLORS["green_bg"], stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="IO")
    svg.node(590, 555, 190, 90, "K8s / Slurm", "带内服务", fill=COLORS["orange_bg"], stroke=COLORS["orange_stroke"], accent=COLORS["orange"], icon="SVC")
    svg.node(850, 555, 190, 90, "BMC / PDU", "OOB 管理", fill=COLORS["red_bg"], stroke=COLORS["red_stroke"], accent=COLORS["red"], icon="OOB")
    cloud(svg, 1110, 545, 170, 110, "客户边界", fill="#ffffff", stroke=COLORS["blue_stroke"])

    svg.line(205, 545, 237, 392, color=COLORS["green"], arrow="green", width=3)
    svg.line(425, 555, 452, 392, color=COLORS["green"], arrow="green", width=3)
    svg.line(685, 555, 667, 392, color=COLORS["orange"], arrow="orange", width=3)
    svg.line(945, 555, 882, 392, color=COLORS["red"], arrow="red", width=3)
    svg.line(1110, 585, 1097, 392, color=COLORS["blue"], arrow="blue", width=3)

    svg.legend(95, 735, [
        ("Storage Network：RoCE + 高吞吐", COLORS["green"], "green"),
        ("In-band：用户/调度/服务访问", COLORS["orange"], "orange"),
        ("OOB：硬件管理隔离", COLORS["red"], "red"),
        ("Customer Edge：eBGP/企业网", COLORS["blue"], "blue"),
    ])
    return svg


def diagram_storage_perf() -> SVG:
    svg = SVG("存储性能规划：不要只看容量，还要看读写吞吐", 1440, 900)
    svg.title_block("参考架构给出 Standard 与 Enhanced 两档聚合读写能力")
    labels = ["单 SU 读", "单 SU 写", "4 SU 读", "4 SU 写"]
    standard = [40, 20, 160, 80]
    enhanced = [125, 62, 500, 250]
    max_v = 520
    x0 = 220
    y0 = 700
    chart_w = 980
    chart_h = 430
    svg.rect(105, 170, 1220, 600, fill=COLORS["slate_bg"], stroke=COLORS["slate_stroke"])
    svg.text(150, 225, "聚合吞吐（GBps）", size=22, weight=700)
    for tick in [0, 100, 200, 300, 400, 500]:
        y = y0 - tick / max_v * chart_h
        svg.line(x0 - 30, y, x0 + chart_w, y, color="#e5e7eb", width=1, arrow=None)
        svg.text(x0 - 45, y + 6, str(tick), size=13, fill=COLORS["muted"], anchor="end")
    for i, label in enumerate(labels):
        x = x0 + i * 225
        std_h = standard[i] / max_v * chart_h
        enh_h = enhanced[i] / max_v * chart_h
        svg.rect(x, y0 - std_h, 70, std_h, rx=8, fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"])
        svg.rect(x + 85, y0 - enh_h, 70, enh_h, rx=8, fill=COLORS["green_bg"], stroke=COLORS["green_stroke"])
        svg.text(x + 35, y0 - std_h - 12, str(standard[i]), size=16, weight=700, fill=COLORS["blue"], anchor="middle")
        svg.text(x + 120, y0 - enh_h - 12, str(enhanced[i]), size=16, weight=700, fill=COLORS["green"], anchor="middle")
        svg.text(x + 78, y0 + 35, label, size=16, weight=700, anchor="middle")
    svg.node(1010, 250, 270, 95, "Standard", "计算主导 / 数据可缓存", fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="S")
    svg.node(1010, 380, 270, 95, "Enhanced", "多模态 / 大数据集 / I/O 敏感", fill=COLORS["green_bg"], stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="E")
    svg.node(1010, 510, 270, 105, "Checkpoint", "TB 级写入会阻塞训练进度", fill=COLORS["orange_bg"], stroke=COLORS["orange_stroke"], accent=COLORS["orange"], icon="CKPT")
    return svg


def diagram_oob_bms() -> SVG:
    svg = SVG("OOB 与 BMS：GB200 时代的管理边界", 1440, 900)
    svg.title_block("硬件管理、液冷、供电和客户边界需要一起规划")
    cloud(svg, 100, 210, 180, 110, "客户边界", fill="#ffffff", stroke=COLORS["blue_stroke"])
    svg.node(370, 215, 230, 90, "eBGP Edge", "企业网 / Internet / 路由交接", fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="BGP")
    svg.node(720, 180, 230, 90, "BMS", "楼宇与机房基础设施", fill=COLORS["orange_bg"], stroke=COLORS["orange_stroke"], accent=COLORS["orange"], icon="BMS")
    svg.node(1060, 170, 230, 90, "CDU / PDU / CTRL", "液冷、供电、控制器", fill=COLORS["red_bg"], stroke=COLORS["red_stroke"], accent=COLORS["red"], icon="OT")

    svg.node(720, 410, 230, 90, "OOB Fabric", "BMC / IPMI / 设备管理口", fill=COLORS["red_bg"], stroke=COLORS["red_stroke"], accent=COLORS["red"], icon="OOB")
    svg.node(370, 555, 230, 90, "In-band Fabric", "用户、调度、服务访问", fill=COLORS["green_bg"], stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="IBN")
    rack_icon(svg, 1080, 500, 95, 150, "DGX Rack", "#1f2937")
    switch_icon(svg, 1185, 545, 130, 55, "Switch", fill="#ffffff", stroke=COLORS["slate_stroke"])

    svg.line(280, 265, 370, 260, color=COLORS["blue"], arrow="blue")
    svg.line(600, 260, 720, 225, color=COLORS["blue"], arrow="blue", dash="8 6")
    svg.line(950, 225, 1060, 215, color=COLORS["orange"], arrow="orange")
    svg.line(835, 270, 835, 410, color=COLORS["orange"], arrow="orange", dash="8 6")
    svg.line(835, 500, 1080, 545, color=COLORS["red"], arrow="red")
    svg.line(600, 600, 1080, 620, color=COLORS["green"], arrow="green")
    svg.line(600, 260, 600, 555, color=COLORS["blue"], arrow="blue")

    svg.rect(85, 720, 1260, 95, fill="#ffffff", stroke="#e5e7eb")
    svg.multiline(715, 760, ["关键点：OOB 不是普通用户网络；BMS/OT 也不是“机房外部系统”，而是 AI 集群可用性的一部分"], size=22, weight=700)
    return svg


def diagram_software_stack() -> SVG:
    svg = SVG("DGX SuperPOD 软件栈：从硬件到作业编排", 1440, 900)
    svg.title_block("Mission Control 将部署、监控、诊断、调度和恢复串成闭环")
    layers = [
        ("AI 应用与框架", "NGC / AI Enterprise / Frameworks / Microservices", COLORS["purple"], COLORS["purple_bg"], COLORS["purple_stroke"]),
        ("工作负载编排", "Run:ai / Slurm / Kubernetes", COLORS["blue"], COLORS["blue_bg"], COLORS["blue_stroke"]),
        ("Mission Control", "健康检查 / 遥测 / 诊断 / 自动恢复 / 作业迁移", COLORS["green"], COLORS["green_bg"], COLORS["green_stroke"]),
        ("集群与网络管理", "BCM / UFM / NMX / 配置管理", COLORS["orange"], COLORS["orange_bg"], COLORS["orange_stroke"]),
        ("基础设施", "DGX GB200 / NVLink / InfiniBand / Ethernet / Storage", "#64748b", COLORS["slate_bg"], COLORS["slate_stroke"]),
    ]
    y = 170
    for idx, (name, desc, color, bg, stroke) in enumerate(layers):
        h = 100 if idx != 2 else 120
        svg.rect(160, y, 1120, h, fill=bg, stroke=stroke)
        svg.rect(160, y, 18, h, rx=12, fill=color, stroke=color, sw=0)
        svg.text(220, y + 42, name, size=24, weight=700)
        svg.text(220, y + 74, desc, size=18, fill=COLORS["muted"])
        if idx < len(layers) - 1:
            svg.line(720, y + h, 720, y + h + 30, color=color if color != "#64748b" else COLORS["blue"], arrow="blue")
        y += h + 30

    svg.node(1050, 355, 190, 80, "Self-Recovery", "降低训练中断", fill="#ffffff", stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="SR", title_size=17)
    svg.node(840, 355, 190, 80, "Telemetry", "观测与定位", fill="#ffffff", stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="OBS", title_size=17)
    svg.node(630, 355, 190, 80, "Diagnostics", "统一诊断", fill="#ffffff", stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="DG", title_size=17)
    return svg


def diagram_runai() -> SVG:
    svg = SVG("Run:ai：控制面与集群侧分离", 1440, 900)
    svg.title_block("研究人员通过 Console / CLI / API 提交作业，平台在 Kubernetes 集群内完成调度与资源管理")
    svg.rect(100, 220, 500, 420, fill=COLORS["blue_bg"], stroke=COLORS["blue_stroke"], dash="10 7")
    svg.text(130, 260, "Run:ai Control Plane", size=24, weight=700, fill=COLORS["blue"])
    svg.node(155, 310, 170, 80, "IAM", "身份与权限", fill="#ffffff", stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="ID", title_size=16)
    svg.node(375, 310, 170, 80, "API Gateway", "入口与鉴权", fill="#ffffff", stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="API", title_size=16)
    svg.node(155, 455, 170, 80, "Resource Mgmt", "配额与资源池", fill="#ffffff", stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="RM", title_size=16)
    svg.node(375, 455, 170, 80, "Monitoring", "指标与分析", fill="#ffffff", stroke=COLORS["blue_stroke"], accent=COLORS["blue"], icon="MON", title_size=16)

    svg.rect(820, 220, 500, 420, fill=COLORS["green_bg"], stroke=COLORS["green_stroke"], dash="10 7")
    svg.text(850, 260, "Run:ai Cluster / Kubernetes", size=24, weight=700, fill=COLORS["green"])
    svg.node(875, 310, 170, 80, "Scheduler", "GPU 调度", fill="#ffffff", stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="SCH", title_size=16)
    svg.node(1095, 310, 170, 80, "Workload Mgmt", "训练/推理作业", fill="#ffffff", stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="JOB", title_size=16)
    svg.node(875, 455, 170, 80, "Metrics", "指标汇聚", fill="#ffffff", stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="MET", title_size=16)
    svg.node(1095, 455, 170, 80, "GPU Pods", "GPU / 存储 / 网络", fill="#ffffff", stroke=COLORS["green_stroke"], accent=COLORS["green"], icon="GPU", title_size=16)

    svg.node(260, 720, 220, 80, "研究人员", "Console / CLI / API", fill=COLORS["purple_bg"], stroke=COLORS["purple_stroke"], accent=COLORS["purple"], icon="USER")
    svg.line(370, 720, 460, 535, color=COLORS["purple"], arrow="purple")
    svg.line(545, 350, 875, 350, color=COLORS["blue"], arrow="blue")
    svg.line(545, 495, 875, 495, color=COLORS["green"], arrow="green")
    svg.line(1180, 535, 1180, 680, color=COLORS["green"], arrow="green")
    svg.node(1060, 680, 240, 80, "GPU 资源利用率", "减少空转，提升吞吐", fill=COLORS["orange_bg"], stroke=COLORS["orange_stroke"], accent=COLORS["orange"], icon="UTIL")
    return svg


DIAGRAMS = {
    "drawn-01-su-overview": diagram_su_overview,
    "drawn-02-rack-internal": diagram_rack_internal,
    "drawn-03-compute-tray": diagram_compute_tray,
    "drawn-04-fabric-overview": diagram_fabric_overview,
    "drawn-05-nvlink-scaleup": diagram_nvlink_scaleup,
    "drawn-06-ib-rail-optimized": diagram_ib_rail,
    "drawn-07-compute-scaleout": diagram_scaleout,
    "drawn-08-ethernet-segmentation": diagram_ethernet_segmentation,
    "drawn-09-storage-performance": diagram_storage_perf,
    "drawn-10-oob-bms-edge": diagram_oob_bms,
    "drawn-11-software-stack": diagram_software_stack,
    "drawn-12-runai": diagram_runai,
}


def main() -> None:
    for name, factory in DIAGRAMS.items():
        svg = factory()
        svg_path = OUT_DIR / f"{name}.svg"
        png_path = OUT_DIR / f"{name}.png"
        validation_path = OUT_DIR / f".{name}.validate.png"
        svg_path.write_text(svg.render(), encoding="utf-8")
        subprocess.run(["rsvg-convert", str(svg_path), "-o", str(validation_path)], check=True)
        validation_path.unlink(missing_ok=True)
        subprocess.run(["rsvg-convert", "-w", "1920", str(svg_path), "-o", str(png_path)], check=True)
        print(svg_path)
        print(png_path)


if __name__ == "__main__":
    main()
