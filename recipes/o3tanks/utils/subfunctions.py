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


from ..globals.o3tanks import OPERATING_SYSTEM, PRIVATE_PROJECT_SETTINGS_PATH, PROJECT_EXTRA_PATH, PUBLIC_PROJECT_SETTINGS_PATH, EngineSettings, GemReference, GemReferenceTypes, GemSettings
from .filesystem import is_directory_empty, read_cfg_property, read_json_property, write_json_property
from .input_output import Level, Messages, ask_for_confirmation, print_msg, throw_error
from .types import CfgPropertyKey, JsonPropertyKey, OSFamilies, Repository, RepositoryResult, RepositoryResultType
import pathlib
import re
import subprocess


# --- SHARED SUB-FUNCTIONS ---

def clear_registered_gems(project_dir, restore_gems = None, filter_gems = None):
	project_manifest_file = get_project_manifest_file(project_dir)

	gems_key = JsonPropertyKey("external_subdirectories", None, None)
	current_gems = read_json_property(project_manifest_file, gems_key)
	if (restore_gems is not None) and len(restore_gems) == 0:
		restore_gems = None

	if current_gems is None and restore_gems is None:
		return

	if filter_gems is None:
		new_gems = restore_gems
	else:
		new_gems = []		
		for current_gem_dir in current_gems:
			if not current_gem_dir in filter_gems:
				new_gems.append(current_gem_dir)

		if restore_gems is None:
			if len(current_gems) == len(new_gems):
				return
		else:
			for restore_gem in restore_gems:
				if not restore_gem in new_gems:
					new_gems.append(restore_gem)

		if len(new_gems) == 0:
			new_gems = None

	write_json_property(project_manifest_file, gems_key, new_gems, False)


def get_builds_root_path(source_dir):
	return source_dir / "build"


def get_external_gem_path(external_gems_dir, gem_dir):
	return (external_gems_dir / gem_dir.relative_to(gem_dir.anchor))


def get_gem_path(gems_dir, gem_version):
	if (gems_dir is None) or not gems_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY)

	return (gems_dir / gem_version)


def get_project_manifest_file(project_dir):
	return project_dir / "project.json"


def get_repository_from_source(source_dir):
	repository_url = read_cfg_property(source_dir / ".git" / "config", CfgPropertyKey("remote \"origin\"", "url"))
	if repository_url is None:
		return RepositoryResult(RepositoryResultType.NOT_FOUND)
	with open(source_dir / ".git" / "HEAD", 'r') as file:
		repository_reference = file.readline().strip('\n\t ')
	
	matches = re.match(r"^ref:\s+refs/heads/(.+)$", repository_reference)
	if matches:
		repository_branch = matches.group(1).strip('\n\t ')
		repository_revision = None
	elif is_commit(repository_reference):
		repository_branch = None
		repository_revision = repository_reference.strip('\n\t ')
	else:		
		return RepositoryResult(RepositoryResultType.INVALID)

	return RepositoryResult(RepositoryResultType.OK , Repository(repository_url, repository_branch, repository_revision))


def get_binary_filename(name):
	if OPERATING_SYSTEM.family is OSFamilies.LINUX:
		return name

	elif OPERATING_SYSTEM.family is OSFamilies.MAC:
		return pathlib.PurePosixPath("{0}.app/Contents/MacOS/{0}".format(name))

	elif OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		return "{}.exe".format(name)

	else:
		throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM.family)


def get_library_filename(name):
	if OPERATING_SYSTEM.family is OSFamilies.LINUX:
		extension = "so"

	elif OPERATING_SYSTEM.family is OSFamilies.MAC:
		extension = "dylib"

	elif OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		extension =  "dll"

	else:
		throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM.family)

	return "{}.{}".format(name, extension)


def get_script_filename(name):
	if OPERATING_SYSTEM.family in [ OSFamilies.LINUX, OSFamilies.MAC ]:
		extension = "sh"

	elif OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		extension =  "bat"

	else:
		throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM.family)

	return "{}.{}".format(name, extension)


def has_configuration(config_dir):
	return config_dir.is_dir() and (
		(config_dir / get_binary_filename("Editor")).is_file() or
		any(config_dir.glob(get_binary_filename("**/*.GameLauncher"))) or
		any(config_dir.glob(get_binary_filename("**/*.ServerLauncher")))
	)


def is_commit(reference):
	if reference is None:
		return False

	return (re.match(r"^[a-z0-9]{40}$", reference) is not None)


def is_engine_version(value):
	return is_image_name(value)


def is_gem(path):
	if is_directory_empty(path):
		return False

	return (path / "gem.json").is_file()


def is_gem_version(value):
	return is_engine_version(value)


def is_image_name(value):
	return re.match(r"^[a-z0-9\.\-_]+$", value)


def is_project(path):
	if is_directory_empty(path):
		return False

	return ((path / "game.cfg").is_file() and get_project_manifest_file(path).is_file())


