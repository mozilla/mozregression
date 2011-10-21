from setuptools import setup, find_packages

desc = """Regression range finder for Mozilla nightly builds"""
summ = """Interactive regression range finder for Mozilla nightly builds"""

setup(name="mozregression",
      version="0.5.4",
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
      install_requires = ['httplib2 == 0.6.0', 'mozrunner == 2.5.1', 'BeautifulSoup >= 3.0.4', 'mozcommitbuilder >= 0.3.9'],
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'Operating System :: OS Independent'
                  ]
     )
