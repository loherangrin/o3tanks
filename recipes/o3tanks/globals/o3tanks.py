# Copyright 2021 Matteo Grasso
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from ..utils.types import CfgPropertyKey, LinuxOSNames, ObjectEnum, OperatingSystem, OSFamilies, User
import os
import pathlib
import platform


# --- TYPES ---

class BuilderCommands(ObjectEnum):
	BUILD = "build"
	CLEAN = "clean"
	INIT = "init"
	SETTINGS = "settings"


class CliCommands(ObjectEnum):
	INSTALL = "install"
	LIST = "list"
	REFRESH = "refresh"
	UNINSTALL = "uninstall"
	UPGRADE = "upgrade"

	BUILD = BuilderCommands.BUILD.value
	CLEAN = BuilderCommands.CLEAN.value
	INIT = BuilderCommands.INIT.value
	OPEN = "open"
	RUN = "run"
	SETTINGS = BuilderCommands.SETTINGS.value

	HELP = "help"
	INFO = "info"
	VERSION = "version"


class UpdaterCommands(ObjectEnum):
	INIT = CliCommands.INIT.value
	REFRESH = CliCommands.REFRESH.value
	UPGRADE = CliCommands.UPGRADE.value


class RunnerCommands(ObjectEnum):
	OPEN = CliCommands.OPEN.value
	RUN = CliCommands.RUN.value


class GPUDrivers(ObjectEnum):
	AMD_OPEN = "amdgpu",
	AMD_PROPRIETARY = "amdgpu-pro"
	INTEL = "i915",
	NVIDIA_OPEN = "nouveau",
	NVIDIA_PROPRIETARY = "nvidia"


class Images(ObjectEnum):
	BUILDER = "builder"
	CLI = "cli"
	INSTALL_BUILDER = "install-builder"
	INSTALL_RUNNER = "install-runner"
	RUNNER = "runner"
	UPDATER = "updater"


class LongOptions(ObjectEnum):
	ALIAS = "as"
	BRANCH = "branch"
	CLEAR = "clear"
	COMMIT = "commit"
	CONFIG = "config"
	ENGINE = "engine"
	FORCE = "force"
	FORK = "fork"
	HELP = CliCommands.HELP.value
	PROJECT = "project"
	QUIET = "quiet"
	SKIP_REBUILD = "no-rebuild"
	REMOVE_BUILD = "remove-build"
	REMOVE_INSTALL = "remove-install"
	REPOSITORY = "repository"
	SAVE_IMAGES = "save-images"
	TAG = "tag"
	VERBOSE = "verbose"
	VERSION = CliCommands.VERSION.value

class ShortOptions(ObjectEnum):
	CONFIG = 'c'
	ENGINE = 'e'
	FORCE = 'f'
	HELP = 'h'
	PROJECT = 'p'
	QUIET = 'q'
	VERBOSE = 'v'


class Settings(ObjectEnum):
	ENGINE = "engine"

class EngineSettings(ObjectEnum):
	VERSION = CfgPropertyKey(Settings.ENGINE.value, "id")
	REPOSITORY = CfgPropertyKey(Settings.ENGINE.value, "repository")
	BRANCH = CfgPropertyKey(Settings.ENGINE.value, "branch")
	REVISION = CfgPropertyKey(Settings.ENGINE.value, "revision")


class Targets(ObjectEnum):
	ENGINE = "engine"
	PROJECT = "project"
	SELF = [ "self", "o3tanks" ]


class Volumes(ObjectEnum):
	SOURCE = "source"
	BUILD = "build"
	INSTALL = "install"
	PACKAGES = "packages"

# --- FUNCTIONS ---

def init_from_env(env_name, env_type, default_value):
	env_value = os.environ.get(env_name)
	if env_value is None:
		return default_value

	if env_type is bool:
		value = (env_value.lower() in [ "1", "on", "true"])
	else:
		value = env_type(env_value)

	return value


def get_os():
	os_family_name = platform.system()

	if os_family_name == "Linux":
		os_family = OSFamilies.LINUX

		if RUN_CONTAINERS:
			env_value = os.environ.get("O3TANKS_CONTAINER_OS")

			if env_value is not None:
				delimiter = ':'
				if delimiter in env_value:
					substring_1, substring_2 = env_value.split(delimiter, 1)
				else:
					substring_1 = env_value
					substring_2 = ''

				os_name = LinuxOSNames.from_value(substring_1)
				os_version = substring_2 if (len(substring_2) > 0 and substring_2 != "latest") else None

			else:
				os_name = LinuxOSNames.UBUNTU
				os_version = "20.04"

		else:
			os_name = None
			os_version = None

	elif os_family_name == "Darwin":
		os_family = OSFamilies.MAC
		os_name = None
		os_version = None

	elif os_family_name == "Windows":
		os_family = OSFamilies.WINDOWS
		os_name = None
		os_version = None

	else:
		os_family = None
		os_name = None
		os_version = None

	return OperatingSystem(os_family, os_name, os_version)


