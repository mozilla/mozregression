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
IS_MAC = sys.platform == 'darwin'


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
    # update PYTHONPATH so python can find mozregui package
    if env.get('PYTHONPATH'):
        env['PYTHONPATH'] = '.' + os.pathsep + env['PYTHONPATH']
    else:
        env['PYTHONPATH'] = '.'
    call(sys.executable, 'mozregui/main.py', env=env)


def do_test(options):
    do_uic(options)
    do_rcc(options)
    call(py_script('flake8'), 'mozregui', 'build.py', 'tests')
    print('Running tests...')
    import pytest
    sys.exit(pytest.main(['tests', '-v']))


def call_cx_freeze():
    args = []
    venv_path = os.path.dirname(sys.executable)
    if IS_WIN:
        # cxfreeze on windows is just a 'cxfreeze' python file in the
        # Scripts dir
        args.append(sys.executable)
        args.append(os.path.join(venv_path, "Scripts", 'cxfreeze'))

        args.append('--icon=wininst/app_icon.ico')
        args.append('--base-name=Win32GUI')
        args.append('--target-name=mozregression-gui.exe')
    else:
        args.append('cxfreeze')
        args.append('--target-name=mozregression-gui')

    # determine python paths needed for cxfreeze
    paths = []
    for p in sys.path:
        # put the system python path in first, because somwhere there
        # is a dependency to distutils - and distutils get patched
        # in the virtualenv
        if p.startswith(venv_path):
            paths.append(p)
        else:
            paths.insert(0, p)
    args.append('--include-path=%s' % os.pathsep.join(['.', '..'] + paths))

    # find taskcluster apis.json file
    import taskcluster.client
    apis_json = os.path.join(os.path.dirname(taskcluster.client.__file__),
                             'apis.json')
    args.append("--zip-include=%s=taskcluster/apis.json" % apis_json)

    args.append('--target-dir=dist')
    args.append('mozregui/main.py')
    call(*args)

    # copy the required cacert.pem file for requests library
    import requests.certs
    shutil.copy(requests.certs.where(), "dist/cacert.pem")


def do_bundle(options):
    do_uic(options, True)
    do_rcc(options, True)

    # clean previous runs
    for dirname in ('build', 'dist'):
        if os.path.isdir(dirname):
            shutil.rmtree(dirname)
    # freeze the application
    call_cx_freeze()
    # create an installer
    if IS_WIN:
        makensis_path = os.path.join(options.nsis_path, "makensis.exe")
        call(makensis_path, 'wininst.nsi', cwd='wininst')
    elif IS_MAC:
        call('hdiutil', 'create', 'dist/mozregression-gui.dmg',
             '-srcfolder', 'dist/', '-ov')
    else:
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
        bundle.add_argument('--nsis-path', default='C:\\NSIS',
                            help='your NSIS path on the'
                            ' system(default: %(default)r)')

    bundle.set_defaults(func=do_bundle)

    return parser.parse_args()


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
