# Copyright 2021-2023 Matteo Grasso
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
import tarfile
import textwrap
import time
import zipfile


# --- VARIABLES ---

CONTAINER_CLIENT = None


# --- SUB-FUNCTIONS ---

def add_to_archive(archive_handle, archive_type, from_path, from_is_dir, to_base_dir, to_path = None):
	to = to_base_dir / to_path if to_path is not None else to_base_dir
	
	if archive_type is ArchiveTypes.CONTAINER:
		executed = CONTAINER_CLIENT.exec_in_container(archive_handle, [ "mkdir", "--parents", to ])
		if not executed:
			return False

		copied = CONTAINER_CLIENT.copy_to_container(archive_handle, from_path, to, content_only = from_is_dir)
		return copied

	elif archive_type is ArchiveTypes.TAR_GZ:
		to /= from_path.name
		archive_handle.add(from_path, arcname = to)
		return True

	elif archive_type is ArchiveTypes.ZIP:
		to /= from_path.name
		archive_handle.write(from_path, arcname = to)
		return True

	else:
		throw_error(Messages.INVALID_ARCHIVE_TYPE, archive_type.value)


def check_asset_processor(engine_version, engine_config, engine_workflow, project_dir, external_gem_dirs, wait = False):
	asset_processor_lock_file = project_dir / ASSET_PROCESSOR_LOCK_PATH
	if asset_processor_lock_file.is_file():
		if wait:
			throw_error(Messages.ASSET_PROCESSOR_ALREADY_RUNNING, asset_processor_lock_file)

		asset_processor_id = read_json_property(asset_processor_lock_file, InstanceProperties.HOSTNAME.value)

		asset_processor_container = CONTAINER_CLIENT.get_container(asset_processor_id)
		overwrite_missing_asset_processor = (asset_processor_container is None)
	else:
		asset_processor_container = None
		overwrite_missing_asset_processor = False

	if asset_processor_container is None:
		asset_processor_container = run_runner(engine_version, engine_config, O3DE_Variants.NON_MONOLITHIC, engine_workflow, project_dir, external_gem_dirs, False, wait, RunnerCommands.OPEN, O3DE_EngineBinaries.ASSET_PROCESSOR, engine_config, overwrite_missing_asset_processor)
		time.sleep(5)

	return asset_processor_container


def check_project_dependencies(project_dir, config = None, variant = None, check_engine = True, check_gems = True):
	was_config_missing = False

	if not check_engine:
		engine_version = None
		engine_workflow = None
	else:
		result = select_engine(project_dir, config, variant)
		if result.type is DependencyResultType.OK:
			engine_version, engine_workflow = result.value
		elif result.type is DependencyResultType.MISSING:
			missing = result.value[0] if (isinstance(result.value, list) and len(result.value) > 0) else None
			if missing is EngineSettings.REPOSITORY:
				engine_url = result.value[1]
				engine_version = None
				engine_config = config if not None else O3DE_DEFAULT_CONFIG
				engine_variant = variant if not None else O3DE_DEFAULT_VARIANT
				engine_workflow = O3DE_DEFAULT_WORKFLOW

			elif missing is LongOptions.CONFIG:
				engine_url = result.value[1]
				engine_version = result.value[2]
				engine_config = result.value[3]
				engine_variant = result.value[4]
				engine_workflow = result.value[5]
				was_config_missing = True

			else:
				throw_error(Messages.INVALID_DEPENDENCY_RESULT_VALUE, missing)

			install_missing_engine(project_dir, engine_url, engine_version, engine_config, engine_variant, engine_workflow)

			result = select_engine(project_dir, config, variant)
			if result.type is not DependencyResultType.OK:
				throw_error(Messages.UNCOMPLETED_MISSING_INSTALL)

			engine_version, engine_workflow = result.value

		elif result.type is DependencyResultType.DIFFERENT:
			different = result.value[0] if (isinstance(result.value, list) and len(result.value) > 0) else None
			if different is EngineSettings.REPOSITORY:
				throw_error(Messages.BINDING_DIFFERENT_REPOSITORY, Targets.ENGINE.value)
			elif different is EngineSettings.WORKFLOW:
				throw_error(Messages.BINDING_DIFFERENT_WORKFLOW, result.value[1], result.value[2])
			else:
				throw_error(Messages.INVALID_DEPENDENCY_RESULT_VALUE, different)

		elif result.type is DependencyResultType.NOT_FOUND:
			throw_error(Messages.BINDING_INSTALL_NOT_FOUND, Targets.ENGINE.value)
		else:
			throw_error(Messages.BINDING_INVALID_REPOSITORY, Targets.ENGINE.value)

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
						missing = result.value[0] if (isinstance(result.value, list) and len(result.value) > 0) else None
						if missing is GemSettings.REPOSITORY:
							gem_url = result.value[1]
							gem_version = install_missing_gem(project_dir, gem_index, gem_url)
						else:
							throw_error(Messages.INVALID_DEPENDENCY_RESULT_VALUE, missing)

					elif result.type is DependencyResultType.DIFFERENT:
						different = result.value[0] if (isinstance(result.value, list) and len(result.value) > 0) else None
						if different is GemSettings.REPOSITORY:
							throw_error(Messages.BINDING_DIFFERENT_REPOSITORY, "{} at index '{}'".format(Targets.GEM.value, gem_index))
						else:
							throw_error(Messages.INVALID_DEPENDENCY_RESULT_VALUE, different)

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

	return [ engine_version, was_config_missing, engine_workflow, external_gem_dirs ]


def copy_project_to_archive(bin_dir, cache_dir, bundle_files, binary_name, platform, variant, archive_handle, archive_type, archive_base_dir):
	if (bin_dir is None) or (cache_dir is None):
		return False

	library_suffix = get_library_filename("")

	for content in bin_dir.iterdir():
		if not content.is_file():
			continue

		if content.name != binary_name and content.suffix != library_suffix:
			continue

		if content.is_symlink():
			copied = add_to_archive(archive_handle, archive_type, content, False, archive_base_dir)
			if not copied:
				return False
			
			bin_file = content.resolve()
		else:
			bin_file = content

		copied = add_to_archive(archive_handle, archive_type, bin_file, False, archive_base_dir)
		if not copied:
			return False

	archive_cache_path = pathlib.Path("Cache") / platform.value

	if len(bundle_files) > 0:
		for bundle_file in bundle_files:
			copied = add_to_archive(archive_handle, archive_type, bundle_file, False, archive_base_dir, archive_cache_path)
			if not copied:
				return False

	else:
		copied = add_to_archive(archive_handle, archive_type, cache_dir, True, archive_base_dir, archive_cache_path)
		if not copied:
			return False

	if variant is O3DE_Variants.NON_MONOLITHIC:
		copied = add_to_archive(archive_handle, archive_type, bin_dir / "Registry", True, archive_base_dir, archive_cache_path / "registry")
		if not copied:
			return False

	return True


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


def get_engine_workflow_from_project(project_dir):
	engine_workflow = read_json_property(project_dir / PRIVATE_PROJECT_SETTINGS_PATH, EngineSettings.WORKFLOW)

	return O3DE_BuildWorkflows.from_value(engine_workflow)


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
			if new_dir is None:
				throw_error(Messages.VOLUME_NOT_FOUND, name)

			new_dirs.append(new_dir)

	if force:
		new_dirs = []
		for name in names:
			new_dir = CONTAINER_CLIENT.get_volume_path(name)
			if new_dir is None:
				throw_error(Messages.VOLUME_NOT_FOUND, name)

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


def print_workflow(build_workflow):
	if build_workflow is None:
		return "Invalid"
	if build_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
		return "Engine"
	elif build_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		return "Project / Pre-built"
	elif build_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
		return "Project / Source"
	else:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, build_workflow)


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


def select_engine(project_dir, engine_config, engine_variant):
	if not (project_dir / PROJECT_EXTRA_PATH).is_dir():
		return DependencyResult(DependencyResultType.OK, [ O3DE_DEFAULT_VERSION, O3DE_DEFAULT_WORKFLOW ])
	
	engine_version = get_engine_version_from_project(project_dir)

	result_type, engine_repository = get_engine_repository_from_project(project_dir)
	if result_type is not RepositoryResultType.OK:
		return DependencyResult(DependencyResultType.INVALID)

	engine_url = engine_repository.url
	if engine_repository.branch is not None:
		engine_url += '#' + engine_repository.branch
	elif engine_repository.revision is not None:
		engine_url += '#' + engine_repository.revision

	if engine_version is None:
		if engine_repository is None:
			return DependencyResult(DependencyResultType.OK, [ O3DE_DEFAULT_VERSION, O3DE_DEFAULT_WORKFLOW ])

		engine_version = search_engine_by_repository(engine_repository)

		if engine_version is not None:
			run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, EngineSettings.VERSION.value.section, EngineSettings.VERSION.value.index, EngineSettings.VERSION.value.name, engine_version, False, True, False)

		else:
			return DependencyResult(DependencyResultType.MISSING, [ EngineSettings.REPOSITORY, engine_url ])

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
				return DependencyResult(DependencyResultType.DIFFERENT, [ EngineSettings.REPOSITORY, installed_engine_repository, engine_repository ])

	build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
	build_dir = CONTAINER_CLIENT.get_volume_path(build_volume)

	install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
	install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)

	installed_engine_workflow = get_build_workflow(source_dir, build_dir, install_dir)
	if installed_engine_workflow is None:
		return DependencyResult(DependencyResultType.INVALID)

	engine_workflow = get_engine_workflow_from_project(project_dir)
	if engine_workflow is None:
		engine_workflow = installed_engine_workflow
		run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, EngineSettings.WORKFLOW.value.section, EngineSettings.WORKFLOW.value.index, EngineSettings.WORKFLOW.value.name, engine_workflow.value, False, True, False)

	elif installed_engine_workflow is not engine_workflow:
		return DependencyResult(DependencyResultType.DIFFERENT, [ EngineSettings.WORKFLOW, installed_engine_workflow.value, engine_workflow.value ])

	if (engine_config is not None) and (engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK) and not has_install_config(install_dir, engine_config, engine_variant):
		return DependencyResult(DependencyResultType.MISSING, [ LongOptions.CONFIG, engine_url, engine_version, engine_config, engine_variant, engine_workflow ])

	return DependencyResult(DependencyResultType.OK, [ engine_version, engine_workflow ])


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

			return DependencyResult(DependencyResultType.MISSING, [ GemSettings.REPOSITORY, gem_url ])

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
				return DependencyResult(DependencyResultType.DIFFERENT, [ GemSettings.REPOSITORY, installed_gem_repository, gem_repository ])

	return DependencyResult(DependencyResultType.OK, gem_version)


