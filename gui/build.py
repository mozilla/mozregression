"""
Helper script to work with mozregression-gui.

See python build.py --help
"""

import argparse
import sys
import subprocess
import os
import shutil
import glob
import pipes

IS_WIN = os.name == 'nt'


def call(*args, **kwargs):
    print 'Executing `%s`' % ' '.join(pipes.quote(a) for a in args)
    subprocess.check_call(args, **kwargs)


def py_script(script_name):
    python_dir = os.path.dirname(sys.executable)
    if IS_WIN:
        return os.path.join(python_dir, 'Scripts',
                            script_name + '.exe')
    else:
        return os.path.join(python_dir, script_name)


def do_uic(force=False):
    from PyQt4.uic import compileUi
    for uifile in glob.glob('mozregui/ui/*.ui'):
        pyfile = os.path.splitext(uifile)[0] + '.py'
        if force or not os.path.isfile(pyfile) or \
                (os.path.getmtime(uifile) > os.path.getmtime(pyfile)):
            print "uic'ing %s -> %s" % (uifile, pyfile)
            with open(pyfile, 'w') as f:
                compileUi(uifile, f, False, 4, False)


def do_rcc(force=False):
    rccfile = 'resources.qrc'
    pyfile = 'resources_rc.py'
    pyrcc4 = 'pyrcc4'
    if IS_WIN:
        import PyQt4
        lib_path = os.path.dirname(os.path.realpath(PyQt4.__file__))
        pyrcc4 = os.path.join(lib_path, pyrcc4)
    if force or not os.path.isfile(pyfile) or \
            (os.path.getmtime(rccfile) > os.path.getmtime(pyfile)):
        print "rcc'ing %s -> %s" % (rccfile, pyfile)
        call(pyrcc4, '-o', pyfile, rccfile)


def do_run():
    do_uic()
    do_rcc()
    env = dict(os.environ)
    env['PYTHONPATH'] = '.'
    call(sys.executable, 'mozregui/main.py', env=env)


def do_test():
    do_uic()
    do_rcc()
    call(py_script('flake8'), 'mozregui', 'build.py', 'tests')
    print('Running tests...')
    import nose
    nose.main(argv=['-s', 'tests'])


def do_bundle():
    do_uic(True)
    do_rcc(True)

    # clean previous runs
    for dirname in ('build', 'dist'):
        if os.path.isdir(dirname):
            shutil.rmtree(dirname)
    # create a intaller
    python_lib_path = os.path.join(
        os.getenv('MOZREGUI_PYTHONPATH', "C:\\Python27"),
        "Lib"
    )
    makensis_path = os.path.join(
        os.getenv('MOZREGUI_NSISPATH', "C:\\NSIS"),
        "makensis.exe"
    )
    gui_path = os.path.realpath('.')
    moz_path = os.path.realpath('..')
    python_dir = os.path.join(
        os.path.dirname(sys.executable),
        "Scripts"
    )
    args = []
    args.append('--icon=wininst/app_icon.ico')
    args.append('--base-name=Win32GUI')
    args.append('--include-path=%s;%s;%s\site-packages;%s'
                % (gui_path, moz_path, python_lib_path, python_lib_path))
    args.append('--target-name=mozregression-gui.exe')
    args.append('--target-dir=dist')
    args.append('mozregui/main.py')
    call(sys.executable, os.path.join(python_dir, 'cxfreeze'), *args)
    call(makensis_path, 'wininst.nsi', cwd='wininst')


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    uic = subparsers.add_parser('uic', help='build uic files')
    uic.set_defaults(func=do_uic)

    rcc = subparsers.add_parser('rcc', help='build rcc files')
    rcc.set_defaults(func=do_rcc)

    run = subparsers.add_parser('run', help='run the application')
    run.set_defaults(func=do_run)

    test = subparsers.add_parser('test', help='run the unit tests')
    test.set_defaults(func=do_test)

    bundle = subparsers.add_parser('bundle',
                                   help='bundle the application (freeze)')
    bundle.set_defaults(func=do_bundle)

    return parser.parse_args()


def main():
    # chdir in this folder
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    options = parse_args()
    try:
        options.func()
    except Exception, e:
        sys.exit('ERROR: %s' % e)


if __name__ == '__main__':
    main()
