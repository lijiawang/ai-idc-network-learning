#!/usr/bin/env python3
from __future__ import annotations

import html
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


OUT = Path(__file__).resolve().parent

FONT = (
    "'Helvetica Neue', Helvetica, Arial, 'PingFang SC', "
    "'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif"
)

BLUE = "#2563eb"
GREEN = "#16a34a"
ORANGE = "#ea580c"
RED = "#dc2626"
PURPLE = "#9333ea"
GRAY = "#6b7280"
TEXT = "#111827"
SUBTLE = "#6b7280"
BORDER = "#d1d5db"
BG = "#ffffff"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def text_width(value: str, size: int = 13) -> int:
    width = 0
    for ch in value:
        width += size if ord(ch) > 127 else int(size * 0.58)
    return width


def start_svg(width: int, height: int, title: str = "", subtitle: str = "") -> list[str]:
    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
    )
    lines.append("  <style>")
    lines.append(f"    text {{ font-family: {FONT}; }}")
    lines.append("  </style>")
    lines.append("  <defs>")
    for marker_id, color in [
        ("arrow-blue", BLUE),
        ("arrow-green", GREEN),
        ("arrow-orange", ORANGE),
        ("arrow-red", RED),
        ("arrow-purple", PURPLE),
        ("arrow-gray", GRAY),
    ]:
        lines.append(
            f'    <marker id="{marker_id}" markerWidth="10" markerHeight="7" '
            f'refX="9" refY="3.5" orient="auto">'
        )
        lines.append(f'      <polygon points="0 0, 10 3.5, 0 7" fill="{color}"/>')
        lines.append("    </marker>")
    lines.append(
        '    <linearGradient id="blue-fade" x1="0%" y1="0%" x2="100%" y2="0%">'
    )
    lines.append('      <stop offset="0%" stop-color="#eff6ff"/>')
    lines.append('      <stop offset="100%" stop-color="#dbeafe"/>')
    lines.append("    </linearGradient>")
    lines.append("  </defs>")
    lines.append(f'  <rect width="{width}" height="{height}" fill="{BG}"/>')
    if title:
        label(lines, 42, 42, title, size=24, weight=700, anchor="start")
    if subtitle:
        label(lines, 42, 72, subtitle, size=13, fill=SUBTLE, anchor="start")
    return lines


def finish_svg(name: str, lines: list[str], width: int, height: int) -> None:
    lines.append("</svg>")
    svg_path = OUT / f"{name}.svg"
    png_path = OUT / f"{name}.png"
    svg_path.write_text("\n".join(lines), encoding="utf-8")
    ET.parse(svg_path)
    rsvg = shutil.which("rsvg-convert")
    if rsvg:
        subprocess.run(
            [rsvg, "-w", str(width * 2), "-h", str(height * 2), str(svg_path), "-o", str(png_path)],
            check=True,
        )
    print(f"generated {svg_path.name}" + (f" and {png_path.name}" if rsvg else ""))


def rect(
    lines: list[str],
    x: int,
    y: int,
    w: int,
    h: int,
    fill: str = "#ffffff",
    stroke: str = BORDER,
    rx: int = 8,
    sw: float = 1.5,
    dash: str = "",
    opacity: float | None = None,
) -> None:
    attrs = [
        f'x="{x}"',
        f'y="{y}"',
        f'width="{w}"',
        f'height="{h}"',
        f'rx="{rx}"',
        f'fill="{fill}"',
        f'stroke="{stroke}"',
        f'stroke-width="{sw}"',
    ]
    if dash:
        attrs.append(f'stroke-dasharray="{dash}"')
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    lines.append("  <rect " + " ".join(attrs) + "/>")


def label(
    lines: list[str],
    x: int,
    y: int,
    value: str,
    size: int = 14,
    fill: str = TEXT,
    anchor: str = "middle",
    weight: int = 400,
    opacity: float | None = None,
) -> None:
    attrs = [
        f'x="{x}"',
        f'y="{y}"',
        f'font-size="{size}"',
        f'fill="{fill}"',
        f'text-anchor="{anchor}"',
        f'font-weight="{weight}"',
    ]
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    lines.append("  <text " + " ".join(attrs) + f">{esc(value)}</text>")


def multi_label(
    lines: list[str],
    x: int,
    y: int,
    values: list[str],
    size: int = 13,
    fill: str = SUBTLE,
    anchor: str = "middle",
    line_gap: int = 18,
) -> None:
    for idx, value in enumerate(values):
        label(lines, x, y + idx * line_gap, value, size=size, fill=fill, anchor=anchor)


