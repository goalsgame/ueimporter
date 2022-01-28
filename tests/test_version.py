import json

import ueimporter.version as version


def test_ueimporter_json_with_tag_will_succeed():
    version_dict = {
        'GitReleaseTag': '4.27.1-release'
    }
    assert version.UEImporterJson(
        version_dict).git_release_tag == '4.27.1-release'


def test_ueimporter_json_without_key_will_yield_empty_tag():
    version_dict = {
        'MisspelledGitReleaseTag': '4.27.1-release'
    }
    assert version.UEImporterJson(version_dict).git_release_tag == ''
    assert version.UEImporterJson({}).git_release_tag == ''


def test_ueimporter_json_set_tag_will_succeed():
    version_dict = {
        'GitReleaseTag': '4.27.1-release'
    }
    ueimporter_json = version.UEImporterJson(version_dict)
    ueimporter_json.git_release_tag = '4.27.2-release'
    assert ueimporter_json.git_release_tag == '4.27.2-release'


def test_ueimporter_json_will_yeild_json_with_tag():
    version_dict = {
        'GitReleaseTag': '4.27.1-release'
    }
    assert version.UEImporterJson(version_dict).to_json(indent=4) == \
        """{
    "GitReleaseTag": "4.27.1-release"
}"""


def test_ueimporter_json_without_key_will_yeild_json_with_empty_tag():
    assert version.UEImporterJson({}).to_json(indent=4) == \
        """{
    "GitReleaseTag": ""
}"""


def test_ueimporter_json_with_invalid_key_will_yeild_json_with_valid_keys():
    version_dict = {
        'GitReleaseTag': '4.27.1-release',
        'ThisKeyDoesNotBelong': 'SomeValue',
    }
    assert version.UEImporterJson(version_dict).to_json(indent=4) == \
        """{
    "GitReleaseTag": "4.27.1-release"
}"""


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
