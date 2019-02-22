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


if sys.version_info < (2, 7) or sys.version_info >= (3, 0):
    sys.exit("mozregression currently require python >=2.7 and <3.")

DEPENDENCIES = [
    'mozfile==2.0.0',
    'mozprocess==0.26',
    'mozprofile==2.1.0',
    'mozrunner==7.2.0',
    'BeautifulSoup==3.2.1',
    'mozinstall==1.16.0',
    'mozinfo==1.1.0',
    'mozlog==3.9',
    'mozversion==1.5',
    'requests[security]==2.20.0',
    'redo==1.6',
    'mozdevice==3.0.1',
    'taskcluster==6.0.0',
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
