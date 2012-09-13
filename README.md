#mozregression
[mozregression](http://mozilla.github.com/mozregression) is an interactive regression range finder for Mozilla nightly builds.

#install
you can install mozregression with [setuptools](http://pypi.python.org/pypi/setuptools) or [pip](http://pypi.python.org/pypi/pip). [OS-specific instructions](http://mozilla.github.com/mozregression/)

	easy_install mozregression

#usage
To find the regression range for a bug, supply mozregression with the date of the last known good nightly and the date of a bad nightly (optional):

	mozregression --good=2010-03-16 --bad=2010-09-08

This will download and run several nightly builds on new profiles and narrow down the range. After checking a few nightlies, you'll get the regression range which looks something like this:

	Last good nightly: 2010-09-08 First bad nightly: 2010-09-09

	Pushlog: http://hg.mozilla.org/mozilla-central/pushloghtml?fromchange=36f5cf6b2d42&tochange=8e0fce7d5b49
	
#other options
Just run the nightly for a particular date:

	moznightly --date=2010-10-23

Find regression range on Thunderbird nightlies:

	mozregression --app=thunderbird

Find regression range on Firefox mobile nightlies:

	mozregression --app=fennec

Other branches/repos:

	mozregression --repo=mozilla-1.9.2

Other options exist for running the nightlies with a particular
profile, addons, and browser arguments.

#dependencies

mozregression uses mozcommitbuilder:

https://github.com/mozilla/mozcommitbuilder
