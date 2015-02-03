import os
import sys
from setuptools import setup
from mozregression import __version__

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
          'mozfile >= 0.1',
          'mozprofile >= 0.4',
          'mozrunner >= 6.5',
          'BeautifulSoup >= 3.0.4',
          'mozinstall >= 1.4',
          'mozinfo >= 0.4',
          'mozlog >= 2.7',
          'mozversion >= 1.1',
          'requests >= 2.5.0',
          'cachecontrol >= 0.10.2',
          # used in conjunction with cachecontrol
          'lockfile >= 0.10.2',
          'futures >= 2.1.6',
          'mozdevice >= 0.43'
      ],
      tests_require=['mock'],
      test_suite='tests',
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'Operating System :: OS Independent'
                   ]
      )
