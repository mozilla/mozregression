import copy
import datetime
import json
import re

from mozregression.build_data import NightlyUrlBuilder
from mozregression.utils import url_links, get_http_session, get_build_regex


# modified fetch_configs #

class CommonConfig(object):
    """
    Define the configuration for both nightly and inbound fetching.

    :attr name: the name of the application
    """
    def __init__(self, app_name):
        self.app_name = app_name

    def build_regex(self, os, bits):
        """
        Returns a string regex that can match a build file on the servers.
        """
        if self.app_name == 'fennec':
            return r".*android-arm\.apk$"
        return get_build_regex(self.app_name, os, bits) + '$'

    def build_info_regex(self, os, bits):
        """
        Returns a string regex that can match a build info file (txt)
        on the servers.
        """
        if self.app_name == 'fennec':
            return r".*android-arm\.txt"
        return get_build_regex(self.app_name, os, bits,
                               with_ext=False) + r'\.txt$'

    def is_nightly(self):
        """
        Returns True if the configuration can be used for nightly fetching.
        """
        return isinstance(self, NightlyConfigMixin)

    def is_inbound(self):
        """
        Returns True if the configuration can be used for inbound fetching.
        """
        return isinstance(self, InboundConfigMixin)


class NightlyConfigMixin(object):
    """
    Define the nightly-related required configuration to find nightly builds.

    A nightly build url is divided in 2 parts here:

    1. the base part as returned by :meth:`get_nighly_base_url`
    2. the final part, which can be found using :meth:`get_nighly_repo_regex`

    The final part contains a repo name, which is returned by
    :meth:`get_nightly_repo`.

    Note that subclasses must implement :meth:`_get_nightly_repo` to
    provide a default value.
    """
    nightly_base_repo_name = "firefox"
    nightly_repo = None

    def get_nighly_base_url(self, date):
        """
        Returns the base part of the nightly build url for a given date.
        """
        return ("http://ftp.mozilla.org/pub/mozilla.org/%s/nightly/%04d/%02d/"
                % (self.nightly_base_repo_name, date.year, date.month))

    def set_nightly_repo(self, repo):
        """
        Allow to define the repo name.

        If None, :meth:`_get_nightly_repo` will be called to return a value
        when :meth:`get_nightly_repo` is called.
        """
        self.nightly_repo = repo

    def get_nightly_repo(self, date):
        """
        Returns the repo name for a given date.
        """
        return self.nightly_repo or self._get_nightly_repo(date)

    def _get_nightly_repo(self, date):
        """
        Returns a default repo name for a given date.
        """
        raise NotImplementedError

    def get_nightly_repo_regex(self, date):
        """
        Returns a string regex that can match the last folder name for a given
        date.
        """
        repo = self.get_nightly_repo(date)
        return (r'^%04d-%02d-%02d-[\d-]+%s/$'
                % (date.year, date.month, date.day, repo))

    def can_go_inbound(self):
        """
        Indicate if we can bissect inbound from this nightly config.
        """
        # we can go on inbound if no nightly repo has been specified.
        return self.is_inbound() and not self.nightly_repo


class FireFoxNightlyConfigMixin(NightlyConfigMixin):
    def _get_nightly_repo(self, date):
        if date < datetime.date(2008, 6, 17):
            return "trunk"
        else:
            return "mozilla-central"


class ThunderbirdNightlyConfigMixin(NightlyConfigMixin):
    nightly_base_repo_name = 'thunderbird'

    def _get_nightly_repo(self, date):

        if date < datetime.date(2008, 7, 26):
            return "trunk"
        elif date < datetime.date(2009, 1, 9):
            return "comm-central"
        elif date < datetime.date(2010, 8, 21):
            return "comm-central-trunk"
        else:
            return "comm-central"


class B2GNightlyConfigMixin(NightlyConfigMixin):
    nightly_base_repo_name = 'b2g'

    def _get_nightly_repo(self, date):
        return "mozilla-central"


class FennecNightlyConfigMixin(NightlyConfigMixin):
    nightly_base_repo_name = "mobile"

    def _get_nightly_repo(self, date):
        if date < datetime.date(2014, 12, 6):
            return "mozilla-central-android"
        if date < datetime.date(2014, 12, 13):
            return "mozilla-central-android-api-10"
        return "mozilla-central-android-api-11"


class InboundConfigMixin(object):
    """
    Define the inbound-related required configuration.
    """
    inbound_branch = 'mozilla-inbound'

    def set_inbound_branch(self, inbound_branch):
        if inbound_branch:
            self.inbound_branch = inbound_branch

    def inbound_base_urls(self):
        raise NotImplementedError


