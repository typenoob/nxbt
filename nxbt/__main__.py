# nuitka-project-if: {OS} in ("Windows"):
#   nuitka-project: --output-filename=nxbt.exe
# nuitka-project-else:
#   nuitka-project: --output-filename=nxbt

# nuitka-project: --mode=onefile
# nuitka-project: --file-version=0.1.0
# nuitka-project: --product-version=0.1.0
# nuitka-project: --output-dir=release
# nuitka-project: --no-deployment-flag=self-execution
# nuitka-project: --include-data-dir=./nxbt/web/static=nxbt/web/static
# nuitka-project: --include-data-dir=./nxbt/web/templates=nxbt/web/templates
# nuitka-project: --remove-output
# nuitka-project: --nofollow-import-to=grpc

import sys
import importlib

# Using Cython to speed up compile time
# nuitka-project: --nofollow-import-to=bumble.hci
sys.modules["bumble.hci"] = importlib.import_module("lib.bumble.hci")
# nuitka-project: --nofollow-import-to=bumble.l2cap
sys.modules["bumble.l2cap"] = importlib.import_module("lib.bumble.l2cap")


if __name__ == "__main__":
    from nxbt.cli import main

    main()
