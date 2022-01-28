import json

from ueimporter.version import parse_unreal_engine_build_json
from ueimporter.version import release_tag_to_unreal_engine_version


def test_parse_unreal_engine_build_json():
    file_content = json.dumps({
        'MajorVersion': '4',
        'MinorVersion': '27',
        'PatchVersion': '1',

    })
    assert parse_unreal_engine_build_json(file_content) == '4.27.1'


def test_parse_unreal_engine_build_json_without_patch_will_fail():
    file_content = json.dumps({
        'MajorVersion': '4',
        'MinorVersion': '27',

    })
    assert parse_unreal_engine_build_json(file_content) == None


def test_release_tag_to_unreal_engine_version():
    assert release_tag_to_unreal_engine_version('4.27.1-release') == '4.27.1'
    assert release_tag_to_unreal_engine_version('4.27.2-release') == '4.27.2'
    assert release_tag_to_unreal_engine_version(
        '5.0.0-early-access-1') == '5.0.0'
    assert release_tag_to_unreal_engine_version(
        '5.0.0-early-access-2') == '5.0.0'


def test_release_tag_to_unreal_engine_version_without_patch_will_fail():
    assert release_tag_to_unreal_engine_version('4.27.0-release') == '4.27.0'
