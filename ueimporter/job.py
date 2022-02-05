import shutil
import os
import sys

import ueimporter.git as git
from ueimporter import LogLevel


def create_jobs(changes, plastic_repo, source_root_path, pretend, logger):
    add = AddJob(logger=logger,
                 plastic_repo=plastic_repo,
                 source_root_path=source_root_path,
                 pretend=pretend)
    delete = DeleteJob(logger=logger,
                       plastic_repo=plastic_repo,
                       source_root_path=source_root_path,
                       pretend=pretend)
    modify = ModifyJob(logger=logger,
                       plastic_repo=plastic_repo,
                       source_root_path=source_root_path,
                       pretend=pretend)
    move = MoveJob(logger=logger,
                   plastic_repo=plastic_repo,
                   source_root_path=source_root_path,
                   pretend=pretend)
    job_dict = {
        git.Add: add,
        git.Delete: delete,
        git.Modify: modify,
        git.Move: move,
    }
    for change in changes:
        job = job_dict.get(change.__class__, None)
        if job:
            job.add_change(change)
        else:
            logger.eprint('Error: Unrecognized change type {change}')
            sys.exit(1)

    jobs = [add, delete, modify, move]
    return [job for job in jobs if len(job.changes) > 0]


def find_dirs_to_create(target_root, filenames):
    dirs_to_add = set()
    for filename in filenames:
        directory = filename.parent
        while not directory in dirs_to_add and \
                not target_root.joinpath(directory).is_dir():
            dirs_to_add.add(directory)
    return sorted(dirs_to_add)


class JobProgressListener:
    def __init__(self):
        pass

    def start_job(self, desc, change_count):
        pass

    def end_job(self):
        pass

    def start_batch(self, changes):
        pass

    def end_batch(self):
        pass

    def start_step(self, desc):
        pass

    def end_step(self, desc=None):
        pass


class Job:
    def __init__(self, desc, plastic_repo, source_root_path, pretend, logger):
        self._desc = desc
        self.plastic_repo = plastic_repo
        self.source_root_path = source_root_path
        self.pretend = pretend
        self.logger = logger
        self._changes = []
        self._processed_change_count = 0

    @property
    def desc(self):
        return self._desc

    @property
    def changes(self):
        return self._changes

    @property
    def unprocessed_changes(self):
        return self._changes[self._processed_change_count:]

    def add_change(self, change):
        self._changes.append(change)

    def trim_trailing_changes(self, max_change_count):
        assert max_change_count >= 0
        max_change_count = min(len(self._changes), max_change_count)
        self._changes = self._changes[0:max_change_count]

    def remove_changes(self, changes_to_remove):
        if not changes_to_remove:
            return
        change_set = set(self.changes) - set(changes_to_remove)
        self._changes = sorted(change_set, key=lambda m: m.filename)

    def process(self, batch_size, max_change_count, listener):
        changes = self.unprocessed_changes
        change_count = len(changes)
        if max_change_count > 0:
            change_count = min(change_count, max_change_count)
        for batch_start in range(0, change_count, batch_size):
            batch_end = min(batch_start + batch_size, change_count)
            batch_changes = changes[batch_start:batch_end]
            listener.start_batch(self._desc, batch_changes)
            self.process_changes(batch_changes, listener)
            listener.end_batch()
        self._processed_change_count += change_count

    def process_changes(self, changes, listener):
        pass

    def prune_changes_with_missing_source_files(self):
        assert self._processed_change_count == 0
        missing = self.find_changes_with_missing_source_files()
        self.remove_changes(missing)
        return missing

    def find_changes_with_missing_source_files(self):
        return [c for c in self.changes
                if not self.source_root_path.joinpath(c.filename).is_file()]

    def copy(self, filenames):
        # Copy files from source to target plastic workspace
        for filename in filenames:
            self.logger.print(LogLevel.VERBOSE, filename)
            if self.pretend:
                continue

            source_filename = self.source_root_path.joinpath(filename)
            target_filename = self.plastic_repo.to_workspace_path(filename)

            # Copy file including file permissions and create/modify timstamps
            shutil.copy2(source_filename, target_filename)

    def create_target_parent_dirs(self, filenames):
        # Ensure that all parent directories exist in plastic workspace
        dirs_to_create = find_dirs_to_create(
            self.plastic_repo.workspace_root, filenames)
        for directory in dirs_to_create:
            self.logger.print(LogLevel.NORMAL, directory)
            if self.pretend:
                continue

            target_directory = self.plastic_repo.to_workspace_path(directory)
            os.makedirs(target_directory)
        return dirs_to_create

    def remove_empty_parent_dirs(self, filenames):
        remove_count = 0
        parents = set([filename.parent for filename in filenames])

        plastic_workspace_root = self.plastic_repo.workspace_root

        def is_dir_empty(p):
            workspace_path = plastic_workspace_root.joinpath(p)
            for _ in workspace_path.iterdir():
                return False
            return workspace_path.is_dir()

        while len(parents) > 0:
            empty_parents = [p for p in parents if is_dir_empty(p)]
            if len(empty_parents) == 0:
                break

            for directory in empty_parents:
                self.logger.print(LogLevel.NORMAL, directory)

            remove_count += len(empty_parents)
            self.plastic_repo.remove_multiple(empty_parents, self.logger)
            grand_parents = set([p.parent for p in empty_parents
                                 if not p.parent == plastic_workspace_root])
            parents = (parents - set(empty_parents)) | grand_parents

        return remove_count


