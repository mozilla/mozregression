import os
from setuptools import setup

desc = """Regression range finder for Mozilla nightly builds"""
long_desc = """Interactive regression range finder for Mozilla nightly builds.

For more information see the mozregression website: http://mozilla.github.io/mozregression/"""

setup(name="mozregression",
      version="0.23",
      description=desc,
      long_description=long_desc,
      author='Mozilla Automation and Tools Team',
      author_email='tools@lists.mozilla.org',
      url='http://github.com/mozilla/mozregression',
      license='MPL 1.1/GPL 2.0/LGPL 2.1',
      packages=['mozregression'],
      entry_points="""
          [console_scripts]
          mozregression = mozregression.regression:cli
          moznightly = mozregression.runnightly:cli
        """,
      platforms =['Any'],
      install_requires = ['httplib2 >= 0.6.0',
                          'mozcommitbuilder >= 0.4.10',
                          'mozfile >= 0.1',
                          'mozprofile >= 0.4',
                          'mozrunner >= 5.14',
                          'BeautifulSoup >= 3.0.4',
                          'mozinstall >= 1.4',
                          'mozinfo >= 0.4',
                          'mozversion >= 0.5',
                          'requests >= 2.1',
                          'futures >= 2.1.6',
                          ],
      tests_require=['mock'],
      test_suite='tests',
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'Operating System :: OS Independent'
                  ]
     )
