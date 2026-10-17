"""Show local Ollama hardware status and measure a warm Gemma 4 request."""
import ctypes
import os
import platform
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit, urlunsplit

import requests

OLLAMA_CHAT_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_BASE_URL = urlunsplit((*urlsplit(OLLAMA_CHAT_URL)[:2], "", "", "")).rstrip("/")


def memory_total_gib():
    if sys.platform == "win32":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys / (1024**3)
    elif os.path.exists("/proc/meminfo"):
        with open("/proc/meminfo", encoding="ascii") as meminfo:
            for line in meminfo:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024**2)
    else:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        return page_size * pages / (1024**3)
    return None


def gpu_status():
    executable = shutil.which("nvidia-smi")
    if not executable:
        return "nvidia-smi not found"
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return f"nvidia-smi failed: {error}"
    if result.returncode:
        return result.stderr.strip() or "nvidia-smi failed"
    return "; ".join(part.strip() for part in result.stdout.splitlines() if part.strip()) or "No NVIDIA GPU found"


def ollama_version():
    response = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=5)
    response.raise_for_status()
    return response.json()["version"]


def ollama_processes():
    executable = shutil.which("ollama")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "ps"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    return result.stdout.strip()


def gemma_on_gpu(processes):
    if processes is None:
        return "ollama CLI unavailable"
    if not processes:
        return "No model currently loaded"
    rows = [line for line in processes.splitlines() if line.strip()]
    gemma_rows = [line for line in rows if line.lower().startswith("gemma4")]
    if not gemma_rows:
        return "No Gemma 4 process reported"
    if any("gpu" in line.lower() for line in gemma_rows):
        return "Yes (" + "; ".join(gemma_rows) + ")"
    return "No (" + "; ".join(gemma_rows) + ")"


def warm_call_latency():
    payload = {
        "model": "gemma4",
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "stream": False,
        "think": False,
        "options": {"num_predict": 1},
    }
    response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=(10, 300))
    response.raise_for_status()
    response.json()
    started = time.perf_counter()
    response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=(10, 300))
    response.raise_for_status()
    response.json()
    return time.perf_counter() - started


def print_table(rows):
    key_width = max(len("Component"), *(len(key) for key, _ in rows))
    value_width = max(len("Status"), *(len(value) for _, value in rows))
    border = f"+-{'-' * key_width}-+-{'-' * value_width}-+"
    print(border)
    print(f"| {'Component'.ljust(key_width)} | {'Status'.ljust(value_width)} |")
    print(border)
    for key, value in rows:
        print(f"| {key.ljust(key_width)} | {value.ljust(value_width)} |")
    print(border)


def main():
    processor = platform.processor() or platform.machine() or "Unknown"
    memory = memory_total_gib()
    rows = [
        ("CPU", f"{processor} ({os.cpu_count() or 'unknown'} logical cores)"),
        ("RAM", f"{memory:.1f} GiB" if memory is not None else "Unavailable"),
        ("GPU", gpu_status()),
    ]
    failed = False
    try:
        rows.append(("Ollama version", ollama_version()))
        processes = ollama_processes()
        rows.append(("Gemma 4 on GPU", gemma_on_gpu(processes)))
    except (requests.RequestException, ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        rows.extend(
            [
                ("Ollama version", "Unavailable"),
                ("Gemma 4 on GPU", "Unavailable"),
            ]
        )
        print(f"Ollama status check failed: {error}", file=sys.stderr)
        failed = True

    try:
        latency = warm_call_latency()
        rows.append(("Warm-call latency", f"{latency:.2f} s"))
    except (requests.RequestException, ValueError, KeyError) as error:
        rows.append(("Warm-call latency", f"Unavailable ({error})"))
        print("Gemma 4 warm-call failed; verify Ollama and run 'ollama pull gemma4'.", file=sys.stderr)
        failed = True

    print_table(rows)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
