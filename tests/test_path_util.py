from pathlib import PurePath

import ueimporter.path_util as path_util


class ChildMock:
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name


class PathMock:
    @classmethod
    def create(cls, *pathsegments):
        leaf = PathMock(*pathsegments)

        parts = leaf.parts
        parents = []
        for i in range(0, len(parts) - 1):
            parent = PathMock(*parts[0: i+1])
            if i > 0:
                parent.parents = parents[0:1]
            parents.insert(0, parent)

        leaf.parents = parents
        p = leaf
        while p.parent != p:
            p.parent.add_child(p)
            p = p.parent
        return leaf

    def __init__(self, *pathsegments):
        self._path = PurePath(*pathsegments)
        self._disk_path = None
        self._parents = []
        self._children = []

    def __str__(self):
        return str(self._path)

    @property
    def name(self):
        return self._path.name

    @property
    def parts(self):
        return self._path.parts

    @property
    def parent(self):
        return self._parents[0] if self._parents else self

    @property
    def parents(self):
        return self._parents

    @parents.setter
    def parents(self, value):
        self._parents = value

    @property
    def anchor(self):
        return self._path.anchor

    def is_absolute(self):
        return self._path.root or self._path.drive

    def joinpath(self, *pathsegments):
        joined_parts = self.parts[:]
        for segment in pathsegments:
            assert type(segment) == PathMock
            joined_parts += segment.parts
        joined_path = PathMock.create(*joined_parts)

        if not self.disk_path:
            return joined_path

        joined_disk_parts = self.disk_path.parts[:]
        for segment in pathsegments:
            assert segment.disk_path
            joined_disk_parts += segment.disk_path.parts
        joined_disk_path = PathMock.create(*joined_disk_parts)
        joined_path.disk_path = joined_disk_path
        return joined_path

    def relative_to(self, *other):
        assert len(other) == 1
        assert type(other[0]) == PathMock
        relative = self._path.relative_to(other[0]._path)
        return PathMock.create(*relative.parts)

    @property
    def disk_path(self):
        return self._disk_path

    @disk_path.setter
    def disk_path(self, value):
        self._disk_path = value
        assert len(self.parents) == len(value.parents)
        for parent, disk_parent in zip(self.parents, value.parents):
            parent.disk_path = disk_parent

    @property
    def children(self):
        return self._children

    def add_child(self, child):
        assert type(child) == PathMock
        self._children.append(child)

    def iterdir(self):
        path_mock = self._disk_path if self._disk_path else self
        for child in path_mock.children:
            yield ChildMock(child.name)


def test_path_mock():
    source = PathMock.create('Engine\\Source\\ThirdParty\\PhysX3\\Externals'
                             '\\CMakeModules\\linux'
                             '\\LinuxCrossToolchain.arm-unknown-linux-gnueabihf.cmake')

    assert str(source) == \
        'Engine\\Source\\ThirdParty\\PhysX3\\Externals' \
        '\\CMakeModules\\linux' \
        '\\LinuxCrossToolchain.arm-unknown-linux-gnueabihf.cmake'
    assert source.name == 'LinuxCrossToolchain.arm-unknown-linux-gnueabihf.cmake'
    assert source.parent.name == 'linux'
    assert (source.parent).parent.name == 'CMakeModules'
    assert not source.is_absolute()

    root_dir = PathMock.create('h:\\Goals\\UnrealEngine_2')
    assert len(root_dir.parents) == 2
    assert str(root_dir) == 'h:\\Goals\\UnrealEngine_2'
    assert root_dir.name == 'UnrealEngine_2'
    assert root_dir.is_absolute()

    joined = root_dir.joinpath(source)
    assert str(joined) == \
        'h:\\Goals\\UnrealEngine_2'\
        '\\Engine\\Source\\ThirdParty\\PhysX3\\Externals' \
        '\\CMakeModules\\linux' \
        '\\LinuxCrossToolchain.arm-unknown-linux-gnueabihf.cmake'


def test_path_mock_root():
    root = PathMock.create('c:\\')
    assert root.name == ''
    assert len(root.parents) == 0
    assert root.parent == root
    assert str(root) == 'c:\\'


def test_path_mock_joinpath():
    root = PathMock.create('c:\\')
    part1 = root.joinpath(PathMock.create('part1'))
    part2 = part1.joinpath(PathMock.create('part2'))

    assert str(root) == 'c:\\'
    assert str(part1) == 'c:\\part1'
    assert str(part2) == 'c:\\part1\\part2'


def test_path_mock_parents():
    path = 'c:\\part1\\part2\\part3\\leaf.txt'
    path_mock = PathMock.create(path)

    part3 = path_mock.parent
    part2 = part3.parent
    part1 = part2.parent
    root = part1.parent

    assert str(root) == 'c:\\'
    assert str(part1) == 'c:\\part1'
    assert str(part2) == 'c:\\part1\\part2'
    assert str(path_mock) == 'c:\\part1\\part2\\part3\\leaf.txt'
