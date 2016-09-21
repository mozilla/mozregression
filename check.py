#!/usr/bin/env python
"""
Run flake8 checks and tests.
"""

import os
import argparse
import pipes
import shutil
import tempfile

from subprocess import check_call


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('-G', '--with-gui', action='store_true',
                        help="Also check the GUI component")
    parser.add_argument('-C', '--with-coverage', action='store_true',
                        help="Generate coverage data from the tests run")
    parser.add_argument('-H', '--cover-html', action='store_true',
                        help='generate html files to see test coverage')
    return parser.parse_args()


def run(cmd, **kwargs):
    msg = 'Running: |%s|' % ' '.join(pipes.quote(c) for c in cmd)
    if kwargs.get('cwd'):
        msg += ' in %s' % kwargs['cwd']
    print(msg)
    check_call(cmd, **kwargs)


def rm(path):
    if os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


if __name__ == '__main__':
    options = parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    run(['flake8', '--max-line-length=100', 'mozregression', 'tests', 'setup.py', __file__])

    if options.with_coverage:
        rm('.coverage')
        if options.with_gui:
            rm(os.path.join('gui', '.coverage'))
        test_run_cmd = ['coverage', 'run']
    else:
        test_run_cmd = ['python']

    tmpdir = tempfile.gettempdir()
    tmpfiles = set(os.listdir(tmpdir))
    run(test_run_cmd + ['setup.py', 'test'])
    if options.with_gui:
        run(test_run_cmd + ['build.py', 'test'], cwd='gui')

    remaining_tmpfiles = tmpfiles - set(os.listdir(tmpdir))
    assert not remaining_tmpfiles, "tests leaked some temp files: %s" % (
        ", ".join("`%s`" % os.path.join(tmpdir, f) for f in remaining_tmpfiles)
    )

    if options.with_coverage:
        if options.with_gui:
            shutil.move('.coverage', '.coverage.core')
            shutil.move(os.path.join('gui', '.coverage'), '.coverage.gui')
            run(['coverage', 'combine'])
        if options.cover_html:
            rm('htmlcov')
            run(['coverage', 'html'])
            print("See coverage: |firefox %s|"
                  % os.path.join(here, 'htmlcov', 'index.html'))
