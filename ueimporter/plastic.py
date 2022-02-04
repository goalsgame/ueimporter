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
        return self.run_cmd(['add', path], logger)

    def remove(self, path, logger):
        return self.run_cmd(['remove', path], logger)

    def checkout(self, path, logger):
        self.run_cmd(['checkout', path], logger)

    def move(self, from_path, to_path, logger):
        self.run_cmd(['move', from_path, to_path], logger)

    def add_multiple(self, paths, logger):
        for p in paths:
            self.add(p, logger)

    def remove_multiple(self, paths, logger):
        for p in paths:
            self.remove(p, logger)

    def checkout_multiple(self, paths, logger):
        for p in paths:
            self.checkout(p, logger)

    def move_multiple(self, from_to_path_pairs, logger):
        for (from_p, to_p) in from_to_path_pairs:
            self.move(from_p, to_p, logger)

    def run_cmd(self, arguments, logger):
        command = ['cm'] + arguments
        logger.print(' '.join([str(s) for s in command]))
        if self.pretend:
            return ''

        stdout = ueimporter.run(command, logger, cwd=self.workspace_root)

        logger.indent()
        for line in stdout.split('\n'):
            if len(line) > 0:
                logger.print(line)
        logger.deindent()

        return stdout