def arrow(
    lines: list[str],
    d: str,
    color: str = BLUE,
    width: float = 2.5,
    marker: str = "arrow-blue",
    dash: str = "",
) -> None:
    attrs = [
        f'd="{esc(d)}"',
        f'stroke="{color}"',
        f'stroke-width="{width}"',
        'fill="none"',
        f'marker-end="url(#{marker})"',
    ]
    if dash:
        attrs.append(f'stroke-dasharray="{dash}"')
    lines.append("  <path " + " ".join(attrs) + "/>")


def arrow_label(lines: list[str], x: int, y: int, value: str, color: str = BLUE) -> None:
    w = text_width(value, 13) + 18
    rect(lines, x - w // 2, y - 16, w, 23, fill="#ffffff", stroke="#e5e7eb", rx=6, sw=1)
    label(lines, x, y, value, size=13, fill=color, weight=600)


def gpu(lines: list[str], x: int, y: int, name: str, accent: str = "#eff6ff") -> None:
    rect(lines, x, y, 126, 88, fill=accent, stroke="#bfdbfe", rx=10)
    label(lines, x + 63, y + 28, name, size=18, weight=700)
    rect(lines, x + 18, y + 47, 90, 18, fill="#ffffff", stroke="#93c5fd", rx=4, sw=1)
    label(lines, x + 63, y + 60, "HBM", size=11, fill=BLUE, weight=700)
    label(lines, x + 63, y + 78, "显存", size=11, fill=SUBTLE)


def host_memory(lines: list[str], x: int, y: int) -> None:
    rect(lines, x, y, 138, 92, fill="#fff7ed", stroke="#fed7aa", rx=10)
    label(lines, x + 69, y + 30, "Host", size=17, weight=700, fill=ORANGE)
    label(lines, x + 69, y + 52, "Memory", size=15, weight=600, fill=ORANGE)
    label(lines, x + 69, y + 75, "CPU 内存", size=12, fill=SUBTLE)


def cpu(lines: list[str], x: int, y: int, name: str = "CPU") -> None:
    rect(lines, x, y, 128, 70, fill="#f9fafb", stroke="#d1d5db", rx=8)
    label(lines, x + 64, y + 31, name, size=17, weight=700)
    label(lines, x + 64, y + 53, "控制 / 调度", size=12, fill=SUBTLE)


def legend(lines: list[str], x: int, y: int, items: list[tuple[str, str, str]]) -> None:
    cursor = x
    for text_value, color, marker_id in items:
        lines.append(
            f'  <line x1="{cursor}" y1="{y}" x2="{cursor + 34}" y2="{y}" '
            f'stroke="{color}" stroke-width="2.2" marker-end="url(#{marker_id})"/>'
        )
        label(lines, cursor + 44, y + 4, text_value, size=12, fill=SUBTLE, anchor="start")
        cursor += 44 + text_width(text_value, 12) + 34


def cover() -> None:
    width, height = 900, 383
    lines = start_svg(width, height)
    label(lines, 60, 72, "GPUDirect P2P", size=36, weight=800, anchor="start")
    label(lines, 60, 112, "单机多 GPU 的显存直通车", size=24, weight=700, anchor="start")
    label(lines, 60, 146, "GPU HBM ↔ GPU HBM，不再把数据绕到 CPU 内存中转", size=15, fill=SUBTLE, anchor="start")
    gpu(lines, 116, 214, "GPU0")
    gpu(lines, 658, 214, "GPU1")
    cpu(lines, 386, 174, "CPU")
    rect(lines, 338, 255, 220, 52, fill="url(#blue-fade)", stroke="#93c5fd", rx=26, sw=1.5)
    arrow(lines, "M 252 281 L 642 281", color=BLUE, width=5, marker="arrow-blue")
    arrow_label(lines, 450, 251, "P2P 直接拷贝 / 直接访问", BLUE)
    arrow(lines, "M 450 244 L 450 218", color=GRAY, width=1.7, marker="arrow-gray", dash="5,4")
    label(lines, 450, 334, "PCIe / NVLink / NVSwitch 是可能的物理路径", size=13, fill=SUBTLE)
    finish_svg("00-cover-gpudirect-p2p", lines, width, height)


def traditional_vs_p2p() -> None:
    width, height = 1200, 650
    lines = start_svg(
        width,
        height,
        "传统中转 vs GPUDirect P2P",
        "P2P 的核心价值：让同一台服务器内的 GPU 显存尽量直接交换数据。",
    )
    rect(lines, 48, 110, 520, 470, fill="#ffffff", stroke="#e5e7eb", rx=14)
    rect(lines, 632, 110, 520, 470, fill="#ffffff", stroke="#e5e7eb", rx=14)
    label(lines, 74, 145, "没有 P2P / P2P 不可用", size=18, weight=700, anchor="start")
    label(lines, 658, 145, "GPUDirect P2P 可用", size=18, weight=700, anchor="start")
    multi_label(lines, 74, 173, ["数据先落到 Host Memory，再写入另一张 GPU", "路径更长，CPU 内存带宽也会被卷入"], size=12, anchor="start")
    multi_label(lines, 658, 173, ["数据从 GPU0 HBM 直接到 GPU1 HBM", "CPU 负责发起/同步，不当大货仓中转"], size=12, anchor="start")

    gpu(lines, 80, 330, "GPU0")
    host_memory(lines, 242, 320)
    gpu(lines, 430, 330, "GPU1")
    arrow(lines, "M 206 374 L 238 374", color=ORANGE, marker="arrow-orange")
    arrow(lines, "M 380 374 L 426 374", color=ORANGE, marker="arrow-orange")
    arrow_label(lines, 224, 350, "拷贝 1", ORANGE)
    arrow_label(lines, 405, 350, "拷贝 2", ORANGE)
    multi_label(lines, 306, 466, ["两段搬运", "Host Memory 中转", "延迟和带宽压力更高"], size=13)

    gpu(lines, 700, 330, "GPU0")
    gpu(lines, 996, 330, "GPU1")
    cpu(lines, 850, 230, "CPU")
    arrow(lines, "M 826 374 L 990 374", color=BLUE, width=3.5, marker="arrow-blue")
    arrow_label(lines, 908, 348, "一次 P2P 搬运", BLUE)
    arrow(lines, "M 914 300 L 914 327", color=GRAY, width=1.8, marker="arrow-gray", dash="5,4")
    multi_label(lines, 914, 466, ["CPU 仍会发起 API / 同步任务", "但大块数据不再经 CPU 内存倒一手"], size=13)
    legend(
        lines,
        74,
        548,
        [("Host 中转路径", ORANGE, "arrow-orange"), ("P2P 显存直连路径", BLUE, "arrow-blue")],
    )
    finish_svg("01-traditional-copy-vs-p2p", lines, width, height)


def topology_matters() -> None:
    width, height = 1200, 690
    lines = start_svg(
        width,
        height,
        "P2P 能不能快，关键看拓扑",
        "同样支持 GPUDirect P2P，NVLink/NVSwitch、同 PCIe Switch、跨 Socket 的体验会完全不同。",
    )
    rect(lines, 50, 105, 1100, 152, fill="#f8fafc", stroke="#cbd5e1", rx=14)
    label(lines, 78, 137, "最快：NVLink / NVSwitch", size=17, weight=700, anchor="start")
    gpu(lines, 126, 158, "GPU0")
    gpu(lines, 402, 158, "GPU1")
    gpu(lines, 780, 158, "GPU2")
    rect(lines, 575, 164, 130, 76, fill="#ecfeff", stroke="#67e8f9", rx=10)
    label(lines, 640, 195, "NVSwitch", size=16, weight=700, fill="#0891b2")
    label(lines, 640, 218, "Scale-up Fabric", size=12, fill=SUBTLE)
    arrow(lines, "M 252 202 L 396 202", color=GREEN, width=3.5, marker="arrow-green")
    arrow(lines, "M 528 202 L 571 202", color=GREEN, width=3.5, marker="arrow-green")
    arrow(lines, "M 705 202 L 774 202", color=GREEN, width=3.5, marker="arrow-green")
    label(lines, 973, 197, "带宽高，延迟低", size=15, weight=700, fill=GREEN)
    label(lines, 973, 223, "单机大模型训练的黄金路线", size=12, fill=SUBTLE)

    rect(lines, 50, 286, 520, 285, fill="#ffffff", stroke="#e5e7eb", rx=14)
    label(lines, 78, 320, "较常见：同一个 PCIe Switch", size=17, weight=700, anchor="start")
    cpu(lines, 246, 356, "CPU0")
    rect(lines, 222, 454, 176, 52, fill="#f0fdf4", stroke="#bbf7d0", rx=8)
    label(lines, 310, 486, "PCIe Switch", size=15, weight=700, fill=GREEN)
    gpu(lines, 88, 462, "GPU0")
    gpu(lines, 432, 462, "GPU1")
    arrow(lines, "M 214 506 L 218 506", color=BLUE, marker="arrow-blue")
    arrow(lines, "M 398 506 L 428 506", color=BLUE, marker="arrow-blue")
    arrow(lines, "M 151 462 L 151 420 L 310 420 L 310 450", color=BLUE, width=2.4, marker="arrow-blue")
    arrow(lines, "M 495 462 L 495 420 L 310 420 L 310 450", color=BLUE, width=2.4, marker="arrow-blue")
    label(lines, 310, 546, "通常可 P2P，但带宽受 PCIe 代际和链路宽度限制", size=12, fill=SUBTLE)

    rect(lines, 630, 286, 520, 285, fill="#ffffff", stroke="#e5e7eb", rx=14)
    label(lines, 658, 320, "更远：跨 CPU Socket / NUMA", size=17, weight=700, anchor="start")
    cpu(lines, 702, 360, "CPU0")
    cpu(lines, 980, 360, "CPU1")
    label(lines, 904, 397, "UPI / IF", size=12, fill=GRAY)
    arrow(lines, "M 830 394 L 976 394", color=GRAY, marker="arrow-gray", dash="7,5")
    rect(lines, 686, 458, 160, 48, fill="#f9fafb", stroke="#d1d5db", rx=8)
    rect(lines, 968, 458, 160, 48, fill="#f9fafb", stroke="#d1d5db", rx=8)
    label(lines, 766, 488, "PCIe Switch", size=14, fill=SUBTLE, weight=700)
    label(lines, 1048, 488, "PCIe Switch", size=14, fill=SUBTLE, weight=700)
    gpu(lines, 650, 526, "GPU0")
    gpu(lines, 1002, 526, "GPU1")
    arrow(lines, "M 776 570 L 999 570", color=RED, width=2.3, marker="arrow-red", dash="6,5")
    arrow_label(lines, 890, 548, "路径更长", RED)
    label(lines, 890, 628, "可能能通，但延迟/带宽通常不如近端路径", size=12, fill=SUBTLE)

    legend(
        lines,
        78,
        638,
        [("NVLink/NVSwitch", GREEN, "arrow-green"), ("PCIe P2P", BLUE, "arrow-blue"), ("跨 Socket 远路径", RED, "arrow-red")],
    )
    finish_svg("02-p2p-topology-matters", lines, width, height)


def cuda_api_flow() -> None:
    width, height = 1200, 560
    lines = start_svg(
        width,
        height,
        "应用如何使用 P2P：先判断，再启用，再拷贝",
        "不要只看 GPU 型号，程序应该用 CUDA Runtime API 对每一对 GPU 做能力判断。",
    )
    steps = [
        (70, 185, "1", "枚举 GPU", ["cudaGetDeviceCount", "确认多卡进程"]),
        (275, 185, "2", "逐对询问", ["cudaDeviceCanAccessPeer", "能不能互访"]),
        (505, 185, "3", "启用 Peer", ["cudaDeviceEnablePeerAccess", "为目标 GPU 开门"]),
        (735, 185, "4", "发起传输", ["cudaMemcpyPeerAsync", "或 kernel 读写 peer HBM"]),
        (970, 185, "5", "验证性能", ["nvidia-smi topo -m", "p2pBandwidthLatencyTest"]),
    ]
    for x, y, num, title, sublines in steps:
        rect(lines, x, y, 160, 142, fill="#ffffff", stroke="#d1d5db", rx=12)
        rect(lines, x + 16, y + 18, 34, 34, fill="#eff6ff", stroke="#bfdbfe", rx=17)
        label(lines, x + 33, y + 42, num, size=17, weight=700, fill=BLUE)
        label(lines, x + 80, y + 44, title, size=17, weight=700)
        multi_label(lines, x + 80, y + 82, sublines, size=12, fill=SUBTLE, line_gap=20)
    for x in [230, 460, 690, 925]:
        arrow(lines, f"M {x} 256 L {x + 40} 256", color=BLUE, marker="arrow-blue")

    rect(lines, 275, 385, 160, 72, fill="#fef2f2", stroke="#fecaca", rx=10)
    label(lines, 355, 415, "如果返回 0", size=15, weight=700, fill=RED)
    label(lines, 355, 439, "不要强行假设 P2P", size=12, fill=SUBTLE)
    arrow(lines, "M 355 327 L 355 381", color=RED, marker="arrow-red", dash="5,4")

    rect(lines, 735, 385, 395, 72, fill="#f8fafc", stroke="#cbd5e1", rx=10)
    label(lines, 758, 416, "注意", size=15, weight=700, fill=GRAY, anchor="start")
    label(lines, 758, 440, "CPU 仍负责提交命令和同步；P2P 只是让大块数据少绕 Host Memory。", size=12, fill=SUBTLE, anchor="start")
    arrow(lines, "M 810 327 L 810 381", color=GRAY, marker="arrow-gray", dash="5,4")

    finish_svg("03-p2p-cuda-api-flow", lines, width, height)


def nccl_relation() -> None:
    width, height = 1200, 620
    lines = start_svg(
        width,
        height,
        "P2P 与 NCCL 的关系",
        "P2P 是底层通信能力；NCCL 会基于拓扑，把 AllReduce 等 collective 组织成 ring/tree/channel。",
    )
    rect(lines, 55, 110, 480, 420, fill="#ffffff", stroke="#e5e7eb", rx=14)
    label(lines, 85, 146, "底层：GPU 对 GPU 的数据通道", size=17, weight=700, anchor="start")
    gpu(lines, 100, 250, "GPU0")
    gpu(lines, 355, 250, "GPU1")
    gpu(lines, 100, 390, "GPU2")
    gpu(lines, 355, 390, "GPU3")
    arrow(lines, "M 226 294 L 349 294", color=BLUE, width=2.8, marker="arrow-blue")
    arrow(lines, "M 226 434 L 349 434", color=BLUE, width=2.8, marker="arrow-blue")
    arrow(lines, "M 163 338 L 163 386", color=GREEN, width=2.8, marker="arrow-green")
    arrow(lines, "M 418 338 L 418 386", color=GREEN, width=2.8, marker="arrow-green")
    label(lines, 291, 221, "P2P / NVLink / PCIe", size=13, fill=SUBTLE)
    multi_label(lines, 291, 501, ["这一层回答：两张 GPU 能不能直接搬？", "路径近不近？带宽高不高？"], size=13)

    rect(lines, 625, 110, 520, 420, fill="#ffffff", stroke="#e5e7eb", rx=14)
    label(lines, 655, 146, "上层：NCCL 组织 collective", size=17, weight=700, anchor="start")
    rect(lines, 690, 205, 390, 72, fill="#eff6ff", stroke="#bfdbfe", rx=12)
    label(lines, 885, 235, "NCCL 初始化：探测拓扑", size=17, weight=700, fill=BLUE)
    label(lines, 885, 258, "NVLink / PCIe / NUMA / P2P 能力", size=12, fill=SUBTLE)
    rect(lines, 690, 328, 390, 72, fill="#f0fdf4", stroke="#bbf7d0", rx=12)
    label(lines, 885, 358, "生成通信图", size=17, weight=700, fill=GREEN)
    label(lines, 885, 381, "Ring / Tree / Channel / Chunk", size=12, fill=SUBTLE)
    rect(lines, 690, 451, 390, 72, fill="#fff7ed", stroke="#fed7aa", rx=12)
    label(lines, 885, 481, "传输时优先走近路", size=17, weight=700, fill=ORANGE)
    label(lines, 885, 504, "可用时使用 P2P；不可用时选择其他单机路径", size=12, fill=SUBTLE)
    arrow(lines, "M 885 277 L 885 324", color=BLUE, marker="arrow-blue")
    arrow(lines, "M 885 400 L 885 447", color=GREEN, marker="arrow-green")
    arrow(lines, "M 535 320 C 575 320 585 238 686 238", color=PURPLE, marker="arrow-purple")
    arrow_label(lines, 610, 291, "拓扑输入", PURPLE)
    legend(
        lines,
        85,
        574,
        [("P2P 传输", BLUE, "arrow-blue"), ("高速近端链路", GREEN, "arrow-green"), ("拓扑信息进入 NCCL", PURPLE, "arrow-purple")],
    )
    finish_svg("04-p2p-and-nccl", lines, width, height)


def main() -> None:
    cover()
    traditional_vs_p2p()
    topology_matters()
    cuda_api_flow()
    nccl_relation()


if __name__ == "__main__":
    main()
