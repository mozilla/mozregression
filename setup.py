import os
from setuptools import setup, find_packages

desc = """Regression range finder for Mozilla nightly builds"""

# take description from README
here = os.path.dirname(os.path.abspath(__file__))
try:
    summ = file(os.path.join(here, 'README.md')).read()
except:
    summ = """Interactive regression range finder for Mozilla nightly builds"""

setup(name="mozregression",
      version="0.6.2",
      description=desc,
      long_description=summ,
      author='Heather Arthur',
      author_email='fayearthur@gmail.com',
      url='http://github.com/harthur/mozregression',
      license='MPL 1.1/GPL 2.0/LGPL 2.1',
      packages=find_packages(exclude=['legacy']),
      entry_points="""
          [console_scripts]
          mozregression = mozregression:regressioncli
          moznightly = mozregression:nightlycli
        """,
      platforms =['Any'],
      install_requires = ['httplib2 >= 0.6.0', 'mozrunner >= 2.5.4', 'BeautifulSoup >= 3.0.4', 'mozcommitbuilder >= 0.4.9'],
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'Operating System :: OS Independent'
                  ]
     )
