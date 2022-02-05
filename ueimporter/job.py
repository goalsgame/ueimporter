import shutil
import os
import sys

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
    for a in changes.adds:
        add.add_change(a)
    for d in changes.deletes:
        delete.add_change(d)
    for m in changes.modifications:
        modify.add_change(m)
    for m in changes.moves:
        move.add_change(m)

    jobs = [add, delete, modify, move]
    return [job for job in jobs if len(job.ops) > 0]


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

    def start_job(self, desc, op_count):
        pass

    def end_job(self):
        pass

    def start_batch(self, ops):
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
        self._ops = []
        self._processed_op_count = 0

    @property
    def desc(self):
        return self._desc

    @property
    def ops(self):
        return self._ops

    @property
    def unprocessed_ops(self):
        return self._ops[self._processed_op_count:]

    def add_change(self, change):
        op = self._op_class(change)
        self._ops.append(op)

    def trim_trailing_ops(self, max_op_count):
        assert max_op_count >= 0
        max_op_count = min(len(self._ops), max_op_count)
        self._ops = self._ops[0:max_op_count]

    def remove_ops(self, ops_to_remove):
        if not ops_to_remove:
            return
        op_set = set(self.ops) - set(ops_to_remove)
        self._ops = sorted(op_set, key=lambda m: m.filename)

    def process(self, batch_size, max_op_count, listener):
        ops = self.unprocessed_ops
        op_count = len(ops)
        if max_op_count > 0:
            op_count = min(op_count, max_op_count)
        for batch_start in range(0, op_count, batch_size):
            batch_end = min(batch_start + batch_size, op_count)
            batch_ops = ops[batch_start:batch_end]
            listener.start_batch(self._desc, batch_ops)
            self.process_ops(batch_ops, listener)
            listener.end_batch()
        self._processed_op_count += op_count

    def process_ops(self, ops, listener):
        pass

    def prune_ops_with_missing_source_files(self):
        assert self._processed_op_count == 0
        missing = self.find_ops_with_missing_source_files()
        self.remove_ops(missing)
        return missing

    def find_ops_with_missing_source_files(self):
        return [op for op in self.ops
                if not self.source_root_path.joinpath(op.filename).is_file()]

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

    def process_ops(self, ops, listener):
        filenames = [op.filename for op in ops]

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

    def process_ops(self, ops, listener):
        filenames = [op.filename for op in ops]

        listener.start_step('Checkout files in plastic')
        self.plastic_repo.checkout_multiple(filenames, self.logger)
        listener.end_step()

        listener.start_step('Copy files from source')
        self.copy(filenames)
        listener.end_step()


class DeleteJob(Job):
    def __init__(self, **kwargs):
        Job.__init__(self, 'Delete', **kwargs)

    def process_ops(self, ops, listener):
        filenames = [op.filename for op in ops]
        listener.start_step('Remove files from plastic')
        self.plastic_repo.remove_multiple(filenames, self.logger)
        listener.end_step()

        listener.start_step(f'Remove empty directories from plastic')
        self.remove_empty_parent_dirs(filenames)
        listener.end_step()

    def find_ops_with_missing_source_files(self):
        # A deleted file never exist in source, thus they can not be missing
        return []


class MoveJob(Job):
    def __init__(self, **kwargs):
        Job.__init__(self, 'Move', **kwargs)

    def process_ops(self, ops, listener):
        target_filenames = [op.target_filename for op in ops]

        listener.start_step('Create missing parent directories')
        dirs_to_add = self.create_target_parent_dirs(target_filenames)
        listener.end_step()

        if dirs_to_add:
            listener.start_step('Add created parent directories to plastic')
            self.plastic_repo.add_multiple(dirs_to_add, self.logger)
            listener.end_step()

        listener.start_step(f'Move files in plastic')
        from_to_pairs = [(op.filename, op.target_filename) for op in ops]
        self.plastic_repo.move_multiple(from_to_pairs, self.logger)
        listener.end_step()

        listener.start_step('Copy files from source')
        self.copy(target_filenames)
        listener.end_step()

        listener.start_step(f'Remove empty directories from plastic')
        source_filenames = [op.filename for op in ops]
        self.remove_empty_parent_dirs(source_filenames)
        listener.end_step()

    def find_ops_with_missing_source_files(self):
        return [op for op in self.ops
                if not self.source_root_path.joinpath(op.target_filename).is_file()]
