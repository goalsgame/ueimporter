import json
import re
import copy

GIT_RELEASE_TAG_KEY = 'GitReleaseTag'


def create_ueimporter_json():
    return UEImporterJson({GIT_RELEASE_TAG_KEY: ''})


def read_ueimporter_json(filename):
    if not filename.is_file():
        return None
    file_content = filename.read_text(encoding='utf-8')
    json_dict = json.loads(file_content)
    return UEImporterJson(json_dict)


def write_ueimporter_json(filename, ueimport_version, force_overwrite=False):
    if not force_overwrite and filename.is_file():
        return False

    file_content = ueimport_version.to_json()
    filename.write_text(file_content, encoding='utf-8')
    return True


class UEImporterJson:
    def __init__(self, version_dict):
        valid_keys = [GIT_RELEASE_TAG_KEY]
        valid_dict = {k: v for k, v in version_dict.items() if k in valid_keys}
        self._dict = copy.deepcopy(valid_dict)
        self._dict.setdefault(GIT_RELEASE_TAG_KEY, '')

    @property
    def git_release_tag(self):
        return self._dict.get(GIT_RELEASE_TAG_KEY, None)

    @git_release_tag.setter
    def git_release_tag(self, value):
        self._dict[GIT_RELEASE_TAG_KEY] = value

    def to_json(self, indent=4):
        return json.dumps(self._dict, sort_keys=True, indent=indent)


def from_build_version_json(file_content):
    # Parse version from Engine/Build/Build.version
    build_version_dict = json.loads(file_content)
    keys = ['MajorVersion', 'MinorVersion', 'PatchVersion']
    for key in keys:
        if not key in build_version_dict:
            return None
    return '.'.join([str(build_version_dict.get(key)) for key in keys])


def from_git_release_tag(release_tag):
    # Parse version from UnrealEngines git release tags
    match = re.match('^([0-9]*).([0-9]*).([0-9]*)-.*', release_tag)
    if match:
        return '.'.join([match.group(i) for i in range(1, 4)])
    else:
        return None
