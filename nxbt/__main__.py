# nuitka-project-if: {OS} in ("Windows"):
#   nuitka-project: --output-filename=nxbt.exe
# nuitka-project-else:
#   nuitka-project: --output-filename=nxbt

# nuitka-project-if: {Flavor} in ("MSYS2 MinGW"):
#   nuitka-project-set: MINGW_PREFIX= __import__("os").environ["MINGW_PREFIX"]
#   nuitka-project: --experimental=force-mingw64,force-accept-windows-gcc
#   nuitka-project: --experimental=force-dependencies-pefile
#   nuitka-project: --include-data-files={MINGW_PREFIX}/bin/libusb-1.0.dll=./
# nuitka-project-else:
#   nuitka-project: --remove-output

# nuitka-project: --mode=onefile
# nuitka-project: --file-version=0.1.0
# nuitka-project: --product-version=0.1.0
# nuitka-project: --output-dir=release
# nuitka-project: --no-deployment-flag=self-execution
# nuitka-project: --include-data-dir=./nxbt/web/static=nxbt/web/static
# nuitka-project: --include-data-dir=./nxbt/web/templates=nxbt/web/templates
# nuitka-project: --nofollow-import-to=grpc
# nuitka-project: --include-windows-runtime-dlls=no
# nuitka-project: --onefile-tempdir-spec={CACHE_DIR}/nxbt


if "__compiled__" in globals():
    import sys
    import importlib
    import os
    from multiprocessing import set_start_method, get_start_method

    # github.com/Nuitka/Nuitka/issues/3947
    if get_start_method() == "forkserver":
        set_start_method("fork", force=True)

    # MSYS2 cryptography workaround
    os.environ["CRYPTOGRAPHY_OPENSSL_NO_LEGACY"] = "1"

    # Using Cython to speed up compile time
    # nuitka-project: --nofollow-import-to=bumble.hci
    sys.modules["bumble.hci"] = importlib.import_module("vendor.bumble.hci")
    # nuitka-project: --nofollow-import-to=bumble.l2cap
    sys.modules["bumble.l2cap"] = importlib.import_module("vendor.bumble.l2cap")

if __name__ == "__main__":
    from nxbt.cli import main

    main()
