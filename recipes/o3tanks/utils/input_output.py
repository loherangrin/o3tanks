# Copyright 2021-2022 Matteo Grasso
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


from ..globals.o3tanks import CliCommands, CliSubCommands, EngineSettings, GemSettings, LongOptions, ShortOptions, get_bin_name, init_from_env
from .types import AutoEnum, JsonPropertyKey
import enum
import logging
import sys


# --- TYPES ---

class Level(enum.IntEnum):
	DEBUG = logging.DEBUG
	INFO = logging.INFO
	WARNING = logging.WARNING
	ERROR = logging.ERROR
	CRITICAL = logging.CRITICAL


class Messages(AutoEnum):
	ADD_GEM_COMPLETED = enum.auto()
	ADD_GEM_COMPLETED_SKIP_REBUILD = enum.auto()
	ADD_GEM_REBUILD = enum.auto()
	ASSET_PROCESSOR_ALREADY_RUNNING = enum.auto()
	BINARY_ERROR = enum.auto()
	BINDING_DIFFERENT_REPOSITORY = enum.auto()
	BINDING_DIFFERENT_WORKFLOW = enum.auto()
	BINDING_INSTALL_NOT_FOUND = enum.auto()
	BINDING_INVALID_REPOSITORY = enum.auto()
	BUILD_IMAGE_FROM_ARCHIVE = enum.auto()
	BUILD_IMAGE_FROM_DIRECTORY = enum.auto()
	CHANGE_OWNERSHIP_EXISTING_VOLUMES = enum.auto()
	CHANGE_OWNERSHIP_NEW_VOLUMES = enum.auto()
	CHANGE_OWNERSHIP_PROJECT = enum.auto()
	CHANGE_OWNERSHIP_SELF = enum.auto()
	CHANGED_SETTINGS = enum.auto()
	CLEAR_DIRECTORY = enum.auto()
	CONFIG_NOT_INSTALLED = enum.auto()
	CONSOLE_FILE_NOT_LOADED = enum.auto()
	CONTAINER_CLIENT_ALREADY_RUNNING = enum.auto()
	CONTAINER_ERROR = enum.auto()
	CONTEXT_NOT_FOUND = enum.auto()
	CONTINUE_QUESTION = enum.auto()
	CORRUPTED_ENGINE_SOURCE = enum.auto()
	EMPTY_COMMAND = enum.auto()
	EMPTY_TARGET = enum.auto()
	ENGINE_BUILD_NOT_FOUND = enum.auto()
	ENGINE_INSTALL_NOT_FOUND = enum.auto()
	ENGINE_SOURCE_NOT_FOUND = enum.auto()
	ERROR_BUILD_IMAGE = enum.auto()
	ERROR_SAVE_IMAGE = enum.auto()
	EXCEED_MAX_PORT_ATTEMPTS = enum.auto()
	EXIT_CODE_NOT_FOUND = enum.auto()
	EXPORT_ARCHIVE_COMPLETED = enum.auto()
	EXPORT_IMAGE_COMPLETED = enum.auto()
	EXPORT_INVALID_CONFIG_AND_BUNDLE = enum.auto()
	EXPORT_MISSING_BINARY = enum.auto()
	EXPORT_MISSING_ASSETS = enum.auto()
	EXPORT_SKIP_BUILD_SOURCE = enum.auto()
	EXPORT_SKIP_PACK_BUNDLES = enum.auto()
	EXPORT_SKIP_PROCESS_ASSETS = enum.auto()
	FAST_FORWARD_ONLY = enum.auto()
	GEM_ALREADY_ADDED = enum.auto()
	GEM_DIFFERENT_VALUES = enum.auto()
	GEM_NOT_ACTIVE = enum.auto()
	INCOMPATIBLE_BUILD_PROJECT_AND_WORKFLOW = enum.auto()
	INCOMPATIBLE_FORK_OPTIONS = enum.auto()
	INCOMPATIBLE_GEM_SETTINGS = enum.auto()
	INCOMPATIBLE_REVISION_OPTIONS = enum.auto()
	INIT_COMPLETED = enum.auto()
	INSTALL_ALREADY_EXISTS = enum.auto()
	INSTALL_ALREADY_EXISTS_DIFFERENT_WORKFLOW = enum.auto()
	INSTALL_AND_CONFIG_ALREADY_EXISTS = enum.auto()
	INSTALL_ENGINE_COMPLETED = enum.auto()
	INSTALL_GEM_COMPLETED = enum.auto()
	INSTALL_APPLICATION_PACKAGES = enum.auto()
	INSTALL_MAIN_SYSTEM_PACKAGES = enum.auto()
	INSTALL_PORTED_SYSTEM_PACKAGES = enum.auto()
	INSTALL_EXTERNAL_SYSTEM_PACKAGES_1 = enum.auto()
	INSTALL_EXTERNAL_SYSTEM_PACKAGES_2 = enum.auto()
	INSTALL_OTHER_COMMANDS = enum.auto()
	INSTALL_PROJECT_COMPLETED = enum.auto()
	INVALID_ANSWER = enum.auto()
	INVALID_ARCHIVE_TYPE = enum.auto()
	INVALID_BINARY = enum.auto()
	INVALID_BUILD_WORKFLOW = enum.auto()
	INVALID_COMMAND = enum.auto()
	INVALID_COMMIT = enum.auto()
	INVALID_CONFIG = enum.auto()
	INVALID_CONSOLE_COMMAND = enum.auto()
	INVALID_CONSOLE_VARIABLE = enum.auto()
	INVALID_CONTAINER_USER = enum.auto()
	INVALID_DESERIALIZATION = enum.auto()
	INVALID_DESERIALIZATION_CONTAINER = enum.auto()
	INVALID_DESERIALIZATION_INPUT = enum.auto()
	INVALID_DESERIALIZATION_LENGTH = enum.auto()
	INVALID_DESERIALIZATION_OUTPUT = enum.auto()
	INVALID_DIRECTORY = enum.auto()
	INVALID_DISPLAY = enum.auto()
	INVALID_ENGINE_SOURCE = enum.auto()
	INVALID_GEM_REFERENCE = enum.auto()
	INVALID_GEM_SETTING = enum.auto()
	INVALID_GEM_SOURCE = enum.auto()
	INVALID_GEM_TEMPLATE = enum.auto()
	INVALID_GEM_TYPE = enum.auto()
	INVALID_FORK = enum.auto()
	INVALID_CHANGES = enum.auto()
	INVALID_CURRENT_USER = enum.auto()
	INVALID_GPU = enum.auto()
	INVALID_IMAGE_IN_NO_CONTAINERS_MODE = enum.auto()
	INVALID_INSTALL_OPTIONS_INCREMENTAL = enum.auto()
	INVALID_INSTALL_OPTIONS_SAVE_IMAGES = enum.auto()
	INVALID_INSTANCE_FILE = enum.auto()
	INVALID_LFS = enum.auto()
	INVALID_LOCAL_BRANCH = enum.auto()
	INVALID_REMOTE_BRANCH = enum.auto()
	INVALID_DEPENDENCY_RESULT_VALUE = enum.auto()
	INVALID_NETWORK = enum.auto()
	INVALID_OPERATING_SYSTEM = enum.auto()
	INVALID_OPTION = enum.auto()
	INVALID_PACKAGE_MANAGER_RESULT = enum.auto()
	INVALID_PROJECT_NAME = enum.auto()
	INVALID_PROJECT_NAME_FOR_IMAGES = enum.auto()
	INVALID_PROPERTY_INDEX = enum.auto()
	INVALID_PROPERTY_KEY = enum.auto()
	INVALID_PROPERTY_VALUE = enum.auto()
	INVALID_REPOSITORY = enum.auto()
	INVALID_REPOSITORY_URL = enum.auto()
	INVALID_REPOSITORY_URL_HASH = enum.auto()
	INVALID_SERIALIZATION = enum.auto()
	INVALID_SERIALIZATION_INPUT = enum.auto()
	INVALID_SERVER_ADDRESS = enum.auto()
	INVALID_SERVER_PORT = enum.auto()
	INVALID_SETTING_DATA = enum.auto()
	INVALID_SETTING_FILE = enum.auto()
	INVALID_SETTING_NAME = enum.auto()
	INVALID_SETTING_SECTION = enum.auto()
	INVALID_SETTING_SYNTAX = enum.auto()
	INVALID_SUBCOMMAND = enum.auto()
	INVALID_TARGET = enum.auto()
	INVALID_TEMPLATE = enum.auto()
	INVALID_USER_NAMESPACE = enum.auto()
	INVALID_VARIANT = enum.auto()
	INVALID_VERSION = enum.auto()
	INVALID_VOLUME_DIRECTORY = enum.auto()
	INVALID_VOLUME_TYPE = enum.auto()
	INSERT_VERSION_NAME = enum.auto()
	INSTALL_QUESTION = enum.auto()
	IS_DEVELOPMENT_MODE = enum.auto()
	IS_NO_CONTAINERS_MODE = enum.auto()
	LFS_NOT_FOUND = enum.auto()
	MISSING_ASSET_PROCESSOR = enum.auto()
	MISSING_BINARY = enum.auto()
	MISSING_BOUND_VERSION = enum.auto()
	MISSING_BUNDLE = enum.auto()
	MISSING_CLANG = enum.auto()
	MISSING_CMAKE = enum.auto()
	MISSING_CONFIG = enum.auto()
	MISSING_DISPLAY = enum.auto()
	MISSING_DOCKER = enum.auto()
	MISSING_GEM_IN_WORKSPACE = enum.auto()
	MISSING_GEM_REFERENCE = enum.auto()
	MISSING_GPU = enum.auto()
	MISSING_INSTALL_AND_CONFIG = enum.auto()
	MISSING_INSTALL_ENGINE = enum.auto()
	MISSING_INSTALL_ENGINE_CONFIG = enum.auto()
	MISSING_INSTALL_ENGINE_PROJECT= enum.auto()
	MISSING_INSTALL_GEM = enum.auto()
	MISSING_LEVEL = enum.auto()
	MISSING_MODULE = enum.auto()
	MISSING_PACKAGES = enum.auto()
	MISSING_PROJECT = enum.auto()
	MISSING_PROPERTY = enum.auto()
	MISSING_PYTHON = enum.auto()
	MISSING_REPOSITORY = enum.auto()
	MISSING_SERVER_FILE = enum.auto()
	MISSING_SETTING_KEY = enum.auto()
	MISSING_VERSION = enum.auto()
	MULTIPLE_GEMS_IN_WORKSPACE = enum.auto()
	NO_UPDATES = enum.auto()
	NO_UPDATES_IF_DETACHED = enum.auto()
	PACKAGE_MANAGER_ERROR = enum.auto()
	PROJECT_DIR_EMPTY = enum.auto()
	PROJECT_DIR_NOT_EMPTY = enum.auto()
	PROJECT_NOT_FOUND = enum.auto()
	REMOVE_GEM_COMPLETED = enum.auto()
	REMOVE_GEM_COMPLETED_SKIP_REBUILD = enum.auto()
	REMOVE_GEM_REBUILD = enum.auto()
	RUN_EXTERNAL_COMMANDS = enum.auto()
	RUN_PRIVILEGED_COMMANDS = enum.auto()
	RUN_RESUME_COMMAND = enum.auto()
	SAVE_QUESTION = enum.auto()
	SETTINGS_NOT_FOUND = enum.auto()
	SERVER_PORT_ALREADY_USED = enum.auto()
	SOURCE_ALREADY_EXISTS = enum.auto()
	SOURCE_NOT_FOUND = enum.auto()
	START_DOWNLOAD_SOURCE = enum.auto()
	START_EXPORT_BUILD_BINARY = enum.auto()
	START_EXPORT_PROCESS_ASSETS = enum.auto()
	START_EXPORT_PACK_ASSETS_TO_BUNDLES = enum.auto()
	START_EXPORT_SAVE_IMAGE = enum.auto()
	UNCOMPLETED_ADD_GEM = enum.auto()
	UNCOMPLETED_BUILD_PROJECT = enum.auto()
	UNCOMPLETED_CHECK_GEM_RESOLVE_RELATIVE_PATH = enum.auto()
	UNCOMPLETED_EXPORT = enum.auto()
	UNCOMPLETED_IMAGE = enum.auto()
	UNCOMPLETED_INIT_ENGINE = enum.auto()
	UNCOMPLETED_INIT_GEM = enum.auto()
	UNCOMPLETED_INIT_PROJECT = enum.auto()
	UNCOMPLETED_INSTALL = enum.auto()
	UNCOMPLETED_UPGRADE = enum.auto()
	UNCOMPLETED_MISSING_INSTALL = enum.auto()
	UNCOMPLETED_REFRESH = enum.auto()
	UNCOMPLETED_REGISTRATION = enum.auto()
	UNCOMPLETED_SOLUTION_GENERATION = enum.auto()
	UNCOMPLETED_UNINSTALL = enum.auto()
	UNINSTALL_ENGINE_COMPLETED = enum.auto()
	UNINSTALL_GEM_COMPLETED = enum.auto()
	UNMANAGED_GEMS = enum.auto()
	UNREACHABLE_X11_DISPLAY = enum.auto()
	UNSUPPORTED_CONTAINERS_AND_NO_CLIENT = enum.auto()
	UNSUPPORTED_OPERATING_SYSTEM_FOR_REQUIREMENTS = enum.auto()
	UNSUPPORTED_INSERT_SETTING_SECTION = enum.auto()
	UPDATES_AVAILABLE = enum.auto()
	UPGRADE_ENGINE_COMPLETED = enum.auto()
	UPGRADE_ENGINE_COMPLETED_SKIP_REBUILD = enum.auto()
	UPGRADE_ENGINE_COMPLETED_SOURCE_ONLY = enum.auto()
	UPGRADE_GEM_COMPLETED = enum.auto()
	UPGRADE_SELF_COMPLETED = enum.auto()
	VERSION_ALREADY_EXISTS = enum.auto()
	VERSION_NOT_FOUND = enum.auto()
	VERSION_NOT_INSTALLED = enum.auto()
	VOLUME_NOT_FOUND = enum.auto()
	VOLUMES_DIR_NOT_FOUND = enum.auto()
	WORKSPACE_MANIFEST_ALREADY_EXISTS = enum.auto()


