import json
import re
from collections import defaultdict
from mozregression.build_data import BuildFolderInfoFetcher
from mozregression.fetch_configs import REGISTRY
from mozregression.utils import url_links


def create_all_configs(app_name):
    configs = []
    klass = REGISTRY.get(app_name)
    for os, all_bits in klass.platforms.iteritems():
        for bits in all_bits:
            configs.append(klass(os, bits))
    return configs


def inbound_build_infos(app_name):
    data = {}
    configs = create_all_configs(app_name)
    for config in configs:
        if not config.is_inbound():
            continue
        for inbound_branch in config.interesting_inbound_branches():
            print 'inbound_branch:', inbound_branch
            if inbound_branch not in data:
                info = data[inbound_branch] = defaultdict(list)
            else:
                info = data[inbound_branch]
            config.set_inbound_branch(inbound_branch)
            base_url = config.inbound_base_urls()
            base_url = base_url[0]
            build_info_folder = BuildFolderInfoFetcher(
                config.build_regex(), config.build_info_regex())
            for url in url_links(base_url):
                if not re.match(r'^(\d{10})/$', url):
                    continue
                print 'url:', url
                build_info = build_info_folder.find_build_info(
                    base_url + url, True)
                build_info['timestamp'] = url[:-1]
                key = '%s-%s' % (config.os, config.bits)
                info[key].append(build_info)
    return data.items()


def cli():
    apps = REGISTRY.names()
    for app_name in apps:
        for repo, info in inbound_build_infos(app_name):
            json.dump(info, open('inbound-%s-%s.json' % (
                app_name.replace('-', '%45'), repo.replace(
                    '-', '%45')), 'w'), sort_keys=True, indent=4, separators=(
                ',', ': '))


if __name__ == '__main__':
    cli()
