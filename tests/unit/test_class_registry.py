from __future__ import absolute_import

from mozregression.class_registry import ClassRegistry

TEST_REGISTRY = ClassRegistry()


@TEST_REGISTRY.register("c1")
class C1(object):
    pass


@TEST_REGISTRY.register("c2")
class C2(object):
    pass


@TEST_REGISTRY.register("c3", some_other_attr=True)
class C3(object):
    pass


def test_get_names():
    TEST_REGISTRY.names() == ["c1", "c2", "c3"]

    TEST_REGISTRY.names(lambda klass: getattr(klass, "some_other_attr", None)) == ["c3"]