class FirefoxInboundConfigMixin(InboundConfigMixin):
    build_base_os_part = ['linux', 'linux64', 'win32', 'win64', 'macosx64']
    root_build_base_url = ('http://inbound-archive.pub.build.mozilla.org/pub'
                           '/mozilla.org/firefox/tinderbox-builds/%s-%s/')

    def inbound_base_urls(self):
        url = []
        for os in self.build_base_os_part:
            url.append(self.root_build_base_url % (self.inbound_branch, os))
        return url


class B2GInboundConfigMixin(FirefoxInboundConfigMixin):
    inbound_branch = 'b2g-inbound'
    build_base_os_part = copy.deepcopy(
        FirefoxInboundConfigMixin.build_base_os_part)
    build_base_os_part[0] = 'linux32'

    root_build_base_url = ('http://ftp.mozilla.org/pub/mozilla.org/b2g'
                           '/tinderbox-builds/%s-%s_gecko/')


class FennecInboundConfigMixin(InboundConfigMixin):
    inbound_branchs = ['mozilla-inbound-android']

    def inbound_base_urls(self):
        return ["http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org"
                "/mobile/tinderbox-builds/%s/" % inbound_branch
                for inbound_branch in self.inbound_branchs]

    def set_inbound_branch(self, inbound_branch):
        if inbound_branch:
            self.inbound_branchs = [inbound_branch]


# modified BuildFolderInfoFetcher #

class BuildFolderInfoFetcher(object):
    """
    Allow to retrieve information from build folders.

    :param build_regex: a regexp or string regexp that can match the build
    file.
    :param build_info_regex: a regexp or string regexp that can match the
    build info file (.txt).
    """
    def __init__(self, build_regex, build_info_regex):
        self.build_regex = build_regex
        self.build_info_regex = build_info_regex

    def find_build_info(self, url, read_txt_content=False):
        """
        Retrieve information from a build folder url.

        Returns a dict with keys build_url and build_txt_url if respectively
        a build file and a build info file are found for the url.

        If read_txt_content is True, the dict is updated with data found
        by calling :meth:`find_build_info_txt`
        """
        build_data = []
        links = url_links(url)
        for i in range(len(self.build_regex)):
            data = {}
            if not url.endswith('/'):
                url += '/'
            for link in links:
                if 'build_url' not in data and self.build_regex[i].match(link):
                    data['build_url'] = url + link
                elif 'build_txt_url' not in data and (
                        self.build_info_regex[i].match(link)):
                    data['build_txt_url'] = url + link
            build_data.append(data)
            if read_txt_content and 'build_txt_url' in data:
                data.update(self.find_build_info_txt(data['build_txt_url']))

        return build_data

    def find_build_info_txt(self, url):
        """
        Retrieve information from a build information txt file.

        Returns a dict with keys date, repository and changeset if information
        is found.
        """
        data = {}
        response = get_http_session().get(url)
        date = response.text.splitlines()[0]
        data['date'] = '%s-%s-%s' % (date[:4], date[4:6], date[6:8])
        for line in response.text.splitlines():
            if '/rev/' in line:
                repository, changeset = line.split('/rev/')
                data['repository'] = repository
                data['changeset'] = changeset
                break
        if not data:
            # the txt file could be in an old format:
            # DATE CHANGESET
            # we can try to extract that to get the changeset at least.
            matched = re.match('^\d+ (\w+)$', response.text.strip())
            if matched:
                data['changeset'] = matched.group(1)
        return data


