import os.path

from pathlib import Path


class Operation:
    def __init__(self, change):
        self._change = change

    @property
    def filename(self):
        return self._change.filename


class AddOp(Operation):
    def __init__(self, change):
        Operation.__init__(self, change)

    def __str__(self):
        return f'Add {self.filename}'


class DeleteOp(Operation):
    def __init__(self, change):
        Operation.__init__(self, change)

    def __str__(self):
        return f'Delete {self.filename}'


class ModifyOp(Operation):
    def __init__(self, change):
        Operation.__init__(self, change)

    def __str__(self):
        return f'Modify {self.filename}'


class MoveOp(Operation):
    def __init__(self, change):
        Operation.__init__(self, change)

    @property
    def target_filename(self):
        return self._change.target_filename

    def __str__(self):
        common = Path(os.path.commonpath(
            [self.filename, self.target_filename]))
        if common:
            from_relative = self.filename.relative_to(common)
            to_relative = self.target_filename.relative_to(common)
            return \
                f'Move {from_relative}\n' \
                f'  to {to_relative}\n' \
                f'  in {common}'
        else:
            return \
                f'Move {self.filename}\n' \
                f'  to {self.target_filename}'
