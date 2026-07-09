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
CYAN = "#0891b2"
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
        ("arrow-cyan", CYAN),
        ("arrow-gray", GRAY),
    ]:
        lines.append(
            f'    <marker id="{marker_id}" markerWidth="10" markerHeight="7" '
            f'refX="9" refY="3.5" orient="auto">'
        )
        lines.append(f'      <polygon points="0 0, 10 3.5, 0 7" fill="{color}"/>')
        lines.append("    </marker>")
    lines.append(
        '    <linearGradient id="rdma-fade" x1="0%" y1="0%" x2="100%" y2="0%">'
    )
    lines.append('      <stop offset="0%" stop-color="#ecfeff"/>')
    lines.append('      <stop offset="100%" stop-color="#eff6ff"/>')
    lines.append("    </linearGradient>")
    lines.append(
        '    <linearGradient id="cover-dark" x1="0%" y1="0%" x2="100%" y2="100%">'
    )
    lines.append('      <stop offset="0%" stop-color="#07132d"/>')
    lines.append('      <stop offset="56%" stop-color="#102a5c"/>')
    lines.append('      <stop offset="100%" stop-color="#0f766e"/>')
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
    weight: int = 400,
) -> None:
    for idx, value in enumerate(values):
        label(lines, x, y + idx * line_gap, value, size=size, fill=fill, anchor=anchor, weight=weight)


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


def line(
    lines: list[str],
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: str = GRAY,
    width: float = 2,
    dash: str = "",
) -> None:
    attrs = [
        f'x1="{x1}"',
        f'y1="{y1}"',
        f'x2="{x2}"',
        f'y2="{y2}"',
        f'stroke="{color}"',
        f'stroke-width="{width}"',
    ]
    if dash:
        attrs.append(f'stroke-dasharray="{dash}"')
    lines.append("  <line " + " ".join(attrs) + "/>")


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
    rect(lines, x, y, 126, 70, fill="#f9fafb", stroke="#d1d5db", rx=8)
    label(lines, x + 63, y + 31, name, size=17, weight=700)
    label(lines, x + 63, y + 53, "控制 / 调度", size=12, fill=SUBTLE)


def nic(lines: list[str], x: int, y: int, name: str = "NIC", fill: str = "#ecfdf5") -> None:
    rect(lines, x, y, 128, 72, fill=fill, stroke="#86efac", rx=9)
    label(lines, x + 64, y + 30, name, size=17, weight=700, fill=GREEN)
    label(lines, x + 64, y + 52, "RDMA 网卡", size=12, fill=SUBTLE)


def switch(lines: list[str], x: int, y: int, name: str = "PCIe Switch") -> None:
    rect(lines, x, y, 170, 54, fill="#f8fafc", stroke="#cbd5e1", rx=8)
    label(lines, x + 85, y + 33, name, size=14, fill=GRAY, weight=700)


def cover() -> None:
    width, height = 900, 383
    lines = start_svg(width, height)
    lines.append(f'  <rect width="{width}" height="{height}" fill="url(#cover-dark)"/>')
    label(lines, 60, 78, "GPUDirect RDMA", size=38, weight=800, fill="#ffffff", anchor="start")
    label(lines, 60, 121, "跨节点 GPU 的显存直通车", size=24, weight=700, fill="#dbeafe", anchor="start")
    label(lines, 60, 155, "GPU HBM ↔ RDMA NIC ↔ 网络 ↔ RDMA NIC ↔ GPU HBM", size=15, fill="#b6e3ff", anchor="start")

    gpu(lines, 82, 224, "GPU A", accent="#eff6ff")
    nic(lines, 258, 232, "NIC A", fill="#ecfdf5")
    rect(lines, 410, 235, 96, 64, fill="#0f172a", stroke="#38bdf8", rx=18, sw=1.5)
    label(lines, 458, 261, "IB / RoCE", size=14, fill="#e0f2fe", weight=700)
    label(lines, 458, 284, "RDMA 网络", size=12, fill="#bae6fd")
    nic(lines, 534, 232, "NIC B", fill="#ecfdf5")
    gpu(lines, 710, 224, "GPU B", accent="#eff6ff")
    arrow(lines, "M 208 268 L 254 268", color=CYAN, width=4.2, marker="arrow-cyan")
    arrow(lines, "M 386 268 L 406 268", color=CYAN, width=4.2, marker="arrow-cyan")
    arrow(lines, "M 506 268 L 530 268", color=CYAN, width=4.2, marker="arrow-cyan")
    arrow(lines, "M 662 268 L 706 268", color=CYAN, width=4.2, marker="arrow-cyan")
    label(lines, 450, 336, "CPU 负责建路和同步，大块数据尽量不进 Host Memory", size=13, fill="#dbeafe")
    finish_svg("00-cover-gpudirect-rdma", lines, width, height)


