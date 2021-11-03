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


from .globals.o3de import *
from .globals.o3tanks import *
from .utils.containers import *
from .utils.input_output import *
from .utils.filesystem import *
from .utils.requirements import *
from .utils.subfunctions import *
from .utils.types import *
import argparse
import os
import re
import sys
import textwrap


# --- VARIABLES ---

CONTAINER_CLIENT = None


# --- SUB-FUNCTIONS ---

def check_project_dependencies(project_dir, check_engine = True, check_gems = True):
	if not check_engine:
		engine_version = None
	else:
		result = select_engine(project_dir)
		if result.type is DependencyResultType.OK:
			engine_version = result.value
		elif result.type is DependencyResultType.MISSING:
			engine_url = result.value
			install_missing_engine(project_dir, engine_url)

			result = select_engine(project_dir)
			if result.type is not DependencyResultType.OK:
				throw_error(Messages.UNCOMPLETED_MISSING_INSTALL)

			engine_version = result.value

		elif result.type is DependencyResultType.DIFFERENT:
			throw_error(Messages.BINDING_DIFFERENT_REPOSITORY, Targets.ENGINE)
		elif result.type is DependencyResultType.NOT_FOUND:
			throw_error(Messages.BINDING_INSTALL_NOT_FOUND, Targets.ENGINE)
		else:
			throw_error(Messages.BINDING_INVALID_REPOSITORY, Targets.ENGINE)

		if not is_engine_installed(engine_version):
			throw_error(Messages.MISSING_BOUND_VERSION, Targets.ENGINE.value, engine_version)

	if not check_gems:
		external_gem_dirs = None
	else:
		gems = read_project_setting_values(project_dir, Settings.GEMS.value, None)
		if gems is not None:
			gems = gems.get(GemSettings.VERSION.value.section)

		external_gem_dirs = []
		if gems is not None:
			for gem_index, gem in enumerate(gems):
				gem_absolute_path = gem.get(GemSettings.ABSOLUTE_PATH.value.name)
				gem_relative_path = gem.get(GemSettings.RELATIVE_PATH.value.name)
				gem_repository_url = gem.get(GemSettings.REPOSITORY.value.name)

				if (gem_absolute_path is not None) or (gem_relative_path is not None):
					if gem_repository_url is not None:
						throw_error(Messages.INCOMPATIBLE_GEM_SETTINGS, gem_index)

					if gem_absolute_path is None:
						real_gem_dir = (get_real_project_dir() if CONTAINER_CLIENT.is_in_container() else project_dir) / gem_relative_path

						resolved = run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, GemSettings.ABSOLUTE_PATH.value.section, gem_index, GemSettings.ABSOLUTE_PATH.value.name, real_gem_dir, False, False, False)
						if not resolved:
							throw_error(Messages.UNCOMPLETED_CHECK_GEM_RESOLVE_RELATIVE_PATH, gem_relative_path)

					else:
						real_gem_dir = pathlib.PurePath(gem_absolute_path)

					external_gem_dirs.append(real_gem_dir)

				elif gem_repository_url is not None:
					if (gem_absolute_path is not None) or (gem_relative_path is not None):
						throw_error(Messages.INCOMPATIBLE_GEM_SETTINGS, gem_index)

					result = select_gem(project_dir, gem_index, gem)
					if result.type is DependencyResultType.OK:
						gem_version = result.value
					elif result.type is DependencyResultType.MISSING:
						gem_url = result.value
						gem_version = install_missing_gem(project_dir, gem_index, gem_url)

					elif result.type is DependencyResultType.DIFFERENT:
						throw_error(Messages.BINDING_DIFFERENT_REPOSITORY, "{} at index '{}'".format(Targets.GEM.value, gem_index))
					elif result.type is DependencyResultType.NOT_FOUND:
						throw_error(Messages.BINDING_INSTALL_NOT_FOUND, "{} at index '{}'".format(Targets.GEM.value, gem_index))
					else:
						throw_error(Messages.BINDING_INVALID_REPOSITORY, "{} at index '{}'".format(Targets.GEM.value, gem_index))

					gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
					gems_dir = CONTAINER_CLIENT.get_volume_path(gems_volume)

					gem_dir = search_gem_path(gems_dir, gem_version)
					if not is_gem(gem_dir):
						throw_error(Messages.UNCOMPLETED_MISSING_INSTALL)

				elif len(gem) == 0:
					continue

				else:
					throw_error(Messages.INVALID_GEM_SETTING, gem_index)

	return [ engine_version, external_gem_dirs ]


def generate_repository_url(repository, fork, branch, tag, commit, default_repository = None):
	if repository is None:
		if default_repository is None:
			throw_error(Messages.MISSING_REPOSITORY)

		if fork is None:
			url = default_repository
		else:
			if not re.match(r"^[a-zA-Z0-9\-]+/[a-zA-Z0-9\.\-]+$", fork):
				throw_error(Messages.INVALID_FORK)

			matches = re.match(r"^([\w]+://[^/]+).*$", default_repository)
			if matches is None:
				throw_error(Messages.INVALID_REPOSITORY_URL)

			host_url = matches.group(1)
			url = "{}/{}.git".format(host_url, fork)
	else:
		if fork is not None:
			throw_error(Messages.INCOMPATIBLE_FORK_OPTIONS)
		elif re.search(r"#", repository):
			throw_error(Messages.INVALID_REPOSITORY_URL_HASH)
		else:
			url = repository

	if (branch is None) and (commit is None) and (tag is None):
		pass

	elif (branch is not None) and (commit is None) and (tag is None):
		url += '#' + branch

	elif (branch is None) and (commit is not None) and (tag is None):
		if not is_commit(commit):
			throw_error(Messages.INVALID_COMMIT)
		
		url += '#' + commit

	elif (branch is None) and (commit is None) and (tag is not None):	
		url += '#' + tag

	elif not ((branch is None) and (commit is None) and (tag is None)):	
		throw_error(Messages.INCOMPATIBLE_REVISION_OPTIONS)

	return url


def get_all_engine_versions():
	volume_prefix = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE)
	start_delimiter = len(volume_prefix)

	generic_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, 'a')
	end_delimiter = len(generic_volume)

	volume_prefix_length = start_delimiter + (end_delimiter - start_delimiter - 1)

	source_volumes = CONTAINER_CLIENT.list_volumes("^{}*".format(volume_prefix))

	engine_versions = []
	for source_volume in source_volumes:
		engine_version = source_volume[volume_prefix_length:]
		engine_versions.append(engine_version)

	return engine_versions


def get_all_gem_versions(gems_dir = None):
	if gems_dir is None:
		gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
		gems_dir = CONTAINER_CLIENT.get_volume_path(gems_volume)
		if gems_dir is None:
			return []

	gem_versions = []
	for content in gems_dir.iterdir():
		if content.is_dir() and (is_gem(content) or search_gem_path(content) is not None):
			gem_version = content.name
			gem_versions.append(gem_version)

	return gem_versions


def get_engine_repository_from_project(project_dir):
	settings_file = select_project_settings_file(project_dir, EngineSettings.REPOSITORY.value)
	repository = read_json_property(settings_file, JsonPropertyKey(Settings.ENGINE.value, None, None))

	if (repository is None) or not (EngineSettings.REPOSITORY.value.name in repository):
		return RepositoryResult(RepositoryResultType.NOT_FOUND)

	if (EngineSettings.BRANCH.value.name in repository) and (EngineSettings.REVISION.value.name in repository):
		return RepositoryResult(RepositoryResultType.INVALID)

	return RepositoryResult(
		RepositoryResultType.OK,
		Repository(
			repository[EngineSettings.REPOSITORY.value.name],
			repository.get(EngineSettings.BRANCH.value.name),
			repository.get(EngineSettings.REVISION.value.name)
		)
	)


def get_engine_version_from_project(project_dir):
	engine_version = read_json_property(project_dir / PRIVATE_PROJECT_SETTINGS_PATH, EngineSettings.VERSION)

	return engine_version


def get_gem_repository_from_project(project_dir, gem_index, gem = None):
	if (gem is None) and (gem_index is not None):
		settings_file = select_project_settings_file(project_dir, EngineSettings.REPOSITORY.value)
		gem = read_json_property(settings_file, JsonPropertyKey(Settings.GEM.value, gem_index, None))
	
	if (gem is None) or not (GemSettings.REPOSITORY.value.name in gem):
		return RepositoryResult(RepositoryResultType.NOT_FOUND)

	if (GemSettings.BRANCH.value.name in gem) and (GemSettings.REVISION.value.name in gem):
		return RepositoryResult(RepositoryResultType.INVALID)

	return RepositoryResult(
		RepositoryResultType.OK,
		Repository(
			gem[GemSettings.REPOSITORY.value.name],
			gem.get(GemSettings.BRANCH.value.name),
			gem.get(GemSettings.REVISION.value.name)
		)
	)


def has_build_config(build_dir, config):
	config_dir = get_build_config_path(build_dir, config)

	return has_configuration(config_dir)


def has_install_config(install_dir, config):
	config_dir = get_install_config_path(install_dir, config)

	return has_configuration(config_dir)


def has_configuration(config_dir):
	return config_dir.is_dir() and (
		(config_dir / get_binary_filename("Editor")).is_file() or
		any(config_dir.glob(get_binary_filename("**/*.GameLauncher"))) or
		any(config_dir.glob(get_binary_filename("**/*.ServerLauncher")))
	)


def is_engine_installed(engine_version):
	source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
	source_dir = CONTAINER_CLIENT.get_volume_path(source_volume)

	return (
		source_dir is not None and
		(source_dir / ".git").is_dir() and
		(source_dir / "engine.json").is_file()
	)


def is_gem_installed(gem_version):
	gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
	gems_dir = CONTAINER_CLIENT.get_volume_path(gems_volume)
	if gems_dir is None:
		return False

	gem_dir = search_gem_path(gems_dir, gem_version)
	return (gem_dir is not None)


def has_superuser_privileges():
	return (os.geteuid() == 0)


def initialize_volumes(names, resume_command, force = False):
	created = False
	new_dirs = []
	for name in names:
		if not CONTAINER_CLIENT.volume_exists(name):
			CONTAINER_CLIENT.create_volume(name)
			created = True

			new_dir = CONTAINER_CLIENT.get_volume_path(name)
			new_dirs.append(new_dir)

	if force:
		new_dirs = []
		for name in names:
			new_dir = CONTAINER_CLIENT.get_volume_path(name)
			new_dirs.append(new_dir)

	if len(new_dirs) == 0:
		return

	instructions = Messages.CHANGE_OWNERSHIP_NEW_VOLUMES if created else Messages.CHANGE_OWNERSHIP_EXISTING_VOLUMES
	mapping = { "/var/lib/docker/volumes": get_real_volumes_dir() } if CONTAINER_CLIENT.is_in_container() else None

	check_ownership(new_dirs, instructions, resume_command, mapping)


def parse_repository_url(value):
	matches = re.match(r"^((http[s]?|ssh)://[\w/\.\-]+\.git)(#([\w/\.\-]+))?$", value)
	if matches is None:
		throw_error(Messages.INVALID_REPOSITORY_URL)

	protocol = matches.group(2)
	url = matches.group(1)
	reference = matches.group(4) if (len(matches.groups()) > 3) else "main"

	return [ protocol, url, reference ]


def search_engine_by_repository(engine_repository):
	engine_versions = get_all_engine_versions()
	if len(engine_versions) == 0:
		return None

	engine_version = None
	for candidate_version in engine_versions:
		source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, candidate_version)
		source_dir = CONTAINER_CLIENT.get_volume_path(source_volume)

		result_type, installed_engine_repository = get_repository_from_source(source_dir)

		if (result_type is RepositoryResultType.OK) and (installed_engine_repository == engine_repository):
			engine_version = candidate_version
			break

	return engine_version


def search_gem_by_repository(gem_repository):
	gem_versions = get_all_gem_versions()
	if len(gem_versions) == 0:
		return None

	gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
	gems_dir = CONTAINER_CLIENT.get_volume_path(gems_volume)

	gem_version = None
	for candidate_version in gem_versions:
		parent_gem_dir = get_gem_path(gems_dir, candidate_version)
		gem_dir = search_gem_path(gems_dir, candidate_version)
		if gem_dir is None:
			continue

		result_type, installed_gem_repository = get_repository_from_source(parent_gem_dir)

		if (result_type is RepositoryResultType.OK) and (installed_gem_repository == gem_repository):
			gem_version = candidate_version
			break

	return gem_version


