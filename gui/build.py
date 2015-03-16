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

VENV_PATH = 'venv'
IS_WIN = os.name == 'nt'


def call(*args, **kwargs):
    print 'Executing `%s`' % ' '.join(pipes.quote(a) for a in args)
    subprocess.check_call(args, **kwargs)


def py_script(script_name):
    if IS_WIN:
        return os.path.join(VENV_PATH, 'Scripts',
                            script_name + '.exe')
    else:
        return os.path.join(VENV_PATH, 'bin', script_name)


def do_uic(force=False):
    try:
        from pysideuic import compileUi
    except ImportError:
        sys.exit("please execute this from the virtualenv.")
    for uifile in glob.glob('mozregui/ui/*.ui'):
        pyfile = os.path.splitext(uifile)[0] + '.py'
        if force or not os.path.isfile(pyfile) or \
                (os.path.getmtime(uifile) > os.path.getmtime(pyfile)):
            print "uic'ing %s -> %s" % (uifile, pyfile)
            with open(pyfile, 'w') as f:
                compileUi(uifile, f, False, 4, False)


def do_venv(python=sys.executable):
    if not os.path.exists(VENV_PATH):
        call('virtualenv', '-p', python, VENV_PATH)
    # install things
    pip = py_script('pip')
    call(pip, 'install', '-r', 'test-requirements.txt')


def do_run():
    do_uic()
    env = dict(os.environ)
    env['PYTHONPATH'] = '.'
    call(sys.executable, 'mozregui/main.py', env=env)


def do_test():
    do_uic()
    call('flake8', 'mozregui', 'build.py', 'tests')
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

    venv = subparsers.add_parser('venv', help='create a virtualenv')
    venv.set_defaults(func=do_venv)

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