def select_recommended_config(engine_version, max_limit = O3DE_Configs.PROFILE):
	source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
	source_dir = CONTAINER_CLIENT.get_volume_path(source_volume)

	build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
	build_dir = get_build_path(CONTAINER_CLIENT.get_volume_path(build_volume), O3DE_Variants.NON_MONOLITHIC)
	
	install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
	install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)

	engine_workflow = get_build_workflow(source_dir, build_dir, install_dir)
	if engine_workflow is None:
		return None

	elif engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
		for config in O3DE_Configs:
			if has_build_config(build_dir, config):
				engine_config = config

			if config is max_limit:
				break

	elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		for config in O3DE_Configs:
			install_builder_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_BUILDER, engine_version, config)

			if (
				CONTAINER_CLIENT.image_exists(install_builder_image) or
				has_install_config(install_dir, config, O3DE_DEFAULT_VARIANT)
			):
				engine_config = config

			if config is max_limit:
				break

	elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
		engine_config = O3DE_DEFAULT_CONFIG

	else:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow.value)

	return engine_config


# --- FUNCTIONS (GENERIC) ---

def apply_updates():
	resume_command = ' '.join([
		get_bin_name(),
		CliCommands.UPGRADE.value,
		CliSubCommands.SELF.value[0]
	])

	if CONTAINER_CLIENT.is_in_container():
		installation_dir = O3DE_PROJECT_SOURCE_DIR
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
				"INSTALL_GPU_AMD": "true" if GPU_DRIVER_NAME in [ GPUDrivers.AMD_OPEN, GPUDrivers.AMD_PROPRIETARY ] else "false",
				"RENDER_GROUP_ID": str(GPU_RENDER_GROUP_ID) if GPU_RENDER_GROUP_ID > 0 else "-1",
				"RENDER_GROUP_NAME": "render",
				"VIDEO_GROUP_ID": str(GPU_VIDEO_GROUP_ID) if GPU_VIDEO_GROUP_ID > 0 else "-1",
				"VIDEO_GROUP_NAME": "video"
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
	elif OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		return

	container_user = CONTAINER_CLIENT.get_container_user()
	if (container_user.uid is None) or (container_user.gid is None):
		throw_error(Messages.INVALID_CONTAINER_USER)

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
				change_owner(wrong_path, container_user)

			show_instructions = False

		except Exception as error:
			real_path = wrong_path
			if mapping is not None:
				for mapping_from, mapping_to in mapping.items():
					try:
						relative_path = wrong_path.relative_to(mapping_from)
						real_path = mapping_to / relative_path
						break
					except ValueError:
						continue

			print_msg(Level.ERROR, Messages.UNCOMPLETED_CHANGE_OWNERSHIP, real_path, error)
			print_msg(Level.INFO, '')

			show_instructions = True

	else:
		show_instructions = True

	if show_instructions:
		real_container_user = CONTAINER_CLIENT.get_container_user(False)
		if (real_container_user.uid is None) or (real_container_user.gid is None):
			throw_error(Messages.INVALID_CONTAINER_USER)

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


def exec_in_runner(container, command):
	full_command = [ "python3", "-u", "-m", "o3tanks.{}".format(Images.RUNNER.value) ]
	if len(command) > 0:
		full_command += serialize_list(command, False)

	executed = CONTAINER_CLIENT.exec_in_container(container, full_command, True, True)
	return executed


def print_version_info():
	print("O3Tanks version {}".format(get_version_number()))
	print("A containerized version manager for 'O3DE (Open 3D Engine)'")
	print('https://github.com/loherangrin/o3tanks/')
	print('')
	print('Copyright (c) 2021-2023 Matteo Grasso')
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
			volumes[build_volume] = str(O3DE_ENGINE_BUILDS_DIR)
			
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

	completed = CONTAINER_CLIENT.run_container(
		ContainerRunMode.FOREGROUND,
		builder_image,
		list(command),
		interactive = is_tty(),
		binds = binds,
		volumes = volumes
	)
	
	return completed


def run_runner(engine_version, engine_config, engine_variant, engine_workflow, project_dir, external_gem_dirs, force_headless, wait, *command):
	if engine_config is None:
		throw_error(Messages.MISSING_CONFIG)

	binds = {}
	volumes = {}

	runner_image = CONTAINER_CLIENT.get_image_name(Images.RUNNER)
	if engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
		source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)

		build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
		build_dir = get_build_path(CONTAINER_CLIENT.get_volume_path(build_volume), engine_variant)

		if not is_engine_installed(engine_version) or not has_build_config(build_dir, engine_config):
			throw_error(Messages.MISSING_INSTALL_AND_CONFIG, engine_version, engine_config.value)

		volumes[source_volume] = str(O3DE_ENGINE_SOURCE_DIR)
		volumes[build_volume] = str(O3DE_ENGINE_BUILDS_DIR)

	elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		install_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_RUNNER, engine_version, engine_config)

		if CONTAINER_CLIENT.image_exists(install_image):
			runner_image = CONTAINER_CLIENT.install_image
		else:
			install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
			install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)

			if not has_install_config(install_dir, engine_config, engine_variant):
				throw_error(Messages.MISSING_INSTALL_AND_CONFIG, engine_version, engine_config.value, engine_variant.value)

			volumes[install_volume] = str(O3DE_ENGINE_INSTALL_DIR)

	elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
		source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)

		if not is_engine_installed(engine_version):
			throw_error(Messages.ENGINE_SOURCE_NOT_FOUND, source_volume)

		volumes[source_volume] = str(O3DE_ENGINE_SOURCE_DIR)

	else:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow)
		
	gems_volume = CONTAINER_CLIENT.get_volume_name(Volumes.GEMS)
	volumes[gems_volume] = str(O3DE_GEMS_DIR)

	if project_dir is not None and project_dir.is_dir():
		binds[str(get_real_project_dir() if CONTAINER_CLIENT.is_in_container() else project_dir)] = str(O3DE_PROJECT_SOURCE_DIR)
	else:
		throw_error(Messages.MISSING_PROJECT)

	if external_gem_dirs is not None:
		for external_gem_dir in external_gem_dirs:
			binds[str(external_gem_dir)] = str(get_external_gem_path(O3DE_GEMS_EXTERNAL_DIR, external_gem_dir))

	if DEVELOPMENT_MODE:
		scripts_dir = get_real_bin_file().parent / SCRIPTS_PATH
		binds[str(scripts_dir)] = str(ROOT_DIR)

	completed =	CONTAINER_CLIENT.run_container(
		ContainerRunMode.FOREGROUND if wait else ContainerRunMode.BACKGROUND,
		runner_image,
		list(command),
		interactive = is_tty() if wait else False,
		display = not force_headless,
		gpu = True,
		binds = binds,
		volumes = volumes,
		network_name = NETWORK_NAME,
		network_disabled = False if (NETWORK_NAME is not None) else True
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

	elif target is Targets.PROJECT:
		project_dir = arguments[0]
		arguments = arguments[1:]

		binds[str(project_dir)] = str(O3DE_PROJECT_SOURCE_DIR)

	elif target is Targets.SELF:
		binds[str(get_real_bin_file().parent)] = str(O3DE_PROJECT_SOURCE_DIR)

	else:
		throw_error(Messages.INVALID_TARGET, target)

	if DEVELOPMENT_MODE:
		scripts_dir = get_real_bin_file().parent / SCRIPTS_PATH
		binds[str(scripts_dir)] = str(ROOT_DIR)

	completed = CONTAINER_CLIENT.run_container(
		ContainerRunMode.FOREGROUND,
		updater_image,
		[ command, target, *arguments ],
		interactive = is_tty(),
		binds = binds,
		volumes = volumes
	)

	return completed


def search_updates():
	resume_command = ' '.join([
		get_bin_name(),
		CliCommands.REFRESH.value,
		CliSubCommands.SELF.value[0]
	])

	if CONTAINER_CLIENT.is_in_container():
		installation_dir = O3DE_PROJECT_SOURCE_DIR
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
	builds_dir = CONTAINER_CLIENT.get_volume_path(build_volume)
	if builds_dir is None:
		throw_error(Messages.ENGINE_BUILD_NOT_FOUND, build_volume)

	install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
	install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)
	if install_dir is None:
		throw_error(Messages.ENGINE_INSTALL_NOT_FOUND, install_volume)

	installed_configs = []
	for engine_variant in O3DE_Variants:
		for engine_config in O3DE_Configs:
			install_builder_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_BUILDER, engine_version, engine_config)
			install_runner_image = CONTAINER_CLIENT.get_image_name(Images.INSTALL_RUNNER, engine_version, engine_config)

			if (
				has_build_config(get_build_path(builds_dir, engine_variant), engine_config) or
				has_install_config(install_dir, engine_config, engine_variant) or
				CONTAINER_CLIENT.image_exists(install_builder_image) or
				CONTAINER_CLIENT.image_exists(install_runner_image)
			):
				installed_configs.append([ engine_config, engine_variant ])

	upgraded = run_updater(engine_version, UpdaterCommands.UPGRADE, Targets.ENGINE)
	if not upgraded:
		throw_error(Messages.UNCOMPLETED_UPGRADE)

	if len(installed_configs) == 0:
		print_msg(Level.INFO, Messages.UPGRADE_ENGINE_COMPLETED_SOURCE_ONLY)

	elif not rebuild:
		print_msg(Level.INFO, Messages.UPGRADE_ENGINE_COMPLETED_SKIP_REBUILD)

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

		resume_command = [
			get_bin_name(),
			CliCommands.INSTALL.value,
			CliSubCommands.ENGINE.value,
			print_option(LongOptions.FORCE),
			print_option(LongOptions.ALIAS, engine_version)
		]

		if engine_repository.url != O3DE_REPOSITORY_URL:
			resume_command.append(print_option(LongOptions.REPOSITORY, engine_repository.url))
		
		if engine_repository.branch is not None:
			resume_command.append(print_option(LongOptions.BRANCH, engine_repository.branch))
		elif engine_repository.revision is not None:
			resume_command.append(print_option(LongOptions.COMMIT, engine_repository.revision))

		if engine_config != O3DE_DEFAULT_CONFIG:
			resume_command.append(print_option(LongOptions.CONFIG, engine_config.value))

		if remove_build:
			resume_command.append(print_option(LongOptions.REMOVE_BUILD))

		if remove_install:
			resume_command.append(print_option(LongOptions.REMOVE_INSTALL))

		if save_images is not False:
			if save_images is True:
				resume_command.append(print_option(LongOptions.SAVE_IMAGES))
			else:
				resume_command.append(print_option(LongOptions.SAVE_IMAGES, save_images))

		resume_command = ' '.join(resume_command)

		print_msg(Level.INFO, resume_command)


