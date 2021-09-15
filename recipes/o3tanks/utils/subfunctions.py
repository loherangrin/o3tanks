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


from ..globals.o3tanks import PRIVATE_PROJECT_SETTINGS_PATH, PUBLIC_PROJECT_SETTINGS_PATH, EngineSettings
from .filesystem import read_cfg_property
from .input_output import Messages, throw_error
from .types import CfgPropertyKey, Repository, RepositoryResult, RepositoryResultType
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


def is_commit(reference):
	if reference is None:
		return False

	return (re.match(r"^[a-z0-9]{40}$", reference) is not None)


def select_project_settings_file(project_dir, setting_key):
	if (setting_key == EngineSettings.VERSION):
		settings_file = project_dir / PRIVATE_PROJECT_SETTINGS_PATH
	elif (setting_key == EngineSettings.REPOSITORY) or (setting_key == EngineSettings.BRANCH) or (setting_key == EngineSettings.REVISION):
		settings_file = project_dir / PUBLIC_PROJECT_SETTINGS_PATH
	else:
		throw_error(Messages.INVALID_SETTING_FILE, setting_key.section, setting_key.name)

	return settings_file
