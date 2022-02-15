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


from .globals.o3de import *
from .globals.o3tanks import *
from .utils.filesystem import *
from .utils.input_output import *
from .utils.serialization import *
from .utils.subfunctions import *
from .utils.types import *
import subprocess


# -- SUBFUNCTIONS ---

def delete_openssl_files(build_dir, config):
	build_config_dir = get_build_config_path(build_dir, config)
	openssl_files = [ 
		"libcrypto.so",
		"libcrypto.so.1.1",
		"libssl.so",
		"libssl.so.1.1"
	]

	openssl_directories = [
		build_config_dir,
		build_config_dir / "AWSCoreEditorQtBin",
		build_config_dir / "EditorPlugins"
	]

	for directory in openssl_directories:
		for file in openssl_files:
			library = directory / file
			if library.exists():
				library.unlink()


def search_clang_binaries():
	supported_versions = [ "12", "11", "6.0", None ]

	for version in supported_versions:
		suffix = "-{}".format(version) if version is not None else ""
		clang_bin = "clang{}".format(suffix)
		clang_cpp_bin = "clang++{}".format(suffix)

		try:
			subprocess.run([ clang_bin, "--version" ], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL, check = True)
			subprocess.run([ clang_cpp_bin, "--version" ], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL, check = True)

			return [ clang_bin, clang_cpp_bin ]

		except:
			pass

	return [ None, None ]


def generate_configurations(engine_workflow, is_engine):
	if is_engine:
		source_dir = O3DE_ENGINE_SOURCE_DIR
		build_dir = O3DE_ENGINE_BUILD_DIR
	else:
		source_dir = O3DE_PROJECT_SOURCE_DIR
		build_dir = O3DE_PROJECT_BUILD_DIR

	common_options = [
		"-B", str(build_dir),
		"-S", str(source_dir),
		"-DLY_UNITY_BUILD=ON",
		"-DLY_3RDPARTY_PATH={}".format(O3DE_PACKAGES_DIR)
	]

	is_project_centric = (engine_workflow is not O3DE_BuildWorkflows.ENGINE_CENTRIC)
	if is_project_centric:
		common_options.append("-DLY_DISABLE_TEST_MODULES=TRUE")
	
		if not is_engine:			
			common_options.append("-DCMAKE_MODULE_PATH={}/cmake".format(
				O3DE_ENGINE_SOURCE_DIR if (engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE) else O3DE_ENGINE_INSTALL_DIR
			))

		elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
			return True
	else:
		common_options.append("-DLY_PROJECTS=AutomatedTesting")

	if OPERATING_SYSTEM.family is OSFamilies.LINUX:
		clang_bin, clang_cpp_bin = search_clang_binaries()

		if (clang_bin is None) or (clang_cpp_bin is None):
			throw_error(Messages.MISSING_CLANG)

		os_options = [
			"-G", "Ninja Multi-Config",
			"-DCMAKE_C_COMPILER={}".format(clang_bin),
			"-DCMAKE_CXX_COMPILER={}".format(clang_cpp_bin)
		]

	elif OPERATING_SYSTEM.family is OSFamilies.MAC:
		os_options = [
			"-G", "XCode"
		]

	elif OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		os_options = [
			"-G", "Visual Studio 16 2019"
		]
	
	else:
		throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM.family)

	all_options = common_options + os_options
	result = execute_cmake(all_options)

	return (result is not None and result.returncode == 0)


def get_setting_key(setting_section, setting_index, setting_name = None):
	if setting_section is None:
		return JsonPropertyKey(None, None, None)

	section = Settings.from_value(setting_section)
	if section is None:
		throw_error(Messages.INVALID_SETTING_SECTION, setting_section)

	if setting_name is not None:
		if section is Settings.ENGINE:
			section = EngineSettings
		elif section is Settings.GEMS:
			section = GemSettings
		else:
			throw_error(Messages.INVALID_SETTING_SECTION, setting_section)

		index = -1 if setting_index is not None else setting_index

		if not section.has_value(JsonPropertyKey(setting_section, index, setting_name)):
			throw_error(Messages.INVALID_SETTING_NAME, setting_name)

	setting_key = JsonPropertyKey(setting_section, setting_index, setting_name)
	return setting_key


def execute_cmake(arguments):
	cmake_file = "cmake"

	try:
		result = subprocess.run([ cmake_file ] + arguments)

	except FileNotFoundError as error:
		if error.filename == cmake_file or (OPERATING_SYSTEM.family is OSFamilies.WINDOWS and error.filename is None):
			throw_error(Messages.MISSING_CMAKE)
		else:
			raise error

	return result


# --- FUNCTIONS (ENGINE) ---