def install_engine(repository, engine_version, engine_config, engine_variant, engine_workflow, force = False, incremental = False, save_images = False):
	repository_protocol, repository_url, repository_reference = parse_repository_url(repository)

	if engine_workflow is not O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		if incremental:
			throw_error(Messages.INVALID_INSTALL_OPTIONS_INCREMENTAL)
		elif save_images:
			throw_error(Messages.INVALID_INSTALL_OPTIONS_SAVE_IMAGES)

	resume_command = [
		get_bin_name(),
		CliCommands.INSTALL.value,
		CliSubCommands.ENGINE.value,
		print_option(LongOptions.FORCE),
		print_option(LongOptions.ALIAS, engine_version)
	]

	if repository_url != O3DE_REPOSITORY_URL:
		resume_command.append(print_option(LongOptions.REPOSITORY, repository_url))
	
	if repository_reference is not None:
		if is_commit(repository_reference):
			resume_command.append(print_option(LongOptions.COMMIT, repository_reference))
		elif repository_reference != engine_version:
			resume_command.append(print_option(LongOptions.BRANCH, repository_reference))

	if engine_config != O3DE_DEFAULT_CONFIG:
		resume_command.append(print_option(LongOptions.CONFIG, engine_config.value))

	if engine_workflow != O3DE_DEFAULT_WORKFLOW:
		resume_command.append(print_option(LongOptions.WORKFLOW, engine_workflow.value))

	if incremental:
		resume_command.append(print_option(LongOptions.INCREMENTAL))

	if save_images is not False:
		if save_images is True:
			resume_command.append(print_option(LongOptions.SAVE_IMAGES))
		else:
			resume_command.append(print_option(LongOptions.SAVE_IMAGES, save_images))

	resume_command = ' '.join(resume_command)

	source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
	build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
	install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
	packages_volume = CONTAINER_CLIENT.get_volume_name(Volumes.PACKAGES)

	required_volumes = [ source_volume, build_volume, install_volume, packages_volume ]
	initialize_volumes(required_volumes, resume_command, force)

	source_dir = CONTAINER_CLIENT.get_volume_path(source_volume)
	build_dir = get_build_path(CONTAINER_CLIENT.get_volume_path(build_volume), engine_variant)
	install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)
	packages_dir = CONTAINER_CLIENT.get_volume_path(packages_volume)

	if not force:
		installed_engine_workflow = get_build_workflow(source_dir, build_dir, install_dir)

		if installed_engine_workflow is not None:
			if installed_engine_workflow is not engine_workflow:
				throw_error(Messages.INSTALL_ALREADY_EXISTS_DIFFERENT_WORKFLOW, engine_version, print_workflow(installed_engine_workflow))

			if engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
				if has_build_config(build_dir, engine_config):
					throw_error(Messages.INSTALL_AND_CONFIG_ALREADY_EXISTS, engine_version, engine_config.value, engine_variant.value)

			elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
				if has_install_config(install_dir, engine_config, engine_variant):
					throw_error(Messages.INSTALL_AND_CONFIG_ALREADY_EXISTS, engine_version, engine_config.value, engine_variant.value)			

			elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
				throw_error(Messages.INSTALL_ALREADY_EXISTS, Targets.ENGINE.value.capitalize(), engine_version)

			else:
				throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow)

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

	if not is_engine_installed(engine_version):
		throw_error(Messages.INVALID_ENGINE_SOURCE)

	if not RUN_CONTAINERS:
		check_requirements(resume_command)

	initialized = run_builder(engine_version, None, None, None, BuilderCommands.INIT, Targets.ENGINE, engine_variant, engine_workflow)
	if not initialized:
		throw_error(Messages.UNCOMPLETED_INSTALL)

	built = run_builder(engine_version, None, None, None, BuilderCommands.BUILD, Targets.ENGINE, engine_config, engine_variant, engine_workflow)
	if not built:
		throw_error(Messages.UNCOMPLETED_INSTALL)

	if not incremental and (engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK):
		run_builder(engine_version, None, None, None, BuilderCommands.CLEAN, Targets.ENGINE, engine_config, engine_variant, True, False)

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
				new_container = CONTAINER_CLIENT.run_container(ContainerRunMode.STANDBY, from_image, network_disabled = True)

				bin_dir = get_install_bin_path(O3DE_ENGINE_INSTALL_DIR, engine_config)

				executed = CONTAINER_CLIENT.exec_in_container(new_container, [ "mkdir", "--parents", bin_dir ])
				if not executed:
					throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)

				for content in install_dir.iterdir():
					if content.is_dir() and (content.name == "bin"):
						continue

					copied = CONTAINER_CLIENT.copy_to_container(new_container, content, O3DE_ENGINE_INSTALL_DIR)
					if not copied:
						throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)

				copied = CONTAINER_CLIENT.copy_to_container(new_container, install_dir / bin_dir.relative_to(O3DE_ENGINE_INSTALL_DIR), bin_dir, content_only = True)
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

		if not incremental:
			run_builder(engine_version, None, None, None, BuilderCommands.CLEAN, Targets.ENGINE, engine_config, engine_variant, False, True)

	else:
		CONTAINER_CLIENT.remove_image(install_builder_image)
		CONTAINER_CLIENT.remove_image(install_runner_image)


def install_missing_engine(project_dir, engine_url, engine_version, engine_config, engine_variant, engine_workflow):
	if engine_version is None:
		print_msg(Level.INFO, Messages.MISSING_INSTALL_ENGINE, engine_url)
	else:
		print_msg(Level.INFO, Messages.MISSING_INSTALL_ENGINE_CONFIG, engine_version, engine_config.value, engine_variant.value)

	if not ask_for_confirmation(Messages.INSTALL_QUESTION):
		exit(1)

	if engine_version is None:
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

	install_engine(engine_url, engine_version, engine_config, engine_variant, engine_workflow)


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

	return gem_version