def traditional_vs_gdrdma() -> None:
    width, height = 1200, 690
    lines = start_svg(
        width,
        height,
        "传统 Host 中转 vs GPUDirect RDMA",
        "跨节点通信时，GDRDMA 的核心价值是减少 GPU 显存与 CPU 内存之间的 staging copy。",
    )
    rect(lines, 48, 108, 520, 500, fill="#ffffff", stroke="#e5e7eb", rx=14)
    rect(lines, 632, 108, 520, 500, fill="#ffffff", stroke="#e5e7eb", rx=14)
    label(lines, 74, 145, "没有 GPUDirect RDMA", size=18, weight=700, anchor="start")
    label(lines, 658, 145, "GPUDirect RDMA 可用", size=18, weight=700, anchor="start")
    multi_label(lines, 74, 173, ["GPU 数据先拷到 Host Memory", "NIC 再从 CPU 内存发到网络"], size=12, anchor="start")
    multi_label(lines, 658, 173, ["NIC 可以直接 DMA 读写 GPU 显存", "CPU 仍负责控制面，不当大货仓"], size=12, anchor="start")

    gpu(lines, 82, 360, "GPU A")
    host_memory(lines, 240, 350)
    nic(lines, 430, 360, "NIC A")
    arrow(lines, "M 208 404 L 236 404", color=ORANGE, marker="arrow-orange")
    arrow(lines, "M 382 404 L 426 404", color=ORANGE, marker="arrow-orange")
    arrow_label(lines, 224, 380, "拷贝 1", ORANGE)
    arrow_label(lines, 405, 380, "拷贝 2", ORANGE)
    label(lines, 310, 496, "Host Memory staging", size=14, fill=ORANGE, weight=700)
    multi_label(lines, 310, 522, ["多一次显存 ↔ CPU 内存搬运", "PCIe、NUMA、内存带宽都会被卷入"], size=12)

    gpu(lines, 692, 360, "GPU A")
    nic(lines, 996, 360, "NIC A")
    cpu(lines, 846, 244, "CPU")
    arrow(lines, "M 818 404 L 990 404", color=CYAN, width=3.8, marker="arrow-cyan")
    arrow_label(lines, 905, 380, "DMA 直接读写 HBM", CYAN)
    arrow(lines, "M 909 314 L 909 354", color=GRAY, width=1.7, marker="arrow-gray", dash="5,4")
    multi_label(lines, 906, 493, ["控制面：CPU 发起、注册、同步", "数据面：NIC ↔ GPU HBM 直接搬"], size=12)

    label(lines, 600, 638, "注意：这里画的是本机 GPU 到本机 NIC 的一段；完整跨节点路径还要经过网络和对端 NIC/GPU。", size=13, fill=SUBTLE)
    finish_svg("01-traditional-host-vs-gdrdma", lines, width, height)


def stack_layers() -> None:
    width, height = 1200, 640
    lines = start_svg(
        width,
        height,
        "RDMA、GPUDirect RDMA、IB/RoCE、NCCL 不是同一层",
        "先把这些词放回各自的位置，后面看日志和排障才不会乱。",
    )
    layers = [
        (105, 132, 990, 72, "#eff6ff", "#bfdbfe", "应用 / 框架", "PyTorch、Megatron、vLLM、训练脚本发起 collective 或 send/recv"),
        (105, 226, 990, 72, "#f0fdf4", "#bbf7d0", "通信库", "NCCL / MPI / UCX 负责选路、拆包、调度和调用网络后端"),
        (105, 320, 990, 72, "#ecfeff", "#67e8f9", "GPUDirect RDMA", "让 RDMA NIC 直接 DMA 访问 GPU memory，减少 Host Memory 中转"),
        (105, 414, 990, 72, "#fff7ed", "#fed7aa", "RDMA 网络", "InfiniBand 或 RoCE 承载远端内存访问，普通 TCP 不等于 RDMA"),
        (105, 508, 990, 72, "#f8fafc", "#cbd5e1", "硬件拓扑", "GPU、PCIe Switch、CPU/NUMA、NIC、交换机和线缆决定物理路径"),
    ]
    for x, y, w, h, fill, stroke, title, body in layers:
        rect(lines, x, y, w, h, fill=fill, stroke=stroke, rx=12)
        label(lines, x + 34, y + 43, title, size=18, weight=700, anchor="start", fill=TEXT)
        label(lines, x + 230, y + 43, body, size=14, anchor="start", fill=SUBTLE)
    for y in [204, 298, 392, 486]:
        arrow(lines, f"M 600 {y} L 600 {y + 20}", color=GRAY, width=1.8, marker="arrow-gray")
    label(lines, 878, 360, "GDRDMA 是数据路径优化", size=16, fill=CYAN, weight=700)
    label(lines, 878, 386, "不是一种交换机，也不是 NCCL 本身", size=12, fill=SUBTLE)
    finish_svg("02-rdma-stack-layers", lines, width, height)


