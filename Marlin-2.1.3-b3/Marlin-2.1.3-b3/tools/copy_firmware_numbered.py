# tools/copy_firmware_numbered.py
#
# Post-build hook for PlatformIO:
# - Always copy the produced BIN (firmware.bin) — not the ELF —
# - Save to: ./firmware/<env>/firmwareNNN.bin (persistent across cleans)
# - Keep a per-environment counter up to 100

import os
import shutil
from glob import glob

Import("env")  # Provided by PlatformIO/SCons

MAX_COUNT = 100
ROOT_DIR  = env["PROJECT_DIR"]
ENV_NAME  = env.subst("$PIOENV")
DEST_DIR  = os.path.join(ROOT_DIR, "firmware", ENV_NAME)

def zero_pad(n, width=3):
    return str(n).zfill(width)

def find_bin(env):
    """Return absolute path to firmware.bin in the build dir, or None if not found."""
    build_dir  = env.subst("$BUILD_DIR")
    progname   = env.subst("$PROGNAME")          # usually "firmware" for Marlin

    # Preferred exact name
    candidate = os.path.join(build_dir, f"{progname}.bin")
    if os.path.isfile(candidate):
        return candidate

    # If target artifact was ELF, try replacing extension with .bin
    # (e.g., .pio/build/<env>/firmware.elf -> firmware.bin)
    elf = os.path.join(build_dir, f"{progname}{env.subst('$PROGSUFFIX')}")
    if elf.endswith(".elf"):
        maybe_bin = elf[:-4] + ".bin"
        if os.path.isfile(maybe_bin):
            return maybe_bin

    # Last resort: any .bin in the build dir that starts with progname
    hits = sorted(glob(os.path.join(build_dir, f"{progname}*.bin")))
    if hits:
        # Pick the most recently modified one
        hits.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return hits[0]

    return None

def post_build_copy(target, source, env):  # match SCons signature
    produced_bin = find_bin(env)
    if not produced_bin:
        print("[copy_firmware_numbered] ERROR: Could not find firmware BIN in build dir.")
        print("[copy_firmware_numbered] Looked for 'firmware.bin' next to the ELF.")
        return

    os.makedirs(DEST_DIR, exist_ok=True)

    # Per-environment counter
    counter_file = os.path.join(DEST_DIR, ".counter")
    count = 0
    if os.path.isfile(counter_file):
        try:
            with open(counter_file, "r", encoding="utf-8") as f:
                count = int(f.read().strip())
        except Exception:
            count = 0

    # Find next slot up to MAX_COUNT
    next_n = count + 1
    while next_n <= MAX_COUNT:
        dest_candidate = os.path.join(DEST_DIR, f"firmware{zero_pad(next_n)}.bin")
        if not os.path.exists(dest_candidate):
            break
        next_n += 1

    if next_n > MAX_COUNT:
        print(f"[copy_firmware_numbered] Reached MAX_COUNT={MAX_COUNT}. No copy made.")
        return

    dest_path = os.path.join(DEST_DIR, f"firmware{zero_pad(next_n)}.bin")
    shutil.copyfile(produced_bin, dest_path)

    # Persist new counter
    with open(counter_file, "w", encoding="utf-8") as f:
        f.write(str(next_n))

    rel = os.path.relpath(dest_path, ROOT_DIR)
    print(f"[copy_firmware_numbered] Saved: {rel}")

# Register as a post-action on the final program target (ELF or otherwise)
env.AddPostAction("$BUILD_DIR/${PROGNAME}${PROGSUFFIX}", post_build_copy)
