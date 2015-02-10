import datetime
import json
import re
from mozregression.build_data import BuildFolderInfoFetcher
from mozregression.fetch_configs import REGISTRY
from mozregression.utils import url_links, get_http_session
from collections import defaultdict


def create_all_configs(app_name):
    configs = []
    klass = REGISTRY.get(app_name)
    for os, all_bits in klass.platforms.iteritems():
        for bits in all_bits:
            configs.append(klass(os, bits))
    return configs

def inbound_build_infos(app_name):
    data = []
    configs = create_all_configs(app_name)
    for config in configs:
        print config.inbound_branch
        base_urls = config.inbound_base_urls()
        build_info_folder = BuildFolderInfoFetcher(config.build_regex(),
                                           config.build_info_regex())
        for base_url in base_urls:
            print 'base_url:', base_url
            i=0
            for url in url_links(base_url):
                if not re.match(r'^(\d{10})/$', url):
                    continue
                print 'url:', url
                build_info = build_info_folder.find_build_info(base_url + url)
                build_info_text = build_info_folder.find_build_info_txt(
                    build_info['build_txt_url'])

                result = {}
                response = get_http_session().get(build_info['build_text_url'])[0]
                result['date'] = (response[6:8], response[4:6], response[:4])
                result['build_url'] = build_info['build_url']
                result['changeset'] = build_info_text['changeset']
                result['repository'] = build_info_text['repository']
                data.append(result)
                i=i+1
                if i == 5:
                    return data

def get_inbound_info(apps):
    for app_name in apps:
        json.dump(inbound_build_infos(app_name), open('inbound-%s.json' % app_name, 'w'), sort_keys=True, indent=4, separators=(',', ': '))

if __name__ == '__main__':
    print inbound_build_infos('firefox')