def select_engine(project_dir):
	if not (project_dir / PROJECT_EXTRA_PATH).is_dir():
		return DependencyResult(DependencyResultType.OK, O3DE_DEFAULT_VERSION)
	
	engine_version = get_engine_version_from_project(project_dir)

	result_type, engine_repository = get_engine_repository_from_project(project_dir)
	if result_type is not RepositoryResultType.OK:
		return DependencyResult(DependencyResultType.INVALID)

	if engine_version is None:
		if engine_repository is None:
			return DependencyResult(DependencyResultType.OK, O3DE_DEFAULT_VERSION)

		engine_version = search_engine_by_repository(engine_repository)

		if engine_version is not None:
			run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, EngineSettings.VERSION.value.section, EngineSettings.VERSION.value.index, EngineSettings.VERSION.value.name, engine_version, False, True, False)

		else:
			engine_url = engine_repository.url
			if engine_repository.branch is not None:
				engine_url += '#' + engine_repository.branch
			elif engine_repository.revision is not None:
				engine_url += '#' + engine_repository.revision

			return DependencyResult(DependencyResultType.MISSING, engine_url)

	else:
		source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
		source_dir = CONTAINER_CLIENT.get_volume_path(source_volume)

		if source_dir is None:
			engine_version = search_engine_by_repository(engine_repository)

			if engine_version is not None:
				run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, EngineSettings.VERSION.value.section, EngineSettings.VERSION.value.index, EngineSettings.VERSION.value.name, engine_version, False, True, False)
			else:
				return DependencyResult(DependencyResultType.NOT_FOUND)

		else:
			result_type, installed_engine_repository = get_repository_from_source(source_dir)

			if result_type is not RepositoryResultType.OK:			
				return DependencyResult(DependencyResultType.NOT_FOUND)
			elif (result_type is RepositoryResultType.OK) and (installed_engine_repository != engine_repository):
				return DependencyResult(DependencyResultType.DIFFERENT)

	return DependencyResult(DependencyResultType.OK, engine_version)


def select_gem(project_dir, gem_index, gem = None):
	if gem is None:
		if not (project_dir / PROJECT_EXTRA_PATH).is_dir():
			return DependencyResult(DependencyResultType.INVALID)

		gem = read_project_setting_values(project_dir, Settings.GEMS.value, gem_index)
		if gem is not None:
			gem = gem.get(GemSettings.VERSION.value.section)
			if gem is not None:
				gem = gem[0]

		if gem is None:
			return DependencyResult(DependencyResultType.INVALID)								

	gem_version = gem.get(GemSettings.VERSION.value.name)

	result_type, gem_repository = get_gem_repository_from_project(project_dir, gem_index, gem)
	if result_type is not RepositoryResultType.OK:
		return DependencyResult(DependencyResultType.INVALID)

	if gem_version is None:
		if gem_repository is None:
			return DependencyResult(DependencyResultType.INVALID)

		gem_version = search_gem_by_repository(gem_repository)

		if gem_version is not None:
			run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, GemSettings.VERSION.value.section, gem_index, GemSettings.VERSION.value.name, gem_version, False, True, False)

		else:
			gem_url = gem_repository.url
			if gem_repository.branch is not None:
				gem_url += '#' + gem_repository.branch
			elif gem_repository.revision is not None:
				gem_url += '#' + gem_repository.revision

			return DependencyResult(DependencyResultType.MISSING, gem_url)

	else:
		gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
		gems_dir = CONTAINER_CLIENT.get_volume_path(gems_volume)

		parent_gem_dir = get_gem_path(gems_dir, gem_version)
		gem_dir = search_gem_path(parent_gem_dir)
		if gem_dir is None:
			gem_version = search_gem_by_repository(gem_repository)

			if gem_version is not None:
				run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, GemSettings.VERSION.value.section, gem_index, GemSettings.VERSION.value.name, gem_version, False, True, False)
			else:
				return DependencyResult(DependencyResultType.NOT_FOUND)

		else:
			result_type, installed_gem_repository = get_repository_from_source(parent_gem_dir)

			if result_type is not RepositoryResultType.OK:			
				return DependencyResult(DependencyResultType.NOT_FOUND)
			elif (result_type is RepositoryResultType.OK) and (installed_gem_repository != gem_repository):
				return DependencyResult(DependencyResultType.DIFFERENT)

	return DependencyResult(DependencyResultType.OK, gem_version)


def select_recommended_config(engine_version):
	build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
	build_dir = CONTAINER_CLIENT.get_volume_path(build_volume)
	
	install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
	install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)
	
	engine_config = None
	for config in O3DE_Configs:
		install_builder_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_BUILDER, engine_version, config)

		if (
			CONTAINER_CLIENT.image_exists(install_builder_image) or 
			(install_dir is not None and has_install_config(install_dir, config)) or
			(build_dir is not None and has_build_config(build_dir, config))
		):
			engine_config = config

	return engine_config


# --- FUNCTIONS (GENERIC) ---

def apply_updates():
	resume_command = [
		get_bin_name(),
		CliCommands.UPGRADE.value,
		CliSubCommands.SELF.value[0]
	]

	if CONTAINER_CLIENT.is_in_container():
		installation_dir = ROOT_DIR
		mapping = { str(installation_dir): get_real_bin_file().parent }
	else:
		installation_dir = get_real_bin_file().parent
		mapping = None

	check_ownership(installation_dir, Messages.CHANGE_OWNERSHIP_SELF, resume_command, mapping)

	upgraded = run_updater(None, UpdaterCommands.UPGRADE, Targets.SELF)
	if not upgraded:
		throw_error(Messages.UNCOMPLETED_UPGRADE)

	print_msg(Level.INFO, Messages.UPGRADE_SELF_COMPLETED)


def check_container_client():
	global CONTAINER_CLIENT
	if CONTAINER_CLIENT is not None:
		print_msg(Level.WARNING, Messages.CONTAINER_CLIENT_ALREADY_RUNNING)
		return

	CONTAINER_CLIENT = ContainerClient.open()


def check_builder():
	check_image(Images.BUILDER, "builder")

def check_runner():
	check_image(Images.RUNNER, "runner")

def check_updater():
	check_image(Images.UPDATER, "updater")

def check_image(image_id, build_stage):
	image_name = CONTAINER_CLIENT.get_image_name(image_id)

	if not CONTAINER_CLIENT.image_exists(image_name):
		recipe = "Dockerfile.linux"
		if CONTAINER_CLIENT.is_in_container():
			if DEVELOPMENT_MODE:
				archive_file = None
				context_dir = ROOT_DIR.parent / "o3tanks_recipes"
			else:
				archive_file = pathlib.Path(os.environ["O3TANKS_DIR"]) / "context.tar"
				context_dir = None
		else:
			archive_file = None
			context_dir = pathlib.Path(__file__).resolve().parent

		if image_id is Images.RUNNER:
			build_arguments = {
				"INSTALL_GPU_INTEL": "true" if GPU_DRIVER_NAME is GPUDrivers.INTEL else "false",
				"INSTALL_GPU_AMD": "true" if GPU_DRIVER_NAME in [ GPUDrivers.AMD_OPEN, GPUDrivers.AMD_PROPRIETARY ] else "false"
			}
		else:
			build_arguments = {}

		if archive_file is not None:
			CONTAINER_CLIENT.build_image_from_archive(archive_file, image_name, recipe, build_stage, build_arguments)
		else:
			CONTAINER_CLIENT.build_image_from_directory(context_dir, image_name, recipe, build_stage, build_arguments)

		if not CONTAINER_CLIENT.image_exists(image_name):
			throw_error(Messages.ERROR_BUILD_IMAGE, image_name)


def check_requirements(resume_command):
	commands = solve_unmet_requirements()

	if commands.empty():
		return

	if not commands.is_default:
		print_msg(Level.INFO, Messages.MISSING_PACKAGES)
	else:
		print_msg(Level.WARNING, Messages.UNSUPPORTED_OPERATING_SYSTEM_FOR_REQUIREMENTS)

	if len(commands.main_system_packages) > 0:
		print_msg(Level.INFO, '')
		print_msg(Level.INFO, Messages.INSTALL_MAIN_SYSTEM_PACKAGES)

		for command in commands.main_system_packages:
			print_msg(Level.INFO, "  sudo {}".format(command))

	if len(commands.ported_system_packages) > 0:
		print_msg(Level.INFO, '')
		print_msg(Level.INFO, Messages.INSTALL_PORTED_SYSTEM_PACKAGES)

		for package_url in commands.ported_system_packages:
			print_msg(Level.INFO, "  {}".format(package_url))

	if len(commands.external_system_packages) > 0:
		print_msg(Level.INFO, '')
		print_msg(Level.INFO, Messages.INSTALL_EXTERNAL_SYSTEM_PACKAGES_1)

		for repository_url, command in commands.external_system_packages.items():
			print_msg(Level.INFO, "  {}".format(repository_url))

		print_msg(Level.INFO, '')
		print_msg(Level.INFO, Messages.INSTALL_EXTERNAL_SYSTEM_PACKAGES_2)

		for repository_url, command in commands.external_system_packages.items():
			print_msg(Level.INFO, "  sudo {}".format(command))

	if len(commands.application_packages) > 0:
		print_msg(Level.INFO, '')
		print_msg(Level.INFO, Messages.INSTALL_APPLICATION_PACKAGES)

		for command in commands.application_packages:
			print_msg(Level.INFO, "  {}".format(command))

	if len(commands.other_commands) > 0:
		print_msg(Level.INFO, '')
		print_msg(Level.INFO, Messages.INSTALL_OTHER_COMMANDS)

		for command in commands.other_commands:
			print_msg(Level.INFO, "  sudo {}".format(command))

	print_msg(Level.INFO, '')
	print_msg(Level.INFO, Messages.RUN_RESUME_COMMAND)
	print_msg(Level.INFO, resume_command)

	exit(1)


def check_ownership(paths, instructions, resume_command, mapping = None):
	if paths is None:
		return
	elif not isinstance(paths, list):
		paths = [ paths ]
	elif len(paths) == 0:
		return

	current_user = CONTAINER_CLIENT.get_current_user()
	if current_user is None:
		throw_error(Messages.INVALID_CURRENT_USER)

	container_user = CONTAINER_CLIENT.get_container_user()
	if container_user is None:
		throw_error(Messages.INVALID_CONTAINER_USER)

	if (current_user.uid == container_user.uid) and (current_user.gid == container_user.gid):
		return

	wrong_paths = []
	for path in paths:
		current_ownership = path.stat()

		if (current_ownership.st_uid == container_user.uid) and (current_ownership.st_gid == container_user.gid):
			continue

		wrong_paths.append(path)

	if len(wrong_paths) == 0:
		return

	if has_superuser_privileges():
		try:
			for wrong_path in wrong_paths:
				os.chown(wrong_path, container_user.uid, container_user.gid)

			show_instructions = False

		except PermissionError:
			show_instructions = True
	else:
		show_instructions = True

	if show_instructions:
		print_msg(Level.INFO, instructions)
		print_msg(Level.INFO, '')
		print_msg(Level.INFO, Messages.RUN_PRIVILEGED_COMMANDS)

		for wrong_path in wrong_paths:
			real_path = wrong_path
			if mapping is not None:
				for mapping_from, mapping_to in mapping.items():
					try:
						relative_path = wrong_path.relative_to(mapping_from)
						real_path = mapping_to / relative_path
						break
					except ValueError:
						continue						

			real_container_user = CONTAINER_CLIENT.get_container_user(False)
			print_msg(Level.INFO, "sudo chown --recursive {}:{} {}".format(real_container_user.uid, real_container_user.gid, real_path))
		
		print_msg(Level.INFO, '')
		print_msg(Level.INFO, Messages.RUN_RESUME_COMMAND)
		print_msg(Level.INFO, resume_command)

		exit(1)


def close_container_client():
	global CONTAINER_CLIENT
	if CONTAINER_CLIENT is not None:
		CONTAINER_CLIENT.close()
		CONTAINER_CLIENT = None


def print_version_info():
	print("O3Tanks version {}".format(get_version_number()))
	print("A containerized version manager for 'O3DE (Open 3D Engine)'")
	print('https://github.com/loherangrin/o3tanks/')
	print('')
	print('Copyright (c) 2021 Matteo Grasso')
	print('Released under the Apache License, version 2.0')
	print('Please see LICENSE and NOTICE files for license terms')


