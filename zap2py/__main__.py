#!/usr/bin/env python3
from __future__ import annotations
"""
zap2py main entrypoint
YAML-driven multi-lineup EPG grabber orchestrator with optional Tvheadend socket delivery.
"""
import sys
import time
import yaml
import socket as _socket
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

@dataclass
class Lineup:
    name: str
    user: Optional[str] = None
    password: Optional[str] = None
    outfile: Optional[str] = None
    verbosity: int = 1
    sleep: float = 0.5
    use_socket: bool = False
    socket: Optional[str] = None
    cache: Optional[str] = None
    zip: Optional[str] = None
    lineup_id: Optional[str] = None

def _ts() -> str:
    return f"[{datetime.now():%Y-%m-%d %H:%M:%S}]"

def log(msg: str, level: str = "INFO") -> None:
    print(f"{_ts()} [{level}] {msg}", flush=True)

def load_yaml_config(path: str) -> dict:
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    if "lineups" not in data or not isinstance(data["lineups"], list) or not data["lineups"]:
        sys.exit(f"[FATAL] No 'lineups' section found in YAML: {path}")
    return data

def run_lineup(lu: Lineup, defaults: dict) -> int:
    name = getattr(lu, "name", "Unknown_Lineup")
    outfile = getattr(lu, "outfile", None) or f"/tmp/{name.replace(' ', '_')}.xml"
    cache_base = defaults.get("cache_base", "cache")
    safe_name = name.replace(" ", "_")
    cache = getattr(lu, "cache", None) or f"{cache_base}/{safe_name}"
    verbosity = int(getattr(lu, "verbosity", defaults.get("verbosity", 1)))
    delay = float(getattr(lu, "sleep", defaults.get("sleep", 0.5)))

    if verbosity == 0:
        vflag = "-q"
    elif verbosity >= 2:
        vflag = "-v"
    else:
        vflag = ""

    cmd = [
        sys.executable, "-m", "zap2py.core",
        *([vflag] if vflag else []),
        "-S", str(delay),
        "-c", cache,
        "-D",
    ]

    if getattr(lu, "user", None):
        cmd += ["-u", lu.user]
    if getattr(lu, "password", None):
        cmd += ["-p", lu.password]

    if getattr(lu, "zip", None):
        cmd += ["-Z", str(lu.zip)]
    if getattr(lu, "lineup_id", None):
        cmd += ["-Y", lu.lineup_id]

    cmd += ["-o", outfile]

    redacted = ["*****" if (i>0 and cmd[i-1] == "-p") else part for i, part in enumerate(cmd)]

    log(f"Running lineup '{name}' with output -> {outfile}")
    log("[DEBUG] Command: " + " ".join(redacted))

    start = time.time()
    result = subprocess.run(cmd, text=True)
    elapsed = int(time.time() - start)

    if result.returncode != 0:
        log(f"{name}: zap2py core failed (exit={result.returncode})", level="ERROR")
        return result.returncode

    log(f"{name}: completed successfully in {elapsed}s (exit=0)")

    if getattr(lu, "use_socket", False):
        sock_path = getattr(lu, "socket", None) or defaults.get("socket")
        if not sock_path:
            log(f"{name}: use_socket=true but no socket path provided", level="WARN")
            return 1

        log(f"Sending {outfile} -> {sock_path}")
        try:
            with open(outfile, "rb") as f, _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
                s.settimeout(30)
                s.connect(sock_path)
                s.sendall(f.read())
            log(f"{name}: feed delivered successfully to Tvheadend socket")
        except Exception as e:
            log(f"{name}: failed to send to socket {sock_path}: {e}", level="ERROR")
            return 2

    return 0

def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        cfg_path = "lineups.yaml"
        print(f"[INFO] No config path specified, using default: {cfg_path}")
    else:
        cfg_path = sys.argv[1]

    log(f"Starting EPG update from config: {cfg_path}")
    data = load_yaml_config(cfg_path)
    defaults = data.get("defaults", {}) or {}
    defaults.setdefault("cache_base", "cache")

    lineups_cfg = data.get("lineups", [])
    log(f"Found {len(lineups_cfg)} lineup(s) in YAML")

    failed = 0
    for entry in lineups_cfg:
        merged = {**defaults, **(entry or {})}
        lineup = Lineup(
            name=merged["name"],
            user=merged.get("user"),
            password=merged.get("password"),
            outfile=merged.get("outfile"),
            verbosity=int(merged.get("verbosity", defaults.get("verbosity", 1))),
            sleep=float(merged.get("sleep", defaults.get("sleep", 0.5))),
            use_socket=bool(merged.get("use_socket", defaults.get("use_socket", False))),
            socket=merged.get("socket", defaults.get("socket")),
            cache=merged.get("cache"),
            zip=merged.get("zip"),
            lineup_id=merged.get("lineup_id"),
        )

        code = run_lineup(lineup, defaults)
        if code != 0:
            failed += 1

        time.sleep(lineup.sleep)

    log(f"All lineups processed. Failures: {failed}")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