def build_engine(engine_workflow, engine_config):
	if engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
		return True
	elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		targets = [ "install" ]
	elif engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
		targets = [ "Editor", "AutomatedTesting.GameLauncher" ]
	else:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow)

	if not O3DE_ENGINE_BUILD_DIR.exists() or is_directory_empty(O3DE_ENGINE_BUILD_DIR):
		generate_engine_configurations(engine_workflow)

	options = [
		"--build", str(O3DE_ENGINE_BUILD_DIR),
		"--config", engine_config.value,
		"--target", *targets
	]

	if OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		options.append("--")
		options.append("/m")

	result = execute_cmake(options)
	if result.returncode != 0:
		return result.returncode

	if engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		required_paths = [ (pathlib.PurePath("python") / "runtime") ]

		for path in required_paths:
			from_path = O3DE_ENGINE_SOURCE_DIR / path
			to_path = O3DE_ENGINE_INSTALL_DIR / path
			
			if to_path.exists() and not is_directory_empty(to_path):
				continue

			copy_all(from_path, to_path)

	current_ap_config_file = O3DE_ENGINE_SOURCE_DIR / "Registry" / "AssetProcessorPlatformConfig.setreg"
	current_ap_buffer = []
	new_ap_config_file = current_ap_config_file.with_suffix(".setreg.tmp")
	new_ap_handler = None

	with current_ap_config_file.open('r') as current_ap_handler:
		while True:
			line = current_ap_handler.readline()
			if len(line) == 0:
				break

			elif '"pattern": ".*/[Uu]ser/.*"' in line:
				current_ap_buffer.append('                    "pattern": "{}/[Uu]ser/.*"\n'.format(str(O3DE_ENGINE_SOURCE_DIR)))
				current_ap_buffer.append('                },\n')
				current_ap_buffer.append('                "Exclude User2": {\n')
				current_ap_buffer.append('                    "pattern": "{}/[Uu]ser/.*"\n'.format(str(O3DE_PROJECT_SOURCE_DIR)))

				new_ap_handler = new_ap_config_file.open('w')
				new_ap_handler.writelines(current_ap_buffer)
				break

			else:
				current_ap_buffer.append(line)

		if new_ap_handler is not None:
			while True:
				line = current_ap_handler.readline()
				if len(line) == 0:
					break

				new_ap_handler.write(line)

			new_ap_handler.close()

	if new_ap_handler is not None:
		current_ap_config_file.unlink()
		new_ap_config_file.rename(current_ap_config_file)

	delete_openssl_files(O3DE_ENGINE_BUILD_DIR, engine_config)

	return result.returncode


def clean_engine(engine_config, remove_build, remove_install):
	clean_dirs = []

	has_other_build_config = False
	has_other_install_config = False

	if engine_config is not None:
		if remove_build:
			for other_config in O3DE_Configs:
				if other_config is engine_config:
					continue

				if has_build_config(O3DE_ENGINE_BUILD_DIR, other_config):
					has_other_build_config = True
					break

			if has_other_build_config:
				build_config_dir = get_build_config_path(O3DE_ENGINE_BUILD_DIR, engine_config)
				clean_dirs.append(build_config_dir)

		if remove_install:
			for other_config in O3DE_Configs:
				if other_config is engine_config:
					continue

				if has_install_config(O3DE_ENGINE_INSTALL_DIR, other_config):
					has_other_install_config = True
					break

			if has_other_install_config:
				install_config_dir = get_install_config_path(O3DE_ENGINE_INSTALL_DIR, engine_config)
				clean_dirs.append(install_config_dir)

	if remove_build and not has_other_build_config:
		clean_dirs.append(O3DE_ENGINE_BUILD_DIR)

	if remove_install and not has_other_install_config:
		clean_dirs.append(O3DE_ENGINE_INSTALL_DIR)

	for clean_dir in clean_dirs:
		clear_directory(clean_dir)


def generate_engine_configurations(engine_workflow):
	get_python_file = get_script_filename("get_python")

	try:
		result = subprocess.run([ O3DE_ENGINE_SOURCE_DIR / "python" / get_python_file ])

	except FileNotFoundError as error:
		if error.filename == get_python_file or (OPERATING_SYSTEM.family is OSFamilies.WINDOWS and error.filename is None):
			throw_error(Messages.CORRUPTED_ENGINE_SOURCE, error.filename)
		else:
			raise error

	if result.returncode != 0:
		throw_error(Messages.UNCOMPLETED_REGISTRATION, result.returncode, "\n{}\n{}".format(result.stdout, result.stderr))

	generated = generate_configurations(engine_workflow, True)
	if not generated:
		throw_error(Messages.UNCOMPLETED_SOLUTION_GENERATION)


# --- FUNCTIONS (GEM) ---

