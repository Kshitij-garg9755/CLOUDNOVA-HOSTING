import base64
import json
from urllib.parse import quote

from app.services.frameworks import detect


def safe_root_directory(value: str) -> str:
    value = (value or "").strip().replace("\\", "/")
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        raise ValueError("Root directory must be a repository-relative path")
    while value.startswith("./"):
        value = value[2:]
    value = value.strip("/")
    if value in {"", "."}:
        return ""
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Root directory must be a repository-relative path")
    return value


def inspect_repository(client, installation_id: str, full_name: str, branch: str, root_directory: str = ".") -> dict:
    root = safe_root_directory(root_directory)
    base = f"/repos/{full_name}/contents"
    path = f"{base}/{quote(root, safe='/')}" if root else base
    listing = client.request(installation_id, path, {"ref": branch})
    if not isinstance(listing, list):
        raise ValueError("Selected root path must be a directory")

    entries = [entry for entry in listing if isinstance(entry, dict)]
    paths = [entry.get("path", entry.get("name", "")) for entry in entries]
    names = {entry.get("name", "").lower(): entry for entry in entries}

    def read_text(filename: str) -> str:
        entry = names.get(filename.lower())
        if not entry or entry.get("type") != "file":
            return ""
        content = client.request(installation_id, f"{path}/{quote(filename)}", {"ref": branch}).get("content", "")
        try:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return ""

    package = {}
    package_text = read_text("package.json")
    if package_text:
        try:
            package = json.loads(package_text)
        except (json.JSONDecodeError, TypeError):
            package = {}
    python_dependencies = read_text("requirements.txt") + "\n" + read_text("pyproject.toml")
    return detect(paths, package, python_dependencies)
