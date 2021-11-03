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


from ..globals.o3tanks import OPERATING_SYSTEM, PRIVATE_PROJECT_SETTINGS_PATH, PUBLIC_PROJECT_SETTINGS_PATH, EngineSettings
from .filesystem import read_cfg_property, read_json_property
from .input_output import Messages, throw_error
from .types import CfgPropertyKey, JsonPropertyKey, OSFamilies, Repository, RepositoryResult, RepositoryResultType
import pathlib
import re


# --- SHARED SUB-FUNCTIONS ---

def get_build_config_path(build_dir, config):
	return pathlib.Path("{}/bin/{}".format(build_dir, config.value))

def get_install_config_path(install_dir, config):
	return pathlib.Path("{}/bin/Linux/{}".format(install_dir, config.value))


def get_engine_repository_from_source(source_dir):
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


def is_commit(reference):
	if reference is None:
		return False

	return (re.match(r"^[a-z0-9]{40}$", reference) is not None)


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


def select_project_settings_file(project_dir, setting_key):
	no_index_setting_key = JsonPropertyKey(setting_key.section, -1, setting_key.name) if setting_key.index is not None else setting_key

	if (
		no_index_setting_key == EngineSettings.VERSION.value
	):
		settings_file = project_dir / PRIVATE_PROJECT_SETTINGS_PATH
	elif (
		no_index_setting_key == EngineSettings.REPOSITORY.value or
		no_index_setting_key == EngineSettings.BRANCH.value or
		no_index_setting_key == EngineSettings.REVISION.value
	):
		settings_file = project_dir / PUBLIC_PROJECT_SETTINGS_PATH
	else:
		throw_error(Messages.INVALID_SETTING_FILE, setting_key.section, setting_key.name)

	return settings_file