def generate_gem(gem_name, base_template, has_examples, engine_version, gem_dir = O3DE_PROJECT_SOURCE_DIR):
	if not is_directory_empty(gem_dir):
		throw_error(Messages.PROJECT_DIR_NOT_EMPTY)

	if has_examples:
		example_project_dir = gem_dir / WORKSPACE_GEM_EXAMPLE_PATH
		gem_dir /= WORKSPACE_GEM_SOURCE_PATH
	else:
		example_project_dir = None

	try:
		result = subprocess.run([
				O3DE_CLI_FILE, "create-gem",
				"--gem-name", gem_name,
				"--gem-path", str(gem_dir),
				"--template-name", base_template,
				"--force",
				"--no-register"
			])

	except FileNotFoundError as error:
		if error.filename == O3DE_CLI_FILE.name or (OPERATING_SYSTEM.family is OSFamilies.WINDOWS and error.filename is None):
			throw_error(Messages.CORRUPTED_ENGINE_SOURCE, error.filename)
		else:
			raise error

	if result.returncode != 0:
		throw_error(Messages.UNCOMPLETED_INIT_GEM)

	if example_project_dir is not None:
		example_project_name = "{}Examples".format(gem_name)
		if not example_project_dir.exists():
			example_project_dir.mkdir(parents = True)

		generate_project(example_project_name, O3DE_ProjectTemplates.STANDARD.value, engine_version, example_project_dir)
		change_gem_status(example_project_dir, GemReference(GemReferenceTypes.PATH, gem_dir), True)

		relative_gem_path = "../{}".format(WORKSPACE_GEM_SOURCE_PATH)
		write_project_setting(example_project_dir, GemSettings.RELATIVE_PATH.value.section, GemSettings.RELATIVE_PATH.value.index, GemSettings.RELATIVE_PATH.value.name, relative_gem_path)
		write_json_property(get_project_manifest_file(example_project_dir), JsonPropertyKey("external_subdirectories", None, None), [ relative_gem_path ])

		workspace_dir = example_project_dir.parent
		workspace_manifest_file = workspace_dir / "repo.json"
		if workspace_manifest_file.exists():
			throw_error(Messages.WORKSPACE_MANIFEST_ALREADY_EXISTS)

		(workspace_dir / WORKSPACE_GEM_DOCUMENTATION_PATH).mkdir(parents = True)

		with workspace_manifest_file.open('wt') as file_handler:
			workspace_manifest = {
				"gems": [
					str(gem_dir.relative_to(workspace_dir))
				],
				"projects": [
					str(example_project_dir.relative_to(workspace_dir))
				]
			}

			json.dump(workspace_manifest, file_handler, indent = 4, sort_keys = True)

		with (workspace_dir / "README.md").open('wt') as file_handler:
			file_handler.writelines([
				"# {}\n".format(gem_name),
				"<YOUR_GEM_DESCRIPTION>\n",
				"\n",
				"# Install\n",
				"Please choose one of the following options to install this gem in your O3DE (Open 3D Engine) projects:\n",
				"\n",
				"## Automatic installation (recommended)\n",
				"Following steps require to install **O3Tanks**, a version manager for O3DE to streamline the development workflow. You can find additional information at the [official site](https://github.com/loherangrin/o3tanks/).\n",
				"```\n",
				"o3tanks install gem https://<this_repository_url>.git --as <any_name>\n",
				"o3tanks add gem <any_name> --project <project_path>\n",
				"```\n",
				"\n",
				"## Manual installation\n",
				"1. Clone this repository into a directory of your choice:\n",
				"```\n",
				"git clone https://<this_repository_url>.git <gem_dir>\n",
				"```\n",
				"2. Register the gem into your engine:\n",
				"```\n",
				"<o3de_dir>/scripts/o3de register --gem-path <gem_dir>\n",
				"```\n",
				"3. Open the O3DE project manager:\n",
				"```\n",
				"<o3de_dir>/build/bin/<config>/o3de\n",
				"```\n",
				"4. Select your project, press *Configure gems...* and then search in the gems list for *{}*.\n",
				"5. Press the toggle widget to activate this gem.\n".format(gem_name),
				"6. Re-build the project using the project manager or the terminal, according to your platform.\n",
				"\n",
				"# Usage\n",
				"<YOUR_INSTRUCTIONS>\n",
				"\n",
				"# Examples\n",
				"A sample project is contained in the `/examples/` directory. It shows how to setup the gem and its basic usage.\n",
				"<YOUR_ADDITIONAL_DESCRIPTION>\n",
				"\n",
				"# License\n",
				"<YOUR_LEGAL_INFO>\n"
			])


