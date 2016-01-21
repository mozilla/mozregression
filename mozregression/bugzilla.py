import re
from mozregression.json_pushes import JsonPushes

RE_BUG_ID = re.compile('bug\s+(\d+)', re.I)


def find_bugids_in_push(branch, changeset):
    jp = JsonPushes(branch)
    push = jp.push(changeset, full='1')
    branches = set()
    for chset in push.changesets:
        res = RE_BUG_ID.search(chset['desc'])
        if res:
            branches.add(res.group(1))
    return [b for b in branches]


def bug_url(bugid):
    return 'https://bugzilla.mozilla.org/show_bug.cgi?id=%s' % bugid
