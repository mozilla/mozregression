from mozregression.fetch_configs import create_config
from mozregression.build_data import BuildFolderInfoFetcher, NightlyUrlBuilder
import datetime

# create a config for firefox (you can also use b2g, thunderbird, fennec or fennec-32)
config = create_config("firefox", "mac", 64)
print 'config:',config

# to find nightlies, you can do:
nightly_builder = NightlyUrlBuilder(config)
print 'nightly_builder:',nightly_builder

# there are multiple builds for one date in nightlies, here just take the first one
url = nightly_builder.get_urls(datetime.date(2014, 12, 02))[0]
print 'url:',url

# now we have the url, let's look for build info (inside the build dir)
# and build_info_text (inside the txt file of the build dir)
build_info_folder = BuildFolderInfoFetcher(config.build_regex(),
                                           config.build_info_regex())
build_info = build_info_folder.find_build_info(url, True)
build_info_text = build_info_folder.find_build_info_txt(build_info['build_txt_url'])

print 'build_info:', build_info
# print 'build_info_text:', build_info_text


# for inbound, the logic must be extracted from the InboundBuildData constructor.