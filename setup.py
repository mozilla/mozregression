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

desc = """Regression range finder for Mozilla nightly builds"""
long_desc = """Interactive regression range finder for Mozilla nightly builds.
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
          mozregression = mozregression.main:cli
        """,
      platforms=['Any'],
      install_requires=[
          'mozfile >= 1.2',
          'mozprofile >= 0.25',
          'mozrunner >= 6.8',
          'BeautifulSoup >= 3.0.4',
          'mozinstall >= 1.12',
          'mozinfo >= 0.8',
          'mozlog >= 3.0',
          'mozversion >= 1.3',
          'requests>=2.4.3',
          'redo',
          'cachecontrol[filecache] >= 0.11.5',
          'futures >= 2.1.6',
          'mozdevice >= 0.46',
          'taskcluster',
      ],
      tests_require=['mock', 'pytest'],
      test_suite='tests',
      cmdclass={'test': PyTest},
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'Operating System :: OS Independent'
                   ]
      )
