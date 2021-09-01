# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2021-09-01

### Added

#### Command-Line Interface (CLI)

- Add shell script to boot the command-line interface on Linux systems.
  - Use POSIX-compliant instructions to be compatible with multiple shells (e.g. bash, dash, ksh, zsh).
- Add `build` command to build a project runtime from its source code.
  - `--config` option to build a specific build configuration.
  - `--project` option to use an alternative project root instead of the current directory.
  - `binary` argument to choose between `client` and `server` runtimes.
- Add `clean` command to remove all built project files (binaries and intermediates).
  - `--config` option to clean a specific build configuration.
  - `--force` option to remove files even if the project is corrupted.
  - `--project` option to use an alternative project root instead of the current directory.
- Add `help` command to show available commands and their usage.
- Add `init` to create a new empty project.
  - `--as` option to assign a project name instead of using the project root directory name.
  - `--engine` option to use a specific engine version.
  - `--project` option to use an alternative project root instead of the current directory.
- Add `install` command to download, build and install a new engine version.
  - `--branch` option to download a specific branch.
  - `--commit` option to download a specific commit.
  - `--config` option to build a specific configuration.
  - `--force` option to re-install an already installed / corrupted version of the engine.
  - `--fork` option to download from a fork on GitHub.
  - `--remove-build` option to remove built files after the building stage.
  - `--remove-install` option to remove installed files after the install stage, or to stop at the building stage (if `--save-images` option is not set).
  - `--repository` option to download from a remote Git repository.
  - `--save-images` option to generate images that contain the engine installation.
  - `--tag` option to download a specific tag.
- Add `list` command to list all installed engine versions.
- Add `open` command as a placeholder for opening the editor (not supported yet).
  - `--config` option to use a specific build configuration.
  - `--engine` option to override the linked engine version.
  - `--project` option to use an alternative project root instead of the current directory.
- Add `refresh` command to check if new updates are available for a specific engine version.
  - `self` argument to check O3Tanks instead of an engine version.
- Add `run` command as a placeholder for running a project runtime (not supported yet).
  - `--config` option to use a specific build configuration.
  - `--project` option to use an alternative project root instead of the current directory.
  - `binary` argument to choose between `client` and `server` runtimes.
- Add `settings` to view / modify the project settings.
  - `--clear` option to delete the setting value.
  - `--project` option to use an alternative project root instead of the current directory.
  - `setting` argument to select all settings or a specific one.
  - `value` argument to set a new value for the setting or view its current one.
- Add `uninstall` command to uninstall an engine version.
  - `--config` option to uninstall only a specific build configuration.
  - `--force` option to remove files even if the installation is corrupted.
- Add `upgrade` command to apply new updates to the local engine installation.
  - `--no-rebuild` option to skip re-building all configurations after a successful upgrade.
  - `self` argument to check O3Tanks instead of an engine version.
- Add `version` command to show version and legal information.
- Add `-q` global option to suppress all output messages (silent mode).
- Add `-v` global option to show debug messages.
- Add `-vv` global option to show debug messages and the calling stacktrace, if an error occurs.
- Add `O3TANKS_DEV_MODE` environment variable to enable the development mode.
  - Python scripts are loaded from the host instead of from images.
- Add `O3TANKS_NO_CLI_CONTAINER` environment variable to run CLI on the host instead of in a container.

#### Containers

- Add multi-stage recipe to build Linux-based containers.
- Add `builder` container to build engines or projects from their source codes.
- Add `cli` container to interact with the user and to orchestrate the other containers.
- Add `runner` container to execute built binaries.
  - Only binaries with textual output are supported.
- Add `updater` container to download source codes from repositories.
  - Only remote Git repositories are supported.

[0.1.0]: https://github.com/loherangrin/o3tanks/releases/tag/v0.1.0