def run_builder(engine_version, engine_config, project_dir, external_gem_dirs, *command):
	install_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_BUILDER, engine_version, engine_config) if engine_config is not None else None
	
	binds = {}
	volumes = {}

	if (install_image is not None) and CONTAINER_CLIENT.image_exists(install_image):
		builder_image = install_image
	else:
		builder_image = CONTAINER_CLIENT.get_image_name(Images.BUILDER)

		if engine_version is not None:
			source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
			volumes[source_volume] = str(O3DE_ENGINE_SOURCE_DIR)

			packages_volume = CONTAINER_CLIENT.get_volume_name(Volumes.PACKAGES)
			volumes[packages_volume] = str(O3DE_PACKAGES_DIR)

			gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
			volumes[gems_volume] = str(O3DE_GEMS_DIR)

			build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
			volumes[build_volume] = str(O3DE_ENGINE_BUILD_DIR)
			
			install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
			volumes[install_volume] = str(O3DE_ENGINE_INSTALL_DIR)

	if project_dir is not None and project_dir.is_dir():
		binds[str(get_real_project_dir() if CONTAINER_CLIENT.is_in_container() else project_dir)] = str(O3DE_PROJECT_SOURCE_DIR)

	if external_gem_dirs is not None:
		for external_gem_dir in external_gem_dirs:
			binds[str(external_gem_dir)] = str(get_external_gem_path(O3DE_GEMS_EXTERNAL_DIR, external_gem_dir))

	if DEVELOPMENT_MODE:
		scripts_dir = get_real_bin_file().parent / SCRIPTS_PATH
		binds[str(scripts_dir)] = str(ROOT_DIR)

	completed = CONTAINER_CLIENT.run_foreground_container(
		builder_image,
		list(command),
		interactive = is_tty(),
		binds = binds,
		volumes = volumes
	)
	
	return completed


def run_runner(engine_version, engine_config, project_dir, external_gem_dirs, headless, *command):
	if engine_config is None:
		throw_error(Messages.MISSING_CONFIG)

	install_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_RUNNER, engine_version, engine_config)

	binds = {}
	volumes = {}

	if CONTAINER_CLIENT.image_exists(install_image):
		runner_image = CONTAINER_CLIENT.install_image
	else:
		runner_image = CONTAINER_CLIENT.get_image_name(Images.RUNNER)

		build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
		install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
		source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
		gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)

		if CONTAINER_CLIENT.volume_exists(install_volume):
			install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)

			if has_install_config(install_dir, engine_config):				
				volumes[install_volume] = str(O3DE_ENGINE_INSTALL_DIR)

		if (len(volumes) == 0) and CONTAINER_CLIENT.volume_exists(build_volume) and CONTAINER_CLIENT.volume_exists(source_volume):
			build_dir = CONTAINER_CLIENT.get_volume_path(build_volume)

			if has_build_config(build_dir, engine_config):
				volumes[source_volume] = str(O3DE_ENGINE_SOURCE_DIR)
				volumes[build_volume] = str(O3DE_ENGINE_BUILD_DIR)

		if len(volumes) == 0:
			throw_error(Messages.MISSING_INSTALL_AND_CONFIG, engine_version, engine_config.value)

		volumes[gems_volume] = str(O3DE_GEMS_DIR)

	if project_dir is not None and project_dir.is_dir():
		binds[str(get_real_project_dir() if CONTAINER_CLIENT.is_in_container() else project_dir)] = str(O3DE_PROJECT_SOURCE_DIR)
	else:
		throw_error(Messages.MISSING_PROJECT)

	if external_gem_dirs is not None:
		for external_gem_dir in external_gem_dirs:
			binds[str(external_gem_dir)] = str(get_external_gem_path(O3DE_GEMS_EXTERNAL_DIR, external_gem_dir))

	if not headless:
		has_display = True
		has_gpu = True
	else:
		has_display = False
		has_gpu = False

	if DEVELOPMENT_MODE:
		scripts_dir = get_real_bin_file().parent / SCRIPTS_PATH
		binds[str(scripts_dir)] = str(ROOT_DIR)

	completed =	CONTAINER_CLIENT.run_foreground_container(
		runner_image,
		list(command),
		interactive = is_tty(),
		display = has_display,
		gpu = has_gpu,
		binds = binds,
		volumes = volumes
	)

	return completed


def run_updater(engine_version, command, target, *arguments):
	updater_image = CONTAINER_CLIENT.get_image_name(Images.UPDATER)

	binds = {}
	volumes = {}

	if target is Targets.ENGINE:
		source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
		volumes[source_volume] = str(O3DE_ENGINE_SOURCE_DIR)
	elif target is Targets.GEM:
		gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
		volumes[gems_volume] = str(O3DE_GEMS_DIR)
	elif target is Targets.SELF:
		binds[str(get_real_bin_file().parent)] = str(O3DE_ENGINE_SOURCE_DIR)
	else:
		throw_error(Messages.INVALID_TARGET, target)

	if DEVELOPMENT_MODE:
		scripts_dir = get_real_bin_file().parent / SCRIPTS_PATH
		binds[str(scripts_dir)] = str(ROOT_DIR)

	completed = CONTAINER_CLIENT.run_foreground_container(
		updater_image,
		[ command, target, *arguments ],
		interactive = is_tty(),
		binds = binds,
		volumes = volumes
	)

	return completed


def search_updates():
	resume_command = [
		get_bin_name(),
		CliCommands.REFRESH.value,
		CliSubCommands.SELF.value[0]
	]

	if CONTAINER_CLIENT.is_in_container():
		installation_dir = ROOT_DIR
		mapping = { str(installation_dir): get_real_bin_file().parent }
	else:
		installation_dir = get_real_bin_file().parent
		mapping = None

	check_ownership(installation_dir, Messages.CHANGE_OWNERSHIP_SELF, resume_command, mapping)

	run_updater(None, UpdaterCommands.REFRESH, Targets.SELF)


# --- FUNCTIONS (ENGINE) ---

def apply_engine_updates(engine_version, rebuild):
	if not is_engine_installed(engine_version):
		throw_error(Messages.MISSING_VERSION, Targets.ENGINE.value, engine_version)

	source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
	source_dir = CONTAINER_CLIENT.get_volume_path(source_volume)
	if source_dir is None:
		throw_error(Messages.ENGINE_SOURCE_NOT_FOUND, source_volume)

	build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
	build_dir = CONTAINER_CLIENT.get_volume_path(build_volume)
	if build_dir is None:
		throw_error(Messages.ENGINE_BUILD_NOT_FOUND, build_volume)

	install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
	install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)
	if install_dir is None:
		throw_error(Messages.ENGINE_INSTALL_NOT_FOUND, install_volume)

	installed_configs = []
	for engine_config in O3DE_Configs:
		install_builder_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_BUILDER, engine_version, engine_config)
		install_runner_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_RUNNER, engine_version, engine_config)

		if (
			has_build_config(build_dir, engine_config) or
		   	has_install_config(install_dir, engine_config) or
		   	CONTAINER_CLIENT.image_exists(install_builder_image) or
		   	CONTAINER_CLIENT.image_exists(install_runner_image)
		):
			installed_configs.append(engine_config)

	upgraded = run_updater(engine_version, UpdaterCommands.UPGRADE, Targets.ENGINE)
	if not upgraded:
		throw_error(Messages.UNCOMPLETED_UPGRADE)

	if len(installed_configs) == 0:
		print_msg(Level.INFO, Messages.UPGRADE_ENGINE_COMPLETED_SOURCE_ONLY)

	elif not rebuild:
		print_msg(Level.INFO, Messages.SKIP_REBUILD)

	result_type, engine_repository = get_repository_from_source(source_dir)
	if result_type is not RepositoryResultType.OK:
		throw_error(Messages.BINDING_INVALID_REPOSITORY)

	if CONTAINER_CLIENT.is_in_container():
		mapping = { "/var/lib/docker/volumes": get_real_volumes_dir() } if CONTAINER_CLIENT.is_in_container() else None
		for mapping_from, mapping_to in mapping.items():
			source_path = source_dir.relative_to(mapping_from)
			source_dir = mapping_to / source_path

	print_msg(Level.INFO, Messages.RUN_EXTERNAL_COMMANDS, "(or use your preferred GIT client)")
	print_msg(Level.INFO, "cd {}".format(source_dir))
	print_msg(Level.INFO, "git lfs pull")

	if (len(installed_configs) == 0) or not rebuild:
		exit(0)

	print_msg(Level.INFO, '')
	print_msg(Level.INFO, Messages.RUN_RESUME_COMMAND)

	remove_build = CONTAINER_CLIENT.is_volume_empty(build_volume)
	remove_install = CONTAINER_CLIENT.is_volume_empty(install_volume)

	for engine_config in O3DE_Configs:
		install_builder_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_BUILDER, engine_version, engine_config)
		install_runner_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_RUNNER, engine_version, engine_config)

		if CONTAINER_CLIENT.image_exists(install_builder_image) and CONTAINER_CLIENT.image_exists(install_runner_image):
			save_images = True
		elif CONTAINER_CLIENT.image_exists(install_builder_image):
			save_images = Images.BUILDER
		elif CONTAINER_CLIENT.image_exists(install_runner_image):
			save_images = Images.RUNNER
		else:
			save_images = False

		resume_command = [ get_bin_name(), CliCommands.INSTALL.value, print_option(LongOptions.FORCE) ]
		if engine_repository.url != O3DE_REPOSITORY_URL:
			resume_command.append(print_option(LongOptions.REPOSITORY, engine_repository.url))
		
		if engine_repository.branch is not None:
			resume_command.append(print_option(LongOptions.BRANCH, engine_repository.branch))
		elif engine_repository.revision is not None:
			resume_command.append(print_option(LongOptions.COMMIT, engine_repository.revision))

		if engine_config != O3DE_DEFAULT_CONFIG:
			resume_command.append(print_option(LongOptions.CONFIG, engine_config))

		if remove_build:
			resume_command.append(print_option(LongOptions.REMOVE_BUILD))

		if remove_install:
			resume_command.append(print_option(LongOptions.REMOVE_INSTALL))

		if save_images is not False:
			if save_images is True:
				resume_command.append(print_option(LongOptions.SAVE_IMAGES))
			else:
				resume_command.append(print_option(LongOptions.SAVE_IMAGES, save_images))

		resume_command.append(engine_version)
		resume_command = ' '.join(resume_command)

		print_msg(Level.INFO, resume_command)


