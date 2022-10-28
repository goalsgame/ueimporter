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


def get_case_of_child_on_disk(parent, child_name):
    child_name_lower = child_name.lower()
    candidates = [c for c in parent.iterdir()
            if c.name.lower() == child_name_lower]
    if not candidates:
        return ''

    case_match = next(c for c in candidates if c.name == child_name)
    if case_match:
        return case_match.name
    else:
        return candidates[0].name


def to_path_with_case_matching_disk(filename, root_dir):
    assert not filename.is_absolute()
    absolute_disk_path = root_dir
    for part in filename.parts:
        disk_part_name = get_case_of_child_on_disk(absolute_disk_path, part)
        absolute_disk_path = absolute_disk_path.joinpath(disk_part_name)
    return absolute_disk_path


def find_parent_dirs_where_case_mismatch_disk(path, root_dir):
    absolute_disk_path = to_path_with_case_matching_disk(path, root_dir)
    disk_path = absolute_disk_path.relative_to(root_dir)

    path_cls = path.__class__

    mismatches = []
    assert len(path.parts) == len(disk_path.parts)
    for i, (part, disk_part) in enumerate(zip(path.parts, disk_path.parts)):
        assert part.lower() == disk_part.lower()
        if part == disk_part:
            continue

        from_path = path_cls(*disk_path.parts[0:i+1])
        to_path = path_cls(*path.parts[0:i+1])
        mismatches.append((from_path, to_path))
    return mismatches