def buffer_flow() -> None:
    width, height = 1200, 640
    lines = start_svg(
        width,
        height,
        "一块 GPU Buffer 是怎么被 RDMA NIC 访问的",
        "真实实现有驱动和内核细节，入门先抓住：识别、注册、映射、DMA、同步。",
    )
    steps = [
        (68, 170, "1", "CUDA 分配显存", ["cudaMalloc 得到", "GPU device pointer"]),
        (282, 170, "2", "通信库识别", ["判断这是 GPU buffer", "不是普通 Host 指针"]),
        (496, 170, "3", "注册 / pin", ["驱动固定显存页", "建立 peer mapping"]),
        (710, 170, "4", "NIC 获得映射", ["通过 peer memory", "访问 GPU 页面"]),
        (924, 170, "5", "DMA 传输", ["NIC 直接读写 HBM", "完成后做同步"]),
    ]
    for x, y, num, title, sublines in steps:
        rect(lines, x, y, 170, 138, fill="#ffffff", stroke="#d1d5db", rx=12)
        rect(lines, x + 16, y + 18, 34, 34, fill="#ecfeff", stroke="#67e8f9", rx=17)
        label(lines, x + 33, y + 42, num, size=17, weight=700, fill=CYAN)
        label(lines, x + 85, y + 44, title, size=16, weight=700)
        multi_label(lines, x + 85, y + 82, sublines, size=12, fill=SUBTLE, line_gap=20)
    for x in [238, 452, 666, 880]:
        arrow(lines, f"M {x} 239 L {x + 38} 239", color=CYAN, marker="arrow-cyan")

    rect(lines, 110, 390, 300, 112, fill="#eff6ff", stroke="#bfdbfe", rx=12)
    gpu(lines, 142, 410, "GPU")
    rect(lines, 278, 422, 98, 38, fill="#ffffff", stroke="#93c5fd", rx=6, sw=1)
    label(lines, 327, 446, "GPU Buffer", size=13, fill=BLUE, weight=700)

    rect(lines, 452, 390, 300, 112, fill="#f8fafc", stroke="#cbd5e1", rx=12)
    label(lines, 602, 426, "nvidia-peermem / 驱动协作", size=16, weight=700)
    multi_label(lines, 602, 456, ["把 GPU 显存页暴露给 peer device", "通常还会使用 registration cache"], size=12)

    rect(lines, 794, 390, 300, 112, fill="#f0fdf4", stroke="#bbf7d0", rx=12)
    nic(lines, 850, 410, "RDMA NIC")
    label(lines, 1006, 447, "DMA Engine", size=13, fill=GREEN, weight=700)
    arrow(lines, "M 410 446 L 448 446", color=BLUE, marker="arrow-blue")
    arrow(lines, "M 752 446 L 790 446", color=GREEN, marker="arrow-green")

    label(lines, 600, 566, "pin/register 不是免费操作，所以高性能通信库会尽量缓存注册结果，而不是每次传输都从头来一遍。", size=13, fill=SUBTLE)
    finish_svg("03-gpu-buffer-rdma-flow", lines, width, height)


