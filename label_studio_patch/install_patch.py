"""Install (or remove) the Retrieve Predictions progress bar in an existing Label Studio 1.23.2.

What it changes in the Label Studio package of the active Python environment:
  * label_studio/data_manager/actions/basic.py   server side: batches and counts
  * web/dist/apps/labelstudio/                    the built web page (Data Manager)

The original files are kept next to them as basic.py.orig and labelstudio.orig, so
--undo puts stock Label Studio back exactly. Stop Label Studio before running this and
start it again afterwards.

Examples (PowerShell, with the same .venv active that runs `label-studio start`):
    python label_studio_patch/install_patch.py          # install
    python label_studio_patch/install_patch.py --undo   # back to stock Label Studio
"""
import argparse
import importlib.metadata
import importlib.util
import shutil
import sys
import zipfile
from pathlib import Path

SUPPORTED_VERSION = "1.23.2"
HERE = Path(__file__).resolve().parent
NEW_BASIC = HERE / "basic.py"
NEW_FRONTEND_ZIP = HERE / "labelstudio_frontend.zip"


def find_install():
    """Locate the installed Label Studio package without starting it.

    Returns:
        (basic.py path, web/dist/apps/labelstudio folder path)

    Raises:
        SystemExit: If Label Studio isn't installed, is the wrong version, or the
            expected files are missing.
    """
    spec = importlib.util.find_spec("label_studio")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("Label Studio isn't installed in this Python environment. "
                         "Activate the .venv you run `label-studio start` from, then rerun.")

    version = importlib.metadata.version("label-studio")
    if version != SUPPORTED_VERSION:
        raise SystemExit(f"This patch is built for Label Studio {SUPPORTED_VERSION}, but {version} is "
                         f"installed. Run: python -m pip install label-studio=={SUPPORTED_VERSION}")

    package = Path(list(spec.submodule_search_locations)[0])
    basic = package / "data_manager" / "actions" / "basic.py"
    frontend = package.parent / "web" / "dist" / "apps" / "labelstudio"
    for path in (basic, frontend):
        if not path.exists():
            raise SystemExit(f"Expected Label Studio file not found: {path}")
    return basic, frontend


def install(basic, frontend):
    """Back up the stock files (first time only) and copy in the patched ones."""
    basic_orig = basic.with_name("basic.py.orig")
    frontend_orig = frontend.with_name("labelstudio.orig")

    # Back up only once, so reinstalling never overwrites the stock copy with a patched one
    if not basic_orig.exists():
        shutil.copy2(basic, basic_orig)
    if not frontend_orig.exists():
        shutil.copytree(frontend, frontend_orig)

    shutil.copy2(NEW_BASIC, basic)

    # Replace the web page build with the patched one
    shutil.rmtree(frontend)
    with zipfile.ZipFile(NEW_FRONTEND_ZIP) as z:
        z.extractall(frontend.parent)  # the zip contains the labelstudio/ folder

    print("Installed the Retrieve Predictions progress bar.")


def undo(basic, frontend):
    """Restore the stock files saved by install()."""
    basic_orig = basic.with_name("basic.py.orig")
    frontend_orig = frontend.with_name("labelstudio.orig")
    if not basic_orig.exists() or not frontend_orig.exists():
        raise SystemExit("No backup found, so the patch isn't installed (or was installed by hand). "
                         f"To get stock Label Studio, run: python -m pip install --force-reinstall "
                         f"--no-deps label-studio=={SUPPORTED_VERSION}")

    shutil.copy2(basic_orig, basic)
    basic_orig.unlink()
    shutil.rmtree(frontend)
    frontend_orig.rename(frontend)
    print("Removed the patch; Label Studio is back to stock.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--undo", action="store_true", help="Restore stock Label Studio")
    args = p.parse_args()

    basic, frontend = find_install()
    print(f"Label Studio {SUPPORTED_VERSION} found in {basic.parents[3]}")
    if args.undo:
        undo(basic, frontend)
    else:
        install(basic, frontend)
    print("Restart Label Studio (Ctrl+C in its window, then `label-studio start`), "
          "then refresh the browser page with Ctrl+F5.")


if __name__ == "__main__":
    sys.exit(main())