def install_engine(repository, engine_version, engine_config, force = False, remove_build = False, remove_install = False, save_images = False):
	repository_protocol, repository_url, repository_reference = parse_repository_url(repository)

	if remove_build and remove_install and not save_images:
		throw_error(Messages.INVALID_INSTALL_OPTIONS_REMOVE)
	elif remove_install and not save_images:
		binaries = [ "Editor" ]
	else:
		binaries = []

	resume_command = [
		get_bin_name(),
		CliCommands.INSTALL.value,
		CliSubCommands.ENGINE.value,
		print_option(LongOptions.FORCE)
	]

	if repository_url != O3DE_REPOSITORY_URL:
		resume_command.append(print_option(LongOptions.REPOSITORY, repository_url))
	
	if repository_reference is not None:
		if is_commit(repository_reference):
			resume_command.append(print_option(LongOptions.COMMIT, repository_reference))
		elif repository_reference != engine_version:
			resume_command.append(print_option(LongOptions.BRANCH, repository_reference))

	if engine_config != O3DE_DEFAULT_CONFIG:
		resume_command.append(print_option(LongOptions.CONFIG, engine_config))

	if remove_build:
		resume_command.append(print_option(LongOptions.REMOVE_BUILD))

	if remove_install:
		resume_command.append(print_option(LongOptions.REMOVE_INSTALL))

	if save_images is not False:
		if save_images is True:
			resume_command.append(print_option(LongOptions.SAVE_IMAGES))
		else:
			resume_command.append(print_option(LongOptions.SAVE_IMAGES, save_images))

	resume_command.append(engine_version)
	resume_command = ' '.join(resume_command)

	source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
	build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
	install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
	packages_volume = CONTAINER_CLIENT.get_volume_name(Volumes.PACKAGES)

	required_volumes = [ source_volume, build_volume, install_volume, packages_volume ]
	initialize_volumes(required_volumes, resume_command, force)

	source_dir = CONTAINER_CLIENT.get_volume_path(source_volume)
	build_dir = CONTAINER_CLIENT.get_volume_path(build_volume)
	install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)
	packages_dir = CONTAINER_CLIENT.get_volume_path(packages_volume)

	if not is_engine_installed(engine_version):
		downloaded = run_updater(engine_version, UpdaterCommands.INIT, Targets.ENGINE, repository_url, repository_reference)
		if not downloaded:
			throw_error(Messages.UNCOMPLETED_INIT_ENGINE)

		if CONTAINER_CLIENT.is_in_container():
			mapping = { "/var/lib/docker/volumes": get_real_volumes_dir() }
			for mapping_from, mapping_to in mapping.items():
				source_path = source_dir.relative_to(mapping_from)
				source_dir = mapping_to / source_path

		print_msg(Level.INFO, Messages.RUN_EXTERNAL_COMMANDS, "(or use your preferred GIT client)")
		print_msg(Level.INFO, "cd {}".format(source_dir))
		print_msg(Level.INFO, "git lfs install")
		print_msg(Level.INFO, "git lfs pull")
		print_msg(Level.INFO, '')
		print_msg(Level.INFO, Messages.RUN_RESUME_COMMAND)
		print_msg(Level.INFO, resume_command)

		exit(0)

	if not force:
		if not CONTAINER_CLIENT.is_volume_empty(install_volume):
			throw_error(Messages.INSTALL_ALREADY_EXISTS, Targets.ENGINE.value.capitalize(), engine_version)

		if has_build_config(build_dir, engine_config):
			throw_error(Messages.INSTALL_AND_CONFIG_ALREADY_EXISTS, engine_version, engine_config)

	if not is_engine_installed(engine_version):
		throw_error(Messages.INVALID_ENGINE_SOURCE)

	if not RUN_CONTAINERS:
		check_requirements(resume_command)

	initialized = run_builder(engine_version, None, None, None, BuilderCommands.INIT, Targets.ENGINE)
	if not initialized:
		throw_error(Messages.UNCOMPLETED_INSTALL)

	built = run_builder(engine_version, None, None, None, BuilderCommands.BUILD, Targets.ENGINE, engine_config, *binaries)
	if not built:
		throw_error(Messages.UNCOMPLETED_INSTALL)

	if remove_build:
		config_limit = None
		for config in O3DE_Configs:
			if (config != engine_config) and has_build_config(build_dir, config):
				config_limit = engine_config
				break

		run_builder(engine_version, None, None, None, BuilderCommands.CLEAN, Targets.ENGINE, config_limit, True, False)

	install_builder_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_BUILDER, engine_version, engine_config)
	install_runner_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_RUNNER, engine_version, engine_config)

	if save_images:
		if CONTAINER_CLIENT.is_volume_empty(install_volume):
			throw_error(Messages.UNCOMPLETED_INSTALL)

		from_images = []
		new_images = []

		if (save_images == Images.BUILDER.value) or (save_images is True):
			from_images.append(Images.BUILDER)
			new_images.append(install_builder_image)

		if (save_images == Images.RUNNER.value) or (save_images is True):
			from_images.append(Images.RUNNER)
			new_images.append(install_runner_image)		

		for from_image_type, new_image_name in zip(from_images, new_images):
			from_image = CONTAINER_CLIENT.get_image_name(from_image_type)

			new_container = None
			try:
				new_container = CONTAINER_CLIENT.run_detached_container(from_image, wait = True, network_disabled = True)

				config_dir = get_install_config_path(O3DE_ENGINE_INSTALL_DIR, engine_config)

				executed = CONTAINER_CLIENT.exec_in_container(new_container, [ "mkdir", "--parents", config_dir ])
				if not executed:
					throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)

				for content in install_dir.iterdir():
					if content.is_dir() and (content.name == "bin"):
						continue

					copied = CONTAINER_CLIENT.copy_to_container(new_container, content, O3DE_ENGINE_INSTALL_DIR)
					if not copied:
						throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)

				copied = CONTAINER_CLIENT.copy_to_container(new_container, install_dir / config_dir.relative_to(O3DE_ENGINE_INSTALL_DIR), config_dir, content_only = True)
				if not copied:
					throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)

				copied = CONTAINER_CLIENT.copy_to_container(new_container, packages_dir, O3DE_PACKAGES_DIR, content_only = True)
				if not copied:
					throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)

				new_image = new_container.commit(				
					tag = new_image_name,
					changes = [
						"ENTRYPOINT [ \"python3\", \"-m\", \"o3tanks." + from_image_type.value + "\" ]",
						"CMD []"
					]
				)

				if new_image is None:
					throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)
				elif (new_image is not None) and (len(new_image.tags) == 0) and (len(new_image.id) > 0):
					new_image.tag(new_image_name)

			except docker.errors.ContainerError:
				throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)

			finally:
				if new_container is not None:
					new_container.kill()

	else:
		CONTAINER_CLIENT.remove_image(install_builder_image)
		CONTAINER_CLIENT.remove_image(install_runner_image)

	if remove_install:
		config_limit = None
		for config in O3DE_Configs:
			if (config == engine_config) and has_install_config(install_dir, config):
				config_limit = engine_config
				break

		run_builder(engine_version, None, None, None, BuilderCommands.CLEAN, Targets.ENGINE, config_limit, False, True)


def install_missing_engine(project_dir, engine_url):
	print_msg(Level.INFO, Messages.MISSING_INSTALL_ENGINE, engine_url)
	if not ask_for_confirmation(Messages.INSTALL_QUESTION):
		exit(1)

	while True:
		engine_version = ask_for_input(Messages.INSERT_VERSION_NAME)
		if not is_engine_version(engine_version):
			print_msg(Level.INFO, Messages.INVALID_VERSION, engine_version)
		elif is_engine_installed(engine_version):
			print_msg(Level.INFO, Messages.VERSION_ALREADY_EXISTS, engine_version)
		else:
			break

	run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, EngineSettings.VERSION.value.section, EngineSettings.VERSION.value.index, EngineSettings.VERSION.value.name, engine_version, False, False, False)

	check_updater()

	engine_config = O3DE_DEFAULT_CONFIG
	install_engine(engine_url, engine_version, engine_config)


def install_missing_gem(project_dir, gem_index, gem_url):
	print_msg(Level.INFO, Messages.MISSING_INSTALL_GEM, gem_url)
	if not ask_for_confirmation(Messages.INSTALL_QUESTION):
		exit(1)

	while True:
		gem_version = ask_for_input(Messages.INSERT_VERSION_NAME)
		if not is_gem_version(gem_version):
			print_msg(Level.INFO, Messages.INVALID_VERSION, gem_version)
		elif is_gem_installed(gem_version):
			print_msg(Level.INFO, Messages.VERSION_ALREADY_EXISTS, gem_version)
		else:
			break

	run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, GemSettings.VERSION.value.section, gem_index, GemSettings.VERSION.value.name, gem_version, False, False, False)

	check_updater()

	install_gem(gem_url, gem_version)


def list_engines():
	MAX_LENGTHS_VERSION=20
	MAX_LENGTHS_SIZE=10
	MAX_LENGTHS_CONFIG=7

	table_row = "{:<" + str(MAX_LENGTHS_VERSION) + "} {:^" + str(MAX_LENGTHS_SIZE) + "}"

	engines_row = table_row + "   {:^" + str(MAX_LENGTHS_SIZE) + "} {:^" + str(MAX_LENGTHS_SIZE) + "} {:^" + str(MAX_LENGTHS_SIZE) + "}  "
	for config in O3DE_Configs:
		engines_row += " {:^" + str(MAX_LENGTHS_CONFIG) + "}"

	gems_row = table_row
	packages_row = table_row

	all_config_names = [ config.value.upper() for config in O3DE_Configs ]
	print(engines_row.format("ENGINES", "TOTAL", "SOURCE", "BUILD", "INSTALL", *all_config_names))

	engine_versions = get_all_engine_versions()
	if len(engine_versions) == 0:
		all_empty_configs = [ '' for config in O3DE_Configs ]
		print(engines_row.format("<none>", '', '', '', '', *all_empty_configs))

	else:
		for engine_version in engine_versions:
			source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
			source_dir = CONTAINER_CLIENT.get_volume_path(source_volume)
			source_size = calculate_size(source_dir)

			build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
			build_dir = CONTAINER_CLIENT.get_volume_path(build_volume)
			build_size = calculate_size(build_dir)

			install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
			install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)
			install_size = calculate_size(install_dir)

			if not RUN_CONTAINERS:
				source_size -= (build_size + install_size)

			total_size = source_size + build_size + install_size

			installed_configs = []
			for config in O3DE_Configs:
				install_image = CONTAINER_CLIENT.get_image_name(Volumes.INSTALL, engine_version, config)

				mark = 'x' if has_build_config(build_dir, config) or has_install_config(install_dir, config) or CONTAINER_CLIENT.image_exists(install_image) else ''
				installed_configs.append(mark)

			print(engines_row.format(
				engine_version if len(engine_version) <= MAX_LENGTHS_VERSION else (engine_version[0:MAX_LENGTHS_VERSION-3] + "..."),
				format_size(total_size),
				format_size(source_size),
				format_size(build_size),
				format_size(install_size),
				*installed_configs
			))

	print('')
	print(gems_row.format("GEMS", "TOTAL"))

	gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
	gems_dir = CONTAINER_CLIENT.get_volume_path(gems_volume)

	gem_versions = get_all_gem_versions(gems_dir)
	if len(gem_versions) == 0:
		print(gems_row.format("-", ""))
	else:
		for gem_version in gem_versions:
			gem_dir = get_gem_path(gems_dir, gem_version)
			gem_size = calculate_size(gem_dir)
			print(gems_row.format(gem_version, format_size(gem_size)))

	packages_volume = CONTAINER_CLIENT.get_volume_name(Volumes.PACKAGES)
	packages_dir = CONTAINER_CLIENT.get_volume_path(packages_volume)
	packages_size = calculate_size(packages_dir)

	print('')
	print(packages_row.format("PACKAGES", "TOTAL"))
	if packages_size < 0:
		print(packages_row.format("-", ""))
	else:
		print(packages_row.format("all", format_size(packages_size)))

	if DATA_DIR is not None:
		print('')
		print("DATA LOCATION")
		print(str(DATA_DIR))


def search_engine_updates(engine_version):
	if not is_engine_installed(engine_version):
		throw_error(Messages.MISSING_VERSION, Targets.ENGINE.value, engine_version)

	run_updater(engine_version, UpdaterCommands.REFRESH, Targets.ENGINE)


def uninstall_engine(engine_version, engine_config = None, force = False):
	source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
	if not force and not CONTAINER_CLIENT.volume_exists(source_volume):
		throw_error(Messages.VERSION_NOT_INSTALLED, engine_version)
	
	build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
	install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)

	if engine_config is None:
		CONTAINER_CLIENT.remove_volume(source_volume)
		CONTAINER_CLIENT.remove_volume(build_volume)
		CONTAINER_CLIENT.remove_volume(install_volume)

		for config in O3DE_Configs:
			install_builder_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_BUILDER, engine_version, config)
			install_runner_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_RUNNER, engine_version, config)

			CONTAINER_CLIENT.remove_image(install_builder_image)
			CONTAINER_CLIENT.remove_image(install_runner_image)

	else:
		build_dir = CONTAINER_CLIENT.get_volume_path(build_volume)
		install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)

		no_config = True

		if has_build_config(build_dir, engine_config) or has_install_config(install_dir, engine_config):
			run_builder(engine_version, None, None, None, BuilderCommands.CLEAN, Targets.ENGINE, engine_config, False, False)
			no_config = False
		
		install_builder_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_BUILDER, engine_version, engine_config)
		if CONTAINER_CLIENT.image_exists(install_builder_image):
			CONTAINER_CLIENT.remove_image(install_builder_image)
			no_config = False		

		install_runner_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_RUNNER, engine_version, engine_config)
		if CONTAINER_CLIENT.image_exists(install_runner_image):
			CONTAINER_CLIENT.remove_image(install_runner_image)
			no_config = False		

		if no_config:
			throw_error(Messages.CONFIG_NOT_INSTALLED, engine_config.value, engine_version)

	print_msg(Level.INFO, Messages.UNINSTALL_ENGINE_COMPLETED, engine_version)


# --- FUNCTIONS (GEM) ---

