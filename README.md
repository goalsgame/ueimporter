# ueimporter

Script used to import Unreal Engine releases into Game plastic repository.

## Table of Contents
1. [Installation](#install)
    1. [Development mode](#install-dev-mode)
    2. [Uninstallation](#install-uninstall)

2. [Usage](#usage)

3. [Development](#dev)
    1. [Testing](#dev-test)


## Installation <a name="install" />

Install a snapshot of `ueimporter` using `pip`, from the git repo root
```
$ pip install --user .
```
This enables you to invoke `ueimporter` from any directory (such as the target
plastic repo root)

Each time you want to upgrade `ueimporter` you simply pull down the latest code
and run the command again.

### Uninstall <a name="install-uninstall" />
To uninstall you simply call pip, can be invoked from anywhere:
```
$ pip uninstall ueimporter
```

### Development mode <a name="install-dev-mode" />

If you plan do do active development of `ueimporter` it's more convenient to
install in editable/development mode. This way `pip` installs thin
wrappers in it's registry that simply forwards all invocations to the code
in your git repository.

Again, from your git repo root
```
$ pip install --user -e .
```

## Usage <a name="usage" />

Here's an example that upgrade from `4.27.1` to `4.27.2`.

```
ueimporter^
 --git-repo-root="H:\UnrealEngine"^
 --from-release-tag="4.27.1-release"^
 --to-release-tag="4.27.2-release"^
 --zip-package-root="H:\Vendor\UnrealEngine"^
 --plastic-workspace-root="H:\Goals\Game"
 --plastic
```

The `--pretend` argument makes the script simply log the files it will upgrade,
without actually doing it. Remove this parameter once you feel confident
that it's what you want.

## Development <a name="dev" />

Make sure to install `ueimporter` in dev mode, as described [above](#install-dev-mode).

### Testing <a name="dev-test" />

`ueimporter` use [pytest](https://docs.pytest.org) to run unit tests, it's
automatically installed when you install `ueimporter` with `pip`.

It's simple to use, again from the repo root:
```
# Run all tests
$ pytest

# Run a specific test-file (tests/test_main.py)
$ pytest -q test_main.py

```
