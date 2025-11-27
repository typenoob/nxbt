# nuitka-project-if: {OS} in ("Windows"):
#   nuitka-project: --output-filename=nxbt.exe
# nuitka-project-else:
#   nuitka-project: --output-filename=nxbt

# nuitka-project: --mode=onefile
# nuitka-project: --file-version=0.1.0
# nuitka-project: --product-version=0.1.0
# nuitka-project: --output-dir=release
# nuitka-project: --include-data-dir=./nxbt/web/static=static
# nuitka-project: --include-data-dir=./nxbt/web/templates=templates
# nuitka-project: --include-onefile-external-data=static
# nuitka-project: --include-onefile-external-data=templates
# nuitka-project: --remove-output


from nxbt.cli import main

main()