def add_gem_to_project(project_dir, gem_reference, rebuild):
	engine_version, external_gem_dirs = check_project_dependencies(project_dir)
	if not is_engine_installed(engine_version):
		throw_error(Messages.MISSING_VERSION, Targets.ENGINE.value, engine_version)

	gem_value = gem_reference.print()
	if gem_reference.type is GemReferenceTypes.ENGINE:
		gem_value = "{}/1".format(gem_value)

	if gem_reference.type is GemReferenceTypes.PATH:
		if external_gem_dirs is None:
			external_gem_dirs = []

		external_gem_dirs.append(gem_reference.value)

	added = run_builder(engine_version, None, project_dir, external_gem_dirs, BuilderCommands.SETTINGS, Targets.PROJECT, Settings.GEMS.value, -1, None, gem_value, False, False, False)

	if added and rebuild:
		engine_config = select_recommended_config(engine_version)
		if engine_config is None:
			throw_error(Messages.VERSION_NOT_FOUND, engine_version)

		print_msg(Level.INFO, Messages.ADD_GEM_REBUILD, gem_value)

		built = run_builder(engine_version, engine_config, project_dir, external_gem_dirs, BuilderCommands.BUILD, Targets.PROJECT, engine_config)
		if not built:
			throw_error(Messages.UNCOMPLETED_BUILD_PROJECT)

	return added


def apply_gem_updates(gem_version):
	if not is_gem_installed(gem_version):
		throw_error(Messages.MISSING_VERSION, Targets.GEM.value, gem_version)

	upgraded = run_updater(None, UpdaterCommands.UPGRADE, Targets.GEM, gem_version)
	if not upgraded:
		throw_error(Messages.UNCOMPLETED_UPGRADE)

	print_msg(Level.INFO, Messages.UPGRADE_GEM_COMPLETED)


def install_gem(repository, gem_version, force = False):
	repository_protocol, repository_url, repository_reference = parse_repository_url(repository)

	if not force and is_gem_installed(gem_version):
		throw_error(Messages.INSTALL_ALREADY_EXISTS, Targets.GEM.value.capitalize(), gem_version)

	resume_command = [
		get_bin_name(),
		CliCommands.INSTALL.value,
		CliSubCommands.GEM.value,
		repository_url
	]

	if repository_reference is not None:
		if is_commit(repository_reference):
			resume_command.append(print_option(LongOptions.COMMIT, repository_reference))
		else:
			resume_command.append(print_option(LongOptions.BRANCH, repository_reference))

	resume_command.append(gem_version)
	resume_command = ' '.join(resume_command)

	gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
	initialize_volumes([ gems_volume ], resume_command, force)

	downloaded = run_updater(None, UpdaterCommands.INIT, Targets.GEM, repository_url, repository_reference, gem_version)
	if not downloaded:
		throw_error(Messages.UNCOMPLETED_INSTALL)

	if not is_gem_installed(gem_version):
		gems_dir = CONTAINER_CLIENT.get_volume_path(gems_volume)
		gem_dir = search_gem_path(gems_dir, gem_version)
		throw_error(Messages.INVALID_GEM_SOURCE, gem_dir)

	return gem_version


def remove_gem_from_project(project_dir, gem_reference, rebuild):
	if gem_reference.type is GemReferenceTypes.ENGINE:
		gem_index = -1
		gem_value = "{}/0".format(gem_reference.print())
		clear_option = False
	else:
		gem_index = search_gem_index(project_dir, gem_reference)
		if gem_index is None:
			throw_error(Messages.GEM_NOT_ACTIVE, gem_reference.print())
		gem_value = None
		clear_option = True

	engine_version, external_gem_dirs = check_project_dependencies(project_dir)
	if not is_engine_installed(engine_version):
		throw_error(Messages.MISSING_VERSION, Targets.ENGINE.value, engine_version)

	removed = run_builder(engine_version, None, project_dir, external_gem_dirs, BuilderCommands.SETTINGS, Targets.PROJECT, Settings.GEMS.value, gem_index, None, gem_value, clear_option, False, False)

	if removed and rebuild:
		engine_config = select_recommended_config(engine_version)
		if engine_config is None:
			throw_error(Messages.VERSION_NOT_FOUND, engine_version)

		print_msg(Level.INFO, Messages.REMOVE_GEM_REBUILD, gem_index)

		built = run_builder(engine_version, engine_config, project_dir, external_gem_dirs, BuilderCommands.BUILD, Targets.PROJECT, engine_config)
		if not built:
			throw_error(Messages.UNCOMPLETED_BUILD_PROJECT)

	return removed


def search_gem_updates(gem_version):
	if not is_gem_installed(gem_version):
		throw_error(Messages.MISSING_VERSION, Targets.GEM.value, gem_version)

	run_updater(None, UpdaterCommands.REFRESH, Targets.GEM, gem_version)


def uninstall_gem(gem_version):
	gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
	if not CONTAINER_CLIENT.volume_exists(gems_volume):
		throw_error(Messages.VOLUME_NOT_FOUND, gems_volume)
	
	gems_dir = CONTAINER_CLIENT.get_volume_path(gems_volume)
	parent_gem_dir = get_gem_path(gems_dir, gem_version)
	if not parent_gem_dir.is_dir():
		throw_error(Messages.VERSION_NOT_INSTALLED, gem_version)

	gem_dir = search_gem_path(parent_gem_dir)
	if gem_dir is None:
		throw_error(Messages.INVALID_GEM_SOURCE, gem_version)

	removed = remove_directory(parent_gem_dir, require_confirmation = True)
	if not removed:
		throw_error(Messages.UNCOMPLETED_UNINSTALL)

	print_msg(Level.INFO, Messages.UNINSTALL_GEM_COMPLETED, gem_version)


# --- FUNCTIONS (PROJECT) ---

def create_project(engine_version, project_dir, project_name = None, base_template = None, has_examples = False):
	engine_config = select_recommended_config(engine_version)
	if engine_config is None:
		throw_error(Messages.VERSION_NOT_FOUND, engine_version)

	project_type = Targets.PROJECT

	resume_command = [ get_bin_name(), CliCommands.INIT.value ]
	if (base_template is not None):
		if base_template in O3DE_GemTemplates:
			project_type = Targets.GEM

			resume_command.append(CliSubCommands.GEM.value)

			if base_template is O3DE_GemTemplates.ASSETS_ONLY:
				gem_type = O3DE_GemTypes.ASSETS_ONLY
			elif base_template is O3DE_GemTemplates.CODE_AND_ASSETS:
				gem_type = O3DE_GemTypes.CODE_AND_ASSETS
			else:
				throw_error(Messages.INVALID_GEM_TEMPLATE, base_template)

			resume_command.append(print_option(LongOptions.TYPE, gem_type.value))

			if not has_examples:
				resume_command.append(print_option(LongOptions.SKIP_EXAMPLES))

		elif base_template in O3DE_ProjectTemplates:
			resume_command.append(CliSubCommands.PROJECT.value)

			if base_template is O3DE_ProjectTemplates.MINIMAL:
				resume_command.append(print_option(LongOptions.MINIMAL_PROJECT))

		else:
			throw_error(Messages.INVALID_TEMPLATE, base_template)

	if engine_version != O3DE_DEFAULT_VERSION:
		resume_command.append(print_option(LongOptions.ENGINE, engine_version))
	
	if project_name is not None:
		resume_command.append(print_option(LongOptions.ALIAS, project_name))
	else:
		project_name = (get_real_project_dir() if CONTAINER_CLIENT.is_in_container() else project_dir).name

	resume_command = ' '.join(resume_command)

	mapping = { str(project_dir): get_real_project_dir() } if CONTAINER_CLIENT.is_in_container else None

	check_ownership(project_dir, Messages.CHANGE_OWNERSHIP_PROJECT, resume_command, mapping)

	if project_type is Targets.GEM:
		initialized = run_builder(engine_version, engine_config, project_dir, None, BuilderCommands.INIT, Targets.GEM, project_name, base_template, has_examples, engine_version)
	elif project_type is Targets.PROJECT:
		initialized = run_builder(engine_version, engine_config, project_dir, None, BuilderCommands.INIT, Targets.PROJECT, project_name, base_template, engine_version)
	else:
		throw_error(Messages.INVALID_TARGET, project_type)

	if initialized:
		print_msg(Level.INFO, Messages.INIT_COMPLETED, get_real_project_dir() if CONTAINER_CLIENT.is_in_container() else project_dir)


def build_project(project_dir, binary, config):
	engine_version, external_gem_dirs = check_project_dependencies(project_dir)

	run_builder(engine_version, config, project_dir, external_gem_dirs, BuilderCommands.BUILD, Targets.PROJECT, config, binary)


def clean_project(project_dir, config, force = False):
	engine_version, external_gem_dirs = check_project_dependencies(project_dir)

	run_builder(engine_version, config, project_dir, external_gem_dirs, BuilderCommands.CLEAN, Targets.PROJECT, config, force)


def manage_project_settings(project_dir, setting_key_section , setting_key_index, setting_key_name, setting_value, clear):
	run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, setting_key_section, setting_key_index, setting_key_name, setting_value, clear, False, True)


def open_project(project_dir, engine_config = None, new_engine_version = None):
	if new_engine_version is None:
		engine_version, external_gem_dirs = check_project_dependencies(project_dir)
	else:
		if not is_engine_installed(new_engine_version):
			throw_error(Messages.MISSING_VERSION, Targets.ENGINE.value, new_engine_version)

		engine_version = new_engine_version
		not_used, external_gem_dirs = check_project_dependencies(project_dir, check_engine = False)

	if engine_config is None:
		engine_config = select_recommended_config(engine_version)
		if engine_config is None:
			throw_error(Messages.VERSION_NOT_FOUND, engine_version)

	if new_engine_version is not None:
		run_builder(engine_version, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, Settings.ENGINE.value, None, None, new_engine_version, False, True, False)

	editor_library_file = project_dir / "build" / OPERATING_SYSTEM.family.value / "bin" / engine_config.value / get_library_filename("libEditorCore")
	if not editor_library_file.is_file():
		built = run_builder(engine_version, engine_config, project_dir, external_gem_dirs, BuilderCommands.BUILD, Targets.PROJECT, engine_config)
		if not built:
			throw_error(Messages.UNCOMPLETED_BUILD_PROJECT)

	run_runner(engine_version, engine_config, project_dir, external_gem_dirs, False, RunnerCommands.OPEN, engine_config)


def run_project(project_dir, binary, config):	
	engine_version, external_gem_dirs = check_project_dependencies(project_dir)
	
	if binary is O3DE_ProjectBinaries.CLIENT:
		headless = False
	elif binary is O3DE_ProjectBinaries.SERVER:
		headless = True
	else:
		throw_error(Messages.INVALID_BINARY, binary)

	run_runner(engine_version, config, project_dir, external_gem_dirs, headless, RunnerCommands.RUN, binary, config)


# --- CLI HANDLER (GENERIC) ---

def handle_empty_command(**kwargs):
	throw_error(Messages.EMPTY_COMMAND)


def handle_empty_target(**kwargs):
	throw_error(Messages.EMPTY_TARGET)


def handle_help_command(parser):
	parser.print_help()


def handle_version_command():
	print_version_info()


# --- CLI HANDLER (ENGINE) ---

def handle_install_engine_command(version_name, engine_config_name, repository, fork, branch, tag, commit, force, remove_build, remove_install, save_images, **kwargs):
	repository_url = generate_repository_url(repository, fork, branch, tag, commit, default_repository = O3DE_REPOSITORY_URL)

	if version_name is not None:
		engine_version = version_name
	else:
		if fork is not None:
			user_name = fork.split('/')
			engine_version = "{}-{}".format(user_name[0], branch if branch is not None else O3DE_DEFAULT_VERSION)

		elif repository is None or repository == O3DE_REPOSITORY_URL:
			engine_version = branch if branch is not None else tag if tag is not None else O3DE_DEFAULT_VERSION

		else:
			if repository_url.startswith(O3DE_REPOSITORY_HOST):
				matches = re.match(r"^[\w]+://[^/]+/([^/]+)/(.+)\.git.*$", repository_url)
				user_name = matches.group(1)
				project_name = matches.group(2)

				engine_version = "{}-{}".format(user_name, project_name)

			else:
				matches = re.match(r"^(.*/)?([^/#]+)", repository_url)
				engine_version = matches.group(2)
				if engine_version.endswith(".git"):
					engine_version = engine_version[:-4]

			if branch is not None:
				engine_version += "-{}".format(branch)
			elif tag is not None:
				engine_version += "-{}".format(tag)

	if not is_engine_version(engine_version):
		throw_error(Messages.INVALID_VERSION, engine_version)

	engine_config = O3DE_Configs.from_value(engine_config_name)
	if engine_config is None:
		throw_error(Messages.INVALID_CONFIG, engine_config_name)

	try:
		check_container_client()
		check_updater()
		check_builder()
		if save_images is not False:
			check_runner()

		install_engine(repository_url, engine_version, engine_config, force, remove_build, remove_install, save_images)
		print_msg(Level.INFO, Messages.INSTALL_ENGINE_COMPLETED, engine_version)

	finally:
		close_container_client()


