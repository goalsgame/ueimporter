import json

import ueimporter.version as version


def test_from_build_version_json():
    file_content = json.dumps({
        'MajorVersion': '4',
        'MinorVersion': '27',
        'PatchVersion': '1',

    })
    assert version.from_build_version_json(file_content) == '4.27.1'


def test_from_build_version_json_without_patch_will_fail():
    file_content = json.dumps({
        'MajorVersion': '4',
        'MinorVersion': '27',

    })
    assert version.from_build_version_json(file_content) == None


def test_from_git_release_tag():
    assert version.from_git_release_tag('4.27.1-release') == '4.27.1'
    assert version.from_git_release_tag('4.27.2-release') == '4.27.2'
    assert version.from_git_release_tag(
        '5.0.0-early-access-1') == '5.0.0'
    assert version.from_git_release_tag(
        '5.0.0-early-access-2') == '5.0.0'


def test_from_git_release_tag_without_patch_will_fail():
    assert version.from_git_release_tag('4.27.0-release') == '4.27.0'
