# tools/fleet_make_100.py
#
# Repeats: build -> copy .pio/build/<env>/firmware.bin -> save as firmwareNNN.bin
# Appends manifest.csv with index,filename,uuid,timestamp,env,git_commit

import argparse
import csv
import os
import re
import subprocess
import sys
from datetime import datetime
from glob import glob
from pathlib import Path
from shutil import which

UUID_RE = re.compile(r'^\s*#\s*define\s+MACHINE_UUID\s+"([^"]+)"', re.MULTILINE)

def find_pio_cmd():
    for cmd in ("platformio", "pio"):
        if which(cmd):
            return cmd
    return None

def next_index(dest_dir: Path, width: int = 3) -> int:
    dest_dir.mkdir(parents=True, exist_ok=True)
    hits = glob(str(dest_dir / "firmware*.bin"))
    max_n = 0
    for p in hits:
        m = re.search(r"firmware(\d{3})\.bin$", Path(p).name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1

def read_uuid_from_config(config_h: Path) -> str:
    try:
        txt = config_h.read_text(encoding="utf-8")
        m = UUID_RE.search(txt)
        return m.group(1) if m else ""
    except Exception:
        return ""

def git_commit_short(project_dir: Path) -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(project_dir))
        return out.decode().strip()
    except Exception:
        return ""

def append_manifest(dest_dir: Path, idx: int, filename: str, uuid_str: str, env_name: str, project_dir: Path):
    manifest = dest_dir / "manifest.csv"
    is_new = not manifest.exists()
    row = {
        "index": idx,
        "filename": filename,
        "uuid": uuid_str,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "env": env_name,
        "git_commit": git_commit_short(project_dir),
    }
    with open(manifest, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if is_new:
            writer.writeheader()
        writer.writerow(row)

def run_build(pio_cmd: str, env_name: str, project_dir: Path, clean_first: bool=False) -> int:
    if clean_first:
        rc = subprocess.run([pio_cmd, "run", "-e", env_name, "-t", "clean"], cwd=str(project_dir)).returncode
        if rc != 0:
            return rc
    return subprocess.run([pio_cmd, "run", "-e", env_name], cwd=str(project_dir)).returncode

def main():
    parser = argparse.ArgumentParser(description="Compile and archive up to N unique Marlin firmwares with manifest.")
    parser.add_argument("-e", "--env", default="STM32G0B1RE_btt")
    parser.add_argument("-n", "--limit", type=int, default=100)
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--clean-each", action="store_true")
    args = parser.parse_args()

    pio_cmd = find_pio_cmd()
    if not pio_cmd:
        print("[fleet] ERROR: PlatformIO CLI not found on PATH.")
        sys.exit(1)

    project_dir = Path(args.project_dir).resolve()
    env_name = args.env
    src_bin = project_dir / ".pio" / "build" / env_name / "firmware.bin"
    dest_dir = project_dir / "firmware" / env_name
    config_h = project_dir / "Marlin" / "Configuration.h"  # adjust if needed

    idx = next_index(dest_dir)
    if idx > args.limit:
        print(f"[fleet] Already at or beyond limit ({args.limit}). Nothing to do.")
        sys.exit(0)

    print(f"[fleet] Using CLI: {pio_cmd}")
    print(f"[fleet] Project:   {project_dir}")
    print(f"[fleet] Env:       {env_name}")
    print(f"[fleet] Source:    {src_bin}")
    print(f"[fleet] Target:    {dest_dir} (firmwareNNN.bin)")
    print(f"[fleet] Start N:   {idx} -> {args.limit}")

    produced = 0
    while idx <= args.limit:
        print(f"\n[fleet] Build {idx}/{args.limit} ...")
        rc = run_build(pio_cmd, env_name, project_dir, clean_first=args.clean_each)
        if rc != 0:
            print(f"[fleet] Build failed with exit code {rc}. Stopping.")
            sys.exit(rc)

        if not src_bin.is_file():
            print(f"[fleet] ERROR: Not found: {src_bin}")
            sys.exit(2)

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_name = f"firmware{idx:03d}.bin"
        dest_path = dest_dir / dest_name
        if dest_path.exists():
            print(f"[fleet] WARNING: {dest_name} exists. Skipping copy.")
        else:
            dest_path.write_bytes(src_bin.read_bytes())
            uuid_str = read_uuid_from_config(config_h)
            append_manifest(dest_dir, idx, dest_name, uuid_str, env_name, project_dir)
            print(f"[fleet] Saved -> {dest_path.relative_to(project_dir)} (UUID: {uuid_str})")
            produced += 1

        idx += 1

    print(f"\n[fleet] Done. New binaries produced: {produced}")

if __name__ == "__main__":
    main()
