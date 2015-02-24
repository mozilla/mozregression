"""
Another way to do the prefetch script.

 - build_data is not used at all (interesting parts have been copied)
 - fetch_configs is used, but not much - it could be rewritten to be
   used in more appropriate way.

For the test here, I wrote the FirefoxConfig by adding platforms like this:

@REGISTRY.register('firefox')
class FirefoxConfig(CommonConfig,
                    FireFoxNightlyConfigMixin,
                    FirefoxInboundConfigMixin):
    platforms = {
        'linux': [32, 64],
        'win': [32, 64],
        'mac': [64]
    }
"""

import datetime
import json
import re
from mozregression.fetch_configs import REGISTRY
from mozregression.utils import url_links, get_http_session
from collections import defaultdict

def find_build_info_txt(url):
    """
    Retrieve information from a build information txt file.

    Returns a dict with keys repository and changeset if information
    is found.
    """
    data = {}
    response = get_http_session().get(url)
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

def create_all_configs(app_name):
    configs = []
    klass = REGISTRY.get(app_name)
    for os, all_bits in klass.platforms.iteritems():
        for bits in all_bits:
            configs.append(klass(os, bits))
    return configs

def crawl_nightlies(nightly_base_repo_name, filter_year=None, filter_month=None, filter_repo=None):
    build_regex = re.compile(r'^(\d{4})-(\d{2})-(\d{2})-[\d-]+(.+)/$')
    base_url = 'http://ftp.mozilla.org/pub/mozilla.org/%s/nightly/' % nightly_base_repo_name
    for year in url_links(base_url, regex=r'\d{4}/$'):
        if filter_year and not filter_year(int(year[:-1])):
            continue
        year_url = base_url + year
        for month in url_links(year_url, regex=r'\d{2}/$'):
            if filter_month and not filter_month(int(month[:-1])):
                continue
            month_url = year_url + month
            for build_link in url_links(month_url):
                result = build_regex.match(build_link)
                if result:
                    repo = result.group(4)
                    if filter_repo and not filter_repo(repo):
                        continue
                    build_date = datetime.date(int(result.group(1)),
                                               int(result.group(2)),
                                               int(result.group(3)))
                    link = month_url + build_link
                    yield link, build_date, repo


def nightlies_build_infos(app_name, **filters):
    klass = REGISTRY.get(app_name)
    configs = create_all_configs(app_name)
    data = {}
    i=0
    for build_link, build_date, repo in crawl_nightlies(klass.nightly_base_repo_name, **filters):
        if i>2:
            break
        print 'looking into', build_link
        build_content = url_links(build_link)
        if repo not in data:
            info = data[repo] = defaultdict(list)
        else:
            info = data[repo]
        print 'info:', info
        print 'data:', data
        for config in configs:
            build_info = {}
            for fname in build_content:
                if re.match(config.build_regex(), fname):
                    build_info['build_url'] = build_link + fname
                elif re.match(config.build_info_regex(), fname):
                    build_info.update(find_build_info_txt(build_link + fname))
            if build_info:
                key = '%s-%s' % (config.os, config.bits)
                info[key].append(build_info)
        i=i+1
    return data.items()

# for testing, limit the year/month/repo we want to use
filters = {
    'filter_year': lambda year: year == 2015,
    'filter_month': lambda month: month == 02,
    'filter_repo': lambda repo: repo in ('mozilla-central'),
}

# uncomment this to fetch everything - this will take a LOT of time
# filters = {}


for repo, info in nightlies_build_infos('firefox', **filters):

    json.dump(info, open('nightly-%s.json' % repo, 'w'), sort_keys=True, indent=4, separators=(',', ': '))

