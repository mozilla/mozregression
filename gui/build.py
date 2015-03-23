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


def do_run():
    do_uic()
    env = dict(os.environ)
    env['PYTHONPATH'] = '.'
    call(sys.executable, 'mozregui/main.py', env=env)


def do_test():
    do_uic()
    call(py_script('flake8'), 'mozregui', 'build.py', 'tests')
    print('Running tests...')
    import nose
    nose.main(argv=['-s', 'tests'])


def do_bundle():
    do_uic(True)

    # clean previous runs
    for dirname in ('build', 'dist'):
        if os.path.isdir(dirname):
            shutil.rmtree(dirname)

    # run pyinstaller
    pyinstaller = py_script('pyinstaller')
    call(pyinstaller, '-F', '--paths=.', '--name=mozregression-gui',
         'mozregui/main.py')


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    uic = subparsers.add_parser('uic', help='build uic files')
    uic.set_defaults(func=do_uic)

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