def change_gem_status(project_dir, gem_reference, active):
	if gem_reference.type is GemReferenceTypes.ENGINE:
		cli_option_name = "--gem-name"
		cli_option_value = gem_reference.value
	else:
		cli_option_name = "--gem-path"

		if gem_reference.type is GemReferenceTypes.VERSION:
			gem_dir = search_gem_path(O3DE_GEMS_DIR, gem_reference.value)

		elif gem_reference.type is GemReferenceTypes.PATH:
			gem_dir = gem_reference.value
			if not gem_dir.is_absolute():
				gem_dir = (project_dir / gem_dir).resolve()

		else:
			throw_error(Messages.INVALID_GEM_REFERENCE, gem_reference)

		if not is_gem(gem_dir):
			throw_error(Messages.INVALID_GEM_SOURCE, gem_dir)

		cli_option_value = str(gem_dir)

	if not is_project(project_dir):
		throw_error(Messages.PROJECT_NOT_FOUND, project_dir)

	action = "enable-gem" if active else "disable-gem"
	try:
		result = subprocess.run([
			O3DE_CLI_FILE, action,
			cli_option_name, cli_option_value,
			"--project-path", str(project_dir)
		])

	except FileNotFoundError as error:
		if error.filename == O3DE_CLI_FILE.name or (OPERATING_SYSTEM.family is OSFamilies.WINDOWS and error.filename is None):
			throw_error(Messages.CORRUPTED_ENGINE_SOURCE, error.filename)
		else:
			raise error

	if result.returncode != 0:
		throw_error(Messages.UNCOMPLETED_REGISTRATION, result.returncode, "\n{}\n{}".format(result.stdout, result.stderr))


# --- FUNCTIONS (PROJECT) ---

def build_project(config, binary, regenerate_solution = False):
	if is_directory_empty(O3DE_PROJECT_SOURCE_DIR):
		throw_error(Messages.PROJECT_DIR_EMPTY)

	if regenerate_solution or (not O3DE_PROJECT_BUILD_DIR.is_dir() or is_directory_empty(O3DE_PROJECT_BUILD_DIR)):
		engine_workflow = get_build_workflow(O3DE_ENGINE_SOURCE_DIR, O3DE_ENGINE_BUILD_DIR, O3DE_ENGINE_INSTALL_DIR)
		if engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
			throw_error(Messages.INCOMPATIBLE_BUILD_PROJECT_AND_WORKFLOW, engine_workflow.value)

		old_gems = register_gems(O3DE_CLI_FILE, O3DE_PROJECT_SOURCE_DIR, O3DE_GEMS_DIR, O3DE_GEMS_EXTERNAL_DIR, show_unmanaged = True)

		generated = generate_configurations(engine_workflow, False)
		if not generated:
			clear_registered_gems(O3DE_PROJECT_SOURCE_DIR, old_gems)
			throw_error(Messages.UNCOMPLETED_SOLUTION_GENERATION)
	else:
		old_gems = register_gems(O3DE_CLI_FILE, O3DE_PROJECT_SOURCE_DIR, O3DE_GEMS_DIR, O3DE_GEMS_EXTERNAL_DIR, show_unmanaged = True)

	options = [
		"--build", str(O3DE_PROJECT_BUILD_DIR),
		"--config", config.value
	]

	if binary is None:
		target_name = None
	elif binary is O3DE_ProjectBinaries.TOOLS:
		target_name = "Editor"
	else:
		if binary is O3DE_ProjectBinaries.CLIENT:
			target_name = "GameLauncher"

		elif binary is O3DE_ProjectBinaries.SERVER:
			target_name = "ServerLauncher"

		else:
			throw_error(Messages.INVALID_BINARY, binary.value)

		project_manifest = get_project_manifest_file(O3DE_PROJECT_SOURCE_DIR)
		project_name = read_json_property(project_manifest, JsonPropertyKey(None, None, "project_name"))
		if project_name is None:
			clear_registered_gems(O3DE_PROJECT_SOURCE_DIR, old_gems)
			throw_error(Messages.INVALID_PROJECT_NAME)

		target_name = "{}.{}".format(project_name, target_name)

	if target_name is not None:
		options.append("--target")
		options.append(target_name)

	if OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		options.append("--")
		options.append("/m")

	result = execute_cmake(options)

	if result.returncode == 0:
		delete_openssl_files(O3DE_PROJECT_BUILD_DIR, config)

	clear_registered_gems(O3DE_PROJECT_SOURCE_DIR, old_gems)

	return result.returncode


def check_project_settings(project_dir):
	project_extra_dir = project_dir / PROJECT_EXTRA_PATH
	if not project_extra_dir.exists():
		project_extra_dir.mkdir(parents = True)
	elif not project_extra_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY)

	private_project_extra_dir = project_dir / PRIVATE_PROJECT_EXTRA_PATH
	if not private_project_extra_dir.exists():
		private_project_extra_dir.mkdir(parents = True)
	elif not private_project_extra_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY)

	public_project_extra_dir = project_dir / PUBLIC_PROJECT_EXTRA_PATH
	if not public_project_extra_dir.exists():
		public_project_extra_dir.mkdir(parents = True)
	elif not public_project_extra_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY)

	gitignore_file = project_extra_dir / ".gitignore"
	if not gitignore_file.exists():
		private_name = private_project_extra_dir.name
		
		gitignore_file.write_text(private_name + '/')