def list_engines():
	MAX_LENGTHS_VERSION=20
	MAX_LENGTHS_SIZE=10
	MAX_LENGTHS_WORKFLOW=19
	MAX_LENGTHS_CONFIG=10

	table_row = "{:<" + str(MAX_LENGTHS_VERSION) + "} {:^" + str(MAX_LENGTHS_SIZE) + "}"

	engines_row = table_row + "   {:^" + str(MAX_LENGTHS_SIZE) + "} {:^" + str(MAX_LENGTHS_SIZE) + "} {:^" + str(MAX_LENGTHS_SIZE) + "}   {:^" + str(MAX_LENGTHS_WORKFLOW) + "}   "
	for config in O3DE_Configs:
		engines_row += " {:^" + str(MAX_LENGTHS_CONFIG) + "}"

	gems_row = table_row
	packages_row = table_row

	all_config_names = [ config.value.upper() for config in O3DE_Configs ]
	print(engines_row.format("ENGINES", "TOTAL", "SOURCE", "BUILD", "SDK", "BUILD WORKFLOW", *all_config_names))

	engine_versions = get_all_engine_versions()
	if len(engine_versions) == 0:
		all_empty_configs = [ '' for config in O3DE_Configs ]
		print(engines_row.format("<none>", '', '', '', '', '', *all_empty_configs))

	else:
		for engine_version in engine_versions:
			source_volume = CONTAINER_CLIENT.get_volume_name(Volumes.SOURCE, engine_version)
			source_dir = CONTAINER_CLIENT.get_volume_path(source_volume)
			source_size = calculate_size(source_dir)

			build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
			builds_dir = CONTAINER_CLIENT.get_volume_path(build_volume)
			build_size = calculate_size(builds_dir)

			install_volume = CONTAINER_CLIENT.get_volume_name(Volumes.INSTALL, engine_version)
			install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)
			install_size = calculate_size(install_dir)

			if not RUN_CONTAINERS:
				source_size -= (build_size + install_size)

			total_size = source_size + build_size + install_size

			installed_configs = []
			engine_workflow = O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE if is_engine_installed(engine_version) else None
			for config in O3DE_Configs:
				install_image = CONTAINER_CLIENT.get_image_name(Volumes.INSTALL, engine_version, config)

				installed_variants = []
				for variant in O3DE_Variants:
					config_exists = False

					if (
						has_install_config(install_dir, config, variant) or
						CONTAINER_CLIENT.image_exists(install_image)
					):
						config_exists = True
						engine_workflow = O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK

					elif has_build_config(get_build_path(builds_dir, variant), config):
						config_exists = True
						if engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
							engine_workflow = O3DE_BuildWorkflows.ENGINE_CENTRIC

					if config_exists:
						installed_variants.append(variant)

				if len(installed_variants) == 0:
					mark = ''
				elif len(installed_variants) == 1:
					mark = "Monolit." if installed_variants[0] is O3DE_Variants.MONOLITHIC else "Non-Mon."
				else:
					mark = "Both"

				installed_configs.append(mark)

			if engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
				installed_configs = ['Any' for config in O3DE_Configs]

			print(engines_row.format(
				engine_version if len(engine_version) <= MAX_LENGTHS_VERSION else (engine_version[0:MAX_LENGTHS_VERSION-3] + "..."),
				format_size(total_size),
				format_size(source_size),
				format_size(build_size),
				format_size(install_size),
				print_workflow(engine_workflow),
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


def uninstall_engine(engine_version, engine_config = None, engine_variant = None, force = False):
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
		build_dir = get_build_path(CONTAINER_CLIENT.get_volume_path(build_volume), engine_variant)
		install_dir = CONTAINER_CLIENT.get_volume_path(install_volume)

		no_config = True

		if has_build_config(build_dir, engine_config) or has_install_config(install_dir, engine_config, engine_variant):
			run_builder(engine_version, None, None, None, BuilderCommands.CLEAN, Targets.ENGINE, engine_config, engine_variant, True, True)
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
	engine_version, not_used, not_used, external_gem_dirs = check_project_dependencies(project_dir)
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
		engine_variant = O3DE_Variants.NON_MONOLITHIC
		project_build_dir = get_build_path(get_builds_root_path(project_dir), engine_variant, OPERATING_SYSTEM)

		print_msg(Level.INFO, Messages.ADD_GEM_REBUILD, gem_value)

		for engine_config in [ O3DE_Configs.DEBUG, O3DE_Configs.PROFILE ]:
			if not has_build_config(project_build_dir, engine_config):
				continue

			built = run_builder(engine_version, engine_config, project_dir, external_gem_dirs, BuilderCommands.BUILD, Targets.PROJECT, engine_config, engine_variant, O3DE_ProjectBinaries.TOOLS, True)
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

	engine_version, not_used, not_used, external_gem_dirs = check_project_dependencies(project_dir)
	if not is_engine_installed(engine_version):
		throw_error(Messages.MISSING_VERSION, Targets.ENGINE.value, engine_version)

	removed = run_builder(engine_version, None, project_dir, external_gem_dirs, BuilderCommands.SETTINGS, Targets.PROJECT, Settings.GEMS.value, gem_index, None, gem_value, clear_option, False, False)

	if removed and rebuild:
		engine_variant = O3DE_Variants.NON_MONOLITHIC
		project_build_dir = get_build_path(get_builds_root_path(project_dir), engine_variant, OPERATING_SYSTEM)

		print_msg(Level.INFO, Messages.REMOVE_GEM_REBUILD, gem_index)

		for engine_config in [ O3DE_Configs.DEBUG, O3DE_Configs.PROFILE ]:
			if not has_build_config(project_build_dir, engine_config):
				continue

			built = run_builder(engine_version, engine_config, project_dir, external_gem_dirs, BuilderCommands.BUILD, Targets.PROJECT, engine_config, engine_variant, O3DE_ProjectBinaries.TOOLS, True)
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


def build_project(project_dir, binary, config, variant):
	engine_version, was_config_missing, not_used, external_gem_dirs = check_project_dependencies(project_dir, config, variant)

	run_builder(engine_version, config, project_dir, external_gem_dirs, BuilderCommands.BUILD, Targets.PROJECT, config, variant, binary, was_config_missing)


def clean_project(project_dir, config, variant, remove_build, remove_cache, force = False):
	engine_version, not_used, not_used, external_gem_dirs = check_project_dependencies(project_dir, config if not force else None, variant if not force else None)

	run_builder(engine_version, config, project_dir, external_gem_dirs, BuilderCommands.CLEAN, Targets.PROJECT, config, variant, remove_build, remove_cache, force)


def export_project(project_dir, binary, config, variant, output_type, output_name = None, level_names = None, bundle_names = None, build_source = True, process_assets = True):
	engine_version, was_config_missing, engine_workflow, external_gem_dirs = check_project_dependencies(project_dir, config, variant)

	project_name = read_json_property(project_dir / "project.json", JsonPropertyKey(None, None, "project_name"))
	if project_name is None:
		throw_error(Messages.INVALID_PROJECT_NAME)

	build_dir = get_build_path(get_builds_root_path(project_dir), variant)
	bin_dir = get_build_bin_path(build_dir, config)

	if binary is O3DE_ProjectBinaries.CLIENT:
		binary_suffix = "GameLauncher"
	elif binary is O3DE_ProjectBinaries.SERVER:
		binary_suffix = "ServerLauncher"
	else:
		throw_error(Messages.INVALID_BINARY, binary.value)

	binary_name = get_binary_filename("{}.{}".format(project_name, binary_suffix))

	if build_source:
		print_msg(Level.INFO, Messages.START_EXPORT_BUILD_BINARY, config.value, variant.value)

		built = run_builder(engine_version, config, project_dir, external_gem_dirs, BuilderCommands.BUILD, Targets.PROJECT, config, variant, None, was_config_missing)
		if not built:
			throw_error(Messages.UNCOMPLETED_EXPORT)
	else:
		if (bin_dir is None) or not (bin_dir / binary_name).is_file():
			throw_error(Messages.EXPORT_MISSING_BINARY, config.value, variant.value)

		print_msg(Level.INFO, Messages.EXPORT_SKIP_BUILD_SOURCE)

	engine_config = O3DE_Configs.PROFILE
	engine_variant = O3DE_Variants.NON_MONOLITHIC

	platform = get_platform()
	if platform is None:
		throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM.family)

	cache_dir = project_dir / "Cache" / platform.value
	use_bundles = config is O3DE_Configs.RELEASE

	bundles_dir = project_dir / "AssetBundling" / "Bundles"
	if bundle_names is not None and len(bundle_names) > 0:
		if not use_bundles:
			throw_error(Messages.EXPORT_INVALID_CONFIG_AND_BUNDLE, config.value)

		bundle_files = []
		for bundle_name in bundle_names:
			if not bundle_name.endswith(".pak"):
				bundle_name = "{}.pak".format(bundle_name)

			bundle_file = bundles_dir / bundle_name
			if not bundle_file.is_file():
				throw_error(Messages.MISSING_BUNDLE, bundle_name)

			bundle_files.append(bundle_file)

		print_msg(Level.INFO, Messages.EXPORT_SKIP_PACK_BUNDLES, ", ".join(bundle_names))

	else:
		if process_assets:
			print_msg(Level.INFO, Messages.START_EXPORT_PROCESS_ASSETS)

			processed = run_runner(engine_version, engine_config, engine_variant, engine_workflow, project_dir, external_gem_dirs, True, True, RunnerCommands.OPEN, O3DE_EngineBinaries.ASSET_PROCESSOR, engine_config)
			if not processed:
				throw_error(Messages.UNCOMPLETED_EXPORT)
		else:
			if not cache_dir.is_dir() or is_directory_empty(cache_dir):
				throw_error(Messages.EXPORT_MISSING_ASSETS)

			print_msg(Level.INFO, Messages.EXPORT_SKIP_PROCESS_ASSETS)

		if not use_bundles:
			bundle_files = []
		else:
			seedlists_dir = project_dir / "AssetBundling" / "SeedLists"
			game_seedlist_file = seedlists_dir / "GameSeedList.seed"

			assetlists_dir = project_dir / "AssetBundling" / "AssetLists"
			game_assetlist_file = assetlists_dir / "game_{}.assetlist".format(platform.value)
			engine_assetlist_file = assetlists_dir / "engine_{}.assetlist".format(platform.value)

			game_bundle_name = "game_{}.pak".format(platform.value)
			game_bundle_file = bundles_dir / game_bundle_name
		
			engine_bundle_name = "engine_{}.pak".format(platform.value)
			engine_bundle_file = bundles_dir / engine_bundle_name

			print_msg(Level.INFO, Messages.START_EXPORT_PACK_ASSETS_TO_BUNDLES, "{}, {}".format(game_bundle_name, engine_bundle_name))

			bundler_commands = [
				[
					"seeds",
					"--seedListFile", str(game_seedlist_file),
					"--platform", platform.value
				],
				[
					"assetLists",
					"--assetListFile", str(game_assetlist_file),
					"--seedListFile", str(game_seedlist_file),
					"--platform", platform.value,
					"--allowOverwrites"
				],
				[
					"assetLists",
					"--assetListFile", str(engine_assetlist_file),
					"--platform", platform.value,
					"--addDefaultSeedListFiles",
					"--allowOverwrites"
				],
				[
					"bundles",
					"--assetListFile", str(game_assetlist_file),
					"--outputBundlePath", str(game_bundle_file),
					"--platform", platform.value,
					"--allowOverwrites"
				],
				[
					"bundles",
					"--assetListFile", str(engine_assetlist_file),
					"--outputBundlePath", str(engine_bundle_file),
					"--platform", platform.value,
					"--allowOverwrites"
				]
			]

			levels_dir = project_dir / "Cache" / platform.value / "levels"
			if level_names is not None:
				for level_name in level_names:
					level_name = level_name.lower()

					level_file = levels_dir / level_name / "{}.spawnable".format(level_name)
					if not level_file.is_dir():
						throw_error(Messages.MISSING_LEVEL, str(level_file))

			else:
				level_names = []

				for content in levels_dir.iterdir():
					if content.is_dir():
						for subcontent in content.iterdir():
							if subcontent.is_file() and subcontent.suffix == ".spawnable":
								level_names.append(content.name)
								break

			for level_name in level_names:
				bundler_commands[0].append("--addSeed")
				bundler_commands[0].append("levels/{0}/{0}.spawnable".format(level_name))

			for bundler_command in bundler_commands:
				executed = run_runner(engine_version, engine_config, engine_variant, engine_workflow, project_dir, external_gem_dirs, True, True, RunnerCommands.OPEN, O3DE_EngineBinaries.ASSET_BUNDLER, engine_config, False, bundler_command)
				if not executed:
					throw_error(Messages.UNCOMPLETED_EXPORT)

			bundle_files = [
				game_bundle_file,
				engine_bundle_file
			]

	output_root_dir = project_dir / "install"
	if not output_root_dir.exists():
		output_root_dir.mkdir(parents = True)

	if output_type is ArchiveTypes.CONTAINER:
		from_image = CONTAINER_CLIENT.get_image_name(Images.RUNNER)

		new_image_name = "{}-{}".format(project_name.lower(), "server" if binary is O3DE_ProjectBinaries.SERVER else "client") if output_name is None else output_name
		if not is_image_name(new_image_name):
			throw_error(Messages.INVALID_PROJECT_NAME_FOR_IMAGES, project_name)

		print_msg(Level.INFO, Messages.START_EXPORT_SAVE_IMAGE, new_image_name)

		new_container = None
		try:
			new_container = CONTAINER_CLIENT.run_container(ContainerRunMode.STANDBY, from_image, network_disabled = True)

			output_base_dir = O3DE_PROJECT_SOURCE_DIR
			copied = copy_project_to_archive(bin_dir, cache_dir, bundle_files, binary_name, platform, variant, new_container, output_type, output_base_dir)
			if not copied:
				throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)

			autoexec_name = "server.cfg" if binary is O3DE_ProjectBinaries.SERVER else "client.cfg"
			autoexec_file = cache_dir / autoexec_name

			new_image = new_container.commit(
				tag = new_image_name,
				changes = [
					"WORKDIR \"{}\"".format(output_base_dir),
					"ENTRYPOINT [ \"./{}\", \"-bg_ConnectToAssetProcessor=0\"{} ]".format(
						binary_name,
						 ", \"--rhi=null\", \"-NullRenderer\"" if binary is O3DE_ProjectBinaries.SERVER else ""
					),
					"CMD [ {} ]".format(
						"\"--console-command-file={}\"".format(autoexec_name) if autoexec_file.is_file() else ""
					)
				]
			)

			if new_image is None:
				throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)
			elif (new_image is not None) and (len(new_image.tags) == 0) and (len(new_image.id) > 0):
				new_image.tag(new_image_name)
			print_msg(Level.INFO, Messages.EXPORT_IMAGE_COMPLETED, new_image_name)

		except docker.errors.ContainerError:
			throw_error(Messages.ERROR_SAVE_IMAGE, new_image_name)

		finally:
			if new_container is not None:
				new_container.kill()

	else:
		open_flag = 'w'
		if output_type is ArchiveTypes.TAR_GZ:
			open_flag += ":gz"			
		elif output_type is ArchiveTypes.ZIP:
			pass
		else:
			throw_error(Messages.INVALID_ARCHIVE_TYPE, output_type.value)

		archive_suffix = ".{}".format(output_type.value)
		archive_name = "{}.{}".format(project_name, "Server" if binary is O3DE_ProjectBinaries.SERVER else "Client") if output_name is None else output_name
		if not archive_name.endswith(archive_suffix):
			archive_name += archive_suffix

		archive_file = output_root_dir / archive_name
		with (zipfile.ZipFile(archive_file, open_flag, ) if output_type is ArchiveTypes.ZIP else tarfile.open(archive_file, open_flag)) as new_archive:
			copied = copy_project_to_archive(bin_dir, cache_dir, bundle_files, binary_name, platform, variant, new_archive, output_type, pathlib.PosixPath("/"))
			if not copied:
				throw_error(Messages.ERROR_SAVE_IMAGE, archive_name)

		if CONTAINER_CLIENT.is_in_container:
			relative_path = archive_file.relative_to(project_dir)
			real_archive_file = get_real_project_dir() / relative_path
		else:
			real_archive_file = archive_file

		print_msg(Level.INFO, Messages.EXPORT_ARCHIVE_COMPLETED, real_archive_file)


