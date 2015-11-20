"""
Representation of the bisection history.
"""

from collections import namedtuple


BisectionStep = namedtuple('BisectionStep', 'build_range, index, verdict')


class BisectionHistory(list):
    """
    Hold the history of a bisection.

    This is basically a list of :class:`BisectionStep`, the top
    most step being the most recent.

    Note that it is not a full mozregression bisection history
    since it only store steps for one handler - e.g only for
    one branch.
    """
    def add(self, build_range, index, verdict):
        self.append(BisectionStep(build_range, index, verdict))
