import re

import ueimporter.path_util as path_util


class OpValidation:
    @classmethod
    def valid(cls):
        return OpValidation(True, None)

    @classmethod
    def invalid(cls, error_message):
        return OpValidation(False, error_message)

    @classmethod
    def invalid_exist(cls, filename, root_path):
        return OpValidation.invalid(
            f'File already exist in {root_path}')

    @classmethod
    def invalid_not_exist(cls, filename, root_path):
        return OpValidation.invalid(
            f'File does not exist in {root_path}')

    def __init__(self, is_valid, error_message):
        self._is_valid = is_valid
        self._error_message = error_message

    def __str__(self):
        if self._is_valid:
            return 'Valid operation'
        else:
            return f'{self._error_message}'

    def __bool__(self):
        return self._is_valid


class Operation:
    def __init__(self, change):
        self._change = change

    def __str__(self):
        return str(self._change)

    @property
    def filename(self):
        return self._change.filename

    def validate(self, source_root, target_root):
        assert False, f'{self.__class__} does not implement validate()'


class AddOp(Operation):
    def __init__(self, change):
        Operation.__init__(self, change)

    def validate(self, source_root, target_root):
        if not source_root.joinpath(self.filename).is_file():
            return OpValidation.invalid_not_exist(self.filename, source_root)
        if target_root.joinpath(self.filename).is_file():
            return OpValidation.invalid_exist(self.filename, target_root)
        return OpValidation.valid()


class DeleteOp(Operation):
    def __init__(self, change):
        Operation.__init__(self, change)

    def validate(self, source_root, target_root):
        if source_root.joinpath(self.filename).is_file():
            return OpValidation.invalid_exist(self.filename, source_root)
        if not target_root.joinpath(self.filename).is_file():
            return OpValidation.invalid_not_exist(self.filename, target_root)
        return OpValidation.valid()


class ModifyOp(Operation):
    def __init__(self, change):
        Operation.__init__(self, change)

    def validate(self, source_root, target_root):
        if not source_root.joinpath(self.filename).is_file():
            return OpValidation.invalid_not_exist(self.filename, source_root)
        if not target_root.joinpath(self.filename).is_file():
            return OpValidation.invalid_not_exist(self.filename, target_root)
        return OpValidation.valid()


class MoveOp(Operation):
    def __init__(self, change):
        Operation.__init__(self, change)

    @property
    def target_filename(self):
        return self._change.target_filename

    def validate(self, source_root, target_root):
        if self.filename == self.target_filename:
            return OpValidation.invalid(
                f'{self.filename} is moved to the same file')
        if not source_root.joinpath(self.target_filename).is_file():
            return OpValidation.invalid_not_exist(
                self.target_filename,
                source_root)
        source_exist_in_target = \
            target_root.joinpath(self.filename).is_file()
        target_exist_in_target = \
            target_root.joinpath(self.target_filename).is_file()
        if not source_exist_in_target and not target_exist_in_target:
            # Even though the source file does not exist in the target root,
            # we might still have a valid move, if the target file
            # already exists. in this case no plastic move will be performed,
            # but the contents of the file will be copied from source.
            return OpValidation.invalid_not_exist(
                self.filename,
                target_root)
        if target_exist_in_target and source_exist_in_target:
            # Even though the target file already exist in the target root,
            # we might still have a valid move, if the source file
            # does not exist. In this case no plastic move will be performed,
            # but the contents of the file will be copied from source.
            return OpValidation.invalid_exist(
                self.target_filename,
                source_root)

        return OpValidation.valid()