def clean_project(config, remove_build, remove_cache, force):
	exit_code = 0

	if remove_build:
		if force:
			clear_directory(O3DE_PROJECT_BUILD_DIR)
		else:
			result = execute_cmake([
				"--build", str(O3DE_PROJECT_BUILD_DIR),
				"--config", config.value,
				"--target", "clean"
			])
			exit_code = result.returncode

	if remove_cache:
		clear_directory(O3DE_PROJECT_CACHE_DIR, not force)
		clear_directory(O3DE_PROJECT_USER_DIR, not force)

	return exit_code


def generate_project(project_name, base_template, engine_version, project_dir = O3DE_PROJECT_SOURCE_DIR):
	if not is_directory_empty(project_dir):
		throw_error(Messages.PROJECT_DIR_NOT_EMPTY)

	try:
		result = subprocess.run([
				O3DE_CLI_FILE, "create-project",
				"--project-name", project_name,
				"--project-path", project_dir,
				"--template-name", base_template
			])

	except FileNotFoundError as error:
		if error.filename == O3DE_CLI_FILE.name or (OPERATING_SYSTEM.family is OSFamilies.WINDOWS and error.filename is None):
			throw_error(Messages.CORRUPTED_ENGINE_SOURCE, error.filename)
		else:
			raise error

	if result.returncode != 0:
		throw_error(Messages.UNCOMPLETED_INIT_PROJECT)

	if engine_version is not None:
		write_project_setting(project_dir, Settings.ENGINE.value, None, None, engine_version)


def read_project_setting(project_dir, setting_section, setting_index, setting_name):
	project_extra_dir = project_dir / PROJECT_EXTRA_PATH
	if not project_extra_dir.is_dir():
		throw_error(Messages.SETTINGS_NOT_FOUND)

	setting_key = get_setting_key(setting_section, setting_index, setting_name)

	expected_setting_keys = []
	if setting_key.is_single():
		expected_setting_keys.append(setting_key)
	else:
		if (setting_key.section == Settings.ENGINE.value) or (setting_key.section is None):
			for key in EngineSettings:
				expected_setting_keys.append(key.value)

		if (setting_key.section == Settings.GEMS.value) or (setting_key.section is None):
			for key in GemSettings:
				expected_setting_keys.append(key.value)		

	n_expected_setting_keys = len(expected_setting_keys)
	if n_expected_setting_keys == 0:
		throw_error(Messages.INVALID_SETTING_SECTION, setting_section)
	elif n_expected_setting_keys == 1:
		settings_file = select_project_settings_file(project_dir, setting_key)

		setting_value = read_json_property(settings_file, setting_key)
		if setting_value is None:
			setting_value = ''

		print_msg(Level.INFO, setting_value)
	else:
		setting_values = read_project_setting_values(project_dir, setting_key.section, setting_key.index)

		output = {}
		for expected_setting_key in expected_setting_keys:
			section_values = setting_values.get(expected_setting_key.section)
			if section_values is None:
				section_values = {}

			if expected_setting_key.is_any() and setting_key.is_all():
				for index, index_values in enumerate(section_values):
					name_value = index_values.get(expected_setting_key.name)
					if name_value is None:
						name_value = ''

					key = JsonPropertyKey(expected_setting_key.section, index, expected_setting_key.name)
					output[print_setting(key)] = name_value

			else:
				name_value = section_values.get(expected_setting_key.name)
				if name_value is None:
					name_value = ''

				key = JsonPropertyKey(expected_setting_key.section, setting_key.index, expected_setting_key.name)
				output[print_setting(key)] = name_value

		output_keys = list(output.keys())
		output_keys.sort()
		for key in output_keys:
			print_msg(Level.INFO, "{} = {}".format(key, output[key]))