def topology_matters() -> None:
    width, height = 1200, 700
    lines = start_svg(
        width,
        height,
        "GDRDMA 快不快，关键看 GPU-NIC 亲缘关系",
        "跨节点训练不是随便找一张网卡就发，GPU 到 NIC 的 PCIe/NUMA 路径会直接影响性能。",
    )
    rect(lines, 50, 112, 530, 455, fill="#ffffff", stroke="#e5e7eb", rx=14)
    label(lines, 80, 148, "近：同 PCIe Switch / 同 NUMA", size=18, weight=700, anchor="start")
    cpu(lines, 252, 196, "CPU0")
    switch(lines, 230, 306, "PCIe Switch A")
    gpu(lines, 112, 420, "GPU0")
    nic(lines, 380, 428, "NIC0")
    arrow(lines, "M 238 464 L 376 464", color=GREEN, width=3.4, marker="arrow-green")
    arrow_label(lines, 308, 440, "近端 GDRDMA", GREEN)
    line(lines, 315, 266, 315, 304, GRAY, 1.7)
    line(lines, 238, 420, 315, 360, GRAY, 1.7)
    line(lines, 444, 428, 315, 360, GRAY, 1.7)
    multi_label(lines, 315, 536, ["路径短、可预测性更好", "多 rail 机器通常希望 GPU i 找 NIC i"], size=13)

    rect(lines, 620, 112, 530, 455, fill="#ffffff", stroke="#e5e7eb", rx=14)
    label(lines, 650, 148, "远：跨 Socket / 跨 NUMA", size=18, weight=700, anchor="start")
    cpu(lines, 676, 205, "CPU0")
    cpu(lines, 966, 205, "CPU1")
    switch(lines, 655, 316, "PCIe Switch A")
    switch(lines, 945, 316, "PCIe Switch B")
    gpu(lines, 650, 430, "GPU0")
    nic(lines, 990, 438, "NIC7")
    arrow(lines, "M 776 474 L 986 474", color=RED, width=2.6, marker="arrow-red", dash="6,5")
    arrow_label(lines, 884, 450, "远端路径", RED)
    line(lines, 802, 241, 962, 241, GRAY, 2, dash="6,5")
    label(lines, 882, 231, "UPI / IF", size=12, fill=GRAY)
    line(lines, 739, 275, 739, 316, GRAY, 1.7)
    line(lines, 1029, 275, 1029, 316, GRAY, 1.7)
    line(lines, 713, 430, 740, 370, GRAY, 1.7)
    line(lines, 1054, 438, 1030, 370, GRAY, 1.7)
    multi_label(lines, 885, 536, ["可能可用，但延迟更高、带宽更差", "不建议靠强制放开 SYS 来赌性能"], size=13)

    label(lines, 600, 635, "实战先看 nvidia-smi topo -m：GPU-NIC 之间的 PIX/PXB/PHB/SYS 距离，比“网卡插了几张”更重要。", size=13, fill=SUBTLE)
    finish_svg("04-gpu-nic-affinity", lines, width, height)


def nccl_decision() -> None:
    width, height = 1200, 700
    lines = start_svg(
        width,
        height,
        "NCCL 在哪里判断要不要用 GPUDirect RDMA",
        "跨节点时 NCCL 进入 NET 路径，再结合网卡、拓扑和环境变量判断能否启用 GDRDMA。",
    )
    rect(lines, 70, 130, 230, 92, fill="#eff6ff", stroke="#bfdbfe", rx=12)
    label(lines, 185, 166, "Collective 调用", size=17, weight=700, fill=BLUE)
    label(lines, 185, 193, "AllReduce / AllGather ...", size=12, fill=SUBTLE)

    rect(lines, 400, 130, 230, 92, fill="#f8fafc", stroke="#cbd5e1", rx=12)
    label(lines, 515, 166, "NCCL 拓扑图", size=17, weight=700)
    label(lines, 515, 193, "GPU / NIC / PCIe / NUMA", size=12, fill=SUBTLE)

    rect(lines, 750, 130, 230, 92, fill="#f0fdf4", stroke="#bbf7d0", rx=12)
    label(lines, 865, 166, "选择传输", size=17, weight=700, fill=GREEN)
    label(lines, 865, 193, "P2P / SHM / NET", size=12, fill=SUBTLE)
    arrow(lines, "M 300 176 L 396 176", color=BLUE, marker="arrow-blue")
    arrow(lines, "M 630 176 L 746 176", color=GREEN, marker="arrow-green")

    rect(lines, 190, 310, 820, 86, fill="#ecfeff", stroke="#67e8f9", rx=14)
    label(lines, 600, 343, "跨节点：进入 NET / IB / RoCE 路径", size=18, weight=700, fill=CYAN)
    label(lines, 600, 370, "如果 GPU buffer + RDMA NIC + 拓扑距离都合适，就尝试走 GDRDMA", size=13, fill=SUBTLE)
    arrow(lines, "M 865 222 L 865 268 C 865 302 810 319 1010 353", color=CYAN, marker="arrow-cyan")

    checks = [
        (120, 485, "GPU buffer", "通信对象真的是 CUDA device memory"),
        (370, 485, "NIC 支持", "IB/RoCE HCA 与驱动可用"),
        (620, 485, "拓扑合适", "GPU-NIC 距离没有太远"),
        (870, 485, "策略允许", "NCCL_NET_GDR_LEVEL 没限制住"),
    ]
    for x, y, title, body in checks:
        rect(lines, x, y, 210, 90, fill="#ffffff", stroke="#d1d5db", rx=12)
        label(lines, x + 105, y + 35, title, size=16, weight=700)
        label(lines, x + 105, y + 62, body, size=12, fill=SUBTLE)
    for x in [330, 580, 830]:
        arrow(lines, f"M {x} 530 L {x + 36} 530", color=GRAY, marker="arrow-gray")

    rect(lines, 385, 610, 430, 52, fill="#fff7ed", stroke="#fed7aa", rx=10)
    label(lines, 600, 643, "任一条件不满足，就可能退回 Host staging 或其他 NET 路径", size=13, fill=ORANGE, weight=700)
    finish_svg("05-nccl-gdrdma-decision", lines, width, height)