def get_default_root_dir():
	path = "/home/{}/o3tanks".format(USER_NAME)

	return (pathlib.PosixPath(path) if RUN_CONTAINERS else pathlib.PurePosixPath(path))


def get_default_data_dir(operating_system):
	if RUN_CONTAINERS:
		return None

	if operating_system.family is OSFamilies.LINUX:
		data_dir = pathlib.PosixPath.home() / ".local" / "share"

	elif operating_system.family is OSFamilies.MAC:
		data_dir = pathlib.PosixPath.home() / "Library" / "Application Support"

	elif operating_system.family is OSFamilies.WINDOWS:
		data_dir = pathlib.WindowsPath(os.environ["LOCALAPPDATA"])

	else:
		return None

	data_dir /= "o3tanks"
	return data_dir


# --- CONSTANTS ---

DEVELOPMENT_MODE = init_from_env("O3TANKS_DEV_MODE", bool, False)
RUN_CONTAINERS = not init_from_env("O3TANKS_NO_CONTAINERS", bool, False)

DISPLAY_ID = init_from_env("O3TANKS_DISPLAY_ID", int, -1)
GPU_DRIVER_NAME = init_from_env("O3TANKS_GPU", GPUDrivers, None)

OPERATING_SYSTEM = get_os()

PROJECT_EXTRA_PATH = pathlib.PurePath(".o3tanks")
PUBLIC_PROJECT_EXTRA_PATH = PROJECT_EXTRA_PATH / "public"
PRIVATE_PROJECT_EXTRA_PATH = PROJECT_EXTRA_PATH / "private"
PUBLIC_PROJECT_SETTINGS_PATH = PUBLIC_PROJECT_EXTRA_PATH / "settings.cfg"
PRIVATE_PROJECT_SETTINGS_PATH = PRIVATE_PROJECT_EXTRA_PATH / "settings.cfg"

USER_NAME = "user"
USER_GROUP = USER_NAME

REAL_USER = User(
	init_from_env("O3TANKS_REAL_USER_NAME", str, None),
	init_from_env("O3TANKS_REAL_USER_GROUP", str, None),
	init_from_env("O3TANKS_REAL_USER_UID", int, None),
	init_from_env("O3TANKS_REAL_USER_GID", int, None)
)

ROOT_DIR = init_from_env("O3TANKS_DIR", pathlib.Path, get_default_root_dir())
DATA_DIR = init_from_env("O3TANKS_DATA_DIR",pathlib.Path, get_default_data_dir(OPERATING_SYSTEM))
if DATA_DIR is not None:
	if not DATA_DIR.is_absolute():
		DATA_DIR = DATA_DIR.resolve()

RECIPES_PATH = pathlib.PurePath("recipes")
SCRIPTS_PATH = RECIPES_PATH / "o3tanks"

VERSION_MAJOR = 0
VERSION_MINOR = 2
VERSION_PATCH = 0
VERSION_PRE_RELEASE = "wip"


# --- VARIABLES ---

BIN_FILE = None
REAL_BIN_FILE = None
REAL_PROJECT_DIR = None


# --- FUNCTIONS ---

def get_bin_name():
	global BIN_FILE
	return BIN_FILE.name if BIN_FILE is not None else "o3tanks"


def get_real_bin_file():
	global REAL_BIN_FILE
	return REAL_BIN_FILE


def get_real_project_dir():
	global REAL_PROJECT_DIR
	return REAL_PROJECT_DIR


def set_bin_file(value):
	global BIN_FILE
	BIN_FILE = pathlib.PurePath(value)


def set_real_bin_file(value):
	global REAL_BIN_FILE
	REAL_BIN_FILE = pathlib.PurePath(value)


def set_real_project_dir(value):
	global REAL_PROJECT_DIR
	REAL_PROJECT_DIR = pathlib.PurePath(value)


def get_version_number():
	version = "{}.{}.{}".format(VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)

	if VERSION_PRE_RELEASE is not None:
		version += "-{}".format(VERSION_PRE_RELEASE)

	return version