def write_project_setting(project_dir, setting_section, setting_index, setting_name, setting_value, show_preview = False, force = False):
	setting_key = get_setting_key(setting_section, setting_index, setting_name)
	current_setting_values = read_project_setting_values(project_dir, setting_key.section, setting_key.index)


	changed_settings = {}
	if setting_key.name is not None:
		new_setting_values = { setting_key.name: setting_value }
	else:
		if setting_key.section is None:
			throw_error(Messages.MISSING_SETTING_KEY)
		elif setting_key.section == Settings.ENGINE.value:
			if setting_value is not None:
				result_type, repository = get_repository_from_source(O3DE_ENGINE_SOURCE_DIR)
				if result_type is not RepositoryResultType.OK:
					throw_error(Messages.INVALID_REPOSITORY)

				engine_workflow = get_build_workflow(O3DE_ENGINE_SOURCE_DIR, O3DE_ENGINE_BUILD_DIR, O3DE_ENGINE_INSTALL_DIR)
				engine_workflow_value = engine_workflow.value if engine_workflow is not None else None

			else:
				repository = Repository(None, None, None)
				engine_workflow_value = None

			new_setting_values = {
				EngineSettings.VERSION.value.name: setting_value,
				EngineSettings.REPOSITORY.value.name: repository.url,
				EngineSettings.BRANCH.value.name: repository.branch,
				EngineSettings.REVISION.value.name: repository.revision,
				EngineSettings.WORKFLOW.value.name: engine_workflow_value
			}

		elif setting_section == Settings.GEMS.value:
			if setting_value is not None:
				gem_reference = parse_gem_reference(setting_value, False)

				if gem_reference.type is GemReferenceTypes.ENGINE:
					if '/' in gem_reference.value:
						gem_name = gem_reference.value[:-2]
						gem_status = (gem_reference.value[-1] == '1')
					else:
						gem_name = gem_reference.value
						gem_status = True
					change_gem_status(project_dir, GemReference(GemReferenceTypes.ENGINE, gem_name), gem_status)
					return

				elif gem_reference.type is GemReferenceTypes.PATH:
					is_absolute_path = gem_reference.value.is_absolute()
					if is_absolute_path:
						path_property = GemSettings.ABSOLUTE_PATH.value.name
						parent_gem_dir = get_external_gem_path(O3DE_GEMS_EXTERNAL_DIR, gem_reference.value)
					else:
						path_property = GemSettings.RELATIVE_PATH.value.name
						parent_gem_dir = (project_dir / gem_reference.value).resolve()

					gem_dir = search_gem_path(parent_gem_dir)
					if gem_dir is None:
						throw_error(Messages.INVALID_GEM_SOURCE, gem_dir)

					if not is_absolute_path:
						new_setting_value = gem_reference.print()
					else:
						host_gem_dir = gem_reference.value
						if gem_dir != parent_gem_dir:
							host_gem_dir /= gem_dir.relative_to(parent_gem_dir)

						new_setting_value = str(host_gem_dir)

					existing_gems = current_setting_values.get(Settings.GEMS.value)
					if existing_gems is not None:
						for existing_gem in existing_gems:
							existing_gem_path = existing_gem.get(path_property)

							if new_setting_value == existing_gem_path:
								throw_error(Messages.GEM_ALREADY_ADDED)

					new_setting_values = {
						path_property: new_setting_value
					}

					gem_references = [ GemReference(GemReferenceTypes.PATH, gem_dir) ]

				elif gem_reference.type is GemReferenceTypes.VERSION:
					parent_gem_dir = get_gem_path(O3DE_GEMS_DIR, setting_value)
					if not parent_gem_dir.is_dir():
						throw_error(Messages.VERSION_NOT_INSTALLED, setting_value)

					gem_dir = search_gem_path(parent_gem_dir)
					if gem_dir is None:
						throw_error(Messages.INVALID_GEM_SOURCE, parent_gem_dir)

					result_type, repository = get_repository_from_source(parent_gem_dir)
					if result_type is not RepositoryResultType.OK:
						throw_error(Messages.INVALID_REPOSITORY)

					existing_gems = current_setting_values.get(Settings.GEMS.value)
					if existing_gems is not None:
						for existing_gem in existing_gems:
							existing_gem_version = existing_gem.get(GemSettings.VERSION.value.name)
							same_version = (setting_value == existing_gem_version)
							same_repository = (repository.url == existing_gem.get(GemSettings.REPOSITORY.value.name))
							same_branch = (repository.branch == existing_gem.get(GemSettings.BRANCH.value.name))
							same_revision = (repository.revision == existing_gem.get(GemSettings.REVISION.value.name))

							if same_version:
								if same_repository and same_branch and same_revision:
									throw_error(Messages.GEM_ALREADY_ADDED)
								else:
									throw_error(Messages.GEM_DIFFERENT_VALUES, "version name", setting_value, "repository information")

							elif same_repository:
								throw_error(Messages.GEM_DIFFERENT_VALUES, "repository", repository.url, "version name ({})".format(existing_gem_version))

					new_setting_values = {
						GemSettings.VERSION.value.name: setting_value,
						GemSettings.REPOSITORY.value.name: repository.url,
						GemSettings.BRANCH.value.name: repository.branch,
						GemSettings.REVISION.value.name: repository.revision
					}

					gem_references = [ GemReference(GemReferenceTypes.PATH, gem_dir) ]

				else:
					throw_error(Messages.INVALID_GEM_REFERENCE, gem_reference.type)

			else:
				if setting_key.is_all():
					new_setting_values = None
				else:
					new_setting_values = {}
					for property in GemSettings:
						new_setting_values[property.value.name] = None

				section_values = current_setting_values.get(setting_key.section)
				if section_values is None:
					gem_references = None
				else:
					if isinstance(section_values, dict):
						section_values = [ section_values ]

					if force:
						gem_references = None
					else:
						gem_references = []
						for index_values in section_values:
							gem_absolute_path = index_values.get(GemSettings.ABSOLUTE_PATH.value.name)
							if gem_absolute_path is not None:
								parent_gem_dir = get_external_gem_path(O3DE_GEMS_EXTERNAL_DIR, pathlib.Path(gem_absolute_path))
								gem_dir = search_gem_path(parent_gem_dir)

							else:
								gem_version = index_values.get(GemSettings.VERSION.value.name)
								if gem_version is None:
									continue

								gem_dir = search_gem_path(O3DE_GEMS_DIR, gem_version)

							if gem_dir is None:
								throw_error(Messages.INVALID_GEM_SOURCE, gem_dir)

							gem_reference = GemReference(GemReferenceTypes.PATH, gem_dir)
							gem_references.append(gem_reference)

		else:
			throw_error(Messages.INVALID_SETTING_SECTION, setting_section)

	if new_setting_values is not None:
		current_section_values = current_setting_values.get(setting_key.section)
		if setting_key.is_any():
			new_setting_index = len(current_section_values) if isinstance(current_section_values, list) else 0
		else:
			new_setting_index = setting_key.index

		for new_setting_name, new_setting_value in new_setting_values.items():
			if isinstance(current_section_values, list):
				if new_setting_index < len(current_section_values):
					current_index_values = current_section_values[new_setting_index]
				else:
					current_index_values = None
			else:
				current_index_values = current_section_values

			if current_index_values is not None:
				current_setting_value = current_index_values.get(new_setting_name)
			else:
				current_setting_value = None

			if current_setting_value == new_setting_value:
				continue

			new_setting_key = JsonPropertyKey(setting_key.section, new_setting_index, new_setting_name)
			settings_file = select_project_settings_file(project_dir, new_setting_key)

			if settings_file not in changed_settings:
				changed_settings[settings_file] = {}
			changed_settings[settings_file][new_setting_key] = (current_setting_value, new_setting_value)

	else:
		for section, section_values in current_setting_values.items():
			for index, index_values in enumerate(section_values):
				for name, current_setting_value in index_values.items():
					new_setting_key = JsonPropertyKey(section, index, name)
					settings_file = select_project_settings_file(project_dir, new_setting_key)

					if settings_file not in changed_settings:
						changed_settings[settings_file] = {}
					changed_settings[settings_file][new_setting_key] = (current_setting_value, None)

	if len(changed_settings) == 0:
		return True

	if show_preview:
		print_msg(Level.INFO, Messages.CHANGED_SETTINGS)

		for settings_file, file_changes in changed_settings.items():
			for new_setting_key, setting_change in file_changes.items():
				current_setting_value, new_setting_value = setting_change

				print_msg(Level.INFO, "- {}: {} -> {}".format(
					print_setting(new_setting_key),
					(current_setting_value if current_setting_value is not None else "<empty>"),
					(new_setting_value if new_setting_value is not None else "<empty>")
				))

		print_msg(Level.INFO, '')
		if not ask_for_confirmation(Messages.SAVE_QUESTION):
			return False

	check_project_settings(project_dir)

	for settings_file, file_changes in changed_settings.items():
		has_no_value = True

		if len(file_changes) == 1:
			new_setting_key, setting_change = next(iter(file_changes.items()))
			new_setting_values = setting_change[1]

		else:
			first_key = next(iter(file_changes))
			new_setting_key = JsonPropertyKey(first_key.section, first_key.index, None)

			is_multi_values = (setting_key.index is None) and (first_key.index is not None)
			if not is_multi_values:
				new_setting_values = {}
				for key, setting_change in file_changes.items():
					new_setting_values[key.name] = setting_change[1]

			else:
				new_setting_values = []
				for key, setting_change in file_changes.items():
					while key.index >= len(new_setting_values):
						new_setting_values.append({})

					new_setting_values[key.index][key.name] = setting_change[1]

		write_json_property(settings_file, new_setting_key, new_setting_values)

	if (
		setting_key.section == Settings.GEMS.value and
		setting_key.name is None and
		gem_references is not None and
		not force
	):
		gem_active = (setting_value is not None)
		gem_dirs = []
		for gem_reference in gem_references:
			change_gem_status(project_dir, gem_reference, gem_active)

			if gem_reference.type is GemReferenceTypes.PATH:
				gem_dirs.append(gem_reference.print())

		clear_registered_gems(project_dir, None, gem_dirs)

	if setting_value is not None:
		return

	purge_index = setting_key.index
	while True:
		written_setting_values = read_project_setting_values(project_dir, setting_key.section, None)
		if setting_key.section not in written_setting_values:
			break

		has_no_value = True

		section_values = written_setting_values[setting_key.section]
		if isinstance(section_values, dict):
			for name, value in section_values.items():
				if value is not None:
					has_no_value = False

		elif isinstance(section_values, list):
			for index_values in section_values:
				for name, value in index_values.items():
					if value is not None:
						has_no_value = False

		else:
			if section_values is not None:
				has_no_value = False

		if has_no_value:
			settings_files = [
				project_dir / PRIVATE_PROJECT_SETTINGS_PATH,
				project_dir / PUBLIC_PROJECT_SETTINGS_PATH
			]

			for settings_file in settings_files:
				write_json_property(settings_file, JsonPropertyKey(setting_key.section, purge_index, None), None)

		if purge_index is not None:
			purge_index = None
		else:
			break


