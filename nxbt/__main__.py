# nuitka-project-if: {OS} in ("Windows"):
#   nuitka-project: --output-filename=nxbt.exe
# nuitka-project-else:
#   nuitka-project: --output-filename=nxbt

# nuitka-project: --mode=onefile
# nuitka-project: --file-version=0.1.0
# nuitka-project: --product-version=0.1.0
# nuitka-project: --output-dir=release
# nuitka-project: --include-data-dir=./nxbt/web/static=nxbt/web/static
# nuitka-project: --include-data-dir=./nxbt/web/templates=nxbt/web/templates
# nuitka-project: --include-data-dir=./nxbt/controller/sdp=nxbt/controller/sdp
# nuitka-project: --remove-output


from nxbt.cli import main

main()
