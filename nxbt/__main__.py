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
# nuitka-project: --nofollow-import-to=bumble.hci
# nuitka-project: --nofollow-import-to=cython
# nuitka-project: --nofollow-import-to=setuptools


from nxbt.cli import main
import sys
from lib.bumble import hci

sys.modules["bumble.hci"] = hci

if __name__ == "__main__":
    main()