def troubleshooting() -> None:
    width, height = 1200, 700
    lines = start_svg(
        width,
        height,
        "排查 GPUDirect RDMA，按这张表从近到远看",
        "先确认本机 GPU-NIC 数据路径，再看 NCCL，再看网络 fabric。",
    )
    items = [
        (90, 130, BLUE, "1. GPU-NIC 拓扑", ["nvidia-smi topo -m", "优先确认 PIX / PXB / PHB / SYS"]),
        (90, 250, GREEN, "2. 驱动模块", ["nvidia-peermem 是否加载", "CUDA / driver / OFED 版本兼容"]),
        (90, 370, CYAN, "3. 显存映射资源", ["BAR1 空间是否异常", "IOMMU 是否影响 peer DMA"]),
        (640, 130, PURPLE, "4. NCCL 日志", ["NCCL_DEBUG=INFO", "NCCL_DEBUG_SUBSYS=INIT,GRAPH,NET"]),
        (640, 250, ORANGE, "5. 网卡选择", ["NCCL_IB_HCA / SOCKET_IFNAME", "多 rail 是否按预期使用"]),
        (640, 370, RED, "6. 网络 fabric", ["IB/RoCE 链路、PFC/ECN", "拥塞、丢包、路由、oversubscription"]),
    ]
    for x, y, color, title, body in items:
        rect(lines, x, y, 470, 90, fill="#ffffff", stroke="#d1d5db", rx=12)
        rect(lines, x + 18, y + 20, 42, 42, fill="#f8fafc", stroke=color, rx=21, sw=2)
        label(lines, x + 39, y + 48, title.split(".")[0], size=18, weight=700, fill=color)
        label(lines, x + 82, y + 36, title, size=16, weight=700, fill=TEXT, anchor="start")
        multi_label(lines, x + 82, y + 62, body, size=12, fill=SUBTLE, anchor="start", line_gap=18)
    arrow(lines, "M 325 220 L 325 246", color=GRAY, marker="arrow-gray")
    arrow(lines, "M 325 340 L 325 366", color=GRAY, marker="arrow-gray")
    arrow(lines, "M 560 415 C 595 415 610 180 636 176", color=GRAY, marker="arrow-gray", dash="5,4")
    arrow(lines, "M 875 220 L 875 246", color=GRAY, marker="arrow-gray")
    arrow(lines, "M 875 340 L 875 366", color=GRAY, marker="arrow-gray")

    rect(lines, 260, 555, 680, 70, fill="#f8fafc", stroke="#cbd5e1", rx=12)
    label(lines, 600, 584, "经验法则", size=16, weight=700)
    label(lines, 600, 609, "先证明“本机 GPU 到 NIC 没绕路”，再讨论交换机、拥塞和训练框架。", size=13, fill=SUBTLE)
    finish_svg("06-gdrdma-troubleshooting", lines, width, height)


def main() -> None:
    cover()
    traditional_vs_gdrdma()
    stack_layers()
    buffer_flow()
    topology_matters()
    nccl_decision()
    troubleshooting()


if __name__ == "__main__":
    main()
