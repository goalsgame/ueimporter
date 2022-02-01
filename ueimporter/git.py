import ueimporter


class Repo:
    def __init__(self, repo_root):
        self.repo_root = repo_root

    def to_repo_path(self, path):
        return self.repo_root.joinpath(path)

    def rev_parse(self, ref, logger):
        return self.run_cmd(['rev-parse', ref], logger)

    def diff(self, from_ref, to_ref, logger):
        arguments = [
            'diff',
            '--name-status',
            from_ref,
            to_ref]
        return self.run_cmd(arguments, logger)

    def run_cmd(self, arguments, logger):
        command = ['git'] + arguments
        logger.print(' '.join([str(s) for s in command]))
        return ueimporter.run(command, logger, cwd=self.repo_root)
