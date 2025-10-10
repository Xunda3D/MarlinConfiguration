# tools/gen_machine_uuid.py
#
# PlatformIO pre-build script: generates a fresh MACHINE_UUID and
# inserts/replaces it in Marlin/Configuration.h on every build.

import os
import re
import uuid

Import("env")  # Provided by PlatformIO/SCons

# --- Settings ---------------------------------------------------------------
# Path to Configuration.h relative to project root
CONFIG_REL_PATH = os.environ.get("MARLIN_CONFIG_PATH", "Marlin/Configuration.h")

# Whether to create a .bak backup before writing
MAKE_BACKUP = True
# ---------------------------------------------------------------------------

proj_dir = env["PROJECT_DIR"]
config_path = os.path.join(proj_dir, CONFIG_REL_PATH)

def gen_uuid_str():
    # Marlin usually expects a plain UUID string in quotes
    return str(uuid.uuid4())

def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def save_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def ensure_backup(path):
    if MAKE_BACKUP:
        bak = path + ".bak"
        if not os.path.exists(bak):
            try:
                with open(path, "rb") as src, open(bak, "wb") as dst:
                    dst.write(src.read())
            except Exception as e:
                print(f"[gen_machine_uuid] Backup skipped ({e})")

def write_uuid(config_path):
    if not os.path.isfile(config_path):
        print(f"[gen_machine_uuid] WARNING: '{config_path}' not found.")
        return

    text = load_text(config_path)
    new_uuid = gen_uuid_str()

    # Pattern matches: #define MACHINE_UUID "anything"
    # - allows extra whitespace
    # - keeps any trailing comment
    define_pat = re.compile(
        r'(^\s*#\s*define\s+MACHINE_UUID\s*)(".*?")(\s*(?://.*|/\*.*?\*/)?\s*$)',
        re.MULTILINE | re.DOTALL
    )

    if define_pat.search(text):
        # Replace existing value only
        updated = define_pat.sub(rf'\1"{new_uuid}"\3', text, count=1)
        action = "updated"
    else:
        # Insert a new define near the top (right after initial comment block if present)
        insert_line = f'#define MACHINE_UUID "{new_uuid}"\n'
        # Try to place after leading license/comment block
        m = re.match(r'(\s*(?:/\*.*?\*/\s*|//[^\n]*\n)*)', text, re.DOTALL)
        if m and m.end() > 0:
            head = text[:m.end()]
            body = text[m.end():]
            updated = head + insert_line + body
        else:
            updated = insert_line + text
        action = "inserted"

    if updated != text:
        ensure_backup(config_path)
        save_text(config_path, updated)
        print(f"[gen_machine_uuid] MACHINE_UUID {action}: {new_uuid}")
    else:
        # Fallback (shouldn’t happen): force insert at top
        ensure_backup(config_path)
        updated = f'#define MACHINE_UUID "{new_uuid}"\n' + text
        save_text(config_path, updated)
        print(f"[gen_machine_uuid] MACHINE_UUID inserted (fallback): {new_uuid}")

# Execute on import (pre-build)
write_uuid(config_path)
