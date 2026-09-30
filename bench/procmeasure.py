"""Subprozess mit Laufzeit- und Spitzen-RAM-Messung (Windows: PeakWorkingSetSize per ctypes).

Gemessen wird der Prozessbaum: der Wurzelprozess (exakt ueber sein Handle) plus alle Nachkommen
(z. B. `dotnet run` startet die eigentliche App als Kindprozess), die alle 0.1 s abgefragt werden.
peak_ram_mb = Maximum der Spitzen-Working-Sets ueber alle Prozesse des Baums (nicht die Summe).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

MB = 1024.0 * 1024.0


def _kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.killpg(pid, 9)
        except Exception:
            pass


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class _PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t)]

    class _PE32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PE32)]
    _k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PE32)]
    _k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    _PROCESS_QUERY_LIMITED = 0x1000
    _PROCESS_VM_READ = 0x0010
    _PROCESS_QUERY = 0x0400

    def _peak_ws(handle) -> int | None:
        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        if _k32.K32GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return int(pmc.PeakWorkingSetSize)
        return None

    def _children_map() -> dict[int, list[int]]:
        snap = _k32.CreateToolhelp32Snapshot(2, 0)
        m: dict[int, list[int]] = {}
        if not snap or snap == wintypes.HANDLE(-1).value:
            return m
        pe = _PE32()
        pe.dwSize = ctypes.sizeof(_PE32)
        ok = _k32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            m.setdefault(int(pe.th32ParentProcessID), []).append(int(pe.th32ProcessID))
            ok = _k32.Process32NextW(snap, ctypes.byref(pe))
        _k32.CloseHandle(snap)
        return m

    def _descendants(pid: int) -> list[int]:
        cm = _children_map()
        out, stack = [], [pid]
        while stack:
            for c in cm.get(stack.pop(), []):
                if c not in out:
                    out.append(c)
                    stack.append(c)
        return out

    def _peak_of_pid(pid: int) -> int | None:
        h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED | _PROCESS_VM_READ, False, pid) or _k32.OpenProcess(_PROCESS_QUERY | _PROCESS_VM_READ, False, pid)
        if not h:
            return None
        try:
            return _peak_ws(h)
        finally:
            _k32.CloseHandle(h)


def run_measured(cmd: list[str], cwd: str, timeout: float, stdout_path, stderr_path, env=None) -> dict:
    """Startet cmd, wartet bis timeout Sekunden, misst Wandzeit und Spitzen-RAM des Prozessbaums."""
    t0 = time.perf_counter()
    res = {"cmd": cmd, "timed_out": False, "peak_ram_mb": None, "peak_ram_root_mb": None,
           "peak_ram_max_child_mb": None, "ram_method": None}
    with open(stdout_path, "wb") as fo, open(stderr_path, "wb") as fe:
        try:
            p = subprocess.Popen(cmd, cwd=cwd, stdout=fo, stderr=fe, env=env,
                                 creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
                                 start_new_session=(os.name != "nt"))
        except FileNotFoundError as e:
            res.update(exit_code=None, wall_s=0.0, error=f"Programm nicht gefunden: {e}")
            return res
        child_peaks: dict[int, int] = {}
        root_peak = 0
        deadline = t0 + timeout
        if os.name == "nt":
            res["ram_method"] = "PeakWorkingSetSize (K32GetProcessMemoryInfo), Prozessbaum, Abfrage alle 0.1 s"
            root_h = int(p._handle)
            while True:
                try:
                    p.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    pass
                v = _peak_ws(root_h)
                root_peak = max(root_peak, v or 0)
                for d in _descendants(p.pid):
                    pk = _peak_of_pid(d)
                    if pk:
                        child_peaks[d] = max(child_peaks.get(d, 0), pk)
                if time.perf_counter() > deadline:
                    res["timed_out"] = True
                    _kill_tree(p.pid)
                    p.wait()
                    break
            v = _peak_ws(root_h)  # nach dem Ende ueber das offene Handle: exakter Spitzenwert
            root_peak = max(root_peak, v or 0)
        else:
            res["ram_method"] = "resource.getrusage(RUSAGE_CHILDREN).ru_maxrss (Fallback, Maximum aller Kinder)"
            import resource
            try:
                p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                res["timed_out"] = True
                _kill_tree(p.pid)
                p.wait()
            ru = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            root_peak = ru * (1 if sys.platform == "darwin" else 1024)
    res["exit_code"] = p.returncode
    res["wall_s"] = round(time.perf_counter() - t0, 3)
    mc = max(child_peaks.values()) if child_peaks else 0
    res["peak_ram_root_mb"] = round(root_peak / MB, 1) if root_peak else None
    res["peak_ram_max_child_mb"] = round(mc / MB, 1) if mc else None
    tot = max(root_peak, mc)
    res["peak_ram_mb"] = round(tot / MB, 1) if tot else None
    return res
