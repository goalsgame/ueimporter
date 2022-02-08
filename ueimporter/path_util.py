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
    for candidate in parent.iterdir():
        if candidate.name.lower() == child_name_lower:
            return candidate.name
    return ''


def to_path_with_case_matching_disk(filename):
    assert filename.is_absolute()
    disk_parts = [get_case_of_child_on_disk(filename.parent, filename.name)]
    for p in filename.parents[:-1]:
        disk_parts.append(get_case_of_child_on_disk(p.parent, p.name))
    disk_parts.append(filename.parents[-1].anchor)
    return filename.__class__(*reversed(disk_parts))


def find_parent_dirs_where_case_mismatch_disk(path, root_dir):
    absolute_path = root_dir.joinpath(path)
    absolute_disk_path = to_path_with_case_matching_disk(absolute_path)
    disk_path = absolute_disk_path.relative_to(root_dir)

    path_cls = path.__class__

    mismatches = []
    assert len(path.parts) == len(disk_path.parts)
    for i, (part, disk_part) in enumerate(zip(path.parts, disk_path.parts)):
        assert part.lower() == disk_part.lower()
        if part == disk_part:
            continue

        from_path = path_cls(*path.parts[0:i+1])
        to_path = path_cls(*disk_path.parts[0:i+1])
        mismatches.append((from_path, to_path))
    return mismatches
