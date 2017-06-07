import sys
from setuptools import setup
from mozregression import __version__
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    """
    Run py.test with the "python setup.py test command"
    """
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ''

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.pytest_args += (' ' + self.distribution.test_suite)

    def run_tests(self):
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


if sys.version_info < (2, 7) or sys.version_info > (3, 0):
    sys.exit("mozregression currently require python >=2.7 and <3.")

DEPENDENCIES = [
    'mozfile==1.2',
    'mozprocess==0.24',
    'mozprofile==0.28',
    'mozrunner==6.13',
    'BeautifulSoup==3.2.1',
    'mozinstall==1.12',
    'mozinfo==0.10',
    'mozlog==3.3',
    'mozversion==1.4',
    # require requests <3 because taskcluster needs it.
    # else there is install errors, see
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1212170
    'requests>=2.4.3,<3',
    'redo==1.6',
    'mozdevice==0.50',
    'taskcluster==0.3.4',
    'colorama==0.3.7',
    'configobj==5.0.6',
]

desc = """Regression range finder for Mozilla nightly builds"""
long_desc = """Regression range finder for Mozilla nightly builds.
For more information see the mozregression website:
http://mozilla.github.io/mozregression/"""

setup(name="mozregression",
      version=__version__,
      description=desc,
      long_description=long_desc,
      author='Mozilla Automation and Tools Team',
      author_email='tools@lists.mozilla.org',
      url='http://github.com/mozilla/mozregression',
      license='MPL 1.1/GPL 2.0/LGPL 2.1',
      packages=['mozregression'],
      entry_points="""
          [console_scripts]
          mozregression = mozregression.main:main
        """,
      platforms=['Any'],
      install_requires=DEPENDENCIES,
      tests_require=['mock', 'pytest', 'pytest-mock'],
      test_suite='tests',
      cmdclass={'test': PyTest},
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Operating System :: OS Independent'
      ])
