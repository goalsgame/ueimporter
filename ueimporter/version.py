import json
import re

def parse_unreal_engine_build_json(build_version_file_content):
    build_version_dict = json.loads(build_version_file_content)
    keys = ['MajorVersion', 'MinorVersion', 'PatchVersion']
    for key in keys:
        if not key in build_version_dict:
            return None
    return '.'.join([str(build_version_dict.get(key)) for key in keys])


def release_tag_to_unreal_engine_version(release_tag):
    match = re.match('^([0-9]*).([0-9]*).([0-9]*)-.*', release_tag)
    if match:
        return '.'.join([match.group(i) for i in range(1, 4)])
    else:
        return None