def install_project(repository, project_dir, config, variant):
	if repository is not None:
		repository_protocol, repository_url, repository_reference = parse_repository_url(repository)

	resume_command = [
		get_bin_name(),
		CliCommands.INSTALL.value,
		CliSubCommands.PROJECT.value
	]

	if repository is not None:
		resume_command.append(repository_url)

		if repository_reference is not None:
			if is_commit(repository_reference):
				resume_command.append(print_option(LongOptions.COMMIT, repository_reference))
			else:
				resume_command.append(print_option(LongOptions.BRANCH, repository_reference))

	resume_command = ' '.join(resume_command)

	if CONTAINER_CLIENT.is_in_container:
		mapping = { str(project_dir): get_real_project_dir() }
		real_project_dir = get_real_project_dir()
	else:
		mapping = None
		real_project_dir = project_dir

	check_ownership(project_dir, Messages.CHANGE_OWNERSHIP_PROJECT, resume_command, mapping)

	if repository is not None:
		downloaded = run_updater(None, UpdaterCommands.INIT, Targets.PROJECT, real_project_dir, repository_url, repository_reference)
		if not downloaded:
			throw_error(Messages.UNCOMPLETED_INSTALL)

		if is_engine_release_number(repository_reference):
			engine_version = get_engine_version_from_project(project_dir)
			if engine_version is None:
				run_builder(engine_version, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, Settings.ENGINE.value, None, EngineSettings.REPOSITORY.value.name, O3DE_REPOSITORY_URL, False, False, False)
				run_builder(engine_version, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, Settings.ENGINE.value, None, EngineSettings.BRANCH.value.name, repository_reference, False, False, False)

		if (project_dir / ".lfsconfig").is_file():
			resume_command = [
				get_bin_name(),
				CliCommands.INSTALL.value,
				CliSubCommands.PROJECT.value
			]

			print_msg(Level.INFO, Messages.RUN_EXTERNAL_COMMANDS, "(or use your preferred GIT client)")
			print_msg(Level.INFO, "cd {}".format(real_project_dir))
			print_msg(Level.INFO, "git lfs install")
			print_msg(Level.INFO, "git lfs pull")
			print_msg(Level.INFO, '')
			print_msg(Level.INFO, Messages.RUN_RESUME_COMMAND)
			print_msg(Level.INFO, ' '.join(resume_command))

			exit(0)

	if not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, real_project_dir)

	check_project_dependencies(project_dir, config, variant)

	print_msg(Level.INFO, Messages.INSTALL_PROJECT_COMPLETED, real_project_dir)


def manage_project_settings(project_dir, setting_key_section , setting_key_index, setting_key_name, setting_value, clear):
	run_builder(None, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, setting_key_section, setting_key_index, setting_key_name, setting_value, clear, False, True)


def open_project(project_dir, engine_config = None, new_engine_version = None, engine_binary = O3DE_EngineBinaries.EDITOR):
	if new_engine_version is None:
		engine_version, not_used, not_used, external_gem_dirs = check_project_dependencies(project_dir)
	else:
		if not is_engine_installed(new_engine_version):
			throw_error(Messages.MISSING_VERSION, Targets.ENGINE.value, new_engine_version)

		engine_version = new_engine_version
		not_used, not_used, not_used, external_gem_dirs = check_project_dependencies(project_dir, check_engine = False)

	if engine_config is None:
		engine_config = select_recommended_config(engine_version)
		if engine_config is None:
			throw_error(Messages.VERSION_NOT_FOUND, engine_version)

	not_used, was_config_missing, engine_workflow, not_used = check_project_dependencies(project_dir, engine_config, O3DE_Variants.NON_MONOLITHIC, check_gems = False)

	if new_engine_version is not None:
		run_builder(engine_version, None, project_dir, None, BuilderCommands.SETTINGS, Targets.PROJECT, Settings.ENGINE.value, None, None, new_engine_version, False, True, False)

	project_name = read_json_property(project_dir / "project.json", JsonPropertyKey(None, None, "project_name"))
	if project_name is None:
		throw_error(Messages.INVALID_PROJECT_NAME)

	if engine_workflow in [ O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE, O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK ]:
		is_project_centric = True
	elif engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
		is_project_centric = False
	else:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow)

	if is_project_centric:
		build_dir = get_build_path(get_builds_root_path(project_dir))
	else:
		build_volume = CONTAINER_CLIENT.get_volume_name(Volumes.BUILD, engine_version)
		build_dir = get_build_path(CONTAINER_CLIENT.get_volume_path(build_volume))

	bin_build_dir = get_build_bin_path(build_dir, engine_config)
	project_library_file = bin_build_dir / get_library_filename("lib" + project_name) if (bin_build_dir is not None) else None

	if (project_library_file is None) or not project_library_file.is_file():
		if is_project_centric:
			built = run_builder(engine_version, engine_config, project_dir, external_gem_dirs, BuilderCommands.BUILD, Targets.PROJECT, engine_config, O3DE_Variants.NON_MONOLITHIC, O3DE_ProjectBinaries.TOOLS, was_config_missing)
			if not built:
				throw_error(Messages.UNCOMPLETED_BUILD_PROJECT)
		else:
			throw_error(Messages.MISSING_INSTALL_ENGINE_PROJECT, engine_version)

	asset_processor_container = check_asset_processor(engine_version, engine_config, engine_workflow, project_dir, external_gem_dirs, wait = (engine_binary is O3DE_EngineBinaries.ASSET_PROCESSOR)) if engine_binary is not O3DE_EngineBinaries.ASSET_BUNDLER else None

	if engine_binary is not O3DE_EngineBinaries.ASSET_PROCESSOR:
		container_command = [ RunnerCommands.OPEN, engine_binary, engine_config ]
		if NETWORK_NAME is None and asset_processor_container is not None:
			exec_in_runner(asset_processor_container, container_command)
		else:
			run_runner(engine_version, engine_config, O3DE_Variants.NON_MONOLITHIC, engine_workflow, project_dir, external_gem_dirs, False, True, *container_command)


def run_project(project_dir, binary, config, variant, level_name = None, console_commands = None, console_variables = None, connect_to_server = False, listen_on_port = None):
	engine_version, not_used, engine_workflow, external_gem_dirs = check_project_dependencies(project_dir)

	if not binary in [ O3DE_ProjectBinaries.CLIENT, O3DE_ProjectBinaries.SERVER]:
		throw_error(Messages.INVALID_BINARY, binary)

	if console_commands is None:
		console_commands = []
	else:
		for command in console_commands:
			matches = parse_console_command(command)
			if matches is None:
				throw_error(Messages.INVALID_CONSOLE_COMMAND, command)

	if console_variables is None:
		console_variables = {}
	else:
		console_variables_dict = {}
		for variable in console_variables:
			matches = parse_console_variable(variable)
			if matches is None:
				throw_error(Messages.INVALID_CONSOLE_VARIABLE, variable)

			variable_name = matches.group(1)
			variable_value = matches.group(2)

			console_variables_dict[variable_name] = variable_value

		console_variables = console_variables_dict

	if binary is O3DE_ProjectBinaries.CLIENT:
		if isinstance(connect_to_server, str):
			matches = re.match(r"^(([a-zA-Z][\w.-]*)|([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})):([0-9]+)$", connect_to_server)
			if matches is None:
				throw_error(Messages.INVALID_SERVER_ADDRESS, connect_to_server)

			server_ip = matches.group(1)
			server_port = matches.group(4)

		else:
			server_lock_file = project_dir / SERVER_LOCK_PATH
			if server_lock_file.is_file():
				server_ip = read_json_property(server_lock_file, InstanceProperties.IP.value)
				server_port = read_json_property(server_lock_file, InstanceProperties.PORT.value)

			elif connect_to_server is None:
				throw_error(Messages.MISSING_SERVER_FILE)

			else:
				server_ip = None
				server_port = None

		if (server_ip is not None) and (server_port is not None):
			console_variables[O3DE_ConsoleVariables.NETWORK_CLIENT_REMOTE_IP.value] = server_ip
			console_variables[O3DE_ConsoleVariables.NETWORK_CLIENT_REMOTE_PORT.value] = server_port

			if connect_to_server is not False:
				console_commands.insert(0, "connect[]")

	if listen_on_port is not None:
		try:
			server_port = int(listen_on_port)
		except:
			throw_error(Messages.INVALID_SERVER_PORT, listen_on_port)

		console_variables[O3DE_ConsoleVariables.NETWORK_SERVER_LISTENING_PORT.value] = server_port
		console_commands.insert(0, "host[]")

	if level_name is not None:
		level_path = pathlib.Path("Levels/{0}/{0}.prefab".format(level_name))
		level_file = project_dir / level_path
		if not level_file.is_file():
			throw_error(Messages.MISSING_LEVEL, (get_real_project_dir() if CONTAINER_CLIENT.is_in_container() else project_dir) / level_path)

		level_command = "LoadLevel[{}]".format(level_path.with_suffix(".spawnable"))
		console_commands.insert(0, level_command)

	asset_processor_container = check_asset_processor(engine_version, config, engine_workflow, project_dir, external_gem_dirs) if config is not O3DE_Configs.RELEASE else None

	container_command = [ RunnerCommands.RUN, binary, config, variant, console_commands, console_variables ]
	if NETWORK_NAME is None and asset_processor_container is not None:
		exec_in_runner(asset_processor_container, container_command)
	else:	
		run_runner(engine_version, config, variant, engine_workflow, project_dir, external_gem_dirs, False, True, *container_command)


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

def handle_install_engine_command(version_name, engine_config_name, engine_variant_name, repository, fork, branch, tag, commit, engine_workflow_name, force, incremental, save_images, **kwargs):
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

	engine_variant = O3DE_Variants.from_value(engine_variant_name)
	if engine_variant is None:
		throw_error(Messages.INVALID_VARIANT, engine_variant_name)

	engine_workflow = O3DE_BuildWorkflows.from_value(engine_workflow_name)
	if engine_workflow is None:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow_name)

	try:
		check_container_client()
		check_updater()
		check_builder()
		if save_images is not False:
			check_runner()

		install_engine(repository_url, engine_version, engine_config, engine_variant, engine_workflow, force, incremental, save_images)
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


def handle_uninstall_engine_command(engine_version, engine_config_name, engine_variant_name, force):
	if not is_engine_version(engine_version):
		throw_error(Messages.INVALID_VERSION, engine_version)

	if engine_config_name is not None:
		engine_config = O3DE_Configs.from_value(engine_config_name)
		if engine_config is None:
			throw_error(Messages.INVALID_CONFIG, engine_config_name)
	else:
		engine_config = None

	if engine_variant_name is not None:
		engine_variant = O3DE_Variants.from_value(engine_variant_name)
		if engine_variant is None:
			throw_error(Messages.INVALID_VARIANT, engine_variant_name)
	else:
		engine_variant = None

	try:
		check_container_client()
	
		uninstall_engine(engine_version, engine_config, engine_variant, force)

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


def handle_build_command(project_path, binary_name, config_name, variant_name):
	binary = O3DE_ProjectBinaries.from_value(binary_name)
	if binary is None:
		if binary_name == CliSubCommands.ASSETS.value:
			binary = O3DE_EngineBinaries.ASSET_PROCESSOR
		else:
			throw_error(Messages.INVALID_BINARY, binary_name)

	config = O3DE_Configs.from_value(config_name)
	if config is None:
		throw_error(Messages.INVALID_CONFIG, config_name)

	variant = O3DE_Variants.from_value(variant_name)
	if variant is None:
		throw_error(Messages.INVALID_VARIANT, variant_name)

	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	try:
		check_container_client()

		if isinstance(binary, O3DE_ProjectBinaries):
			check_builder()

			build_project(project_dir, binary, config, variant)

		elif isinstance(binary, O3DE_EngineBinaries):
			check_runner()

			open_project(project_dir, config, None, binary)

		else:
			throw_error(Messages.INVALID_BINARY, binary_name)

	finally:
		close_container_client()