class AddJob(Job):
    def __init__(self, **kwargs):
        Job.__init__(self, 'Add', **kwargs)

    def process_changes(self, changes, listener):
        filenames = [change.filename for change in changes]

        listener.start_step('Create missing parent directories')
        dirs_to_add = self.create_target_parent_dirs(filenames)
        listener.end_step()

        listener.start_step('Copy files from source')
        self.copy(filenames)
        listener.end_step()

        paths_to_add = sorted(dirs_to_add + filenames)
        listener.start_step(f'Add {len(filenames)} files and'
                            f' {len(dirs_to_add)} directories to plastic')
        self.plastic_repo.add_multiple(paths_to_add, self.logger)
        listener.end_step()


class ModifyJob(Job):
    def __init__(self, **kwargs):
        Job.__init__(self, 'Modify', **kwargs)

    def process_changes(self, changes, listener):
        filenames = [change.filename for change in changes]

        listener.start_step('Checkout files in plastic')
        self.plastic_repo.checkout_multiple(filenames, self.logger)
        listener.end_step()

        listener.start_step('Copy files from source')
        self.copy(filenames)
        listener.end_step()


class DeleteJob(Job):
    def __init__(self, **kwargs):
        Job.__init__(self, 'Delete', **kwargs)

    def process_changes(self, changes, listener):
        filenames = [change.filename for change in changes]
        listener.start_step('Remove files from plastic')
        self.plastic_repo.remove_multiple(filenames, self.logger)
        listener.end_step()

        listener.start_step(f'Remove empty directories from plastic')
        self.remove_empty_parent_dirs(filenames)
        listener.end_step()

    def find_changes_with_missing_source_files(self):
        # A deleted file never exist in source, thus they can not be missing
        return []


class MoveJob(Job):
    def __init__(self, **kwargs):
        Job.__init__(self, 'Move', **kwargs)

    def process_changes(self, changes, listener):
        target_filenames = [change.target_filename for change in changes]

        listener.start_step('Create missing parent directories')
        dirs_to_add = self.create_target_parent_dirs(target_filenames)
        listener.end_step()

        if dirs_to_add:
            listener.start_step('Add created parent directories to plastic')
            self.plastic_repo.add_multiple(dirs_to_add, self.logger)
            listener.end_step()

        listener.start_step(f'Move files in plastic')
        from_to_pairs = [(c.filename, c.target_filename) for c in changes]
        self.plastic_repo.move_multiple(from_to_pairs, self.logger)
        listener.end_step()

        listener.start_step('Copy files from source')
        self.copy(target_filenames)
        listener.end_step()

        listener.start_step(f'Remove empty directories from plastic')
        source_filenames = [change.filename for change in changes]
        self.remove_empty_parent_dirs(source_filenames)
        listener.end_step()

    def find_changes_with_missing_source_files(self):
        return [c for c in self.changes
                if not self.source_root_path.joinpath(c.target_filename).is_file()]