class MessageFormatter(logging.Formatter):
	def __init__(self):
		super().__init__("%(levelname)s: %(message)s")

	def format(self, record):
		if record.levelno == logging.INFO:
			message = record.msg
		else:
			message = super().format(record)

		return message


# --- VARIABLES ---

LOGGER = None
PRINT_CALLSTACK = False
VERBOSE = init_from_env("O3TANKS_VERBOSE", int, 0)


# --- FUNCTIONS ---

def ask_for_confirmation(question_id):
	if not is_tty():
		return True

	question = "{}? [y/n] ".format(get_message_text(question_id))

	while True:
		answer = input(question).lower()

		if answer == 'y' or answer == "yes":
			return True
		elif answer == 'n' or answer == "no":
			return False
		else:
			print_msg(Level.WARNING, Messages.INVALID_ANSWER)


def ask_for_input(description_id, required = True):
	if not is_tty():
		return ''

	description = "{}: ".format(get_message_text(description_id))

	while True:
		answer = input(description)

		if (len(answer) > 0) or not required:
			return answer


def get_message_text(message_id, *args, **kwargs):
	if message_id == Messages.ADD_GEM_COMPLETED:
		message_text = "Gem '{}' is now active"
	elif message_id == Messages.ADD_GEM_COMPLETED_SKIP_REBUILD:
		message_text = "Gem '{}' is now active. Please use '" + print_command(CliCommands.BUILD) + "' to rebuild the project and make changes to take effect"
	elif message_id == Messages.ADD_GEM_REBUILD:
		message_text = "Gem '{}' is now active. Rebuilding the project to make changes to take effect..."
	elif message_id == Messages.ASSET_PROCESSOR_ALREADY_RUNNING:
		message_text = "An instance of Asset Processor is already registered for this project. Please close it before try to run another one. If none is left, please delete the lock file at: {}"
	elif message_id == Messages.BINARY_ERROR:
		message_text = "An error occurred while executing a required binary: {}"
	elif message_id == Messages.BINDING_DIFFERENT_REPOSITORY:
		message_text = "Repository of installed {0} differs from the one required by the project. Please use '" + print_command(CliCommands.SETTINGS) + "' to clear the {0} version and then re-install it with a different name"
	elif message_id == Messages.BINDING_DIFFERENT_WORKFLOW:
		message_text = "Installed engine uses a different build workflow ({}) rather than the one required by the project ({}). Please use '" + print_command(CliCommands.SETTINGS) + "' to clear the worklow or change the engine version to a compatible one"
	elif message_id == Messages.BINDING_INSTALL_NOT_FOUND:
		message_text = "Project is bound to a non-existing {}. Please use '" + print_command(CliCommands.SETTINGS) + "' to clear it or use '" + print_command(CliCommands.INSTALL) + "' to force a new re-installation"
	elif message_id == Messages.BINDING_INVALID_REPOSITORY:
		message_text = "Invalid repository URL for {}. Please use '" + print_command(CliCommands.SETTINGS) + "' to verify that: (1) '" + print_setting(EngineSettings.REPOSITORY) + "' doesn't contains invalid characters (2) '" + print_setting(EngineSettings.BRANCH) + "' and '" + print_setting(EngineSettings.REVISION) + "' aren't both set"
	elif message_id == Messages.BUILD_IMAGE_FROM_ARCHIVE:
		message_text = "Building the image '{}' from the archive at '{}'..."
	elif message_id == Messages.BUILD_IMAGE_FROM_DIRECTORY:
		message_text = "Building the image '{}' from the directory at '{}'..."
	elif message_id == Messages.CHANGE_OWNERSHIP_EXISTING_VOLUMES:
		message_text = "Ownership of volumes must be resetted to be accessible by the containers"
	elif message_id == Messages.CHANGE_OWNERSHIP_NEW_VOLUMES:
		message_text = "New volumes were created, but their ownership must be changed to be owned by the containers user"
	elif message_id == Messages.CHANGE_OWNERSHIP_PROJECT:
		message_text = "Ownership of project directory must be resetted to be accessible by the containers"
	elif message_id == Messages.CHANGE_OWNERSHIP_SELF:
		message_text = "Ownership of O3Tanks directory must be resetted to be accessible by the updater"
	elif message_id == Messages.CHANGED_SETTINGS:
		message_text = "Following project settings are changed:"
	elif message_id == Messages.CLEAR_DIRECTORY:
		message_text = "Following directory will be removed: {}"
	elif message_id == Messages.CONFIG_NOT_INSTALLED:
		message_text = "No config '{}' was found for version '{}'"
	elif message_id == Messages.CONSOLE_FILE_NOT_LOADED:
		message_text = "'{0}' cannot be loaded automatically when at least one console variable or console command is provided. If still needed, please add it manually using: " + print_option(LongOptions.CONSOLE_COMMAND) + " exec[{0}]"
	elif message_id == Messages.CONTAINER_CLIENT_ALREADY_RUNNING:
		message_text = "Another container client is already running, it will be re-used"
	elif message_id == Messages.CONTAINER_ERROR:
		message_text = "Container from image '{}' failed with error code: {}"
	elif message_id == Messages.CONTEXT_NOT_FOUND:
		message_text = "Unable to retrieve the building context at: {}"
	elif message_id == Messages.CONTINUE_QUESTION:
		message_text = "Do you want to continue"
	elif message_id == Messages.CORRUPTED_ENGINE_SOURCE:
		message_text = "One or more required files are missing in the engine source directory ({}). Please use '" + print_command(CliCommands.UNINSTALL) + " " + print_option(LongOptions.FORCE) + "' to remove it and '" + print_command(CliCommands.INSTALL) + "' to download it again"
	elif message_id == Messages.EMPTY_COMMAND:
		message_text = "No command was provided. Please use '" + print_command(CliCommands.HELP) + "' to see all available commands"
	elif message_id == Messages.EMPTY_TARGET:
		message_text = "No target was provided for the command. Please use '" + print_command(CliCommands.HELP) + "' to see the correct syntax"
	elif message_id == Messages.ENGINE_BUILD_NOT_FOUND:
		message_text = "Unable to get the volume '{}' where the built files are generated"
	elif message_id == Messages.ENGINE_INSTALL_NOT_FOUND:
		message_text = "Unable to get the volume '{}' where the engine is installed"
	elif message_id == Messages.ENGINE_SOURCE_NOT_FOUND:
		message_text = "Unable to get the volume '{}' where the source code is stored"
	elif message_id == Messages.ERROR_BUILD_IMAGE:
		message_text = "Unable to build the missing image: {}. Please build it manually"
	elif message_id == Messages.ERROR_SAVE_IMAGE:
		message_text = "Unable to save the required container image: {}"
	elif message_id == Messages.EXCEED_MAX_PORT_ATTEMPTS:
		message_text = "Unable to find an empty port on your system (exceeding max. attempts: {})"
	elif message_id == Messages.EXIT_CODE_NOT_FOUND:
		message_text = "Unable to calculate the exit code of the last container from image '{}'. Assuming it was an error..."
	elif message_id == Messages.EXPORT_ARCHIVE_COMPLETED:
		message_text = "Operation completed! The exported package is available at: {}"
	elif message_id == Messages.EXPORT_IMAGE_COMPLETED:
		message_text = "Operation completed! The exported image is available in your container repository with tag: {}"
	elif message_id == Messages.EXPORT_INVALID_CONFIG_AND_BUNDLE:
		message_text = "Asset bundles cannot be used with '{}' config. Please remove " + print_option(LongOptions.BUNDLE) + " option to use processed asset files instead"
	elif message_id == Messages.EXPORT_MISSING_BINARY:
		message_text = "Unable to find a built binary for '{}' config with '{}' variant. Please remove " + print_option(LongOptions.SKIP_BUILD) + " option or use " + print_command(CliCommands.BUILD) + " command to build it manually, then try again"
	elif message_id == Messages.EXPORT_MISSING_ASSETS:
		message_text = "Unable to find processed assets.  Please remove " + print_option(LongOptions.SKIP_BUILD) + " option and try again. Please remove " + print_option(LongOptions.SKIP_BUILD) + " option or use " + print_command(CliCommands.BUILD) + " " + CliSubCommands.ASSETS + " command to process them manually, then try again"
	elif message_id == Messages.EXPORT_SKIP_BUILD_SOURCE:
		message_text = "Re-using a previous project build"
	elif message_id == Messages.EXPORT_SKIP_PACK_BUNDLES:
		message_text = "Re-using existing bundle files: {}"
	elif message_id == Messages.EXPORT_SKIP_PROCESS_ASSETS:
		message_text = "Re-using previous processed assets"	
	elif message_id == Messages.FAST_FORWARD_ONLY:
		message_text = "Your version has one or more commits ahead the remote and cannot be upgraded automatically using fast-forward. Please 'merge' it manually using an external GIT client"
	elif message_id == Messages.GEM_ALREADY_ADDED:
		message_text = "Gem already exists in this project. Operation will be aborted"
	elif message_id == Messages.GEM_DIFFERENT_VALUES:
		message_text = "Another gem is using the same {} '{}', but with a different {}. Please remove it before installing this new one"
	elif message_id == Messages.GEM_NOT_ACTIVE:
		message_text = "No '{}' gem was found in this project. It may has been alredy disabled"
	elif message_id == Messages.INCOMPATIBLE_BUILD_PROJECT_AND_WORKFLOW:
		message_text = "Command '" + print_command(CliCommands.BUILD) + "' cannot be used when build workflow is set to '{}'. Please use '" + print_command(CliCommands.SETTINGS) + "' to point to another engine version and then try again"
	elif message_id == Messages.INCOMPATIBLE_FORK_OPTIONS:
		message_text = "Option '" + print_option(LongOptions.FORK) + "' and '" + print_option(LongOptions.REPOSITORY) + "' are incompatible. Please set only one"
	elif message_id == Messages.INCOMPATIBLE_GEM_SETTINGS:
		message_text = "Settings '" + print_setting(GemSettings.ABSOLUTE_PATH) + "' (or '" + print_setting(GemSettings.RELATIVE_PATH) + "') and '" + print_setting(GemSettings.REPOSITORY) + "' are incompatible. Please set only one for gem at index '{}'"
	elif message_id == Messages.INCOMPATIBLE_REVISION_OPTIONS:
		message_text = "Option '" + print_option(LongOptions.BRANCH) + "', '" + print_option(LongOptions.COMMIT) + "' and '" + print_option(LongOptions.TAG) + "' are incompatible. Please set only one"
	elif message_id == Messages.INIT_COMPLETED:
		message_text = "Operation completed! Your new project is available at: {}"
	elif message_id == Messages.INSERT_VERSION_NAME:
		message_text = "Insert a name for the new installation"
	elif message_id == Messages.INSTALL_ALREADY_EXISTS:
		message_text = "{} version '{}' is already installed. Please use '" + print_command(CliCommands.REFRESH) + "' to check if updates are available"
	elif message_id == Messages.INSTALL_ALREADY_EXISTS_DIFFERENT_WORKFLOW:
		message_text = "Engine version '{}' is already installed with a different build workflow ({})"
	elif message_id == Messages.INSTALL_AND_CONFIG_ALREADY_EXISTS:
		message_text = "Permutation with config '{1}' and variant '{2}' for engine version '{0}' is already installed. Please use '" + print_command(CliCommands.REFRESH) + "' to check if updates are available"
	elif message_id == Messages.INSTALL_ENGINE_COMPLETED:
		message_text = "Operation completed! Version '{}' is now usable"
	elif message_id == Messages.INSTALL_GEM_COMPLETED:
		message_text = "Operation completed! You can now add gem version '{}' to your projects"
	elif message_id == Messages.INSTALL_APPLICATION_PACKAGES:
		message_text = "- Install these application modules:"
	elif message_id == Messages.INSTALL_MAIN_SYSTEM_PACKAGES:
		message_text = "- Install these missing packages using your package manager:"
	elif message_id == Messages.INSTALL_PORTED_SYSTEM_PACKAGES:
		message_text = "- Download and manually install these additional packages from a different release of your distro:"
	elif message_id == Messages.INSTALL_EXTERNAL_SYSTEM_PACKAGES_1:
		message_text = "- Add these repositories to your package manager:"
	elif message_id == Messages.INSTALL_EXTERNAL_SYSTEM_PACKAGES_2:
		message_text = "- Install these additional packages from the previous repositories:"
	elif message_id == Messages.INSTALL_OTHER_COMMANDS:
		message_text = "- Execute these additional commands:"
	elif message_id == Messages.INSTALL_PROJECT_COMPLETED:
		message_text = "Operation completed! The project is now ready to be used at: {}"
	elif message_id == Messages.INSTALL_QUESTION:
		message_text = "Do you want to install"
	elif message_id == Messages.INVALID_ANSWER:
		message_text = "Invalid answer. Please try again"
	elif message_id == Messages.INVALID_ARCHIVE_TYPE:
		message_text = "Invalid archive type: {}"
	elif message_id == Messages.INVALID_BINARY:
		message_text = "Unsupported binary: {}"
	elif message_id == Messages.INVALID_BUILD_WORKFLOW:
		message_text = "Unsupported build workflow: {}"
	elif message_id == Messages.INVALID_CHANGES:
		message_text = "Unable to parse changes"
	elif message_id == Messages.INVALID_COMMAND:
		message_text = "Invalid command: {}. Please use '" + print_command(CliCommands.HELP) + "' to see all available commands"
	elif message_id == Messages.INVALID_COMMIT:
		message_text = "Invalid commit. Please provide a 40 digits hash value"
	elif message_id == Messages.INVALID_CONFIG:
		message_text = "Invalid configuration name: {}"
	elif message_id == Messages.INVALID_CONSOLE_COMMAND:
		message_text = "Unable to parse a console command due to an invalid syntax: {}.\nPlease use the following formats: <command_name>() or <command_name>(<argument_0>,<...>)"
	elif message_id == Messages.INVALID_CONSOLE_VARIABLE:
		message_text = "Unable to parse a console variable  due to an invalid syntax: {}.\nPlease use the following format: <variable_name>=<variable_value>"
	elif message_id == Messages.INVALID_CONTAINER_USER:
		message_text = "Unable to calculate the container user"
	elif message_id == Messages.INVALID_DESERIALIZATION:
		message_text = "Unable to deserialize an item: {}. Reason: unsupported output type '{}'"
	elif message_id == Messages.INVALID_DESERIALIZATION_CONTAINER:
		message_text = "Unable to deserialize items starting from index '{}'. Reason: unsupported container type '{}'"
	elif message_id == Messages.INVALID_DESERIALIZATION_INPUT:
		message_text = "Unable to deserialize an item: {}. Reason: only '{}' are supported as input type, received '{}'"
	elif message_id == Messages.INVALID_DESERIALIZATION_LENGTH:
		message_text = "Unable to deserialize items starting from index '{}'. Reason: {} index '{}' is exceeding the number of provided arguments ({})"
	elif message_id == Messages.INVALID_DESERIALIZATION_OUTPUT:
		message_text = "Unable to deserialize an item: {}. Reason: it isn't a valid value for type '{}'"
	elif message_id == Messages.INVALID_DIRECTORY:
		message_text = "Directory path is invalid or empty"
	elif message_id == Messages.INVALID_DISPLAY:
		message_text = "Unable to find a valid X11 socket for display :{} at: {}"
	elif message_id == Messages.INVALID_ENGINE_SOURCE:
		message_text = "Engine source files are missing or corrupted. No 'engine.json' manifest was found in the root directory"
	elif message_id == Messages.INVALID_GEM_REFERENCE:
		message_text = "Invalid gem reference: {}"
	elif message_id == Messages.INVALID_GEM_SETTING:
		message_text = "Invalid gem setting: {}"
	elif message_id == Messages.INVALID_GEM_SOURCE:
		message_text = "Gem source files are missing or corrupted. No 'gem.json' manifest was found in the root directory at: {}"
	elif message_id == Messages.INVALID_GEM_TEMPLATE:
		message_text = "Invalid gem template: {}"
	elif message_id == Messages.INVALID_GEM_TYPE:
		message_text = "Invalid gem type: {}"
	elif message_id == Messages.INVALID_FORK:
		message_text = "Invalid fork syntax. Please provide <username>/<fork_name>"
	elif message_id == Messages.INVALID_CURRENT_USER:
		message_text = "Unable to calculate the current user"
	elif message_id == Messages.INVALID_GPU:
		message_text = "Unable to activate hardware acceleration since current GPU drivers ({}) aren't supported. Falling back to software rendering..."
	elif message_id == Messages.INVALID_IMAGE_IN_NO_CONTAINERS_MODE:
		message_text = "Only image names are accepted when active mode is active. Received: {}"
	elif message_id == Messages.INVALID_INSTALL_OPTIONS_INCREMENTAL:
		message_text = "Invalid options combination. Incremental mode can be used only when '" + print_option(LongOptions.WORKFLOW_SDK) + "' is set"
	elif message_id == Messages.INVALID_INSTALL_OPTIONS_SAVE_IMAGES:
		message_text = "Invalid options combination. Images can be generated only when '" + print_option(LongOptions.WORKFLOW_SDK) + "' is set"
	elif message_id == Messages.INVALID_INSTANCE_FILE:
		message_text = "One or more required properties are missing in the instance definition at: {}"
	elif message_id == Messages.INVALID_LFS:
		message_text = "Invalid LFS URL: {}"
	elif message_id == Messages.INVALID_LOCAL_BRANCH:
		message_text = "Unable to parse the local branch"
	elif message_id == Messages.INVALID_REMOTE_BRANCH:
		message_text = "Unable to parse the remote branch tracked by local branch '{}'"
	elif message_id == Messages.INVALID_DEPENDENCY_RESULT_VALUE:
		message_text = "Invalid dependency result value: {}"
	elif message_id == Messages.INVALID_NETWORK:
		message_text = "No network was found with name: {}. Please check the value of O3TANKS_NETWORK or create the network using 'docker network create'"
	elif message_id == Messages.INVALID_OPERATING_SYSTEM:
		message_text = "The current operating system is not supported: {}"
	elif message_id == Messages.INVALID_OPTION:
		message_text = "Unsupported option: {}"
	elif message_id == Messages.INVALID_PACKAGE_MANAGER_RESULT:
		message_text = "Unable to parse a returning line of the package manager: {}"
	elif message_id == Messages.INVALID_PROJECT_NAME:
		message_text = "Unable to retrieve the project name from the manifest file"
	elif message_id == Messages.INVALID_PROJECT_NAME_FOR_IMAGES:
		message_text = "Project name '{}' contains characters that aren't allowed for a container image name. Please use " + print_option(LongOptions.ALIAS, "<string>") + " option to provide a valid name"
	elif message_id == Messages.INVALID_PROPERTY_INDEX:
		message_text = "Index for property '{}' exceeds its size: {}"
	elif message_id == Messages.INVALID_PROPERTY_KEY:
		message_text = "Invalid key for property '{}'. Expecting: {}"
	elif message_id == Messages.INVALID_PROPERTY_VALUE:
		message_text = "Invalid value for property '{}'. Expecting: {}"
	elif message_id == Messages.INVALID_REPOSITORY:
		message_text = "Unable to retrieve repository URL from the engine installation"
	elif message_id == Messages.INVALID_REPOSITORY_URL:
		message_text = "Invalid repository. Only HTTP(s)/SSH URL to a remote GIT repository are supported"
	elif message_id == Messages.INVALID_REPOSITORY_URL_HASH:
		message_text = "Repository cannot contain '#' symbols"
	elif message_id == Messages.INVALID_SERIALIZATION:
		message_text = "Unable to serialize an item: {}. Reason: unsupported output type '{}'"
	elif message_id == Messages.INVALID_SERIALIZATION_INPUT:
		message_text = "Unable to serialize an item: {}. Reason: only '{}' are supported as input type, received '{}'"
	elif message_id == Messages.INVALID_SERVER_ADDRESS:
		message_text = "Invalid server address: {}. Please use the following formats: <hostname>:<port> or <ip_v4>:<port>"
	elif message_id == Messages.INVALID_SERVER_PORT:
		message_text = "Invalid server port: {}. Please use only an integer value"
	elif message_id == Messages.INVALID_SETTING_DATA:
		message_text = "Setting file at '{}' is corrupted: {}"
	elif message_id == Messages.INVALID_SETTING_FILE:
		message_text = "Unable to determine the file where setting '{}.{}' should be"
	elif message_id == Messages.INVALID_SETTING_NAME:
		message_text = "Unsupported setting name: {}"
	elif message_id == Messages.INVALID_SETTING_SECTION:
		message_text = "Unsupported section name: {}"
	elif message_id == Messages.INVALID_SETTING_SYNTAX:
		message_text = "Invalid syntax for setting: {}. Expecting: section.name or section[index].name"
	elif message_id == Messages.INVALID_SUBCOMMAND:
		message_text = "Invalid subcommand: {1}. Please use '" + print_command(CliCommands.HELP) + " {0}' to see all available subcommands for '{0}'"
	elif message_id == Messages.INVALID_TARGET:
		message_text = "Unsupported target: {}"
	elif message_id == Messages.INVALID_TEMPLATE:
		message_text = "Unsupported template: {}"
	elif message_id == Messages.INVALID_USER_NAMESPACE:
		message_text = "Unable to calculate the user namespace for the container user"
	elif message_id == Messages.INVALID_VARIANT:
		message_text = "Invalid variant name: {}"
	elif message_id == Messages.INVALID_VERSION:
		message_text = "Invalid version name: {}. Only following characters are allowed: lowercase characters, numbers, dots, hyphens and underscores"
	elif message_id == Messages.INVALID_VOLUME_DIRECTORY:
		message_text = "A directory was expected for volume '{}' at: {}"
	elif message_id == Messages.INVALID_VOLUME_TYPE:
		message_text = "Unable to determine the type of a volume: {}"
	elif message_id == Messages.IS_DEVELOPMENT_MODE:
		message_text = "[Running in DEV_MODE]"
	elif message_id == Messages.IS_NO_CONTAINERS_MODE:
		message_text = "[Running in NO_CONTAINERS_MODE]"
	elif message_id == Messages.LFS_NOT_FOUND:
		message_text = "Unable to read LFS URL to setup '{}' remote"
	elif message_id == Messages.MISSING_ASSET_PROCESSOR:
		message_text = "A running instance of the asset processor is required, but none was found"
	elif message_id == Messages.MISSING_BINARY:
		message_text = "No binary exists at: {}. Do you have built the project with: config='{}', variant='{}', binary='{}'?"
	elif message_id == Messages.MISSING_BOUND_VERSION:
		message_text = "No {0} version '{1}' was found. Please use '" + print_command(CliCommands.INSTALL) + " {0}' to download it or '" + print_command(CliCommands.SETTINGS) + "' to clear it from project settings"
	elif message_id == Messages.MISSING_BUNDLE:
		message_text = "Unable to find a bundle file: {}. Please use '" + print_command(CliCommands.EXPORT) + " " +  CliSubCommands.ASSETS.value + "' to create it and try again"
	elif message_id == Messages.MISSING_CLANG:
		message_text = "Unable to find 'clang'. Supported versions: 6, 11, 12, 14"
	elif message_id == Messages.MISSING_CMAKE:
		message_text = "Unable to find 'cmake'.\nPlease refer to CMake official documentation for installation instructions:\nhttps://cmake.org/install"
	elif message_id == Messages.MISSING_CONFIG:
		message_text = "No engine config was provided"
	elif message_id == Messages.MISSING_DISPLAY:
		message_text = "No DISPLAY was found"
	elif message_id == Messages.MISSING_DOCKER:
		message_text = "Unable to find 'docker'"
	elif message_id == Messages.MISSING_GEM_REFERENCE:
		message_text = "No attribute is set to identify the gem with index '{}'"
	elif message_id == Messages.MISSING_GEM_IN_WORKSPACE:
		message_text = "No gem was found in the manifest of repository at: {}"
	elif message_id == Messages.MISSING_GPU:
		message_text = "Hardware acceleration is disabled since no GPU was found (or it was forced to NONE)"
	elif message_id == Messages.MISSING_INSTALL_ENGINE:
		message_text = "The engine version required by this project is not installed, but it is available at: {}"
	elif message_id == Messages.MISSING_INSTALL_ENGINE_CONFIG:
		message_text = "Engine version '{}' required by this project is installed, but it hasn't the following permutation: config '{}' - variant '{}'"
	elif message_id == Messages.MISSING_INSTALL_ENGINE_PROJECT:
		message_text = "Engine version '{}' is installed with an engine-centric workflow and doesn't include this project. Please use '" + print_command(CliCommands.SETTINGS) + "' to select another engine with a project-centric workflow"
	elif message_id == Messages.MISSING_INSTALL_GEM:
		message_text = "A gem for this project is not installed, but it is available at: {}"
	elif message_id == Messages.MISSING_INSTALL_AND_CONFIG:
		message_text = "Unable to find an engine installation for version '{}', config '{}' an variant '{}'. Please use '" + print_command(CliCommands.INSTALL) + "' to add it and try again"
	elif message_id == Messages.MISSING_LEVEL:
		message_text = "Unable to find a level file at: {}"
	elif message_id == Messages.MISSING_MODULE:
		message_text = "Unable to find '{0}' module.\nPlease add it to your Python installation using:\npython -m pip install {0}"
	elif message_id == Messages.MISSING_PACKAGES:
		message_text = "At least one dependency to use O3DE engine is missing.\nPlease review and execute the following steps to fix the issue."
	elif message_id == Messages.MISSING_PROJECT:
		message_text = "Project cannot be empty"
	elif message_id == Messages.MISSING_PROPERTY:
		message_text = "Property cannot be empty"
	elif message_id == Messages.MISSING_PYTHON:
		message_text = "Unable to find a valid Python 3 installation"
	elif message_id == Messages.MISSING_REPOSITORY:
		message_text = "Repository URL cannot be empty"
	elif message_id == Messages.MISSING_SERVER_FILE:
		message_text = "A primary server is required, but none was found. Please use '" + print_command(CliCommands.RUN) + " server' to run a new one and try again, or remove the option " + print_option(LongOptions.CONNECT_TO) + " from this command"
	elif message_id == Messages.MISSING_SETTING_KEY:
		message_text = "Setting key cannot be empty"
	elif message_id == Messages.MISSING_VERSION:
		message_text = "No {0} version '{1}' was found. Please use '" + print_command(CliCommands.INSTALL) + " {0}' to download it and try again"
	elif message_id == Messages.MULTIPLE_GEMS_IN_WORKSPACE:
		message_text = "Only one gem for repository is supported, but multiple definitions were found in its manifest file: {}"
	elif message_id == Messages.NO_UPDATES:
		message_text = "No update was found. Your version is up-to-date!"
	elif message_id == Messages.NO_UPDATES_IF_DETACHED:
		message_text = "Source repository points to a specific revision (detached mode). No other updates can be installed"
	elif message_id == Messages.PACKAGE_MANAGER_ERROR:
		message_text = "Unable to calculate missing '{}' packages for '{}' sections"
	elif message_id == Messages.PROJECT_DIR_EMPTY:
		message_text = "Project directory cannot be empty"
	elif message_id == Messages.PROJECT_DIR_NOT_EMPTY:
		message_text = "Directory must be empty to initialize a new project"
	elif message_id == Messages.PROJECT_NOT_FOUND:
		message_text = "No project exists at: {}"
	elif message_id == Messages.REMOVE_GEM_COMPLETED:
		message_text = "Gem '{}' is now disabled"
	elif message_id == Messages.REMOVE_GEM_COMPLETED_SKIP_REBUILD:
		message_text = "Gem '{}' is now disabled. Please use '" + print_command(CliCommands.BUILD) + "' to rebuild the project and make changes to take effect"
	elif message_id == Messages.REMOVE_GEM_REBUILD:
		message_text = "Gem '{}' is now disabled. Rebuilding the project to make changes to take effect..."
	elif message_id == Messages.RUN_EXTERNAL_COMMANDS:
		message_text = "Please run the following commands {}:"
	elif message_id == Messages.RUN_PRIVILEGED_COMMANDS:
		message_text = "Please run the following commands that require root privileges:"
	elif message_id == Messages.RUN_RESUME_COMMAND:
		message_text = "Then, resume the current operation using:"
	elif message_id == Messages.SAVE_QUESTION:
		message_text = "Do you want to save them"
	elif message_id == Messages.SETTINGS_NOT_FOUND:
		message_text = "No setting was found for this project"
	elif message_id == Messages.SERVER_PORT_ALREADY_USED:
		message_text = "Port {} is already in use. Please provide another port using option " + print_option(LongOptions.LISTEN_ON)
	elif message_id == Messages.SOURCE_ALREADY_EXISTS:
		message_text = "Source code was already cloned"
	elif message_id == Messages.SOURCE_NOT_FOUND:
		message_text = "No source repository was found"
	elif message_id == Messages.START_DOWNLOAD_SOURCE:
		message_text = "Downloading the source code from '{}'. Please wait..."
	elif message_id == Messages.START_EXPORT_BUILD_BINARY:
		message_text = "Building the source code using config '{}' and variant '{}'..."
	elif message_id == Messages.START_EXPORT_PROCESS_ASSETS:
		message_text = "Processing assets..."
	elif message_id == Messages.START_EXPORT_PACK_ASSETS_TO_BUNDLES:
		message_text = "Packing processed assets into bundles '{}'..."
	elif message_id == Messages.START_EXPORT_SAVE_IMAGE:
		message_text = "Generating a new container image with name '{}'..."
	elif message_id == Messages.UNCOMPLETED_ADD_GEM:
		message_text = "An error occured while adding the gem to the project (error: {}) {}"
	elif message_id == Messages.UNCOMPLETED_BUILD_PROJECT:
		message_text = "An unexpected error could be occurred while building the project"
	elif message_id == Messages.UNCOMPLETED_CHECK_GEM_RESOLVE_RELATIVE_PATH:
		message_text = "An error occurred while writing the absolute path for: {}"
	elif message_id == Messages.UNCOMPLETED_EXPORT:
		message_text = "An error occurred while exporting the project"
	elif message_id == Messages.UNCOMPLETED_SOLUTION_GENERATION:
		message_text = "An error occurred while generating required files to start the building process"
	elif message_id == Messages.UNCOMPLETED_INIT_ENGINE:
		message_text = "An unexpected error could be occurred while downloading the engine source code"
	elif message_id == Messages.UNCOMPLETED_INIT_GEM:
		message_text = "An unexpected error could be occurred while creating the gem files"
	elif message_id == Messages.UNCOMPLETED_INIT_PROJECT:
		message_text = "An unexpected error could be occurred while creating the project files"
	elif message_id == Messages.UNCOMPLETED_INSTALL:
		message_text = "An unexpected error could be occurred since the installation directory is still empty. Please try again using command: '" + print_command(CliCommands.INSTALL)
	elif message_id == Messages.UNCOMPLETED_MISSING_INSTALL:
		message_text = "An error occurred while installing the missing dependencies. Please try again"
	elif message_id == Messages.UNCOMPLETED_REFRESH:
		message_text = "An error occurred while searching updates. Please try again"
	elif message_id == Messages.UNCOMPLETED_REGISTRATION:
		message_text = "An error occurred while registering the current workspace (error code: {}) {}"
	elif message_id == Messages.UNCOMPLETED_UPGRADE:
		message_text = "Unable to upgrade"
	elif message_id == Messages.UNCOMPLETED_UNINSTALL:
		message_text = "An error occurred while deleting installed files. Please continue manually"
	elif message_id == Messages.UNINSTALL_ENGINE_COMPLETED:
		message_text = "Operation completed! Engine version '{}' has been removed"
	elif message_id == Messages.UNINSTALL_GEM_COMPLETED:
		message_text = "Operation completed! Gem version '{}' has been removed"
	elif message_id == Messages.UNMANAGED_GEMS:
		message_text = "Following unmanaged gems were found in the project manifest and they will cleared out, since they may be left from an uncompleted execution. If are required gems, please use '" + print_command(CliCommands.ADD) + " " + print_command(CliSubCommands.GEM) + "' to register these pathes as managed gems:\n  {}"
	elif message_id == Messages.UNREACHABLE_X11_DISPLAY:
		message_text = "Unable to connect to display :{}. Your xhost may be blocking connections from the container user.\n\nPlease use the following command to enable it:\nxhost +SI:localuser:#{}"
	elif message_id == Messages.UNSUPPORTED_CONTAINERS_AND_NO_CLIENT:
		message_text = "No action can be performed on containers when they are disabled"
	elif message_id == Messages.UNSUPPORTED_OPERATING_SYSTEM_FOR_REQUIREMENTS:
		message_text = "Unable to verify requirements since your distro isn't supported yet.\nYou can try to convert the following instructions for 'Ubuntu 22.04':"
	elif message_id == Messages.UNSUPPORTED_INSERT_SETTING_SECTION:
		message_text = "A setting section cannot be autopopulated. Please set each field using a dedicated '" + print_command(CliCommands.SETTINGS) + "' command"
	elif message_id == Messages.UPDATES_AVAILABLE:
		message_text = "There are {} updates available. Please use '" + print_command(CliCommands.UPGRADE) + "' to update your local installation"
	elif message_id == Messages.UPGRADE_ENGINE_COMPLETED:
		message_text = "Upgrade completed. All related configurations was regenerated"
	elif message_id == Messages.UPGRADE_ENGINE_COMPLETED_SKIP_REBUILD:
		message_text = "Skipping rebuild since option '" + print_option(LongOptions.SKIP_BUILD) + " is set"
	elif message_id == Messages.UPGRADE_ENGINE_COMPLETED_SOURCE_ONLY:
		message_text = "Source code was upgraded correctly. There isn't any installation to rebuild"
	elif message_id == Messages.UPGRADE_GEM_COMPLETED:
		message_text = "Upgrade completed. Please rebuild projects that are using this gem to make the changes to take effect"
	elif message_id == Messages.UPGRADE_SELF_COMPLETED:
		message_text = "Upgrade completed"
	elif message_id == Messages.VERSION_ALREADY_EXISTS:
		message_text = "Version '{}' already exists. Please try again"
	elif message_id == Messages.VERSION_NOT_FOUND:
		message_text = "Version '{}' has source code, but no valid config. Please re-install it using '" + print_command(CliCommands.INSTALL) + ' ' + print_option(LongOptions.FORCE) + "'"
	elif message_id == Messages.VERSION_NOT_INSTALLED:
		message_text = "Version '{}' isn't installed"
	elif message_id == Messages.VOLUME_NOT_FOUND:
		message_text = "Unable to retrieve volume '{}'"
	elif message_id == Messages.VOLUMES_DIR_NOT_FOUND:
		message_text = "Unable to find the volumes storage at: {}"
	elif message_id == Messages.WORKSPACE_MANIFEST_ALREADY_EXISTS:
		message_text = "Unable to initialize the repository since a manifest file ('repo.json') already exists"
	elif isinstance(message_id, str):
		return message_id
	else:
		return "n/a (message: {})".format(message_id)

	return message_text.format(*args, **kwargs)


