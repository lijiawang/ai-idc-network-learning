#!/usr/bin/env python3
"""
GPU information checker for NVIDIA CUDA machines.

Run:
  python gpu_info.py

Required:
  pip install torch

Recommended for richer runtime metrics:
  pip install nvidia-ml-py
"""

from __future__ import annotations

import shutil
import subprocess
import warnings
from dataclasses import dataclass
from typing import Any, Callable

try:
    import torch
except ImportError:
    print("缺少 PyTorch，请先安装 torch。")
    print("例如：pip install torch")
    raise SystemExit(1)


# Compute Capability -> architecture and per-SM core configuration.
ARCH_PER_SM = {
    (7, 0): {"arch": "Volta", "cuda_cores_per_sm": 64, "tensor_cores_per_sm": 8},  # V100/V100S
    (7, 5): {"arch": "Turing", "cuda_cores_per_sm": 64, "tensor_cores_per_sm": 8},  # T4/RTX20
    (8, 0): {"arch": "Ampere GA100", "cuda_cores_per_sm": 64, "tensor_cores_per_sm": 4},  # A100
    (8, 6): {"arch": "Ampere GA10x", "cuda_cores_per_sm": 128, "tensor_cores_per_sm": 4},  # RTX30/A40
    (8, 7): {"arch": "Ampere Jetson/Orin", "cuda_cores_per_sm": 128, "tensor_cores_per_sm": 4},
    (8, 9): {"arch": "Ada", "cuda_cores_per_sm": 128, "tensor_cores_per_sm": 4},  # RTX40/L4/L40
    (9, 0): {"arch": "Hopper", "cuda_cores_per_sm": 128, "tensor_cores_per_sm": 4},  # H100/H200
}


# Small fallback table for specs that are often not exposed by PyTorch.
# The V100S entry matches the machine in your output.
GPU_NAME_SPECS = [
    {
        "keyword": "V100S",
        "memory_type": "HBM2",
        "memory_bus_width_bits": 4096,
        "official_bandwidth_gbs": 1134.0,
    },
]


NVIDIA_SMI_QUERY_FIELDS = [
    "index",
    "uuid",
    "driver_version",
    "memory.total",
    "memory.used",
    "memory.free",
    "utilization.gpu",
    "utilization.memory",
    "temperature.gpu",
    "power.draw",
    "power.limit",
    "clocks.sm",
    "clocks.mem",
    "pcie.link.gen.current",
    "pcie.link.gen.max",
    "pcie.link.width.current",
    "pcie.link.width.max",
]


@dataclass
class RuntimeInfo:
    source: str
    values: dict[str, Any]


