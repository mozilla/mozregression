"""
Helper script to work with mozregression-gui.

See python build.py --help
"""

import argparse
import glob
import os
import pipes
import re
import shutil
import subprocess
import sys
import tarfile

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
UNWANTED_PYSIDE_LIBRARIES = [
    "Qt5?3DAnimation",
    "Qt5?3DCore",
    "Qt5?3DExtras",
    "Qt5?3DInput",
    "Qt5?3DLogic",
    "Qt5?3DRender",
    "Qt5?Charts",
    "Qt5?Concurrent",
    "Qt5?DataVisualization",
    "Qt5?Help",
    "Qt5?Location",
    "Qt5?Multimedia",
    "Qt5?MultimediaWidgets",
    "Qt5?OpenGL",
    "Qt5?Positioning",
    "Qt5?Quick",
    "Qt5?QuickWidgets",
    "Qt5?Scxml",
    "Qt5?Sensors",
    "Qt5?Sql",
    "Qt5?Svg",
    "Qt5?TextToSpeech",
    "Qt5?WebChannel",
    "Qt5?WebEngineCore",
    "Qt5?WebEngineWidgets",
    "Qt5?WebSockets",
    "Qt5?WebView",
    "Qt5?Xml",
    "Qt5?XmlPatterns",
]


def call(*args, **kwargs):
    print("Executing `%s`" % " ".join(pipes.quote(a) for a in args))
    subprocess.check_call(args, **kwargs)


def py_script(script_name):
    python_dir = os.path.dirname(sys.executable)
    if IS_WIN:
        return os.path.join(python_dir, "Scripts", script_name + ".exe")
    else:
        return os.path.join(python_dir, script_name)


def do_uic(options, force=False):
    for uifile in glob.glob("mozregui/ui/*.ui"):
        pyfile = os.path.splitext(uifile)[0] + ".py"
        if (
            force
            or not os.path.isfile(pyfile)
            or (os.path.getmtime(uifile) > os.path.getmtime(pyfile))
        ):
            print("uic'ing %s -> %s" % (uifile, pyfile))
            os.system("pyside2-uic {} > {}".format(uifile, pyfile))


def do_rcc(options, force=False):
    rccfile = "resources.qrc"
    pyfile = "resources_rc.py"
    if (
        force
        or not os.path.isfile(pyfile)
        or (os.path.getmtime(rccfile) > os.path.getmtime(pyfile))
    ):
        print("rcc'ing %s -> %s" % (rccfile, pyfile))
        call("pyside2-rcc", "-o", pyfile, rccfile)


def do_run(options):
    do_uic(options)
    do_rcc(options)
    call(sys.executable, "mozregression-gui.py")


def do_test(options):
    do_uic(options)
    do_rcc(options)
    print("Running tests...")
    import pytest

    sys.exit(pytest.main(["tests", "-v"]))


def do_bundle(options):
    do_uic(options, True)
    do_rcc(options, True)

    # clean previous runs
    for dirname in ("build", "dist"):
        if os.path.isdir(dirname):
            shutil.rmtree(dirname)

    # create a bundle for the application
    call("pyinstaller", "gui.spec")

    # remove any pyside2 files we don't need
    unwanted_re = "|".join(UNWANTED_PYSIDE_LIBRARIES)
    for root, dirs, filenames in os.walk("dist"):
        qt_filenames = [
            os.path.join(root, filename)
            for filename in filenames
            if re.search(unwanted_re, filename)
        ]
        for qt_filename in qt_filenames:
            print("unlinking {}".format(qt_filename))
            os.unlink(qt_filename)

    # create an installer
    if IS_WIN:
        if options.upx_path:
            call(
                options.upx_path, os.path.join("dist", "mozregression-gui", "mozregression-gui.exe")
            )
        makensis_path = os.path.join(options.nsis_path, "makensis.exe")
        call(makensis_path, "wininst.nsi", cwd="wininst")
    elif IS_MAC:
        os.chdir("dist")
        # create a mozregression-gui subdirectory and make the dmg bundle that
        os.mkdir("mozregression-gui")
        os.rename(
            "mozregression GUI.app", os.path.join("mozregression-gui", "mozregression GUI.app")
        )
        call(
            "hdiutil",
            "create",
            "mozregression-gui.dmg",
            "-srcfolder",
            "mozregression-gui",
            "-ov",
        )
    else:
        # seems like some qml stuff is also bundled on Linux
        shutil.rmtree(os.path.join("dist", "mozregression-gui", "PySide2", "qml"))
        with tarfile.open("mozregression-gui.tar.gz", "w:gz") as tar:
            tar.add(r"dist/mozregression-gui", arcname="mozregression-gui")


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    uic = subparsers.add_parser("uic", help="build uic files")
    uic.set_defaults(func=do_uic)

    rcc = subparsers.add_parser("rcc", help="build rcc files")
    rcc.set_defaults(func=do_rcc)

    run = subparsers.add_parser("run", help="run the application")
    run.set_defaults(func=do_run)

    test = subparsers.add_parser("test", help="run the unit tests")
    test.set_defaults(func=do_test)

    bundle = subparsers.add_parser("bundle", help="bundle the application (freeze)")
    if IS_WIN:
        bundle.add_argument(
            "--nsis-path",
            default="C:\\NSIS",
            help="your NSIS path on the" " system(default: %(default)r)",
        )
        bundle.add_argument("--upx-path", default=None, help="Path to upx executable")

    bundle.set_defaults(func=do_bundle)

    return parser.parse_args()


def main():
    # chdir in this folder
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    options = parse_args()
    try:
        options.func(options)
    except Exception as e:
        sys.exit("ERROR: %s" % e)


if __name__ == "__main__":
    main()