def get_verbose():
	global VERBOSE
	return VERBOSE


def init_logger():
	global LOGGER
	LOGGER = logging.getLogger("o3tanks")

	handler = logging.StreamHandler()
	handler.setLevel(logging.NOTSET)

	formatter = MessageFormatter()
	handler.setFormatter(formatter)

	LOGGER.addHandler(handler)
	set_verbose(VERBOSE)


def is_tty():
	return sys.stdin.isatty() and sys.stdout.isatty()


def print_command(command):
	return "{} {}".format(get_bin_name(), command.value)


def print_msg(level, message_id, *args, **kwargs):
	message = get_message_text(message_id, *args, **kwargs)

	if LOGGER is None:
		init_logger()

	if level in [ Level.ERROR, Level.CRITICAL ]:
		LOGGER.log(Level.ERROR, message, stack_info = PRINT_CALLSTACK)
	else:
		LOGGER.log(level, message)


def print_option(option, value = None):
	if isinstance(option, ShortOptions):
		prefix = '-'
	elif isinstance(option, LongOptions):
		prefix = "--"
	else:
		prefix = ''

	if value is not None:
		suffix = ' ' + str(value)
	else:
		suffix = ''

	return "{}{}{}".format(prefix, option.value, suffix)


def print_setting(setting):
	input = setting.value if not isinstance(setting, JsonPropertyKey) else setting

	return "{}{}.{}".format(
		input.section,
		"[{}]".format(
			input.index if input.index >= 0 else ''
		) if input.index is not None else '',
		input.name
	)


def set_verbose(level):
	if LOGGER is None:
		init_logger()

	global VERBOSE
	VERBOSE = level

	if level < 0:
		LOGGER.setLevel(logging.CRITICAL + 1)

	elif level == 0:
		LOGGER.setLevel(logging.INFO)

	elif level > 0:
		LOGGER.setLevel(logging.DEBUG)

		if level > 1:
			global PRINT_CALLSTACK
			PRINT_CALLSTACK = True


def throw_error(*args):
	print_msg(Level.CRITICAL, *args)

	exit(1)
