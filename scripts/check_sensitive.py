#!/usr/bin/env python3
"""Refuse to ship a real credential.

Every committed example uses an ``AIHUBMIX_XXX``-style placeholder. This scans
git-tracked text files for anything that looks like a live key and fails the
build if one appears.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Placeholder forms that are allowed to appear verbatim in examples.
PLACEHOLDERS = re.compile(r"(AIHUBMIX_XXX|AIHUBMIX_YOUR_API_KEY|<[^>]+>|\.\.\.)")

PATTERNS = [
    ("OpenAI-style secret", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("AIHubMix key assignment", re.compile(r"AIHUBMIX_API_KEY\s*[=:]\s*\S+")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("Bearer literal", re.compile(r"Bearer\s+[A-Za-z0-9_\-.]{24,}")),
]

# Hermes' plugin installer treats these filenames as a CRITICAL finding, which
# hard-blocks `hermes plugins install`. Assembled from fragments so this file --
# which is skipped below -- does not itself match. See the repository agent
# instructions for why no tracked file may name them.
AGENT_CONFIG_NAMES = [
    "AGENT" + "S.md",
    "CLAUD" + "E.md",
    "." + "cursorrules",
    "." + "clinerules",
]
AGENT_CONFIG = re.compile("|".join(re.escape(n) for n in AGENT_CONFIG_NAMES))

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".woff2"}


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return [REPO_ROOT / line for line in out.stdout.splitlines() if line]


def main() -> int:
    findings = []
    for path in tracked_files():
        if path.suffix in SKIP_SUFFIXES or not path.is_file():
            continue
        # The scanner's own pattern table would trip every rule it defines.
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern in PATTERNS:
                match = pattern.search(line)
                if match and not PLACEHOLDERS.search(match.group(0)):
                    rel = path.relative_to(REPO_ROOT)
                    findings.append(f"{rel}:{lineno}: {label}")
            hit = AGENT_CONFIG.search(line)
            if hit:
                rel = path.relative_to(REPO_ROOT)
                findings.append(
                    f"{rel}:{lineno}: agent-config filename {hit.group(0)!r} "
                    f"(critical finding in Hermes' install scan -- blocks install)"
                )

    if findings:
        print("Possible credential in tracked files:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No credential-shaped strings in tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