class NightlyBuildData():
    def __init__(self, app_name):
        self.app_name = app_name

    def good_date(self):
        """
        Returns the oldest nightly build date as the good_date
        """
        link = 'http://ftp.mozilla.org/pub/mozilla.org/%s/'
        'nightly/' % self.app_name
        if self.app_name == 'fennec':
            link = "http://ftp.mozilla.org/pub/mozilla.org/mobile/nightly/"
        for year in url_links(link):
            if re.match('20[0-1][0-9]/$', year):
                oldest_year = link + year
                for month in url_links(oldest_year):
                    if re.match('[0-1][0-9]/$', month):
                        oldest_month = oldest_year + month
                        for oldest_build in url_links(oldest_month):
                            if re.match('%s-%s-*' % (
                                    year[:-1], month[:-1]), oldest_build):
                                date = oldest_build.split('-')
                                return '%s-%s-%s' % (date[0], date[1], date[2])

    def get_regex(self):
        """
        Returns build_regex and build_info_regex
        """
        common_config = CommonConfig(self.app_name)
        OS = ['win', 'linux', 'mac']
        BITS = [32, 64]
        build_regex = []
        build_info_regex = []

        for os in OS:
            for bits in BITS:
                build_regex.append(re.compile(
                    common_config.build_regex(os, bits)))
                build_info_regex.append(re.compile(
                    common_config.build_info_regex(os, bits)))
                if os == 'mac':
                    break
        return build_regex, build_info_regex

    def get_nightly_info(self):
        """
        Gets nightly build info of given app_name
        """
        good_date = datetime.datetime.strptime(
            self.good_date(), "%Y-%m-%d").date()
        bad_date = datetime.datetime.now().date()
        day_count = (bad_date - good_date).days + 1
        dates = []
        for n in range(day_count):
            dates.append(good_date + datetime.timedelta(n))

        build_regex, build_info_regex = self.get_regex()
        build_info_folder = BuildFolderInfoFetcher(
            build_regex, build_info_regex)

        if self.app_name == 'firefox':
            app = FireFoxNightlyConfigMixin()
        elif self.app_name == 'thunderbird':
            app = ThunderbirdNightlyConfigMixin()
        elif self.app_name == 'b2g':
            app = B2GNightlyConfigMixin()
        elif self.app_name == 'fennec':
            app = FennecNightlyConfigMixin()

        nightly_builder = NightlyUrlBuilder(app)

        nightly_info = []

        for date in dates:
            url = nightly_builder.get_urls(date)[0]
            print 'url:', url
            build_info = build_info_folder.find_build_info(url)
            # print 'build_info:',build_info
            for builds in build_info:
                result = {}
                if 'build_txt_url' not in builds:
                    continue
                build_info_text = build_info_folder.find_build_info_txt(
                    builds['build_txt_url'])
                result['build_url'] = builds['build_url']
                result['date'] = str(date)
                result['changeset'] = build_info_text['changeset']
                result['repository'] = build_info_text['repository']
                nightly_info.append(result)

        return nightly_info

    def build_json_files(self):
        j = json.dumps(self.get_nightly_info(), indent=2)
        f = open('nightly_%s.json' % self.app_name, 'w')
        print >> f, j
        f.close


class InboundBuildData():
    def __init__(self, app_name):
        self.app_name = app_name

    def get_regex(self, url):
        """
        Returns build_regex and build_info_regex
        """
        common_config = CommonConfig(self.app_name)
        if 'linux64' in url:
            return (
                [re.compile(common_config.build_regex('linux', 64))],
                [re.compile(common_config.build_info_regex('linux', 64))])
        elif 'linux' in url:
            return (
                [re.compile(common_config.build_regex('linux', 32))],
                [re.compile(common_config.build_info_regex('linux', 32))])
        elif 'win32' in url:
            return (
                [re.compile(common_config.build_regex('win', 32))],
                [re.compile(common_config.build_info_regex('win', 32))])
        elif 'win64' in url:
            return (
                [re.compile(common_config.build_regex('win', 64))],
                [re.compile(common_config.build_info_regex('win', 64))])
        elif 'macosx64' in url:
            return (
                [re.compile(common_config.build_regex('mac', 0))],
                [re.compile(common_config.build_info_regex('mac', 0))])
        elif self.app_name == 'fennec':
            return (
                [re.compile(common_config.build_regex('os', 0))],
                [re.compile(common_config.build_info_regex('os', 0))])

    def get_inbound_info(self):

        inbound_info = []

        if self.app_name == 'firefox':
            app = FirefoxInboundConfigMixin()
        elif self.app_name == 'b2g':
            app = B2GInboundConfigMixin()
        elif self.app_name == 'fennec':
            app = FennecInboundConfigMixin()

        os_inbound_url = app.inbound_base_urls()
        print 'os_inbound_url: %s\n' % os_inbound_url
        for urls in os_inbound_url:
            builds = url_links(urls)
            for build_url in builds:
                build_regex, build_info_regex = self.get_regex(urls)
                build_info_folder = BuildFolderInfoFetcher(
                    build_regex, build_info_regex)
                build_info = build_info_folder.find_build_info(urls+build_url)
                print 'build_info: %s\n' % build_info
                for builds in build_info:
                    result = {}
                    if 'build_txt_url' not in builds:
                        continue
                    build_info_text = build_info_folder.find_build_info_txt(
                        builds['build_txt_url'])
                    result['build_url'] = builds['build_url']
                    result['date'] = build_info_text['date']
                    result['changeset'] = build_info_text['changeset']
                    result['repository'] = build_info_text['repository']
                    inbound_info.append(result)

        return inbound_info

    def build_json_files(self):
        j = json.dumps(self.get_inbound_info(), indent=2)
        f = open('inbound_%s.json' % self.app_name, 'w')
        print >> f, j
        f.close


def cli():
    app_list = ['firefox', 'b2g', 'fennec', 'thunderbird']
    for app in app_list:
        nightly = NightlyBuildData(app)
        nightly.build_json_files()
        if app != 'thunderbird':
            inbound = InboundBuildData(app)
            inbound.build_json_files()


if __name__ == '__main__':
    cli()
