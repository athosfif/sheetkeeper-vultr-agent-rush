"""Build the allowlisted source release; never package credentials/account evidence."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FOLDERS = ("src", "web", "sandbox", "fixtures", "tests", "public-evidence")
SELECTED = (
    "README.md", "LICENSE", "pyproject.toml", ".env.example", ".gitignore",
    "docs/README-PREPARATION-20261106-PT.md", "docs/IMPLANTACAO.md",
    "docs/VULTR-EXECUTION-PLAN.md", "docs/VULTR-PROVISIONING.md",
    "scripts/check_docker.py", "scripts/check_browser.py", "scripts/package_source.py",
    "scripts/check_cloud_boundaries.py", "scripts/provision_vultr.sh",
)


def source_files():
    files = []
    for folder in PUBLIC_FOLDERS:
        for file in (ROOT / folder).rglob("*"):
            if (file.is_file() and not file.is_symlink() and "__pycache__" not in file.parts
                    and not file.name.startswith("._") and file.name != ".DS_Store"
                    and file.suffix != ".pyc"):
                files.append(file)
    files.extend(ROOT / name for name in SELECTED if (ROOT / name).is_file())
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/SHEETKEEPER-SOURCE-R03-20261108.zip")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evidence/SOURCE-R03-MANIFEST-20261108.json")
    args = parser.parse_args()
    files = source_files()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file in files:
            bundle.write(file, file.relative_to(ROOT))
    with zipfile.ZipFile(args.output) as bundle:
        assert bundle.testzip() is None
        assert not any(name.startswith(("evidence/", "presentation/")) for name in bundle.namelist())
    manifest = {
        "state": "source_release_packaged_publication_verified_separately",
        "files": [{"path": str(file.relative_to(ROOT)), "sha256": hashlib.sha256(file.read_bytes()).hexdigest()} for file in files],
        "archiveSha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "credentialsIncluded": False,
        "privateEvidenceIncluded": False,
        "allowlist": {"folders": list(PUBLIC_FOLDERS), "selected": list(SELECTED)},
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("Source ZIP verified", len(files), "files", args.output.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
