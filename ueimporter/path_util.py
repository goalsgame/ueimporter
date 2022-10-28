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
