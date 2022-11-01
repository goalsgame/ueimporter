import os
import re
import shutil

import ueimporter.git as git
import ueimporter.op as op
import ueimporter.path_util as path_util


def create_jobs(changes, plastic_repo, source_root_path, pretend, logger):
    # Convert Del + Add of the same file to a Move
    logger.log('Finding deletes followed by adds on the same file')
    logger.indent()
    change_type_to_changes = {
        git.Add: changes.adds,
        git.Delete: changes.deletes,
        git.Modify: changes.modifications,
        git.Move: changes.moves
    }
    for lower_filename, per_file_changes in changes.per_file_changes.items():
        for change in per_file_changes:
            line = f'{type(change).__name__} {change.filename}'
            if type(change) == git.Move:
                line += f' -> {change.target_filename}'
            logger.log(line)

        for i in range(0, len(per_file_changes) - 1):
            change = per_file_changes[i]
            if not change:
                continue

            next_change = per_file_changes[i+1]
            if type(change) == git.Delete and type(next_change) == git.Add:
                move = git.Move(change.filename, next_change.filename)

                logger.log('Replacing')
                logger.indent()
                for change_to_log in [change, next_change]:
                    for line in str(change_to_log).split('\n'):
                        logger.log(line)
                logger.deindent()
                logger.log('With')
                logger.indent()
                for line in str(move).split('\n'):
                    logger.log(line)
                logger.deindent()

                change = move
                per_file_changes[i+1] = None

            job_changes = change_type_to_changes.get(type(change))
            assert job_changes != None
            job_changes.append(change)

    logger.deindent()

    # Convert Move to Modify if move appears to already happened
    # in the target repo
    logger.log('Finding moves that have already been applied in target.')
    logger.indent()
    moves_already_existing_in_target = [
            move for move in changes.moves
            if not plastic_repo.to_workspace_path(move.filename).is_file()
            and plastic_repo.to_workspace_path(move.target_filename).is_file()]
    for move in moves_already_existing_in_target:
        modify = git.Modify(move.target_filename)

        logger.log('Replacing')
        logger.indent()
        for line in str(move).split('\n'):
            logger.log(line)
        logger.deindent()
        logger.log('With')
        logger.indent()
        for line in str(modify).split('\n'):
            logger.log(line)
        logger.deindent()

        changes.modifications.append(modify)
        changes.moves.remove(move)
    logger.deindent()

    jobs = []
    job_class_to_changes = [
        (AddJob, changes.adds),
        (DeleteJob, changes.deletes),
        (ModifyJob, changes.modifications),
        (MoveJob, changes.moves)]
    for (job_class, job_changes) in job_class_to_changes:
        if len(job_changes) == 0:
            continue
        job = job_class(logger=logger,
                        plastic_repo=plastic_repo,
                        source_root_path=source_root_path,
                        pretend=pretend)
        job_changes = sorted(job_changes, key=lambda m: m.filename)
        for change in job_changes:
            job.add_change(change)
        jobs.append(job)

    return jobs


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

    def start_batch(self, job, ops):
        pass

    def end_batch(self):
        pass

    def start_step(self, desc):
        pass

    def end_step(self, desc=None):
        pass


class Job:
    _JOB_DESC = ''

    @classmethod
    @property
    def job_desc(cls):
        return cls._JOB_DESC

    def __init__(self, op_class, plastic_repo, source_root_path, pretend, logger):
        self._op_class = op_class
        self.plastic_repo = plastic_repo
        self.source_root_path = source_root_path
        self.pretend = pretend
        self.logger = logger
        self._ops = []
        self._processed_op_count = 0

    @property
    def desc(self):
        return self.__class__.job_desc

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

    def remove_op(self, op):
        self._ops.remove(op)

    def process(self, batch_size, max_op_count, listener):
        ops = self.unprocessed_ops
        op_count = len(ops)
        if max_op_count > 0:
            op_count = min(op_count, max_op_count)
        for batch_start in range(0, op_count, batch_size):
            batch_end = min(batch_start + batch_size, op_count)
            batch_ops = ops[batch_start:batch_end]
            listener.start_batch(self, batch_ops)
            self.process_ops(batch_ops, listener)
            listener.end_batch()
        self._processed_op_count += op_count

    def process_ops(self, ops, listener):
        pass

    def find_invalid_ops(self):
        invalid_ops = []
        for op in self.ops:
            validation = op.validate(self.source_root_path,
                                     self.plastic_repo.workspace_root)
            if not validation:
                invalid_ops.append((op, validation))
        return invalid_ops

    def copy(self, filenames):
        # Copy files from source to target plastic workspace
        for filename in filenames:
            self.logger.log_verbose(filename)
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
            self.logger.log(directory)
            if self.pretend:
                continue

            target_directory = self.plastic_repo.to_workspace_path(directory)
            os.makedirs(target_directory)
        return dirs_to_create

    def remove_empty_parent_dirs(self, filenames):
        remove_count = 0
        parents = set([filename.parent for filename in filenames])

        plastic_workspace_root = self.plastic_repo.workspace_root

        def is_existing_dir_empty(p):
            workspace_path = plastic_workspace_root.joinpath(p)
            if not workspace_path.exists():
                return False
            for _ in workspace_path.iterdir():
                return False
            return workspace_path.is_dir()

        while len(parents) > 0:
            empty_parents = [p for p in parents if is_existing_dir_empty(p)]
            if len(empty_parents) == 0:
                break

            for directory in empty_parents:
                self.logger.log(directory)

            remove_count += len(empty_parents)
            self.plastic_repo.remove_multiple(empty_parents, self.logger)
            grand_parents = set([p.parent for p in empty_parents
                                 if not p.parent == plastic_workspace_root])
            parents = (parents - set(empty_parents)) | grand_parents

        return remove_count


class AddJob(Job):
    def __init__(self, **kwargs):
        Job.__init__(self, op.AddOp, **kwargs)

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
        Job.__init__(self, op.ModifyOp, **kwargs)

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
        Job.__init__(self, op.DeleteOp, **kwargs)

    def process_ops(self, ops, listener):
        filenames = [op.filename for op in ops]
        listener.start_step('Remove files from plastic')
        self.plastic_repo.remove_multiple(filenames, self.logger)
        listener.end_step()

        listener.start_step(f'Remove empty directories from plastic')
        self.remove_empty_parent_dirs(filenames)
        listener.end_step()


class MoveJob(Job):
    def __init__(self, **kwargs):
        Job.__init__(self, op.MoveOp, **kwargs)

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


# Register operations, and set up descriptions
_JOB_DESC_REGEX = re.compile('^([a-zA-Z]*)Job$')
JOB_CLASSES = [AddJob, DeleteJob, ModifyJob, MoveJob]
for job_class in JOB_CLASSES:
    match = _JOB_DESC_REGEX.match(job_class.__name__)
    assert match
    job_class._JOB_DESC = match.group(1)