def safe_call(fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception:
        return default


def valid(value: Any) -> bool:
    return value not in (None, "", "N/A", "[N/A]")


def clean(value: Any) -> Any:
    return value if valid(value) else None


def to_float(value: Any) -> float | None:
    if not valid(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bytes_to_gib(value: int | float | None) -> str:
    if value is None:
        return ""
    return f"{value / 1024**3:.2f} GiB"


def mib_to_gib(value: str | int | float | None) -> str:
    number = to_float(value)
    if number is None:
        return ""
    return f"{number / 1024:.2f} GiB"


def get_gpu_spec(name: str) -> dict[str, Any]:
    name_upper = name.upper()
    for spec in GPU_NAME_SPECS:
        if spec["keyword"].upper() in name_upper:
            return spec
    return {}


def estimate_memory_bandwidth_gbs(memory_clock_mhz: float | None, bus_width_bits: int | None) -> float | None:
    if not memory_clock_mhz or not bus_width_bits:
        return None
    # NVIDIA tools usually report the physical memory clock. HBM/GDDR are DDR,
    # so peak bandwidth is clock * 2 * bus_width_bytes.
    return memory_clock_mhz * 1_000_000 * 2 * (bus_width_bits / 8) / 1_000_000_000


def fmt_bandwidth(value: float | None) -> str:
    if value is None:
        return ""
    if value >= 1000:
        return f"{value:.0f} GB/s ({value / 1000:.2f} TB/s)"
    return f"{value:.1f} GB/s"


def fmt_percent(value: Any) -> str:
    return f"{value}%" if valid(value) else ""


def fmt_celsius(value: Any) -> str:
    return f"{value} C" if valid(value) else ""


def fmt_watts(value_mw: Any) -> str:
    if value_mw is None:
        return ""
    return f"{value_mw / 1000:.1f} W"


def fmt_mhz(value: Any) -> str:
    return f"{value} MHz" if valid(value) else ""


def fmt_pcie(gen: Any, gen_max: Any, width: Any, width_max: Any) -> str:
    if not (valid(gen) and valid(width)):
        return ""
    current = f"Gen{gen} x{width}"
    if valid(gen_max) and valid(width_max):
        return f"{current} / max Gen{gen_max} x{width_max}"
    return current


def print_line(label: str, value: Any) -> None:
    if valid(value):
        print(f"  {label}: {value}")


def get_torch_mem_info(device_index: int) -> tuple[int | None, int | None]:
    try:
        return torch.cuda.mem_get_info(device_index)
    except TypeError:
        with torch.cuda.device(device_index):
            return torch.cuda.mem_get_info()
    except Exception:
        return None, None


def load_nvml() -> Any | None:
    warnings.filterwarnings("ignore", message="The pynvml package is deprecated.*")
    try:
        import pynvml  # type: ignore

        pynvml.nvmlInit()
        return pynvml
    except Exception:
        return None


def shutdown_nvml(nvml: Any | None) -> None:
    if nvml is not None:
        safe_call(nvml.nvmlShutdown)


def decode_nvml_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def nvml_runtime_info(nvml: Any, device_index: int) -> RuntimeInfo | None:
    handle = safe_call(lambda: nvml.nvmlDeviceGetHandleByIndex(device_index))
    if handle is None:
        return None

    mem = safe_call(lambda: nvml.nvmlDeviceGetMemoryInfo(handle))
    util = safe_call(lambda: nvml.nvmlDeviceGetUtilizationRates(handle))
    pci = safe_call(lambda: nvml.nvmlDeviceGetPciInfo(handle))

    values = {
        "driver_version": decode_nvml_text(safe_call(lambda: nvml.nvmlSystemGetDriverVersion())),
        "uuid": decode_nvml_text(safe_call(lambda: nvml.nvmlDeviceGetUUID(handle))),
        "pci_bus_id": decode_nvml_text(getattr(pci, "busId", None)),
        "memory_total": bytes_to_gib(getattr(mem, "total", None)),
        "memory_used": bytes_to_gib(getattr(mem, "used", None)),
        "memory_free": bytes_to_gib(getattr(mem, "free", None)),
        "gpu_util": fmt_percent(getattr(util, "gpu", None)),
        "memory_util": fmt_percent(getattr(util, "memory", None)),
        "temperature": fmt_celsius(safe_call(lambda: nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU))),
        "power_draw": fmt_watts(safe_call(lambda: nvml.nvmlDeviceGetPowerUsage(handle))),
        "power_limit": fmt_watts(safe_call(lambda: nvml.nvmlDeviceGetEnforcedPowerLimit(handle))),
        "sm_clock_current_mhz": safe_call(lambda: nvml.nvmlDeviceGetClockInfo(handle, nvml.NVML_CLOCK_SM)),
        "sm_clock_max_mhz": safe_call(lambda: nvml.nvmlDeviceGetMaxClockInfo(handle, nvml.NVML_CLOCK_SM)),
        "mem_clock_current_mhz": safe_call(lambda: nvml.nvmlDeviceGetClockInfo(handle, nvml.NVML_CLOCK_MEM)),
        "mem_clock_max_mhz": safe_call(lambda: nvml.nvmlDeviceGetMaxClockInfo(handle, nvml.NVML_CLOCK_MEM)),
        "memory_bus_width_bits": safe_call(lambda: nvml.nvmlDeviceGetMemoryBusWidth(handle)),
        "pcie": fmt_pcie(
            safe_call(lambda: nvml.nvmlDeviceGetCurrPcieLinkGeneration(handle)),
            safe_call(lambda: nvml.nvmlDeviceGetMaxPcieLinkGeneration(handle)),
            safe_call(lambda: nvml.nvmlDeviceGetCurrPcieLinkWidth(handle)),
            safe_call(lambda: nvml.nvmlDeviceGetMaxPcieLinkWidth(handle)),
        ),
    }

    mig_mode = safe_call(lambda: nvml.nvmlDeviceGetMigMode(handle))
    if mig_mode is not None:
        current, pending = mig_mode
        values["mig_mode"] = f"current={current}, pending={pending}"

    return RuntimeInfo(source="NVML/pynvml", values=values)


def nvidia_smi_runtime_infos() -> dict[int, RuntimeInfo]:
    if shutil.which("nvidia-smi") is None:
        return {}

    cmd = [
        "nvidia-smi",
        f"--query-gpu={','.join(NVIDIA_SMI_QUERY_FIELDS)}",
        "--format=csv,noheader,nounits",
    ]
    result = safe_call(lambda: subprocess.run(cmd, check=True, capture_output=True, text=True), None)
    if result is None:
        return {}

    infos: dict[int, RuntimeInfo] = {}
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != len(NVIDIA_SMI_QUERY_FIELDS):
            continue

        raw = {key: clean(value) for key, value in zip(NVIDIA_SMI_QUERY_FIELDS, parts)}
        index = safe_call(lambda: int(raw["index"]))
        if index is None:
            continue

        values = {
            "driver_version": raw["driver_version"],
            "uuid": raw["uuid"],
            "memory_total": mib_to_gib(raw["memory.total"]),
            "memory_used": mib_to_gib(raw["memory.used"]),
            "memory_free": mib_to_gib(raw["memory.free"]),
            "gpu_util": fmt_percent(raw["utilization.gpu"]),
            "memory_util": fmt_percent(raw["utilization.memory"]),
            "temperature": fmt_celsius(raw["temperature.gpu"]),
            "power_draw": f"{raw['power.draw']} W" if valid(raw["power.draw"]) else "",
            "power_limit": f"{raw['power.limit']} W" if valid(raw["power.limit"]) else "",
            "sm_clock_current_mhz": to_float(raw["clocks.sm"]),
            "mem_clock_current_mhz": to_float(raw["clocks.mem"]),
            "pcie": fmt_pcie(
                raw["pcie.link.gen.current"],
                raw["pcie.link.gen.max"],
                raw["pcie.link.width.current"],
                raw["pcie.link.width.max"],
            ),
        }
        infos[index] = RuntimeInfo(source="nvidia-smi", values=values)

    return infos


def enrich_bandwidth(runtime: RuntimeInfo | None, spec: dict[str, Any]) -> tuple[int | None, float | None, str]:
    if runtime is None:
        bus_width = spec.get("memory_bus_width_bits")
        official = spec.get("official_bandwidth_gbs")
        if official:
            return bus_width, official, "型号规格表"
        return bus_width, None, ""

    values = runtime.values
    bus_width = values.get("memory_bus_width_bits") or spec.get("memory_bus_width_bits")
    max_mem_clock = values.get("mem_clock_max_mhz") or values.get("mem_clock_current_mhz")
    estimated = estimate_memory_bandwidth_gbs(to_float(max_mem_clock), bus_width)

    if estimated:
        return bus_width, estimated, "按显存频率和位宽估算"
    if spec.get("official_bandwidth_gbs"):
        return bus_width, spec["official_bandwidth_gbs"], "型号规格表"
    return bus_width, None, ""


def print_runtime_info(runtime: RuntimeInfo | None) -> None:
    if runtime is None:
        print("  运行状态: 未获取到；安装 nvidia-ml-py 或确认 nvidia-smi 可用后会更完整")
        return

    v = runtime.values
    print_line("运行信息来源", runtime.source)
    print_line("驱动版本", v.get("driver_version"))
    print_line("UUID", v.get("uuid"))
    print_line("PCI Bus ID", v.get("pci_bus_id"))
    print_line(
        "显存 已用/空闲/总量",
        f"{v.get('memory_used')} / {v.get('memory_free')} / {v.get('memory_total')}"
        if valid(v.get("memory_used")) and valid(v.get("memory_free")) and valid(v.get("memory_total"))
        else "",
    )
    print_line(
        "GPU利用率 / 显存控制器利用率",
        f"{v.get('gpu_util')} / {v.get('memory_util')}"
        if valid(v.get("gpu_util")) and valid(v.get("memory_util"))
        else "",
    )
    print_line("温度", v.get("temperature"))
    print_line(
        "功耗 当前/上限",
        f"{v.get('power_draw')} / {v.get('power_limit')}"
        if valid(v.get("power_draw")) and valid(v.get("power_limit"))
        else "",
    )
    print_line(
        "SM频率 当前/最高",
        f"{fmt_mhz(v.get('sm_clock_current_mhz'))} / {fmt_mhz(v.get('sm_clock_max_mhz'))}"
        if valid(v.get("sm_clock_current_mhz")) and valid(v.get("sm_clock_max_mhz"))
        else fmt_mhz(v.get("sm_clock_current_mhz")),
    )
    print_line(
        "显存频率 当前/最高",
        f"{fmt_mhz(v.get('mem_clock_current_mhz'))} / {fmt_mhz(v.get('mem_clock_max_mhz'))}"
        if valid(v.get("mem_clock_current_mhz")) and valid(v.get("mem_clock_max_mhz"))
        else fmt_mhz(v.get("mem_clock_current_mhz")),
    )
    print_line("PCIe链路", v.get("pcie"))
    print_line("MIG模式", v.get("mig_mode"))


def main() -> None:
    if not torch.cuda.is_available():
        print("PyTorch 当前看不到 CUDA GPU。")
        print(f"PyTorch版本: {torch.__version__}")
        print(f"PyTorch CUDA版本: {torch.version.cuda}")
        return

    nvml = load_nvml()
    smi_infos = {} if nvml is not None else nvidia_smi_runtime_infos()

    total_sms = 0
    total_cuda_cores = 0
    total_tensor_cores = 0
    total_memory = 0
    total_bandwidth = 0.0
    bandwidth_count = 0

    print(f"PyTorch版本: {torch.__version__}")
    print(f"PyTorch CUDA版本: {torch.version.cuda}")
    print(f"可见GPU数量: {torch.cuda.device_count()}")
    print("说明: 理论显存带宽是峰值估算，不代表当前实时吞吐。")
    print()

    try:
        for i in range(torch.cuda.device_count()):
            prop = torch.cuda.get_device_properties(i)
            cc = (prop.major, prop.minor)
            arch_info = ARCH_PER_SM.get(cc)
            spec = get_gpu_spec(prop.name)
            runtime = nvml_runtime_info(nvml, i) if nvml is not None else smi_infos.get(i)

            sm_count = prop.multi_processor_count
            total_sms += sm_count
            total_memory += prop.total_memory
            free_mem, torch_total_mem = get_torch_mem_info(i)

            bus_width, bandwidth, bandwidth_source = enrich_bandwidth(runtime, spec)
            if bandwidth:
                total_bandwidth += bandwidth
                bandwidth_count += 1

            print(f"GPU {i}: {prop.name}")
            print_line("架构", arch_info["arch"] if arch_info else "")
            print_line("Compute Capability", f"{prop.major}.{prop.minor}")
            print_line("SM数量", sm_count)

            if arch_info:
                cuda_cores = sm_count * arch_info["cuda_cores_per_sm"]
                tensor_cores = sm_count * arch_info["tensor_cores_per_sm"]
                total_cuda_cores += cuda_cores
                total_tensor_cores += tensor_cores
                print_line("CUDA Core", f"{cuda_cores} ({arch_info['cuda_cores_per_sm']} / SM)")
                print_line("Tensor Core", f"{tensor_cores} ({arch_info['tensor_cores_per_sm']} / SM)")
            else:
                print("  CUDA/Tensor Core: 未内置该架构映射，需查官方规格")

            print_line("显存总量", bytes_to_gib(prop.total_memory))
            if free_mem is not None and torch_total_mem is not None:
                print_line("PyTorch可用显存", f"{bytes_to_gib(free_mem)} / {bytes_to_gib(torch_total_mem)}")
            print_line("显存类型", spec.get("memory_type"))
            print_line("显存位宽", f"{bus_width} bit" if bus_width else "")
            print_line(
                "理论显存带宽",
                f"{fmt_bandwidth(bandwidth)} ({bandwidth_source})" if bandwidth and bandwidth_source else fmt_bandwidth(bandwidth),
            )
            print_line("Warp Size", getattr(prop, "warp_size", None))
            print_line("每个SM最大线程数", getattr(prop, "max_threads_per_multi_processor", None))

            print_runtime_info(runtime)
            print()

        print("整机汇总")
        print_line("GPU数量", torch.cuda.device_count())
        print_line("总显存", bytes_to_gib(total_memory))
        print_line("总SM", total_sms)
        print_line("总CUDA Core", total_cuda_cores)
        print_line("总Tensor Core", total_tensor_cores)
        if bandwidth_count == torch.cuda.device_count():
            print_line("理论显存带宽合计", f"{fmt_bandwidth(total_bandwidth)} (各卡峰值相加)")

    finally:
        shutdown_nvml(nvml)


if __name__ == "__main__":
    main()
