"""Adiciona nonce=\"{{ csp_nonce }}\" em tags <script> sem nonce."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = [ROOT / "templates", ROOT / "core" / "templates", ROOT / "ftth_viewer" / "templates"]
SKIP_PARTS = ("includes/cdn_",)


def patch(content: str) -> str:
    def repl_open(m):
        tag = m.group(0)
        if "nonce=" in tag:
            return tag
        if tag == "<script>":
            return '<script nonce="{{ csp_nonce }}">'
        return tag.replace("<script ", '<script nonce="{{ csp_nonce }}" ', 1)

    return re.sub(r"<script(?:\s[^>]*)?>|<script>", repl_open, content, flags=re.IGNORECASE)


def main():
    changed = []
    for base in DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*.html"):
            if any(s in path.as_posix() for s in SKIP_PARTS):
                continue
            text = path.read_text(encoding="utf-8")
            new = patch(text)
            if new != text:
                path.write_text(new, encoding="utf-8")
                changed.append(path.relative_to(ROOT))
    print(f"Patched {len(changed)} files")
    for p in sorted(changed)[:40]:
        print(p)
    if len(changed) > 40:
        print(f"... +{len(changed) - 40} more")


if __name__ == "__main__":
    main()
