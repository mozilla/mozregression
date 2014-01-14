import os
from setuptools import setup

desc = """Regression range finder for Mozilla nightly builds"""
long_desc = """"Interactive regression range finder for Mozilla nightly builds.

For more information see the mozregression _website http://mozilla.github.io/mozregression/"""

setup(name="mozregression",
      version="0.12",
      description=desc,
      long_description=long_desc,
      author='Mozilla Automation and Tools Team',
      author_email='tools@lists.mozilla.org',
      url='http://github.com/mozilla/mozregression',
      license='MPL 1.1/GPL 2.0/LGPL 2.1',
      packages=['mozregression'],
      entry_points="""
          [console_scripts]
          mozregression = mozregression:regressioncli
          moznightly = mozregression:nightlycli
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
                          'requests >= 2.1',
                          ],
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'Operating System :: OS Independent'
                  ]
     )