def handle_clean_command(project_path, config_name, variant_name, remove_build, remove_cache, force):
	config = O3DE_Configs.from_value(config_name)
	if config is None:
		throw_error(Messages.INVALID_CONFIG, config_name)

	if variant_name is not None:
		variant = O3DE_Variants.from_value(variant_name)
		if variant is None:
			throw_error(Messages.INVALID_VARIANT, variant_name)
	else:
		variant = None

	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	if not remove_build and not remove_cache:
		remove_build = True
		remove_cache = False

	try:
		check_container_client()
		check_builder()

		clean_project(project_dir, config, variant, remove_build, remove_cache, force)

	finally:
		close_container_client()


def handle_export_assets_command(project_path, config_name):
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

		open_project(project_dir, config, None, O3DE_EngineBinaries.ASSET_BUNDLER)

	finally:
		close_container_client()


def handle_export_binary_command(project_path, binary_name, config_name, variant_name, output_type_name, output_name, level_names, bundle_names, build_source, process_assets):
	binary = O3DE_ProjectBinaries.from_value(binary_name)
	if binary is None:
		throw_error(Messages.INVALID_BINARY, binary_name)
	
	config = O3DE_Configs.from_value(config_name)
	if config is None:
		throw_error(Messages.INVALID_CONFIG, config_name)

	variant = O3DE_Variants.from_value(variant_name)
	if variant is None:
		throw_error(Messages.INVALID_VARIANT, variant_name)

	if output_type_name is not None:
		output_type = ArchiveTypes.from_value(output_type_name)
		if output_type is None:
			throw_error(Messages.INVALID_ARCHIVE_TYPE, output_type_name)
	else:
		output_type = ArchiveTypes.ZIP if OPERATING_SYSTEM.family is OSFamilies.WINDOWS else ArchiveTypes.TAR_GZ

	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	try:
		check_container_client()
		
		check_builder()
		if output_type is ArchiveTypes.CONTAINER:
			check_runner()

		export_project(project_dir, binary, config, variant, output_type, output_name, level_names, bundle_names, build_source, process_assets)

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


def handle_install_project_command(project_path, config_name, variant_name, repository, branch, tag, commit, **kwargs):
	repository_url = generate_repository_url(repository, None, branch, tag, commit) if repository is not None else None

	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, project_path)
	else:
		if repository is not None:
			if not is_directory_empty(project_dir):
				throw_error(Messages.PROJECT_DIR_NOT_EMPTY, project_path)
		else:
			if not is_project(project_dir):
				throw_error(Messages.PROJECT_NOT_FOUND, project_path)

	config = O3DE_Configs.from_value(config_name)
	if config is None:
		throw_error(Messages.INVALID_CONFIG, config_name)

	variant = O3DE_Variants.from_value(variant_name)
	if variant is None:
		throw_error(Messages.INVALID_VARIANT, variant_name)

	try:
		check_container_client()
		check_updater()
		if tag is not None:
			check_builder()

		install_project(repository_url, project_dir, config, variant)

	finally:
		close_container_client()


def handle_open_editor_command(project_path, engine_config_name, new_engine_version):
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


