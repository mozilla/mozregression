from setuptools import setup

# we pin these dependencies in the requirements files -- all of these
# should be python 3 compatible
DEPENDENCIES = [
    "glean_sdk>=31.1.3",
    "beautifulsoup4>=4.7.1",
    "colorama>=0.4.1",
    "configobj>=5.0.6",
    "mozdevice>=4.0.0,<5",
    "mozfile>=2.0.0",
    "mozinfo>=1.1.0",
    "mozinstall>=2.0.0",
    "mozlog>=4.0",
    "mozprocess>=1.2.0",
    "mozprofile>=2.2.0",
    "mozrunner>=8.0.2",
    "mozversion>=2.1.0",
    "redo>=2.0.2",
    "requests>=2.21.0",
    "taskcluster>=6.0.0",
]

desc = """Regression range finder for Mozilla nightly builds"""
long_desc = """Regression range finder for Mozilla nightly builds.
For more information see the mozregression website:
http://mozilla.github.io/mozregression/"""

setup(
    name="mozregression",
    use_scm_version=True,
    description=desc,
    long_description=long_desc,
    author="Mozilla Automation and Tools Team",
    author_email="tools@lists.mozilla.org",
    url="http://github.com/mozilla/mozregression",
    license="MPL 2.0",
    packages=["mozregression"],
    entry_points="""
          [console_scripts]
          mozregression = mozregression.main:main
        """,
    package_data={"mozregression": ["*.yaml"]},
    platforms=["Any"],
    python_requires=">=3.6",
    setup_requires=["setuptools_scm"],
    install_requires=DEPENDENCIES,
    classifiers=[
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3 :: Only",
    ],
)
