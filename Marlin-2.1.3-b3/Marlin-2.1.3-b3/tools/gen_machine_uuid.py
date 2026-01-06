# tools/gen_machine_uuid.py
#
# PlatformIO pre-build script:
#  - Generates a fresh MACHINE_UUID
#  - Sets CUSTOM_MACHINE_NAME to 1XTNNN where NNN is the next available index
#    in ./firmware/<env>/ (so it matches your archived firmwareNNN.bin)
#
# Works with AutoBuildMarlin (PlatformIO under the hood).

import os
import re
import uuid
from glob import glob

Import("env")  # Provided by PlatformIO/SCons

# --- Settings ---------------------------------------------------------------
CONFIG_REL_PATH = os.environ.get("MARLIN_CONFIG_PATH", "Marlin/Configuration.h")
MAKE_BACKUP = True
MAX_COUNT = 999  # safety cap for NNN (you target up to 100, but 999 keeps it flexible)
# ---------------------------------------------------------------------------

ROOT_DIR = env["PROJECT_DIR"]
ENV_NAME = env.subst("$PIOENV")
CONFIG_PATH = os.path.join(ROOT_DIR, CONFIG_REL_PATH)
DEST_DIR = os.path.join(ROOT_DIR, "firmware", ENV_NAME)

UUID_DEFINE = r'(^\s*#\s*define\s+MACHINE_UUID\s*)(".*?")(\s*(?://.*|/\*.*?\*/)?\s*$)'
NAME_DEFINE = r'(^\s*#\s*define\s+CUSTOM_MACHINE_NAME\s*)(".*?")(\s*(?://.*|/\*.*?\*/)?\s*$)'

def gen_uuid_str():
    return str(uuid.uuid4())

def ensure_backup(path):
    if MAKE_BACKUP and os.path.isfile(path):
        bak = path + ".bak"
        if not os.path.exists(bak):
            try:
                with open(path, "rb") as src, open(bak, "wb") as dst:
                    dst.write(src.read())
            except Exception:
                pass

def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def save_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def next_index_for_env(dest_dir, width=3):
    """
    Scan ./firmware/<env>/ for firmwareNNN.bin and return the next available N (1-based).
    Mirrors the post-build script's logic so MACHINE_NAME aligns with the archived filename.
    """
    if not os.path.isdir(dest_dir):
        return 1
    hits = glob(os.path.join(dest_dir, "firmware*.bin"))
    max_n = 0
    for p in hits:
        m = re.search(r"firmware(\d{3})\.bin$", os.path.basename(p))
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    nxt = max_n + 1
    if nxt < 1:
        nxt = 1
    if nxt > MAX_COUNT:
        nxt = MAX_COUNT
    return nxt

def upsert_define(text, pattern, new_value, insert_hint="#define MACHINE_UUID"):
    """
    Replace existing #define line for a given pattern, or insert near the top (after comment block).
    """
    rx = re.compile(pattern, re.MULTILINE | re.DOTALL)
    if rx.search(text):
        return rx.sub(rf'\1"{new_value}"\3', text, count=1), "replaced"
    # Insert near the top, after header comments if possible
    insert_line = f'{insert_hint}\n#define CUSTOM_MACHINE_NAME "{new_value}"\n' if "CUSTOM_MACHINE_NAME" in pattern else f'#define MACHINE_UUID "{new_value}"\n'
    m = re.match(r'(\s*(?:/\*.*?\*/\s*|//[^\n]*\n)*)', text, re.DOTALL)
    if m and m.end() > 0:
        head, body = text[:m.end()], text[m.end():]
        return head + insert_line + body, "inserted"
    return insert_line + text, "inserted"

def write_updates(config_path):
    if not os.path.isfile(config_path):
        print(f"[gen_machine_uuid] WARNING: '{config_path}' not found.")
        return

    content = load_text(config_path)
    ensure_backup(config_path)

    # 1) Generate UUID
    new_uuid = gen_uuid_str()

    # 2) Compute NNN (next available)
    nnn = next_index_for_env(DEST_DIR)
    machine_name = f"Xunda Tech 1XT{nnn:03d}"

    # 3) Update/insert MACHINE_UUID
    content2, action_uuid = upsert_define(content, UUID_DEFINE, new_uuid)

    # 4) Update/insert CUSTOM_MACHINE_NAME
    #    Try replace; if missing, insert a clean define (not chained to UUID define)
    rx_name = re.compile(NAME_DEFINE, re.MULTILINE | re.DOTALL)
    if rx_name.search(content2):
        content3 = rx_name.sub(rf'\1"{machine_name}"\3', content2, count=1)
        action_name = "replaced"
    else:
        # Insert CUSTOM_MACHINE_NAME near the top (after comment block)
        insert_line = f'#define CUSTOM_MACHINE_NAME "{machine_name}"\n'
        m = re.match(r'(\s*(?:/\*.*?\*/\s*|//[^\n]*\n)*)', content2, re.DOTALL)
        if m and m.end() > 0:
            head, body = content2[:m.end()], content2[m.end():]
            content3 = head + insert_line + body
        else:
            content3 = insert_line + content2
        action_name = "inserted"

    # 5) Save
    save_text(config_path, content3)
    print(f"[gen_machine_uuid] MACHINE_UUID {action_uuid}: {new_uuid}")
    print(f"[gen_machine_uuid] CUSTOM_MACHINE_NAME {action_name}: {machine_name}")
    print(f"[gen_machine_uuid] ENV={ENV_NAME} next index -> {nnn:03d}")

write_updates(CONFIG_PATH)