def handle_list_command():
	check_container_client()
	list_engines()
	close_container_client()


def handle_refresh_engine_command(engine_version):
	if not is_engine_version(engine_version):
		throw_error(Messages.INVALID_VERSION, engine_version)

	try:
		check_container_client()
		check_updater()

		if engine_version in CliSubCommands.SELF.value:
			search_updates()
		else:
			search_engine_updates(engine_version)

	finally:
		close_container_client()


def handle_uninstall_engine_command(engine_version, engine_config_name, force):
	if not is_engine_version(engine_version):
		throw_error(Messages.INVALID_VERSION, engine_version)

	if engine_config_name is not None:
		engine_config = O3DE_Configs.from_value(engine_config_name)
		if engine_config is None:
			throw_error(Messages.INVALID_CONFIG, engine_config_name)
	else:
		engine_config = None

	try:
		check_container_client()
	
		uninstall_engine(engine_version, engine_config, force)

	finally:
		close_container_client()


def handle_upgrade_engine_command(engine_version, rebuild):
	if not is_engine_version(engine_version):
		throw_error(Messages.INVALID_VERSION, engine_version)

	try:
		check_container_client()
		check_updater()
		if rebuild:
			check_builder()		
			check_runner()

		apply_engine_updates(engine_version, rebuild)

	finally:
		close_container_client()


# --- CLI HANDLER (GEM) ---

def handle_add_gem_command(project_path, gem_value, rebuild):
	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	try:
		check_container_client()
		check_builder()

		gem_reference = parse_gem_reference(gem_value, resolve_path = (not CONTAINER_CLIENT.is_in_container()))

		added = add_gem_to_project(project_dir, gem_reference, rebuild)
		if added:
			print_msg(
				Level.INFO,
				Messages.ADD_GEM_COMPLETED if rebuild else Messages.ADD_GEM_COMPLETED_SKIP_REBUILD,
				gem_reference.print()
			)

	finally:
		close_container_client()


def handle_init_gem_command(engine_version, project_path, alias, gem_type, has_examples):
	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, project_path)
	elif not is_directory_empty(project_dir):
		throw_error(Messages.PROJECT_DIR_NOT_EMPTY, project_path)

	try:
		check_container_client()
		check_builder()

		if gem_type == O3DE_GemTypes.ASSETS_ONLY.value:
			base_template = O3DE_GemTemplates.ASSETS_ONLY
		elif gem_type == O3DE_GemTypes.CODE_AND_ASSETS.value:
			base_template = O3DE_GemTemplates.CODE_AND_ASSETS
		else:
			throw_error(Messages.INVALID_GEM_TYPE, gem_type)

		create_project(engine_version, project_dir, alias, base_template, has_examples)

	finally:
		close_container_client()


def handle_install_gem_command(version_name, repository, branch, tag, commit, force, **kwargs):
	repository_url = generate_repository_url(repository, None, branch, tag, commit)

	if version_name is not None:
		gem_version = version_name
	else:
		if repository_url.startswith(O3DE_REPOSITORY_HOST):
			matches = re.match(r"^[\w]+://[^/]+/([^/]+)/(.+)\.git.*$", repository_url)
			user_name = matches.group(1)
			project_name = matches.group(2)
			
			gem_version = "{}-{}".format(user_name, project_name)

		else:
			matches = re.match(r"^(.*/)?([^/#]+)", repository_url)
			gem_version = matches.group(2)
			if gem_version.endswith(".git"):
				gem_version = gem_version[:-4]

		if branch is not None:
			gem_version += "-{}".format(branch)
		elif tag is not None:
			gem_version += "-{}".format(tag)

	if not is_gem_version(gem_version):
		throw_error(Messages.INVALID_VERSION, gem_version)

	try:
		check_container_client()
		check_updater()

		install_gem(repository_url, gem_version, force)
		print_msg(Level.INFO, Messages.INSTALL_GEM_COMPLETED, gem_version)

	finally:
		close_container_client()


def handle_refresh_gem_command(gem_version):
	if not is_gem_version(gem_version):
		throw_error(Messages.INVALID_VERSION, gem_version)

	try:
		check_container_client()
		check_updater()

		search_gem_updates(gem_version)

	finally:
		close_container_client()


def handle_remove_gem_command(project_path, gem_value, rebuild):
	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	try:
		check_container_client()
		check_builder()

		gem_reference = parse_gem_reference(gem_value, resolve_path = (not CONTAINER_CLIENT.is_in_container()))

		removed = remove_gem_from_project(project_dir, gem_reference, rebuild)
		if removed:
			print_msg(
				Level.INFO,
				Messages.REMOVE_GEM_COMPLETED if rebuild else Messages.REMOVE_GEM_COMPLETED_SKIP_REBUILD,
				gem_reference.print()
			)

	finally:
		close_container_client()


def handle_uninstall_gem_command(gem_version):
	if not is_gem_version(gem_version):
		throw_error(Messages.INVALID_VERSION, gem_version)

	try:
		check_container_client()
	
		uninstall_gem(gem_version)

	finally:
		close_container_client()


def handle_upgrade_gem_command(gem_version):
	if not is_gem_version(gem_version):
		throw_error(Messages.INVALID_VERSION, gem_version)

	try:
		check_container_client()
		check_updater()

		apply_gem_updates(gem_version)

	finally:
		close_container_client()


# --- CLI HANDLER (PROJECT) ---

def parse_project_path(value):
	if ContainerClient.calculate_is_in_container():
		set_real_project_dir(value)
		return O3DE_PROJECT_SOURCE_DIR

	project_dir = pathlib.Path(value if value is not None else '.')
	if not project_dir.is_absolute():
		project_dir = project_dir.resolve()

	return project_dir


def handle_build_command(project_path, binary_name, config_name):
	binary = O3DE_ProjectBinaries.from_value(binary_name)
	if binary is None:
		throw_error(Messages.INVALID_BINARY, binary_name)

	config = O3DE_Configs.from_value(config_name)
	if config is None:
		throw_error(Messages.INVALID_CONFIG, config_name)

	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	try:
		check_container_client()
		check_builder()

		build_project(project_dir, binary, config)

	finally:
		close_container_client()


def handle_clean_command(project_path, config_name, force):
	config = O3DE_Configs.from_value(config_name)
	if config is None:
		throw_error(Messages.INVALID_CONFIG, config_name)

	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	try:
		check_container_client()
		check_builder()

		clean_project(project_dir, config, force)

	finally:
		close_container_client()


def handle_init_project_command(engine_version, project_path, alias, is_minimal_project):
	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, project_path)
	elif not is_directory_empty(project_dir):
		throw_error(Messages.PROJECT_DIR_NOT_EMPTY, project_path)

	try:
		check_container_client()
		check_builder()

		base_template = O3DE_ProjectTemplates.MINIMAL if is_minimal_project else O3DE_ProjectTemplates.STANDARD
		create_project(engine_version, project_dir, alias, base_template)

	finally:
		close_container_client()


def handle_open_command(project_path, engine_config_name, new_engine_version):
	if engine_config_name is not None:
		engine_config = O3DE_Configs.from_value(engine_config_name)
		if engine_config is None:
			throw_error(Messages.INVALID_CONFIG, engine_config_name)
	else:
		engine_config = None

	if new_engine_version is not None:
		if not is_engine_version(new_engine_version):
			throw_error(Messages.INVALID_VERSION, new_engine_version)

	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	try:
		check_container_client()
		check_runner()
		if new_engine_version is not None:
			check_builder()
	
		open_project(project_dir, engine_config, new_engine_version)

	finally:
		close_container_client()


def handle_run_command(project_path, binary_name, config_name):
	binary = O3DE_ProjectBinaries.from_value(binary_name)
	if binary is None:
		throw_error(Messages.INVALID_BINARY, binary_name)

	config = O3DE_Configs.from_value(config_name)
	if config is None:
		throw_error(Messages.INVALID_CONFIG, config_name)

	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	try:
		check_container_client()
		check_runner()

		run_project(project_dir, binary, config)

	finally:
		close_container_client()


def handle_settings_command(project_path, setting_key, setting_value, clear):
	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	if setting_key is None:
		setting_key_section = None
		setting_key_index = None
		setting_key_name = None
	else:
		matches = re.match(r"^([^\[\.]+)(\[([0-9]+)\])?(\.([^\[\.]+))?$", setting_key)
		if matches is None:
			throw_error(Messages.INVALID_SETTING_SYNTAX, setting_key)

		setting_key_section = matches.group(1)
		setting_key_index = matches.group(3)
		setting_key_name = matches.group(5)

		if (
			setting_key_section is not None and
			setting_key_name is None and
			clear is False
		):
			throw_error(Messages.UNSUPPORTED_INSERT_SETTING_SECTION)

	try:
		check_container_client()
		check_builder()

		manage_project_settings(project_dir, setting_key_section, setting_key_index, setting_key_name, setting_value, clear)

	finally:
		close_container_client()


# --- CLI HANDLER (SELF) ---

def handle_refresh_self_command():
	try:
		check_container_client()
		check_updater()

		search_updates()

	finally:
		close_container_client()


def handle_upgrade_self_command():
	try:
		check_container_client()
		check_updater()

		apply_updates()

	finally:
		close_container_client()


# --- MAIN ---

