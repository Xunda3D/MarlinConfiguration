# tools/fleet_make_100.py
#
# Workflow:
#   build -> copy .pio/build/<env>/firmware.bin -> save as firmwareNNN.bin
# Repeats until N hits --limit (default 100). Resumes numbering automatically.

import argparse
import os
import re
import subprocess
import sys
from glob import glob
from pathlib import Path
from shutil import which

def find_pio_cmd():
    # Prefer "platformio" but fall back to "pio"
    for cmd in ("platformio", "pio"):
        if which(cmd):
            return cmd
    return None

def next_index(dest_dir: Path, width: int = 3) -> int:
    dest_dir.mkdir(parents=True, exist_ok=True)
    hits = glob(str(dest_dir / f"firmware[0-9]{{{width}}}.bin"))
    if not hits:
        # if glob with quantifier not supported by shell, fallback to any bin
        hits = glob(str(dest_dir / "firmware*.bin"))
    rx = re.compile(rf"firmware(\d{{{width}}})\.bin$")
    max_n = 0
    for p in hits:
        m = rx.search(Path(p).name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1

def run_build(pio_cmd: str, env_name: str, project_dir: Path, clean_first: bool=False) -> int:
    # Optional clean to guarantee a full rebuild
    if clean_first:
        rc = subprocess.run([pio_cmd, "run", "-e", env_name, "-t", "clean"],
                            cwd=str(project_dir)).returncode
        if rc != 0:
            return rc
    # Regular build (no invalid -f flag)
    return subprocess.run([pio_cmd, "run", "-e", env_name],
                          cwd=str(project_dir)).returncode

def main():
    parser = argparse.ArgumentParser(description="Compile and archive up to N unique Marlin firmwares.")
    parser.add_argument("-e", "--env", default="STM32G0B1RE_btt", help="PlatformIO environment name")
    parser.add_argument("-n", "--limit", type=int, default=100, help="Max number of firmware files to produce")
    parser.add_argument("--project-dir", default=".", help="Project root (where platformio.ini lives)")
    parser.add_argument("--clean-each", action="store_true",
                        help="Run 'pio run -t clean' before each build (usually unnecessary if UUID pre-hook edits files).")
    args = parser.parse_args()

    pio_cmd = find_pio_cmd()
    if not pio_cmd:
        print("[fleet] ERROR: PlatformIO CLI not found. Install it or ensure 'platformio'/'pio' is on PATH.")
        sys.exit(1)

    project_dir = Path(args.project_dir).resolve()
    env_name = args.env

    src_bin = project_dir / ".pio" / "build" / env_name / "firmware.bin"
    dest_dir = project_dir / "firmware" / env_name

    idx = next_index(dest_dir)
    if idx > args.limit:
        print(f"[fleet] Already at or beyond limit ({args.limit}). Nothing to do.")
        sys.exit(0)

    print(f"[fleet] Using CLI: {pio_cmd}")
    print(f"[fleet] Project:   {project_dir}")
    print(f"[fleet] Env:       {env_name}")
    print(f"[fleet] Source:    {src_bin}")
    print(f"[fleet] Target:    {dest_dir} (firmwareNNN.bin)")
    print(f"[fleet] Start N:   {idx}  -> up to {args.limit}")

    produced = 0
    while idx <= args.limit:
        print(f"\n[fleet] Build {idx}/{args.limit} ...")
        rc = run_build(pio_cmd, env_name, project_dir, clean_first=args.clean_each)
        if rc != 0:
            print(f"[fleet] Build failed with exit code {rc}. Stopping.")
            sys.exit(rc)

        if not src_bin.is_file():
            print(f"[fleet] ERROR: Not found: {src_bin}")
            print("[fleet] Tip: confirm your -e env name and that the board produces firmware.bin")
            sys.exit(2)

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"firmware{str(idx).zfill(3)}.bin"
        if dest_path.exists():
            print(f"[fleet] WARNING: {dest_path.name} exists. Skipping copy.")
        else:
            dest_path.write_bytes(src_bin.read_bytes())
            print(f"[fleet] Saved -> {dest_path.relative_to(project_dir)}")
            produced += 1

        idx += 1

    print(f"\n[fleet] Done. New binaries produced: {produced}")

if __name__ == "__main__":
    main()
