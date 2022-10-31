from pathlib import PurePosixPath


def commonpath(filename, target_filename):
    max_common_count = min(len(filename.parts), len(target_filename.parts))
    common_count = 0
    for i in range(0, max_common_count - 1):
        if filename.parts[i] == target_filename.parts[i]:
            common_count += 1
        else:
            break
    if common_count > 0:
        return PurePosixPath(*filename.parts[0:common_count])
    else:
        return None


def is_directory_on_case_sensitive_filesystem(directory):
    assert directory.is_dir()

    case_sensitive_filename = '.ueimporter-CaseSensitiveTest.temp'
    case_sensitive_filename_with_path = directory.joinpath(
        case_sensitive_filename)
    lowercase_filename_with_path = directory.joinpath(
        case_sensitive_filename.lower())

    # We have verified that the plastic workspace is clean, thus
    # these files should not exist
    assert not case_sensitive_filename_with_path.exists()
    assert not lowercase_filename_with_path.exists()

    # Create the file, using the case sensitive name
    case_sensitive_filename_with_path.touch()
    assert case_sensitive_filename_with_path.exists()

    # Now, on a case insentitive file system it's possible to open the file
    # using the all-lowercase filename
    case_insensitive_filesystem = lowercase_filename_with_path.exists()

    # Remove the temporary file, we don't need it anymore
    case_sensitive_filename_with_path.unlink()

    return not case_insensitive_filesystem