def handle_run_command(project_path, binary_name, config_name, variant_name, level_name, console_commands, console_variables, connect_to_server, listen_on_port):
	binary = O3DE_ProjectBinaries.from_value(binary_name)
	if binary is None:
		throw_error(Messages.INVALID_BINARY, binary_name)

	config = O3DE_Configs.from_value(config_name)
	if config is None:
		throw_error(Messages.INVALID_CONFIG, config_name)

	variant = O3DE_Variants.from_value(variant_name)
	if variant is None:
		throw_error(Messages.INVALID_VARIANT, variant_name)

	project_dir = parse_project_path(project_path)
	if not project_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY, (project_path if project_path is not None else project_dir))
	elif not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, (project_path if project_path is not None else project_dir))

	try:
		check_container_client()
		check_runner()

		run_project(project_dir, binary, config, variant, level_name, console_commands, console_variables, connect_to_server, listen_on_port)

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

	DESCRIPTIONS_COMMON_CONFIG = "Build configuration: {}".format(", ".join([ config.value for config in O3DE_Configs ]))
	DESCRIPTIONS_COMMON_GEM = "Gem version"
	DESCRIPTIONS_COMMON_GEM_REFERENCE = "Version name of an installed gem, or path to its local workspace"
	DESCRIPTIONS_COMMON_ENGINE = "Engine version"
	DESCRIPTIONS_COMMON_PROJECT = "Path to the project root, instead of the current directory"
	DESCRIPTIONS_COMMON_VARIANT = "Build variant: {}".format(", ".join([ variant.value for variant in O3DE_Variants ]))

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
	DESCRIPTIONS_INSTALL_ENGINE_INCREMENTAL = "Keep intermediate files to speed up future upgrades (only for {})".format(print_option(LongOptions.WORKFLOW, O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK.value))
	DESCRIPTIONS_INSTALL_ENGINE_SAVE_IMAGES = "Generate images containing the engine installation (only for {})".format(print_option(LongOptions.WORKFLOW, O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK.value))
	DESCRIPTIONS_INSTALL_ENGINE_VARIANT = DESCRIPTIONS_COMMON_VARIANT
	DESCRIPTIONS_INSTALL_ENGINE_WORKFLOW = "Build workflow: {}".format(", ".join([ workflow.value for workflow in O3DE_BuildWorkflows ]))
	DESCRIPTIONS_INSTALL_ENGINE_WORKFLOW_ENGINE = "Build all projects in the engine (alias for: {})".format(print_option(LongOptions.WORKFLOW, O3DE_BuildWorkflows.ENGINE_CENTRIC.value))
	DESCRIPTIONS_INSTALL_ENGINE_WORKFLOW_PROJECT = "Build the engine in each project (alias for: {})".format(print_option(LongOptions.WORKFLOW, O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE.value))
	DESCRIPTIONS_INSTALL_ENGINE_WORKFLOW_SDK = "Build the engine once and link it in each project (alias for: {})".format(print_option(LongOptions.WORKFLOW, O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK.value))
	DESCRIPTIONS_INSTALL_GEM = "Download a new gem version"
	DESCRIPTIONS_INSTALL_PROJECT = "Download an existing project and install all its dependencies"
	DESCRIPTIONS_INSTALL_PROJECT_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_INSTALL_PROJECT_PATH = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_INSTALL_PROJECT_VARIANT = DESCRIPTIONS_COMMON_VARIANT
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
	DESCRIPTIONS_UNINSTALL_ENGINE_VARIANT = DESCRIPTIONS_COMMON_VARIANT
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
	DESCRIPTIONS_BUILD_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_BUILD_PROJECT = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_BUILD_ASSETS = "Process assets for a platform"
	DESCRIPTIONS_BUILD_CLIENT = "Build a runtime with full capabilities (input, sound, video)"
	DESCRIPTIONS_BUILD_SERVER = "Build a runtime that can receive connections from other clients"
	DESCRIPTIONS_BUILD_TOOLS = "Build libraries required by the editor"
	DESCRIPTIONS_BUILD_VARIANT = DESCRIPTIONS_COMMON_VARIANT

	DESCRIPTIONS_CLEAN = "Remove all built project files (binaries and intermediates)"
	DESCRIPTIONS_CLEAN_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_CLEAN_FORCE = "Remove files even if the project is corrupted"
	DESCRIPTIONS_CLEAN_PROJECT = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_CLEAN_BUILD = "Remove built files (default)"
	DESCRIPTIONS_CLEAN_CACHE = "Remove cached files"
	DESCRIPTIONS_CLEAN_VARIANT = DESCRIPTIONS_COMMON_VARIANT

	DESCRIPTIONS_EXPORT = "Generate a releasable package containing the project runtimes"
	DESCRIPTIONS_EXPORT_ASSETS = "Manage assets to be packed for each platform"
	DESCRIPTIONS_EXPORT_CLIENT = "Generate a package for the standalone / client runtime"
	DESCRIPTIONS_EXPORT_SERVER = "Generate a package for the dedicated server runtime"
	DESCRIPTIONS_EXPORT_ALIAS = "Assign an output name, instead of the project name"
	DESCRIPTIONS_EXPORT_BUNDLES = "Use existing asset bundle(s), instead of generating new one(s)"
	DESCRIPTIONS_EXPORT_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_EXPORT_LEVELS = "Level(s) to be included in the package. Leave empty to export all levels"
	DESCRIPTIONS_EXPORT_PROJECT = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_EXPORT_SKIP_BUILD_SOURCE = "Don't re-build the project runtime if it already exists"
	DESCRIPTIONS_EXPORT_SKIP_PROCESS_ASSETS = "Don't re-process assets if the cache directory isn't empty"
	DESCRIPTIONS_EXPORT_TYPE = "Package type: {}".format(", ".join([ archive_type.value for archive_type in ArchiveTypes ]))
	DESCRIPTIONS_EXPORT_VARIANT = DESCRIPTIONS_COMMON_VARIANT

	DESCRIPTIONS_INIT = "Create a new empty workspace"
	DESCRIPTIONS_INIT_ALIAS = "Assign a project name, instead of the directory name"
	DESCRIPTIONS_INIT_ENGINE = DESCRIPTIONS_COMMON_ENGINE
	DESCRIPTIONS_INIT_PATH = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_INIT_PROJECT = "Create a new project"
	DESCRIPTIONS_INIT_PROJECT_MINIMAL = "Activate only a minimal set of built-in gems (no sample assets)"
	DESCRIPTIONS_INIT_GEM = "Create a new gem"
	DESCRIPTIONS_INIT_GEM_SKIP_EXAMPLES = "Don't create a project to try the gem"
	DESCRIPTIONS_INIT_GEM_TYPE = "Type of gem: {}".format(", ".join([ gem_type.value for gem_type in O3DE_GemTypes ]))

	DESCRIPTIONS_OPEN = "Open the project with a tool"
	DESCRIPTIONS_OPEN_PROJECT = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_OPEN_EDITOR = "Open the editor to view / modify the project scenes"
	DESCRIPTIONS_OPEN_EDITOR_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_OPEN_EDITOR_ENGINE = "Override the linked engine version"

	DESCRIPTIONS_REMOVE = "Remove an existing resource from the project"
	DESCRIPTIONS_REMOVE_PROJECT = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_REMOVE_GEM = "Deactivate a gem in the project"
	DESCRIPTIONS_REMOVE_GEM_VERSION = DESCRIPTIONS_COMMON_GEM_REFERENCE
	DESCRIPTIONS_REMOVE_GEM_SKIP_REBUILD = "Don't re-build the project if the gem is removed successfully"

	DESCRIPTIONS_RUN = "Run a built project runtime"
	DESCRIPTIONS_RUN_CONSOLE_COMMAND = "Execute a console command"
	DESCRIPTIONS_RUN_CONSOLE_VARIABLE = "Set a console variable (CVar)"
	DESCRIPTIONS_RUN_CONFIG = DESCRIPTIONS_COMMON_CONFIG
	DESCRIPTIONS_RUN_LEVEL = "Start from a specific level"
	DESCRIPTIONS_RUN_PROJECT = DESCRIPTIONS_COMMON_PROJECT
	DESCRIPTIONS_RUN_VARIANT = DESCRIPTIONS_COMMON_VARIANT
	DESCRIPTIONS_RUN_CLIENT = "Run an instance with full capabilities (input, sound and video)"
	DESCRIPTIONS_RUN_CLIENT_CONNECT = "Connect to the primary server (or a specific one)"
	DESCRIPTIONS_RUN_SERVER = "Run an instance that can accept connections from other clients"
	DESCRIPTIONS_RUN_SERVER_LISTEN = "Listen on a specific port"

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

	install_revision_parser = argparse.ArgumentParser(add_help = False)
	install_revision_group = install_revision_parser.add_mutually_exclusive_group()
	install_revision_group.add_argument(print_option(LongOptions.BRANCH), metavar = "<string>", help = DESCRIPTIONS_INSTALL_REPOSITORY_BRANCH)
	install_revision_group.add_argument(print_option(LongOptions.COMMIT), metavar = "<hash>", help = DESCRIPTIONS_INSTALL_REPOSITORY_COMMIT)
	install_revision_group.add_argument(print_option(LongOptions.TAG), metavar = "<string>", help = DESCRIPTIONS_INSTALL_REPOSITORY_TAG)

	install_engine_parser = install_subparsers.add_parser(CliSubCommands.ENGINE.value, parents = [ global_parser, install_common_parser, install_revision_parser ], help = DESCRIPTIONS_INSTALL_ENGINE)
	install_engine_parser.set_defaults(handler = handle_install_engine_command)
	install_engine_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "engine_config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_INSTALL_ENGINE_CONFIG)
	install_engine_parser.add_argument(print_option(LongOptions.VARIANT), dest = "engine_variant_name", default = O3DE_DEFAULT_VARIANT.value, metavar = "<variant>", help = DESCRIPTIONS_INSTALL_ENGINE_VARIANT)
	install_engine_parser.add_argument(print_option(LongOptions.INCREMENTAL), action = "store_true", help = DESCRIPTIONS_INSTALL_ENGINE_INCREMENTAL)
	install_engine_parser.add_argument(print_option(LongOptions.SAVE_IMAGES), action = "store_true", help = DESCRIPTIONS_INSTALL_ENGINE_SAVE_IMAGES)

	install_workflow_group = install_engine_parser.add_mutually_exclusive_group()
	install_workflow_group.add_argument(print_option(ShortOptions.WORKFLOW), print_option(LongOptions.WORKFLOW), dest = "engine_workflow_name", default = O3DE_DEFAULT_WORKFLOW.value, metavar = "<workflow>", help = DESCRIPTIONS_INSTALL_ENGINE_WORKFLOW)
	install_workflow_group.add_argument(print_option(LongOptions.WORKFLOW_ENGINE), dest = "engine_workflow_name", action = "store_const", const = O3DE_BuildWorkflows.ENGINE_CENTRIC.value, help = DESCRIPTIONS_INSTALL_ENGINE_WORKFLOW_ENGINE)
	install_workflow_group.add_argument(print_option(LongOptions.WORKFLOW_PROJECT), dest = "engine_workflow_name", action = "store_const", const = O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE.value, help = DESCRIPTIONS_INSTALL_ENGINE_WORKFLOW_PROJECT)
	install_workflow_group.add_argument(print_option(LongOptions.WORKFLOW_SDK), dest = "engine_workflow_name", action = "store_const", const = O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK.value, help = DESCRIPTIONS_INSTALL_ENGINE_WORKFLOW_SDK)

	install_url_group = install_engine_parser.add_mutually_exclusive_group()
	install_url_group.add_argument(print_option(LongOptions.FORK), metavar = "<username>/<project>", help = DESCRIPTIONS_INSTALL_REPOSITORY_FORK)
	install_url_group.add_argument(print_option(LongOptions.REPOSITORY), metavar = "<url>", help = DESCRIPTIONS_INSTALL_REPOSITORY)

	install_gem_parser = install_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser, install_common_parser, install_revision_parser ], help = DESCRIPTIONS_INSTALL_GEM)
	install_gem_parser.set_defaults(handler = handle_install_gem_command)
	install_gem_parser.add_argument("repository", metavar="<url>", help = DESCRIPTIONS_INSTALL_REPOSITORY)

	install_project_parser = install_subparsers.add_parser(CliSubCommands.PROJECT.value, parents = [ global_parser, install_revision_parser ], help = DESCRIPTIONS_INSTALL_PROJECT)
	install_project_parser.set_defaults(handler = handle_install_project_command)
	install_project_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_INSTALL_PROJECT_CONFIG)
	install_project_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PATH), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_INSTALL_PROJECT_PATH)
	install_project_parser.add_argument(print_option(LongOptions.VARIANT), dest = "variant_name", default = O3DE_DEFAULT_VARIANT.value, metavar = "<variant>", help = DESCRIPTIONS_INSTALL_PROJECT_VARIANT)
	install_project_parser.add_argument("repository", nargs = "?", default = None, metavar="<url>", help = DESCRIPTIONS_INSTALL_REPOSITORY)

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
	uninstall_engine_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "engine_config_name", default = None, metavar = "<config>", help = DESCRIPTIONS_UNINSTALL_ENGINE_CONFIG)
	uninstall_engine_parser.add_argument(print_option(ShortOptions.FORCE), print_option(LongOptions.FORCE), action = "store_true", help = DESCRIPTIONS_UNINSTALL_ENGINE_FORCE)
	uninstall_engine_parser.add_argument("engine_version", metavar="version", help = DESCRIPTIONS_UNINSTALL_ENGINE_VERSION)
	uninstall_engine_parser.add_argument(print_option(LongOptions.VARIANT), dest = "engine_variant_name", default = None, metavar = "<variant>", help = DESCRIPTIONS_UNINSTALL_ENGINE_VARIANT)

	uninstall_gem_parser = uninstall_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser ], help = DESCRIPTIONS_UNINSTALL_GEM)
	uninstall_gem_parser.set_defaults(handler = handle_uninstall_gem_command)
	uninstall_gem_parser.add_argument("gem_version", metavar="version", help = DESCRIPTIONS_UNINSTALL_GEM_VERSION)

	upgrade_parser = subparsers.add_parser(CliCommands.UPGRADE.value, help = DESCRIPTIONS_UPGRADE)
	upgrade_parser.set_defaults(handler = handle_empty_target)
	upgrade_subparsers = upgrade_parser.add_subparsers()

	upgrade_engine_parser = upgrade_subparsers.add_parser(CliSubCommands.ENGINE.value, parents = [ global_parser ], help = DESCRIPTIONS_UPGRADE_ENGINE)
	upgrade_engine_parser.set_defaults(handler = handle_upgrade_engine_command)
	upgrade_engine_parser.add_argument("engine_version", metavar="version", help = DESCRIPTIONS_UPGRADE_ENGINE_VERSION)
	upgrade_engine_parser.add_argument(print_option(LongOptions.SKIP_BUILD), dest = "rebuild", action = "store_false", help = DESCRIPTIONS_UPGRADE_ENGINE_SKIP_REBUILD)

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
	add_gem_parser.add_argument(print_option(LongOptions.SKIP_BUILD), dest = "rebuild", action = "store_false", help = DESCRIPTIONS_ADD_GEM_SKIP_REBUILD)
	add_gem_parser.add_argument("gem_value", metavar="reference", help = DESCRIPTIONS_ADD_GEM_REFERENCE)

	build_parser = subparsers.add_parser(CliCommands.BUILD.value, parents = [ global_parser ], help = DESCRIPTIONS_BUILD)
	build_parser.set_defaults(handler = handle_build_command)
	build_common_parser = argparse.ArgumentParser(add_help = False)
	build_common_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_BUILD_CONFIG)
	build_common_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_BUILD_PROJECT)
	build_binaries_parser = argparse.ArgumentParser(add_help = False)
	build_binaries_parser.add_argument(print_option(LongOptions.VARIANT), dest = "variant_name", default = O3DE_DEFAULT_VARIANT.value, metavar = "<variant>", help = DESCRIPTIONS_BUILD_VARIANT)
	build_subparsers = build_parser.add_subparsers()

	build_assets_parser = build_subparsers.add_parser(CliSubCommands.ASSETS.value, parents = [ global_parser, build_common_parser ], help = DESCRIPTIONS_BUILD_ASSETS)
	build_assets_parser.set_defaults(binary_name = CliSubCommands.ASSETS.value, variant_name = O3DE_DEFAULT_VARIANT.value)

	build_client_parser = build_subparsers.add_parser(O3DE_ProjectBinaries.CLIENT.value, parents = [ global_parser, build_common_parser, build_binaries_parser ], help = DESCRIPTIONS_BUILD_CLIENT)
	build_client_parser.set_defaults(binary_name = O3DE_ProjectBinaries.CLIENT.value)

	build_server_parser = build_subparsers.add_parser(O3DE_ProjectBinaries.SERVER.value, parents = [ global_parser, build_common_parser, build_binaries_parser ], help = DESCRIPTIONS_BUILD_SERVER)
	build_server_parser.set_defaults(binary_name = O3DE_ProjectBinaries.SERVER.value)

	build_tools_parser = build_subparsers.add_parser(O3DE_ProjectBinaries.TOOLS.value, parents = [ global_parser, build_common_parser ], help = DESCRIPTIONS_BUILD_TOOLS)
	build_tools_parser.set_defaults(binary_name = O3DE_ProjectBinaries.TOOLS.value, variant_name = O3DE_DEFAULT_VARIANT.value)

	clean_parser = subparsers.add_parser(CliCommands.CLEAN.value, parents = [ global_parser ], help = DESCRIPTIONS_CLEAN)
	clean_parser.set_defaults(handler = handle_clean_command)
	clean_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_CLEAN_PROJECT)
	clean_parser.add_argument(print_option(LongOptions.BUILD), dest = "remove_build", action = "store_true", help = DESCRIPTIONS_CLEAN_BUILD)
	clean_parser.add_argument(print_option(LongOptions.CACHE), dest = "remove_cache", action = "store_true", help = DESCRIPTIONS_CLEAN_CACHE)
	clean_parser.add_argument(print_option(LongOptions.VARIANT), dest = "variant_name", default = None, metavar = "<variant>", help = DESCRIPTIONS_CLEAN_VARIANT)

	clean_group = clean_parser.add_mutually_exclusive_group()
	clean_group.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_CLEAN_CONFIG)
	clean_group.add_argument(print_option(ShortOptions.FORCE), print_option(LongOptions.FORCE), action = "store_true", help = DESCRIPTIONS_CLEAN_FORCE)

	export_parser = subparsers.add_parser(CliCommands.EXPORT.value, help = DESCRIPTIONS_EXPORT)
	export_parser.set_defaults(handler = handle_empty_command)
	export_common_parser = argparse.ArgumentParser(add_help = False)
	export_common_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_EXPORT_PROJECT)
	export_binaries_parser = argparse.ArgumentParser(add_help = False)
	export_binaries_parser.add_argument(print_option(LongOptions.ALIAS), dest = "output_name", metavar="<string>", help = DESCRIPTIONS_EXPORT_ALIAS)
	export_binaries_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "config_name", default = O3DE_Configs.RELEASE.value, metavar = "<config>", help = DESCRIPTIONS_EXPORT_CONFIG)
	export_binaries_parser.add_argument(print_option(ShortOptions.TYPE), print_option(LongOptions.TYPE), dest = "output_type_name", default = None, metavar = "<type>", help = DESCRIPTIONS_EXPORT_TYPE)
	export_binaries_parser.add_argument(print_option(LongOptions.SKIP_BUILD), dest = "build_source", action = "store_false", help = DESCRIPTIONS_EXPORT_SKIP_BUILD_SOURCE)
	export_binaries_parser.add_argument(print_option(LongOptions.SKIP_PROCESS), dest = "process_assets", action = "store_false", help = DESCRIPTIONS_EXPORT_SKIP_PROCESS_ASSETS)
	export_binaries_parser.add_argument(print_option(LongOptions.VARIANT), dest = "variant_name", default = O3DE_Variants.MONOLITHIC.value, metavar = "<variant>", help = DESCRIPTIONS_EXPORT_VARIANT)
	export_subparsers = export_parser.add_subparsers()
	
	export_group = export_binaries_parser.add_mutually_exclusive_group()
	export_group.add_argument(print_option(LongOptions.BUNDLE), dest = "bundle_names", action = "append", metavar = "<pak>", help = DESCRIPTIONS_EXPORT_BUNDLES)
	export_group.add_argument(print_option(ShortOptions.LEVEL), print_option(LongOptions.LEVEL), dest = "level_names", action = "append", metavar = "<level>", help = DESCRIPTIONS_EXPORT_LEVELS)

	export_assets_parser = export_subparsers.add_parser(CliSubCommands.ASSETS.value, parents = [ global_parser, export_common_parser ], help = DESCRIPTIONS_EXPORT_ASSETS)
	export_assets_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_EXPORT_CONFIG)
	export_assets_parser.set_defaults(handler = handle_export_assets_command)

	export_client_parser = export_subparsers.add_parser(O3DE_ProjectBinaries.CLIENT.value, parents = [ global_parser, export_common_parser, export_binaries_parser ], help = DESCRIPTIONS_EXPORT_CLIENT)
	export_client_parser.set_defaults(handler = handle_export_binary_command, binary_name = O3DE_ProjectBinaries.CLIENT.value)

	export_server_parser = export_subparsers.add_parser(O3DE_ProjectBinaries.SERVER.value, parents = [ global_parser, export_common_parser, export_binaries_parser ], help = DESCRIPTIONS_EXPORT_SERVER)
	export_server_parser.set_defaults(handler = handle_export_binary_command, binary_name = O3DE_ProjectBinaries.SERVER.value)

	init_parser = subparsers.add_parser(CliCommands.INIT.value, help = DESCRIPTIONS_INIT)
	init_parser.set_defaults(handler = handle_empty_target)
	init_common_parser = argparse.ArgumentParser(add_help = False)
	init_common_parser.add_argument(print_option(LongOptions.ALIAS), dest = "alias", metavar = "<name>", help = DESCRIPTIONS_INIT_ALIAS)
	init_common_parser.add_argument(print_option(ShortOptions.ENGINE), print_option(LongOptions.ENGINE), dest = "engine_version", default = O3DE_DEFAULT_VERSION, metavar = "<version>", help = DESCRIPTIONS_INIT_ENGINE)
	init_common_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PATH), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_INIT_PATH)
	init_subparsers = init_parser.add_subparsers()

	init_gem_parser = init_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser, init_common_parser ], help = DESCRIPTIONS_INIT_GEM)
	init_gem_parser.set_defaults(handler = handle_init_gem_command)
	init_gem_parser.add_argument(print_option(ShortOptions.TYPE), print_option(LongOptions.TYPE), dest = "gem_type", default = O3DE_GemTypes.CODE_AND_ASSETS.value, metavar = "<type>", help = DESCRIPTIONS_INIT_GEM_TYPE)
	init_gem_parser.add_argument(print_option(LongOptions.SKIP_EXAMPLES), dest = "has_examples", action = "store_false", help = DESCRIPTIONS_INIT_GEM_SKIP_EXAMPLES)

	init_project_parser = init_subparsers.add_parser(CliSubCommands.PROJECT.value, parents = [ global_parser, init_common_parser ], help = DESCRIPTIONS_INIT_PROJECT)
	init_project_parser.add_argument(print_option(LongOptions.MINIMAL_PROJECT), dest = "is_minimal_project", action = "store_true", help = DESCRIPTIONS_INIT_PROJECT_MINIMAL)
	init_project_parser.set_defaults(handler = handle_init_project_command)

	open_parser = subparsers.add_parser(CliCommands.OPEN.value, help = DESCRIPTIONS_OPEN)
	open_parser.set_defaults(handler = handle_empty_target)
	open_common_parser = argparse.ArgumentParser(add_help = False)
	open_common_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_OPEN_PROJECT)
	open_subparsers = open_parser.add_subparsers()

	open_editor_parser = open_subparsers.add_parser(O3DE_EngineBinaries.EDITOR.value, parents = [ global_parser, open_common_parser ], help = DESCRIPTIONS_OPEN_EDITOR)
	open_editor_parser.set_defaults(handler = handle_open_editor_command)
	open_editor_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "engine_config_name", default = None, metavar = "<config>", help = DESCRIPTIONS_OPEN_EDITOR_CONFIG)
	open_editor_parser.add_argument(print_option(ShortOptions.ENGINE), print_option(LongOptions.ENGINE), dest = "new_engine_version", default = None, metavar = "<version>", help = DESCRIPTIONS_OPEN_EDITOR_ENGINE)

	remove_parser = subparsers.add_parser(CliCommands.REMOVE.value, help = DESCRIPTIONS_REMOVE)
	remove_parser.set_defaults(handler = handle_empty_target)
	remove_common_parser = argparse.ArgumentParser(add_help = False)
	remove_common_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_REMOVE_PROJECT)
	
	remove_subparsers = remove_parser.add_subparsers()
	remove_gem_parser = remove_subparsers.add_parser(CliSubCommands.GEM.value, parents = [ global_parser, remove_common_parser ], help = DESCRIPTIONS_REMOVE_GEM)
	remove_gem_parser.set_defaults(handler = handle_remove_gem_command)
	remove_gem_parser.add_argument(print_option(LongOptions.SKIP_BUILD), dest = "rebuild", action = "store_false", help = DESCRIPTIONS_REMOVE_GEM_SKIP_REBUILD)
	remove_gem_parser.add_argument("gem_value", metavar="reference", help = DESCRIPTIONS_REMOVE_GEM_VERSION)

	run_parser = subparsers.add_parser(CliCommands.RUN.value, parents = [ global_parser ], help = DESCRIPTIONS_RUN)
	run_parser.set_defaults(handler = handle_empty_target)
	run_common_parser = argparse.ArgumentParser(add_help = False)
	run_common_parser.add_argument(print_option(ShortOptions.CONFIG), print_option(LongOptions.CONFIG), dest = "config_name", default = O3DE_DEFAULT_CONFIG.value, metavar = "<config>", help = DESCRIPTIONS_RUN_CONFIG)
	run_common_parser.add_argument(print_option(ShortOptions.CONSOLE_COMMAND), print_option(LongOptions.CONSOLE_COMMAND), dest = "console_commands", action = "append", metavar = "<command>[<arg0>,...]", help = DESCRIPTIONS_RUN_CONSOLE_COMMAND)
	run_common_parser.add_argument(print_option(ShortOptions.CONSOLE_VARIABLE), print_option(LongOptions.CONSOLE_VARIABLE), dest = "console_variables", action = "append", metavar = "<variable>=<value>", help = DESCRIPTIONS_RUN_CONSOLE_VARIABLE)
	run_common_parser.add_argument(print_option(ShortOptions.LEVEL), print_option(LongOptions.LEVEL), dest = "level_name", metavar = "<level>", help = DESCRIPTIONS_RUN_LEVEL)
	run_common_parser.add_argument(print_option(ShortOptions.PROJECT), print_option(LongOptions.PROJECT), dest = "project_path", metavar = "<path>", help = DESCRIPTIONS_RUN_PROJECT)
	run_common_parser.add_argument(print_option(LongOptions.VARIANT), dest = "variant_name", default = O3DE_DEFAULT_VARIANT.value, metavar = "<variant>", help = DESCRIPTIONS_RUN_VARIANT)
	run_subparsers = run_parser.add_subparsers()

	run_client_parser = run_subparsers.add_parser(O3DE_ProjectBinaries.CLIENT.value, parents = [ global_parser, run_common_parser ], help = DESCRIPTIONS_RUN_CLIENT)
	run_client_parser.set_defaults(handler = handle_run_command, binary_name = O3DE_ProjectBinaries.CLIENT.value, listen_on_port = None)
	run_client_parser.add_argument(print_option(LongOptions.CONNECT_TO), dest = "connect_to_server", nargs = "?", default = False, metavar = "<ip>:<port>", help = DESCRIPTIONS_RUN_CLIENT_CONNECT)

	run_server_parser = run_subparsers.add_parser(O3DE_ProjectBinaries.SERVER.value, parents = [ global_parser, run_common_parser ], help = DESCRIPTIONS_RUN_SERVER)
	run_server_parser.set_defaults(handler = handle_run_command, binary_name = O3DE_ProjectBinaries.SERVER.value, connect_to_server = False)
	run_server_parser.add_argument(print_option(LongOptions.LISTEN_ON), dest = "listen_on_port", metavar = "<port>", help = DESCRIPTIONS_RUN_SERVER_LISTEN)

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
			elif help_subcommand == CliSubCommands.PROJECT.value:
				help_parser = install_project_parser
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
			if help_subcommand is None:
				help_parser = build_parser
			elif help_subcommand == CliSubCommands.ASSETS.value:
				help_parser = build_assets_parser
			elif help_subcommand == O3DE_ProjectBinaries.CLIENT.value:
				help_parser = build_client_parser
			elif help_subcommand == O3DE_ProjectBinaries.SERVER.value:
				help_parser = build_server_parser
			elif help_subcommand == O3DE_ProjectBinaries.TOOLS.value:
				help_parser = build_tools_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.CLEAN.value:
			help_parser = clean_parser
		elif help_command == CliCommands.EXPORT.value:
			if help_subcommand is None:
				help_parser = export_parser
			elif help_subcommand == CliSubCommands.ASSETS.value:
				help_parser = export_assets_parser
			elif help_subcommand == O3DE_ProjectBinaries.CLIENT.value:
				help_parser = export_client_parser
			elif help_subcommand == O3DE_ProjectBinaries.SERVER.value:
				help_parser = export_server_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
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
			if help_subcommand is None:
				help_parser = open_parser
			elif help_subcommand == O3DE_EngineBinaries.EDITOR.value:
				help_parser = open_editor_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.REMOVE.value:
			if help_subcommand is None:
				help_parser = remove_parser
			elif help_subcommand == CliSubCommands.GEM.value:
				help_parser = remove_gem_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
		elif help_command == CliCommands.RUN.value:
			if help_subcommand is None:
				help_parser = run_parser
			elif help_subcommand == O3DE_ProjectBinaries.CLIENT.value:
				help_parser = run_client_parser
			elif help_subcommand == O3DE_ProjectBinaries.SERVER.value:
				help_parser = run_server_parser
			else:
				throw_error(Messages.INVALID_SUBCOMMAND, help_command, help_subcommand)
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
