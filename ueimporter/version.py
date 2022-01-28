import json
import re


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