def main():
	if DEVELOPMENT_MODE:
		print_msg(Level.WARNING, Messages.IS_DEVELOPMENT_MODE)

	if not RUN_CONTAINERS:
		print_msg(Level.WARNING, Messages.IS_NO_CONTAINERS_MODE)

	DESCRIPTIONS_COMMON_BINARY = "Project runtime: {}, {}".format(O3DE_ProjectBinaries.CLIENT.value, O3DE_ProjectBinaries.SERVER.value)
	DESCRIPTIONS_COMMON_CONFIG = "Build configuration: {}, {}, {}".format(O3DE_Configs.DEBUG.value, O3DE_Configs.PROFILE.value, O3DE_Configs.RELEASE.value)
	DESCRIPTIONS_COMMON_GEM = "Gem version"
	DESCRIPTIONS_COMMON_GEM_REFERENCE = "Version name of an installed gem, or path to its local workspace"
	DESCRIPTIONS_COMMON_ENGINE = "Engine version"
	DESCRIPTIONS_COMMON_PROJECT = "Path to the project root, instead of the current directory"

	DESCRIPTIONS_GLOBAL_QUIET = "Suppress all output messages (silent mode)"
	DESCRIPTIONS_GLOBAL_VERBOSE = "Show additional messages (verbose mode)"

	DESCRIPTIONS_INSTALL = "Download, build and install a new engine or a new gem"
	DESCRIPTIONS_INSTALL_FORCE = "Re-install even if already installed / corrupted"
	DESCRIPTIONS_INSTALL_REPOSITORY = "Download from a remote Git repository"
	DESCRIPTIONS_INSTALL_REPOSITORY_BRANCH = "Download a specific branch"
	DESCRIPTIONS_INSTALL_REPOSITORY_COMMIT = "Download a specific commit"
	DESCRIPTIONS_INSTALL_REPOSITORY_FORK = "Download from a fork on GitHub"
	DESCRIPTIONS_INSTALL_REPOSITORY_TAG = "Download a specific tag"
	DESCRIPTIONS_INSTALL_ENGINE = "Download, build and install a new engine version"
	DESCRIPTIONS_INSTALL_ENGINE_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_INSTALL_ENGINE_REMOVE_BUILD = "Remove built files after the building stage"
	DESCRIPTIONS_INSTALL_ENGINE_REMOVE_INSTALL = "Remove installed files after the install stage, or stop at the building stage (if {} is not set)".format(print_option(LongOptions.SAVE_IMAGES))
	DESCRIPTIONS_INSTALL_ENGINE_SAVE_IMAGES = "Generate images containing the engine installation"
	DESCRIPTIONS_INSTALL_GEM = "Download a new gem version"
	DESCRIPTIONS_INSTALL_VERSION = "Name for the new installation"

	DESCRIPTIONS_LIST = "List all installed engines and gems"

	DESCRIPTIONS_REFRESH = "Check if new updates are available for an engine, a gem or this tool"
	DESCRIPTIONS_REFRESH_ENGINE = "Check updates for an engine version"
	DESCRIPTIONS_REFRESH_ENGINE_VERSION = DESCRIPTIONS_COMMON_ENGINE
	DESCRIPTIONS_REFRESH_GEM = "Check updates for a gem version"
	DESCRIPTIONS_REFRESH_GEM_VERSION = DESCRIPTIONS_COMMON_GEM
	DESCRIPTIONS_REFRESH_SELF = "Check updates for this tool"

	DESCRIPTIONS_UNINSTALL = "Uninstall an engine or a gem"
	DESCRIPTIONS_UNINSTALL_ENGINE = "Uninstall an engine version"
	DESCRIPTIONS_UNINSTALL_ENGINE_VERSION = DESCRIPTIONS_COMMON_ENGINE
	DESCRIPTIONS_UNINSTALL_ENGINE_CONFIG = "Uninstall only a specific {}".format(DESCRIPTIONS_COMMON_CONFIG.lower())
	DESCRIPTIONS_UNINSTALL_ENGINE_FORCE = "Remove files even if the installation is corrupted"
	DESCRIPTIONS_UNINSTALL_GEM = "Uninstall a gem version"
	DESCRIPTIONS_UNINSTALL_GEM_VERSION = DESCRIPTIONS_COMMON_GEM

	DESCRIPTIONS_UPGRADE = "Apply new updates to a local installation of an engine or a gem"
	DESCRIPTIONS_UPGRADE_ENGINE = "Apply new updates to an engine installation"
	DESCRIPTIONS_UPGRADE_ENGINE_VERSION = DESCRIPTIONS_COMMON_ENGINE
	DESCRIPTIONS_UPGRADE_ENGINE_SKIP_REBUILD = "Don't re-build all configurations if the upgrade is successfully"
	DESCRIPTIONS_UPGRADE_GEM = "Apply new updates to a gem installation"
	DESCRIPTIONS_UPGRADE_GEM_VERSION = DESCRIPTIONS_COMMON_GEM
	DESCRIPTIONS_UPGRADE_SELF = "Apply new updates to this tool"

	DESCRIPTIONS_ADD = "Add a new resource to the project"
	DESCRIPTIONS_ADD_PROJECT = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_ADD_GEM = "Activate a gem in the project"
	DESCRIPTIONS_ADD_GEM_REFERENCE = DESCRIPTIONS_COMMON_GEM_REFERENCE
	DESCRIPTIONS_ADD_GEM_SKIP_REBUILD = "Don't re-build the project if the gem is added successfully"

	DESCRIPTIONS_BUILD = "Build a project runtime from its source code"
	DESCRIPTIONS_BUILD_BINARY = DESCRIPTIONS_COMMON_BINARY
	DESCRIPTIONS_BUILD_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_BUILD_PROJECT = DESCRIPTIONS_COMMON_PROJECT
	
	DESCRIPTIONS_CLEAN = "Remove all built project files (binaries and intermediates)"
	DESCRIPTIONS_CLEAN_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_CLEAN_FORCE = "Remove files even if the project is corrupted"
	DESCRIPTIONS_CLEAN_PROJECT = DESCRIPTIONS_COMMON_PROJECT

	DESCRIPTIONS_INIT = "Create a new empty workspace"
	DESCRIPTIONS_INIT_ALIAS = "Assign a project name, instead of the directory name"
	DESCRIPTIONS_INIT_ENGINE = DESCRIPTIONS_COMMON_ENGINE
	DESCRIPTIONS_INIT_PATH = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_INIT_PROJECT = "Create a new project"
	DESCRIPTIONS_INIT_PROJECT_MINIMAL = "Activate only a minimal set of built-in gems (no sample assets)"
	DESCRIPTIONS_INIT_GEM = "Create a new gem"
	DESCRIPTIONS_INIT_GEM_SKIP_EXAMPLES = "Don't create a project to try the gem"
	DESCRIPTIONS_INIT_GEM_TYPE = "Type of gem: {}, {}".format(O3DE_GemTypes.ASSETS_ONLY.value, O3DE_GemTypes.CODE_AND_ASSETS.value)

	DESCRIPTIONS_OPEN = "Open the editor to view / modify the project"
	DESCRIPTIONS_OPEN_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_OPEN_ENGINE = "Override the linked engine version"
	DESCRIPTIONS_OPEN_PROJECT = DESCRIPTIONS_COMMON_PROJECT

	DESCRIPTIONS_REMOVE = "Remove an existing resource from the project"
	DESCRIPTIONS_REMOVE_PROJECT = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_REMOVE_GEM = "Deactivate a gem in the project"
	DESCRIPTIONS_REMOVE_GEM_VERSION = DESCRIPTIONS_COMMON_GEM_REFERENCE
	DESCRIPTIONS_REMOVE_GEM_SKIP_REBUILD = "Don't re-build the project if the gem is removed successfully"

	DESCRIPTIONS_RUN = "Run a built project runtime"
	DESCRIPTIONS_RUN_BINARY = DESCRIPTIONS_COMMON_BINARY
	DESCRIPTIONS_RUN_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_RUN_PROJECT = DESCRIPTIONS_COMMON_PROJECT

	DESCRIPTIONS_SETTINGS = "View / modify the project settings (e.g. the linked engine version)"
	DESCRIPTIONS_SETTINGS_KEY = "Setting identifier, or <empty> for all settings"
	DESCRIPTIONS_SETTINGS_VALUE = "New value to be stored, or <empty> to show the current one"
	DESCRIPTIONS_SETTINGS_CLEAR = "Delete the stored value"
	DESCRIPTIONS_SETTINGS_PROJECT = DESCRIPTIONS_COMMON_PROJECT

	DESCRIPTIONS_HELP = "Show available commands and their usage"
	DESCRIPTIONS_HELP_COMMAND = "Command name"
	DESCRIPTIONS_HELP_SUBCOMMAND = "Subcommand name (if any)"

	DESCRIPTIONS_VERSION = "Show version and legal information"

	set_bin_file(sys.argv[1])
	set_real_bin_file(sys.argv[2])
	set_real_volumes_dir(sys.argv[3])
	start_args_index = 4

	global_parser = argparse.ArgumentParser(add_help = False)
	global_parser.add_argument(print_option(ShortOptions.QUIET), print_option(LongOptions.QUIET), action = "store_true", help = DESCRIPTIONS_GLOBAL_QUIET)
	global_parser.add_argument(print_option(ShortOptions.VERBOSE), print_option(LongOptions.VERBOSE), action = "count", default = 0, help = DESCRIPTIONS_GLOBAL_VERBOSE)

	main_parser = argparse.ArgumentParser(
		prog = get_bin_name(),
		parents = [ global_parser ],
		formatter_class = argparse.RawTextHelpFormatter,
		description = textwrap.dedent('''\
			( = required, [...] = optional, {...} = choice, <...> = your input)

			A version manager for 'O3DE (Open 3D Engine)' to handle multiple engine installations using containers.
			'''),
		epilog = textwrap.dedent('''\
			For any further information, please visit the project documentation at:
			https://github.com/loherangrin/o3tanks/wiki
			''')
	)
	main_parser.set_defaults(handler = handle_empty_command)
	main_parser.add_argument(print_option(LongOptions.VERSION), action = "store_true", help = DESCRIPTIONS_VERSION)
	subparsers = main_parser.add_subparsers()

	install_parser = subparsers.add_parser(CliCommands.INSTALL.value, help = DESCRIPTIONS_INSTALL)
	install_parser.set_defaults(handler = handle_empty_target)
	install_common_parser = argparse.ArgumentParser(add_help = False)
	install_common_parser.add_argument(print_option(LongOptions.ALIAS), dest = "version_name", metavar="<version>", help = DESCRIPTIONS_INSTALL_VERSION)
	install_common_parser.add_argument(print_option(ShortOptions.FORCE), print_option(LongOptions.FORCE), action = "store_true", help = DESCRIPTIONS_INSTALL_FORCE)
	install_subparsers = install_parser.add_subparsers()

	install_revision_group = install_common_parser.add_mutually_exclusive_group()
	install_revision_group.add_argument(print_option(LongOptions.BRANCH), metavar = "<string>", help = DESCRIPTIONS_INSTALL_REPOSITORY_BRANCH)
	install_revision_group.add_argument(print_option(LongOptions.COMMIT), metavar = "<hash>", help = DESCRIPTIONS_INSTALL_REPOSITORY_COMMIT)
	install_revision_group.add_argument(print_option(LongOptions.TAG), metavar = "<string>", help = DESCRIPTIONS_INSTALL_REPOSITORY_TAG)

	install_engine_parser = install_subparsers.add_parser(CliSubCommands.ENGINE.value, parents = [ global_parser, install_common_parser ], help = DESCRIPTIONS_INSTALL_ENGINE)
	install_engine_parser.set_defaults(handler = handle_install_engine_command)
	install_engine_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "engine_config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_INSTALL_ENGINE_CONFIG)
	install_engine_parser.add_argument(print_option(LongOptions.REMOVE_BUILD), action = "store_true", help = DESCRIPTIONS_INSTALL_ENGINE_REMOVE_BUILD)
	install_engine_parser.add_argument(print_option(LongOptions.REMOVE_INSTALL), action = "store_true", help = DESCRIPTIONS_INSTALL_ENGINE_REMOVE_INSTALL)
	install_engine_parser.add_argument(print_option(LongOptions.SAVE_IMAGES), action = "store_true", help = DESCRIPTIONS_INSTALL_ENGINE_SAVE_IMAGES)

	install_url_group = install_engine_parser.add_mutually_exclusive_group()
	install_url_group.add_argument(print_option(LongOptions.FORK), metavar = "<username>/<project>", help = DESCRIPTIONS_INSTALL_REPOSITORY_FORK)
	install_url_group.add_argument(print_option(LongOptions.REPOSITORY), metavar = "<url>", help = DESCRIPTIONS_INSTALL_REPOSITORY)

	install_gem_parser = install_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser, install_common_parser ], help = DESCRIPTIONS_INSTALL_GEM)
	install_gem_parser.set_defaults(handler = handle_install_gem_command)
	install_gem_parser.add_argument("repository", metavar="<url>", help = DESCRIPTIONS_INSTALL_REPOSITORY)

	list_parser = subparsers.add_parser(CliCommands.LIST.value, parents = [ global_parser ], help = DESCRIPTIONS_LIST)
	list_parser.set_defaults(handler = handle_list_command)

	refresh_parser = subparsers.add_parser(CliCommands.REFRESH.value, help = DESCRIPTIONS_REFRESH)
	refresh_parser.set_defaults(handler = handle_empty_target)
	refresh_subparsers = refresh_parser.add_subparsers()

	refresh_engine_parser = refresh_subparsers.add_parser(CliSubCommands.ENGINE.value, parents = [ global_parser ], help = DESCRIPTIONS_REFRESH_ENGINE)
	refresh_engine_parser.set_defaults(handler = handle_refresh_engine_command)
	refresh_engine_parser.add_argument("engine_version", metavar="version", help = DESCRIPTIONS_REFRESH_ENGINE_VERSION)

	refresh_gem_parser = refresh_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser ], help = DESCRIPTIONS_REFRESH_GEM)
	refresh_gem_parser.set_defaults(handler = handle_refresh_gem_command)
	refresh_gem_parser.add_argument("gem_version", metavar="version", help = DESCRIPTIONS_REFRESH_GEM_VERSION)

	refresh_self_parser = refresh_subparsers.add_parser(CliSubCommands.SELF.value[0], aliases = [ CliSubCommands.SELF.value[1] ], parents = [ global_parser ], help = DESCRIPTIONS_REFRESH_SELF)
	refresh_self_parser.set_defaults(handler = handle_refresh_self_command)

	uninstall_parser = subparsers.add_parser(CliCommands.UNINSTALL.value, help = DESCRIPTIONS_UNINSTALL)
	uninstall_parser.set_defaults(handler = handle_empty_target)
	uninstall_subparsers = uninstall_parser.add_subparsers()

	uninstall_engine_parser = uninstall_subparsers.add_parser(CliSubCommands.ENGINE.value, parents = [ global_parser ], help = DESCRIPTIONS_UNINSTALL_ENGINE)
	uninstall_engine_parser.set_defaults(handler = handle_uninstall_engine_command)
	uninstall_engine_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "engine_config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_UNINSTALL_ENGINE_CONFIG)
	uninstall_engine_parser.add_argument(print_option(ShortOptions.FORCE), print_option(LongOptions.FORCE), action = "store_true", help = DESCRIPTIONS_UNINSTALL_ENGINE_FORCE)
	uninstall_engine_parser.add_argument("engine_version", metavar="version", help = DESCRIPTIONS_UNINSTALL_ENGINE_VERSION)

	uninstall_gem_parser = uninstall_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser ], help = DESCRIPTIONS_UNINSTALL_GEM)
	uninstall_gem_parser.set_defaults(handler = handle_uninstall_gem_command)
	uninstall_gem_parser.add_argument("gem_version", metavar="version", help = DESCRIPTIONS_UNINSTALL_GEM_VERSION)

	upgrade_parser = subparsers.add_parser(CliCommands.UPGRADE.value, help = DESCRIPTIONS_UPGRADE)
	upgrade_parser.set_defaults(handler = handle_empty_target)
	upgrade_subparsers = upgrade_parser.add_subparsers()

	upgrade_engine_parser = upgrade_subparsers.add_parser(CliSubCommands.ENGINE.value, parents = [ global_parser ], help = DESCRIPTIONS_UPGRADE_ENGINE)
	upgrade_engine_parser.set_defaults(handler = handle_upgrade_engine_command)
	upgrade_engine_parser.add_argument("engine_version", metavar="version", help = DESCRIPTIONS_UPGRADE_ENGINE_VERSION)
	upgrade_engine_parser.add_argument(print_option(LongOptions.SKIP_REBUILD), dest = "rebuild", action = "store_false", help = DESCRIPTIONS_UPGRADE_ENGINE_SKIP_REBUILD)

	upgrade_gem_parser = upgrade_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser ], help = DESCRIPTIONS_UPGRADE_GEM)
	upgrade_gem_parser.set_defaults(handler = handle_upgrade_gem_command)
	upgrade_gem_parser.add_argument("gem_version", metavar="version", help = DESCRIPTIONS_UPGRADE_GEM_VERSION)

	upgrade_self_parser = upgrade_subparsers.add_parser(CliSubCommands.SELF.value[0], aliases = [ CliSubCommands.SELF.value[1] ], parents = [ global_parser ], help = DESCRIPTIONS_UPGRADE_SELF)
	upgrade_self_parser.set_defaults(handler = handle_upgrade_self_command)

	add_parser = subparsers.add_parser(CliCommands.ADD.value, help = DESCRIPTIONS_ADD)
	add_parser.set_defaults(handler = handle_empty_target)
	add_common_parser = argparse.ArgumentParser(add_help = False)
	add_common_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_ADD_PROJECT)
	add_subparsers = add_parser.add_subparsers()
	
	add_gem_parser = add_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser, add_common_parser ], help = DESCRIPTIONS_ADD_GEM)
	add_gem_parser.set_defaults(handler = handle_add_gem_command)
	add_gem_parser.add_argument(print_option(LongOptions.SKIP_REBUILD), dest = "rebuild", action = "store_false", help = DESCRIPTIONS_ADD_GEM_SKIP_REBUILD)
	add_gem_parser.add_argument("gem_value", metavar="reference", help = DESCRIPTIONS_ADD_GEM_REFERENCE)

	build_parser = subparsers.add_parser(CliCommands.BUILD.value, parents = [ global_parser ], help = DESCRIPTIONS_BUILD)
	build_parser.set_defaults(handler = handle_build_command)
	build_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_BUILD_CONFIG)
	build_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_BUILD_PROJECT)
	build_parser.add_argument("binary_name", metavar = "binary", help = DESCRIPTIONS_BUILD_BINARY)

	clean_parser = subparsers.add_parser(CliCommands.CLEAN.value, parents = [ global_parser ], help = DESCRIPTIONS_CLEAN)
	clean_parser.set_defaults(handler = handle_clean_command)
	clean_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_CLEAN_PROJECT)
	
	clean_group = clean_parser.add_mutually_exclusive_group()
	clean_group.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_CLEAN_CONFIG)
	clean_group.add_argument(print_option(ShortOptions.FORCE), print_option(LongOptions.FORCE), action = "store_true", help = DESCRIPTIONS_CLEAN_FORCE)

	init_parser = subparsers.add_parser(CliCommands.INIT.value, help = DESCRIPTIONS_INIT)
	init_parser.set_defaults(handler = handle_empty_target)
	init_common_parser = argparse.ArgumentParser(add_help = False)
	init_common_parser.add_argument(print_option(LongOptions.ALIAS), dest = "alias", metavar = "<name>", help = DESCRIPTIONS_INIT_ALIAS)
	init_common_parser.add_argument(print_option(ShortOptions.ENGINE), print_option(LongOptions.ENGINE), dest = "engine_version", default = O3DE_DEFAULT_VERSION, metavar = "<version>", help = DESCRIPTIONS_INIT_ENGINE)
	init_common_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PATH), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_INIT_PATH)
	init_subparsers = init_parser.add_subparsers()

	init_gem_parser = init_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser, init_common_parser ], help = DESCRIPTIONS_INIT_GEM)
	init_gem_parser.set_defaults(handler = handle_init_gem_command)
	init_gem_parser.add_argument(print_option(LongOptions.TYPE), dest = "gem_type", default = O3DE_GemTypes.CODE_AND_ASSETS.value, metavar = "<type>", help = DESCRIPTIONS_INIT_GEM_TYPE)
	init_gem_parser.add_argument(print_option(LongOptions.SKIP_EXAMPLES), dest = "has_examples", action = "store_false", help = DESCRIPTIONS_INIT_GEM_SKIP_EXAMPLES)

	init_project_parser = init_subparsers.add_parser(CliSubCommands.PROJECT.value, parents = [ global_parser, init_common_parser ], help = DESCRIPTIONS_INIT_PROJECT)
	init_project_parser.add_argument(print_option(LongOptions.MINIMAL_PROJECT), dest = "is_minimal_project", action = "store_true", help = DESCRIPTIONS_INIT_PROJECT_MINIMAL)
	init_project_parser.set_defaults(handler = handle_init_project_command)

	open_parser = subparsers.add_parser(CliCommands.OPEN.value, parents = [ global_parser ], help = DESCRIPTIONS_OPEN)
	open_parser.set_defaults(handler = handle_open_command)
	open_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "engine_config_name", default = None, metavar = "<config>", help = DESCRIPTIONS_OPEN_CONFIG)
	open_parser.add_argument(print_option(ShortOptions.ENGINE), print_option(LongOptions.ENGINE), dest = "new_engine_version", default = None, metavar = "<version>", help = DESCRIPTIONS_OPEN_ENGINE)
	open_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_OPEN_PROJECT)

	remove_parser = subparsers.add_parser(CliCommands.REMOVE.value, help = DESCRIPTIONS_REMOVE)
	remove_parser.set_defaults(handler = handle_empty_target)
	remove_common_parser = argparse.ArgumentParser(add_help = False)
	remove_common_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_REMOVE_PROJECT)
	
	remove_subparsers = remove_parser.add_subparsers()
	remove_gem_parser = remove_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser, remove_common_parser ], help = DESCRIPTIONS_REMOVE_GEM)
	remove_gem_parser.set_defaults(handler = handle_remove_gem_command)
	remove_gem_parser.add_argument(print_option(LongOptions.SKIP_REBUILD), dest = "rebuild", action = "store_false", help = DESCRIPTIONS_REMOVE_GEM_SKIP_REBUILD)
	remove_gem_parser.add_argument("gem_value", metavar="reference", help = DESCRIPTIONS_REMOVE_GEM_VERSION)

	run_parser = subparsers.add_parser(CliCommands.RUN.value, parents = [ global_parser ], help = DESCRIPTIONS_RUN)
	run_parser.set_defaults(handler = handle_run_command)
	run_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_RUN_CONFIG)
	run_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_RUN_PROJECT)
	run_parser.add_argument("binary_name", metavar = "binary", help = DESCRIPTIONS_RUN_BINARY)

	settings_parser = subparsers.add_parser(CliCommands.SETTINGS.value, parents = [ global_parser ], help = DESCRIPTIONS_SETTINGS)
	settings_parser.set_defaults(handler = handle_settings_command)
	settings_parser.add_argument("setting_key", nargs = "?", default = None, metavar = "<section>.<key>", help = DESCRIPTIONS_SETTINGS_KEY)
	settings_parser.add_argument("setting_value", nargs = "?", default = None, metavar = "<value>", help = DESCRIPTIONS_SETTINGS_VALUE)
	settings_parser.add_argument(print_option(LongOptions.CLEAR), action = "store_true", help = DESCRIPTIONS_SETTINGS_CLEAR)
	settings_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_SETTINGS_PROJECT)

	help_parser = subparsers.add_parser(CliCommands.HELP.value, help = DESCRIPTIONS_HELP)
	help_parser.add_argument("help_command", nargs = "?", default = None, metavar = "<command>", help = DESCRIPTIONS_HELP_COMMAND)
	help_parser.add_argument("help_subcommand", nargs = "?", default = None, metavar = "<subcommand>", help = DESCRIPTIONS_HELP_SUBCOMMAND)
	help_parser.set_defaults(handler = handle_help_command)

	version_parser = subparsers.add_parser(CliCommands.VERSION.value, aliases = [ CliCommands.INFO.value ], help = DESCRIPTIONS_VERSION)
	version_parser.set_defaults(handler = handle_version_command)


	args = main_parser.parse_args(sys.argv[start_args_index:])
	handler = args.handler
	quiet = args.quiet if LongOptions.QUIET.value in args else -1
	verbose = args.verbose if LongOptions.VERBOSE.value in args else 0
	version = args.version if LongOptions.VERSION.value in args else False

	delattr(args, "handler")
	delattr(args, LongOptions.QUIET.value)
	delattr(args, LongOptions.VERBOSE.value)
	delattr(args, LongOptions.VERSION.value)

	set_verbose(verbose)
	if handler == handle_help_command:
		help_command = args.help_command
		help_subcommand = args.help_subcommand

		if help_command is None:
			help_parser = main_parser
		elif help_command == CliCommands.INSTALL.value:
			if help_subcommand is None:
				help_parser = install_parser
			elif help_subcommand == CliSubCommands.ENGINE.value:
				help_parser = install_engine_parser
			elif help_subcommand == CliSubCommands.GEM.value:
				help_parser = install_gem_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.LIST.value:
			help_parser = list_parser
		elif help_command == CliCommands.REFRESH.value:
			if help_subcommand is None:
				help_parser = refresh_parser
			elif help_subcommand == CliSubCommands.ENGINE.value:
				help_parser = refresh_engine_parser
			elif help_subcommand == CliSubCommands.GEM.value:
				help_parser = refresh_gem_parser
			elif help_subcommand in CliSubCommands.SELF.value:
				help_parser = refresh_self_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.UNINSTALL.value:
			if help_subcommand is None:
				help_parser = uninstall_parser
			elif help_subcommand == CliSubCommands.ENGINE.value:
				help_parser = uninstall_engine_parser
			elif help_subcommand == CliSubCommands.GEM.value:
				help_parser = uninstall_gem_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.UPGRADE.value:
			if help_subcommand is None:
				help_parser = upgrade_parser
			elif help_subcommand == CliSubCommands.ENGINE.value:
				help_parser = upgrade_engine_parser
			elif help_subcommand == CliSubCommands.GEM.value:
				help_parser = upgrade_gem_parser
			elif help_subcommand in CliSubCommands.SELF.value:
				help_parser = upgrade_self_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.ADD.value:
			if help_subcommand is None:
				help_parser = add_parser
			elif help_subcommand == CliSubCommands.GEM.value:
				help_parser = add_gem_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.BUILD.value:
			help_parser = build_parser
		elif help_command == CliCommands.CLEAN.value:
			help_parser = clean_parser
		elif help_command == CliCommands.INIT.value:
			if help_subcommand is None:
				help_parser = init_parser
			elif help_subcommand == CliSubCommands.GEM.value:
				help_parser = init_gem_parser
			elif help_subcommand == CliSubCommands.PROJECT.value:
				help_parser = init_project_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.OPEN.value:
			help_parser = open_parser
		elif help_command == CliCommands.REMOVE.value:
			if help_subcommand is None:
				help_parser = remove_parser
			elif help_subcommand == CliSubCommands.GEM.value:
				help_parser = remove_gem_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.RUN.value:
			help_parser = run_parser
		elif help_command == CliCommands.SETTINGS.value:
			help_parser = settings_parser
		elif help_command == CliCommands.HELP.value:
			help_parser = help_parser
		elif help_command in [ CliCommands.INFO.value, CliCommands.VERSION.value ]:
			help_parser = version_parser
		else:
			throw_error(Messages.INVALID_COMMAND, help_command)

		handle_help_command(help_parser)

	elif version:
		handle_version_command()

	else:
		handler(**vars(args))


if __name__ == "__main__":
	main()
