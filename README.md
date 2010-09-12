#mozregression
[mozregression](http://harthur.github.com/mozregression) is an interactive regression range finder for Mozilla nightly builds.

#install
you can install mozregression with [setuptools](http://pypi.python.org/pypi/setuptools) or [pip](http://pypi.python.org/pypi/pip)

	easy_install mozregression

#usage
To find the regression range for a bug, supply mozregression with the date of the last known good nightly and the date of a bad nightly (optional):
	mozregression --good=2010-03-16 --bad=2010-09-08
	
This will download and run several nightly builds and narrow down the range. After checking a few nightlies, you'll get the regression range which looks something like this:
	Last good nightly: 2010-09-08 First bad nightly: 2010-09-09

	Pushlog: http://hg.mozilla.org/mozilla-central/pushloghtml?fromchange=36f5cf6b2d42&tochange=8e0fce7d5b49