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
import tarfile


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


def do_uic(options, force=False):
    from PyQt4.uic import compileUi
    for uifile in glob.glob('mozregui/ui/*.ui'):
        pyfile = os.path.splitext(uifile)[0] + '.py'
        if force or not os.path.isfile(pyfile) or \
                (os.path.getmtime(uifile) > os.path.getmtime(pyfile)):
            print "uic'ing %s -> %s" % (uifile, pyfile)
            with open(pyfile, 'w') as f:
                compileUi(uifile, f, False, 4, False)


def do_rcc(options, force=False):
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


def do_run(options):
    do_uic(options)
    do_rcc(options)
    env = dict(os.environ)
    env['PYTHONPATH'] = '.'
    call(sys.executable, 'mozregui/main.py', env=env)


def do_test(options):
    do_uic(options)
    do_rcc(options)
    call(py_script('flake8'), 'mozregui', 'build.py', 'tests')
    print('Running tests...')
    import nose
    nose.main(argv=['nosetests', '-s', 'tests'])


def do_bundle(options):
    do_uic(options, True)
    do_rcc(options, True)

    # clean previous runs
    for dirname in ('build', 'dist'):
        if os.path.isdir(dirname):
            shutil.rmtree(dirname)
    # create a installer
    if IS_WIN:
        makensis_path = os.path.join(options.nsis_path, "makensis.exe")
        call_cx_freeze(options.python_lib_path)
        call(makensis_path, 'wininst.nsi', cwd='wininst')
    else:
        call_cx_freeze(options.python_lib_path)
        with tarfile.open('mozregression-gui.tar.gz', 'w:gz') as tar:
            tar.add(r'dist/')


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
    if IS_WIN:
        default_python_path = 'C:\\Python27\\Lib'
        bundle.add_argument('--nsis-path', default='C:\\NSIS',
                            help='your NSIS path on the'
                            ' system(default: %(default)r)')
    else:
        default_python_path = '/usr/lib/python2.7'

    bundle.add_argument('--python-lib-path', default=default_python_path,
                        help='your python library path on the'
                        ' system(default: %(default)r)')
    bundle.set_defaults(func=do_bundle)

    return parser.parse_args()


def call_cx_freeze(python_lib_path):
    args = []
    if IS_WIN:
        python_dir = os.path.join(
            os.path.dirname(sys.executable),
            "Scripts"
        )
        args.append(sys.executable)
        args.append(os.path.join(python_dir, 'cxfreeze'))
        args.append('--icon=wininst/app_icon.ico')
        args.append('--base-name=Win32GUI')
        args.append('--include-path=".;..;{path}\site-packages;{path}"'.format(
            path=python_lib_path))
        args.append('--target-name=mozregression-gui.exe')
    else:
        args.append(py_script('cxfreeze'))
        args.append('--include-path=".:..:{path}:{path}/dist-packages"'.format(
            path=python_lib_path))
        args.append('--target-name=mozregression-gui')
    args.append('--target-dir=dist')
    args.append('mozregui/main.py')
    call(*args)


def main():
    # chdir in this folder
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    options = parse_args()
    try:
        options.func(options)
    except Exception, e:
        sys.exit('ERROR: %s' % e)


if __name__ == '__main__':
    main()
