"""Install (or remove) the Retrieve Predictions progress bar in an existing Label Studio 1.23.2.

Background: how Label Studio is updated without rebuilding it on your PC
------------------------------------------------------------------------
Label Studio installed with pip has two parts:

  1. Python server code, e.g. site-packages/label_studio/data_manager/actions/basic.py.
     Python reads these files each time `label-studio start` runs, so replacing one
     changes the server's behaviour.
  2. The web page, already compiled by HumanSignal into JavaScript bundles in
     site-packages/web/dist/apps/labelstudio/. The server only hands these files to the
     browser; it never rebuilds them. To change the page, the patched source was compiled
     once (Node.js, `yarn ls:build`) and the resulting folder is shipped here as
     labelstudio_frontend.zip.

The patch therefore only needs to swap two things in the installed package:
  * label_studio/data_manager/actions/basic.py   server side: task-ID lookup and counts
  * web/dist/apps/labelstudio/                    the compiled web page with the dialog

The source changes behind those two files are in retrieve-predictions-progress.patch
(see README.md in this folder for how the progress bar works).

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

# The patched files were made from this exact release; another version's basic.py or
# compiled page would differ, so installing them there could break Label Studio
SUPPORTED_VERSION = "1.23.2"

# The patched files ship next to this script
HERE = Path(__file__).resolve().parent
NEW_BASIC = HERE / "basic.py"
NEW_FRONTEND_ZIP = HERE / "labelstudio_frontend.zip"


def find_install():
    """Locate the installed Label Studio package without starting it.

    Uses the Python environment this script runs in, so it must be the same .venv that
    runs `label-studio start`.

    Returns:
        (basic.py path, web/dist/apps/labelstudio folder path)

    Raises:
        SystemExit: If Label Studio isn't installed, is the wrong version, or the
            expected files are missing.
    """
    # find_spec only looks up where the package lives; importing label_studio would
    # start loading Django, which is slow and needs settings
    spec = importlib.util.find_spec("label_studio")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("Label Studio isn't installed in this Python environment. "
                         "Activate the .venv you run `label-studio start` from, then rerun.")

    # Version as recorded by pip (same as `pip show label-studio`)
    version = importlib.metadata.version("label-studio")
    if version != SUPPORTED_VERSION:
        raise SystemExit(f"This patch is built for Label Studio {SUPPORTED_VERSION}, but {version} is "
                         f"installed. Run: python -m pip install label-studio=={SUPPORTED_VERSION}")

    # site-packages/label_studio/... (server code) and site-packages/web/dist/... (web page)
    package = Path(list(spec.submodule_search_locations)[0])
    basic = package / "data_manager" / "actions" / "basic.py"
    frontend = package.parent / "web" / "dist" / "apps" / "labelstudio"
    for path in (basic, frontend):
        if not path.exists():
            raise SystemExit(f"Expected Label Studio file not found: {path}")
    return basic, frontend


def install(basic, frontend):
    """Back up the stock files (first time only) and copy in the patched ones.

    Args:
        basic: Installed basic.py to replace.
        frontend: Installed web/dist/apps/labelstudio folder to replace.
    """
    basic_orig = basic.with_name("basic.py.orig")
    frontend_orig = frontend.with_name("labelstudio.orig")

    # Back up only once, so reinstalling never overwrites the stock copy with a patched one
    if not basic_orig.exists():
        shutil.copy2(basic, basic_orig)
    if not frontend_orig.exists():
        shutil.copytree(frontend, frontend_orig)

    # Server side: the patched actions file (hidden selected_task_ids action + counts)
    shutil.copy2(NEW_BASIC, basic)

    # Web page: delete the stock compiled page and unzip the patched build in its place.
    # The whole folder is replaced, not single files, because the build's file names
    # (142.js, 358.js, ...) and the references between them change with every build.
    shutil.rmtree(frontend)
    with zipfile.ZipFile(NEW_FRONTEND_ZIP) as z:
        z.extractall(frontend.parent)  # the zip contains the labelstudio/ folder

    print("Installed the Retrieve Predictions progress bar.")


def undo(basic, frontend):
    """Restore the stock files saved by install().

    Args:
        basic: Installed (patched) basic.py.
        frontend: Installed (patched) web/dist/apps/labelstudio folder.

    Raises:
        SystemExit: If there are no backups, i.e. the patch was never installed here.
    """
    basic_orig = basic.with_name("basic.py.orig")
    frontend_orig = frontend.with_name("labelstudio.orig")
    if not basic_orig.exists() or not frontend_orig.exists():
        raise SystemExit("No backup found, so the patch isn't installed (or was installed by hand). "
                         f"To get stock Label Studio, run: python -m pip install --force-reinstall "
                         f"--no-deps label-studio=={SUPPORTED_VERSION}")

    # Put the stock files back and remove the backups, leaving no trace of the patch
    shutil.copy2(basic_orig, basic)
    basic_orig.unlink()
    shutil.rmtree(frontend)
    frontend_orig.rename(frontend)
    print("Removed the patch; Label Studio is back to stock.")


def main():
    """Read the command line, find Label Studio, then install or undo the patch."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--undo", action="store_true", help="Restore stock Label Studio")
    args = p.parse_args()

    basic, frontend = find_install()
    # basic.parents[3] is site-packages: basic.py -> actions -> data_manager -> label_studio -> site-packages
    print(f"Label Studio {SUPPORTED_VERSION} found in {basic.parents[3]}")
    if args.undo:
        undo(basic, frontend)
    else:
        install(basic, frontend)

    # The running server keeps the old code in memory, and the browser caches the old
    # page, so both need a restart/refresh to pick up the change
    print("Restart Label Studio (Ctrl+C in its window, then `label-studio start`), "
          "then refresh the browser page with Ctrl+F5.")


if __name__ == "__main__":
    sys.exit(main())