def parse_console_command(command):
	matches = re.match(r"^([\w]+)\[([^,]+(,[^,]+)*)?\]$", command)
	return matches


def parse_console_variable(variable):
	matches = re.match(r"^([\w]+)=(.+)$", variable)
	return matches


def parse_gem_reference(value, resolve_path = False):
	matches = re.match(r"^engine/(([^/]+)(/[0-1])?)$", value)
	if matches is not None:
		reference_type = GemReferenceTypes.ENGINE
		reference_value = matches.group(1)
	elif is_gem_version(value):
		reference_type = GemReferenceTypes.VERSION
		reference_value = value
	else:
		external_gem_dir = pathlib.Path(value)
		if resolve_path:
			external_gem_dir = external_gem_dir.resolve()

		if not external_gem_dir.is_absolute():
			throw_error(Messages.INVALID_VERSION, value)

		reference_type = GemReferenceTypes.PATH
		reference_value = external_gem_dir

	return GemReference(reference_type, reference_value)


def read_project_setting_values(project_dir, setting_section, setting_index):
	settings_files = [
		project_dir / PRIVATE_PROJECT_SETTINGS_PATH,
		project_dir / PUBLIC_PROJECT_SETTINGS_PATH
	]

	setting_key = JsonPropertyKey(
		setting_section,
		setting_index if (setting_index is not None and setting_index >= 0) else None,
		None
	)

	setting_values = {}
	for settings_file in settings_files:
		values = read_json_property(settings_file, setting_key)
		if values is None:
			continue

		elif isinstance(values, list):
			if not setting_key.section in setting_values:
				setting_values[setting_key.section] = []

			for index, index_values in enumerate(values):
				if index < len(setting_values[setting_key.section]):
					setting_values[setting_key.section][index] = { **setting_values[setting_key.section][index], **index_values }
				else:
					setting_values[setting_key.section].append(index_values)

		elif isinstance(values, dict):
			if setting_key.section is None:
				for section, section_values in values.items():
					if not section in setting_values:
						setting_values[section] = section_values
					elif isinstance(setting_values[section], dict) or isinstance(section_values, dict):
						setting_values[section] = { **setting_values[section], **section_values }
					elif isinstance(setting_values[section], list) or isinstance(section_values, list):
						n_current_values = len(setting_values[section])
						n_new_values = len(section_values)
						n_common_values = min(n_current_values, n_new_values)

						i = 0
						while i < n_common_values:
							setting_values[section][i] = { **setting_values[section][i], **section_values[i] }
							i += 1
						while i < n_new_values:
							setting_values[section].append(section_values[i])
							i += 1

			else:
				if not setting_key.section in setting_values:
					setting_values[setting_key.section] = {}

				setting_values[setting_key.section] = { **setting_values[setting_key.section], **values }

	return setting_values


def register_gems(cli_file, project_dir, gems_dir, external_gems_dir, show_unmanaged = False):
	gems = read_project_setting_values(project_dir, GemSettings.VERSION.value.section, None)
	if gems is not None:
		gems = gems.get(GemSettings.VERSION.value.section)

	project_manifest_file = get_project_manifest_file(project_dir)
	gems_manifest_key = JsonPropertyKey("external_subdirectories", None, None)
	old_external_dirs = read_json_property(project_manifest_file, gems_manifest_key)

	if old_external_dirs is None and gems is None:
		return None

	if gems is None:
		gems = []

	if old_external_dirs is None:
		old_external_dirs = []

	new_external_gems = []
	for gem_index, gem in enumerate(gems):
		gem_absolute_path = gem.get(GemSettings.ABSOLUTE_PATH.value.name)
		gem_version = gem.get(GemSettings.VERSION.value.name)

		if gem_absolute_path is not None:
			if gem_version is not None:
				throw_error(Messages.INCOMPATIBLE_GEM_SETTINGS, gem_index)
				
			real_gem_dir = pathlib.Path(gem_absolute_path)
			gem_dir = get_external_gem_path(external_gems_dir, real_gem_dir)

			gem_relative_path = gem.get(GemSettings.RELATIVE_PATH.value.name)

			new_external_gems.append([ str(gem_dir), gem_relative_path ])

		elif gem_version is not None:
			if gem_absolute_path is not None:
				throw_error(Messages.INCOMPATIBLE_GEM_SETTINGS, gem_index)
			
			gem_dir = search_gem_path(gems_dir, gem_version)
			new_external_gems.append([ str(gem_dir), None ])

		else:
			throw_error(Messages.INVALID_GEM_SETTING, gem_index)

	unmanaged_external_dirs = []
	restore_external_dirs = []
	for old_external_dir in old_external_dirs:
		is_managed = False

		for new_external_gem in new_external_gems:
			if (
				(new_external_gem[1] is not None and old_external_dir == new_external_gem[1]) or
				(old_external_dir == new_external_gem[0])
			):
				is_managed = True
				break

		is_relative = not pathlib.PurePath(old_external_dir).is_absolute()
		if is_relative or not is_managed:
			restore_external_dirs.append(old_external_dir)

		if is_managed:
			continue

		is_inside_project = False
		if is_relative:
			try:
				absolute_external_dir = (project_dir / old_external_dir).resolve(strict = True)
				if project_dir in absolute_external_dir.parents:
					old_external_dir = [ str(absolute_external_dir), old_external_dir ]
					is_inside_project = True

			except:
				pass

		if is_inside_project:
			new_external_gems.append(old_external_dir)
		else:
			unmanaged_external_dirs.append(old_external_dir)			

	if len(unmanaged_external_dirs) == 0 and len(new_external_gems) == 0:
		return restore_external_dirs

	if show_unmanaged and len(unmanaged_external_dirs) > 0:
		print_msg(Level.WARNING, Messages.UNMANAGED_GEMS, "\n  ".join(unmanaged_external_dirs))
		if not ask_for_confirmation(Messages.CONTINUE_QUESTION):
			exit(0)

	write_json_property(project_manifest_file, gems_manifest_key, None, sort_keys = False)

	for new_external_gem in new_external_gems:
		try:
			subprocess.run([
				cli_file, "register",
				"--gem-path", new_external_gem[0],
				"--external-subdirectory-project-path", str(project_dir)
			], stdout = subprocess.DEVNULL, check = True)

		except FileNotFoundError as error:
			if error.filename == cli_file.name or (OPERATING_SYSTEM.family is OSFamilies.WINDOWS and error.filename is None):
				throw_error(Messages.CORRUPTED_ENGINE_SOURCE)
			else:
				raise error

		except subprocess.CalledProcessError as error:
			throw_error(Messages.UNCOMPLETED_REGISTRATION, error.returncode, "\n{}\n{}".format(error.stdout, error.stderr))

	return restore_external_dirs


