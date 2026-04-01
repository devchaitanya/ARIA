import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from src.config import REPOS_DIR, CLONE_DEPTH


@dataclass
class RepoMetadata:
    owner: str
    name: str
    local_path: str
    url: str
    branch: str


def parse_github_url(url: str) -> tuple[str, str]:
    patterns = [
        r"github\.com/([^/]+)/([^/.]+)",
        r"github\.com/([^/]+)/([^/.]+)\.git",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise ValueError(f"Invalid GitHub URL: {url}")


def clone_repo(url: str, branch: str = "main") -> RepoMetadata:
    owner, name = parse_github_url(url)
    local_path = os.path.join(REPOS_DIR, f"{owner}__{name}")

    if os.path.exists(local_path):
        shutil.rmtree(local_path)

    git_url = url if url.endswith(".git") else url + ".git"

    try:
        subprocess.run(
            ["git", "clone", "--depth", str(CLONE_DEPTH), "--branch", branch, git_url, local_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["git", "clone", "--depth", str(CLONE_DEPTH), git_url, local_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

    return RepoMetadata(
        owner=owner, name=name, local_path=local_path, url=url, branch=branch
    )


def collect_files(repo_path: str, extensions: set[str], max_size: int, max_files: int) -> list[dict]:
    files = []
    for root, _dirs, filenames in os.walk(repo_path):
        rel_root = os.path.relpath(root, repo_path)
        if any(part.startswith(".") for part in rel_root.split(os.sep)):
            continue
        if any(skip in rel_root for skip in ("node_modules", "vendor", "__pycache__", "dist", "build", ".git")):
            continue

        for fname in filenames:
            if len(files) >= max_files:
                return files
            ext = os.path.splitext(fname)[1]
            if ext not in extensions:
                continue
            fpath = os.path.join(root, fname)
            if os.path.getsize(fpath) > max_size:
                continue
            rel_path = os.path.relpath(fpath, repo_path)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                files.append({"path": rel_path, "content": content, "extension": ext})
            except Exception:
                continue
    return files
