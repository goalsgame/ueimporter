import ueimporter


class Repo:
    def __init__(self, workspace_root, pretend):
        self.workspace_root = workspace_root
        self.pretend = pretend

    def to_workspace_path(self, path):
        return self.workspace_root.joinpath(path)

    def is_workspace_clean(self, logger):
        arguments = ['status',
                     '--machinereadable']
        stdout = self.run_cmd(arguments, logger)
        lines = stdout.split('\n')
        if len(lines) == 1:
            return True
        elif len(lines) == 2:
            return len(lines[1]) == 0
        else:
            return False

    def add(self, path, logger):
        return self.run_cmd(['add'], logger, [path])

    def remove(self, path, logger):
        return self.run_cmd(['add'], logger, [path])

    def checkout(self, path, logger):
        return self.run_cmd(['checkout'], logger, [path])

    def move(self, from_path, to_path, logger):
        return self.run_cmd(['move', from_path, to_path], logger)

    def add_multiple(self, paths, logger):
        return self.run_cmd(['add'], logger, paths)

    def remove_multiple(self, paths, logger):
        return self.run_cmd(['remove'], logger, paths)

    def checkout_multiple(self, paths, logger):
        return self.run_cmd(['checkout'], logger, paths)

    def move_multiple(self, from_to_path_pairs, logger):
        # Unfortunately, we have to process each move as
        # separate commands, as 'cm move' does not support
        # passing input via STDIN
        for (from_p, to_p) in from_to_path_pairs:
            self.move(from_p, to_p, logger)

    def run_cmd(self, arguments, logger, paths=None):
        command = ['cm'] + arguments

        if paths:
            command.append('-')

        logger.log_verbose(' '.join([str(s) for s in command]))

        input_lines = [str(p) for p in paths] if paths else None
        if input_lines:
            logger.log_debug('STDIN:')
            logger.indent()
            for line in input_lines:
                logger.log_debug(line)
            logger.deindent()

        if self.pretend:
            return ''

        stdout = ueimporter.run(command,
                                logger,
                                cwd=self.workspace_root,
                                input_lines=input_lines)

        logger.indent()
        for line in stdout.split('\n'):
            if len(line) > 0:
                logger.log_debug(line)
        logger.deindent()

        return stdout
