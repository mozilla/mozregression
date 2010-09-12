from setuptools import setup, find_packages

desc = """Regression range finder for Mozilla nightly builds"""
summ = """Interactive regression range finder for Mozilla nightly builds"""

PACKAGE_NAME = "mozregression"
PACKAGE_VERSION = "0.1"

setup(name=PACKAGE_NAME,
      version=PACKAGE_VERSION,
      description=desc,
      long_description=summ,
      author='Heather Arthur',
      author_email='fayearthur@gmail.com',
      url='http://github.com/harthur/mozregression',
      license='MPL',
      entry_points="""
          [console_scripts]
          mozregression = regression:cli
          moznightly = runnightly:cli
        """,
      platforms =['Any'],
      install_requires = ['httplib2 >= 0.6.0', 'mozrunner >= 2.5.0', 'BeautifulSoup >= 3.0.4'],
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'Operating System :: OS Independent'
                  ]
     )