def search_gem_index(project_dir, gem_reference):
	project_extra_dir = project_dir / PROJECT_EXTRA_PATH
	if not project_extra_dir.is_dir():
		throw_error(Messages.SETTINGS_NOT_FOUND)

	if gem_reference.type is GemReferenceTypes.PATH:
		gem_setting = GemSettings.ABSOLUTE_PATH
	elif gem_reference.type is GemReferenceTypes.VERSION:
		gem_setting = GemSettings.VERSION
	else:
		throw_error(Messages.INVALID_GEM_REFERENCE, gem_reference.type)

	settings_file = select_project_settings_file(project_dir, gem_setting.value)
	gem_key = JsonPropertyKey(gem_setting.value.section, None, None)
	active_gems = read_json_property(settings_file, gem_key)
	if (active_gems is None) or len(active_gems) == 0:
		return None

	gem_index = None
	for index, active_gem in enumerate(active_gems):
		if active_gem.get(gem_setting.value.name) == gem_reference.print():
			gem_index = index
			break

	return gem_index


def search_gem_path(root_dir, gem_version = None):
	candidate_dir = get_gem_path(root_dir, gem_version) if gem_version is not None else root_dir

	if not candidate_dir.is_dir():
		return None
	elif is_gem(candidate_dir):
		return candidate_dir

	workspace_dir = candidate_dir
	workspace_manifest_file = (workspace_dir / "repo.json")
	if not workspace_manifest_file.is_file():
		return None

	gem_path = read_json_property(workspace_manifest_file, JsonPropertyKey("gems", None, None))
	if gem_path is None:
		throw_error(Messages.MISSING_GEM_IN_WORKSPACE, workspace_dir)
	elif not isinstance(gem_path, list) or len(gem_path) != 1:
		throw_error(Messages.MULTIPLE_GEMS_IN_WORKSPACE, workspace_dir)

	candidate_dir = (workspace_dir / gem_path[0]).resolve()

	return candidate_dir if is_gem(candidate_dir) else None


def select_project_settings_file(project_dir, setting_key):
	no_index_setting_key = JsonPropertyKey(setting_key.section, -1, setting_key.name) if setting_key.index is not None else setting_key

	if (
		no_index_setting_key == EngineSettings.VERSION.value or
		no_index_setting_key == EngineSettings.WORKFLOW.value or
		no_index_setting_key == GemSettings.VERSION.value or
		no_index_setting_key == GemSettings.ABSOLUTE_PATH.value
	):
		settings_file = project_dir / PRIVATE_PROJECT_SETTINGS_PATH
	elif (
		no_index_setting_key == EngineSettings.REPOSITORY.value or
		no_index_setting_key == EngineSettings.BRANCH.value or
		no_index_setting_key == EngineSettings.REVISION.value or
		no_index_setting_key == GemSettings.REPOSITORY.value or
		no_index_setting_key == GemSettings.BRANCH.value or
		no_index_setting_key == GemSettings.REVISION.value or
		no_index_setting_key == GemSettings.RELATIVE_PATH.value
	):
		settings_file = project_dir / PUBLIC_PROJECT_SETTINGS_PATH
	else:
		throw_error(Messages.INVALID_SETTING_FILE, setting_key.section, setting_key.name)

	return settings_file