# --- MAIN ---

def main():
	if DEVELOPMENT_MODE:
		print_msg(Level.WARNING, Messages.IS_DEVELOPMENT_MODE)

		if not RUN_CONTAINERS:
			print_msg(Level.WARNING, Messages.IS_NO_CONTAINERS_MODE)

	if len(sys.argv) < 2:
		throw_error(Messages.EMPTY_COMMAND)

	command = deserialize_arg(1, BuilderCommands)
	target = deserialize_arg(2, Targets)

	if command is None:
		throw_error(Messages.INVALID_COMMAND, sys.argv[1])

	elif target is None:
		throw_error(Messages.INVALID_TARGET, sys.argv[2])

	elif command == BuilderCommands.BUILD:
		config = deserialize_arg(3, O3DE_Configs)
		
		if target == Targets.ENGINE:
			engine_workflow = deserialize_arg(4, O3DE_BuildWorkflows)

			exit_code = build_engine(engine_workflow, config)
			if exit_code != 0:
				exit(exit_code)

		elif target == Targets.PROJECT:
			binary = deserialize_arg(4, O3DE_ProjectBinaries) if len(sys.argv) > 4 else None
			regenerate_solution = deserialize_arg(5, bool) if len(sys.argv) > 5 else False

			exit_code = build_project(config, binary, regenerate_solution)
			if exit_code != 0:
				exit(exit_code)

		else:
			throw_error(Messages.INVALID_TARGET, target.value)

	elif command == BuilderCommands.CLEAN:
		if target == Targets.ENGINE:
			config = deserialize_arg(3, O3DE_Configs)
			remove_build = deserialize_arg(4, bool)
			remove_install = deserialize_arg(5, bool)

			exit_code = clean_engine(config, remove_build, remove_install)
			if exit_code != 0:
				exit(exit_code)

		elif target == Targets.PROJECT:
			config = deserialize_arg(3, O3DE_Configs)
			remove_build = deserialize_arg(4, bool)
			remove_cache = deserialize_arg(5, bool)
			force = deserialize_arg(6, bool)
			
			exit_code = clean_project(config, remove_build, remove_cache, force)
			if exit_code != 0:
				exit(exit_code)
			
		else:
			throw_error(Messages.INVALID_TARGET, target.value)

	elif command == BuilderCommands.INIT:
		if target == Targets.ENGINE:
			engine_workflow = deserialize_arg(3, O3DE_BuildWorkflows)

			generate_engine_configurations(engine_workflow)

		elif target == Targets.GEM:
			gem_name = deserialize_arg(3, str)
			base_template = deserialize_arg(4, str)
			has_examples = deserialize_arg(5, bool)
			engine_version = deserialize_arg(6, str) if has_examples else None

			generate_gem(gem_name, base_template, has_examples, engine_version)

		elif target == Targets.PROJECT:
			project_name = deserialize_arg(3, str)
			base_template = deserialize_arg(4, str)
			engine_version = deserialize_arg(5, str)

			generate_project(project_name, base_template, engine_version)

		else:
			throw_error(Messages.INVALID_TARGET, target.value)

	elif command == BuilderCommands.SETTINGS:
		if target == Targets.PROJECT:
			setting_section = deserialize_arg(3, str)
			setting_index = deserialize_arg(4, int)
			setting_name = deserialize_arg(5, str)
			setting_value = deserialize_arg(6, str)
			clear = deserialize_arg(7, bool)

			if clear:
				force = deserialize_arg(9, bool)
				write_project_setting(O3DE_PROJECT_SOURCE_DIR, setting_section, setting_index, setting_name, None, False, force)
			elif setting_value is None:
				read_project_setting(O3DE_PROJECT_SOURCE_DIR, setting_section, setting_index, setting_name)
			else:
				preview = deserialize_arg(8, bool)
				if preview is None:
					preview = False

				write_project_setting(O3DE_PROJECT_SOURCE_DIR, setting_section, setting_index, setting_name, setting_value, preview, False)

		else:
			throw_error(Messages.INVALID_TARGET, target.value)

	else:
		throw_error(Messages.INVALID_COMMAND, command.value)


if __name__ == "__main__":
	main()
