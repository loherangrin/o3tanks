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


def generate_configurations(source_dir, build_dir):
	common_options = [
		"-B", str(build_dir),
		"-S", str(source_dir),
		"-DLY_UNITY_BUILD=ON",
		"-DLY_3RDPARTY_PATH={}".format(O3DE_PACKAGES_DIR)
	]

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

def build_engine(engine_config, binaries):
	if not O3DE_ENGINE_BUILD_DIR.exists() or is_directory_empty(O3DE_ENGINE_BUILD_DIR):
		generate_engine_configurations()

	options = [
		"--build", str(O3DE_ENGINE_BUILD_DIR),
		"--config", engine_config.value,
		"--target", ', '.join(binaries) if (binaries is not None) else "install"
	]

	if OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		options.append("--")
		options.append("/m")

	result = execute_cmake(options)
	if result.returncode != 0:
		return result.returncode

	if binaries is None:
		required_paths = [ (pathlib.PurePath("python") / "runtime") ]

		for path in required_paths:
			from_path = O3DE_ENGINE_SOURCE_DIR / path
			to_path = O3DE_ENGINE_INSTALL_DIR / path
			
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

	if engine_config is not None:
		if remove_build:
			build_config_dir = get_build_config_path(O3DE_ENGINE_BUILD_DIR, engine_config)
			clean_dirs.append(build_config_dir)

		if remove_install:
			install_config_dir = get_install_config_path(O3DE_ENGINE_INSTALL_DIR, engine_config)
			clean_dirs.append(install_config_dir)

	else:
		if remove_build:
			clean_dirs.append(O3DE_ENGINE_BUILD_DIR)

		if remove_install:
			clean_dirs.append(O3DE_ENGINE_INSTALL_DIR)

	for clean_dir in clean_dirs:
		clear_directory(clean_dir)


def generate_engine_configurations():
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

	generated = generate_configurations(O3DE_ENGINE_SOURCE_DIR, O3DE_ENGINE_BUILD_DIR)
	if not generated:
		throw_error(Messages.UNCOMPLETED_SOLUTION_GENERATION)


# --- FUNCTIONS (PROJECT) ---

def build_project(config, binary):
	if is_directory_empty(O3DE_PROJECT_SOURCE_DIR):
		throw_error(Messages.PROJECT_DIR_EMPTY)

	if binary is None:
		target_name = "Editor"

	else:
		if binary == O3DE_ProjectBinaries.CLIENT:
			target_name = "GameLauncher"

		elif binary == O3DE_ProjectBinaries.SERVER:
			target_name = "ServerLauncher"

		else:
			throw_error(Messages.INVALID_BINARY, binary.value)

		project_name = read_json_property(O3DE_PROJECT_SOURCE_DIR / "project.json", JsonPropertyKey(None, None, "project_name"))
		if project_name is None:
			throw_error(Messages.INVALID_PROJECT_NAME)

		target_name = "{}.{}".format(project_name, target_name)

	try:
		subprocess.run([ O3DE_CLI_FILE, "register", "--this-engine" ], stdout = subprocess.DEVNULL, check = True)
		subprocess.run([ O3DE_CLI_FILE, "register", "--project-path", str(O3DE_PROJECT_SOURCE_DIR) ], stdout = subprocess.DEVNULL, check = True)

	except FileNotFoundError as error:
		if error.filename == O3DE_CLI_FILE.name or (OPERATING_SYSTEM.family is OSFamilies.WINDOWS and error.filename is None):
			throw_error(Messages.CORRUPTED_ENGINE_SOURCE, error.filename)
		else:
			raise error

	except subprocess.CalledProcessError as error:
		throw_error(Messages.UNCOMPLETED_REGISTRATION, error.returncode, "\n{}\n{}".format(error.stdout, error.stderr))

	if not O3DE_PROJECT_BUILD_DIR.is_dir() or is_directory_empty(O3DE_PROJECT_BUILD_DIR):
		generated = generate_configurations(O3DE_PROJECT_SOURCE_DIR, O3DE_PROJECT_BUILD_DIR)
		if not generated:
			throw_error(Messages.UNCOMPLETED_SOLUTION_GENERATION)

	options = [
		"--build", str(O3DE_PROJECT_BUILD_DIR),
		"--config", config.value,
		"--target", target_name
	]

	if OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		options.append("--")
		options.append("/m")

	result = execute_cmake(options)

	if result.returncode == 0:
		delete_openssl_files(O3DE_PROJECT_BUILD_DIR, config)

	return result.returncode


def check_project_settings():
	project_extra_dir = O3DE_PROJECT_SOURCE_DIR / PROJECT_EXTRA_PATH
	if not project_extra_dir.exists():
		project_extra_dir.mkdir(parents = True)
	elif not project_extra_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY)

	private_project_extra_dir = O3DE_PROJECT_SOURCE_DIR / PRIVATE_PROJECT_EXTRA_PATH
	if not private_project_extra_dir.exists():
		private_project_extra_dir.mkdir(parents = True)
	elif not private_project_extra_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY)

	public_project_extra_dir = O3DE_PROJECT_SOURCE_DIR / PUBLIC_PROJECT_EXTRA_PATH
	if not public_project_extra_dir.exists():
		public_project_extra_dir.mkdir(parents = True)
	elif not public_project_extra_dir.is_dir():
		throw_error(Messages.INVALID_DIRECTORY)

	gitignore_file = project_extra_dir / ".gitignore"
	if not gitignore_file.exists():
		private_name = private_project_extra_dir.name
		
		gitignore_file.write_text(private_name + '/')


def clean_project(config, force):
	if force:
		clear_directory(O3DE_PROJECT_BUILD_DIR)
	else:
		try:
			subprocess.run([ O3DE_CLI_FILE, "register", "--this-engine" ], stdout = subprocess.DEVNULL, check = True)
			subprocess.run([ O3DE_CLI_FILE, "register", "--project-path", str(O3DE_PROJECT_SOURCE_DIR) ], stdout = subprocess.DEVNULL, check = True)

		except FileNotFoundError as error:
			if error.filename == O3DE_CLI_FILE.name or (OPERATING_SYSTEM.family is OSFamilies.WINDOWS and error.filename is None):
				throw_error(Messages.CORRUPTED_ENGINE_SOURCE, error.filename)
			else:
				raise error

		except subprocess.CalledProcessError as error:
			throw_error(Messages.UNCOMPLETED_REGISTRATION, error.returncode, "\n{}\n{}".format(error.stdout, error.stderr))

		result = execute_cmake([
			"--build", str(O3DE_PROJECT_BUILD_DIR),
			"--config", config.value,
			"--target", "clean"
		])

		return result.returncode


def generate_project_configurations(project_name, engine_version):
	if not is_directory_empty(O3DE_PROJECT_SOURCE_DIR):
		throw_error(Messages.PROJECT_DIR_NOT_EMPTY)

	try:
		result = subprocess.run([
				O3DE_CLI_FILE, "create-project",
				"--project-name", project_name,
				"--project-path", O3DE_PROJECT_SOURCE_DIR
			])

	except FileNotFoundError as error:
		if error.filename == O3DE_CLI_FILE.name or (OPERATING_SYSTEM.family is OSFamilies.WINDOWS and error.filename is None):
			throw_error(Messages.CORRUPTED_ENGINE_SOURCE, error.filename)
		else:
			raise error

	if result.returncode != 0:
		throw_error(Messages.UNCOMPLETED_INIT_PROJECT)

	write_project_setting(Settings.ENGINE.value, None, None, engine_version)


def read_project_setting(setting_section, setting_index, setting_name):
	project_extra_dir = O3DE_PROJECT_SOURCE_DIR / PROJECT_EXTRA_PATH
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

	n_expected_setting_keys = len(expected_setting_keys)
	if n_expected_setting_keys == 0:
		throw_error(Messages.INVALID_SETTING_SECTION, setting_section)
	elif n_expected_setting_keys == 1:
		settings_file = select_project_settings_file(O3DE_PROJECT_SOURCE_DIR, setting_key)

		setting_value = read_json_property(settings_file, setting_key)
		if setting_value is None:
			setting_value = ''

		print_msg(Level.INFO, setting_value)
	else:
		setting_values = read_project_setting_values(O3DE_PROJECT_SOURCE_DIR, setting_key.section, setting_key.index)

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


def write_project_setting(setting_section, setting_index, setting_name, setting_value, show_preview = False):
	setting_key = get_setting_key(setting_section, setting_index, setting_name)
	current_setting_values = read_project_setting_values(O3DE_PROJECT_SOURCE_DIR, setting_key.section, setting_key.index)

	changed_settings = {}
	if setting_key.name is not None:
		new_setting_values = { setting_key.name: setting_value }
	else:
		if setting_key.section is None:
			throw_error(Messages.MISSING_SETTING_KEY)
		elif setting_key.section == Settings.ENGINE.value:
			if setting_value is not None:
				result_type, repository = get_engine_repository_from_source(O3DE_ENGINE_SOURCE_DIR)
				if result_type is not RepositoryResultType.OK:
					throw_error(Messages.INVALID_REPOSITORY)
			else:
				repository = Repository(None, None, None)

			new_setting_values = {
				EngineSettings.VERSION.value.name: setting_value,
				EngineSettings.REPOSITORY.value.name: repository.url,
				EngineSettings.BRANCH.value.name: repository.branch,
				EngineSettings.REVISION.value.name: repository.revision
			}

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
			settings_file = select_project_settings_file(O3DE_PROJECT_SOURCE_DIR, new_setting_key)

			if settings_file not in changed_settings:
				changed_settings[settings_file] = {}
			changed_settings[settings_file][new_setting_key] = (current_setting_value, new_setting_value)

	else:
		for section, section_values in current_setting_values.items():
			for index, index_values in enumerate(section_values):
				for name, current_setting_value in index_values.items():
					new_setting_key = JsonPropertyKey(section, index, name)
					settings_file = select_project_settings_file(O3DE_PROJECT_SOURCE_DIR, new_setting_key)

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

	check_project_settings()

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

	if setting_value is not None:
		return

	purge_index = setting_key.index
	while True:
		written_setting_values = read_project_setting_values(O3DE_PROJECT_SOURCE_DIR, setting_key.section, None)
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
				O3DE_PROJECT_SOURCE_DIR / PRIVATE_PROJECT_SETTINGS_PATH,
				O3DE_PROJECT_SOURCE_DIR / PUBLIC_PROJECT_SETTINGS_PATH
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
			binaries = deserialize_args(4) if len(sys.argv) > 4 else None

			exit_code = build_engine(config, binaries)
			if exit_code != 0:
				exit(exit_code)

		elif target == Targets.PROJECT:
			binary = deserialize_arg(4, O3DE_ProjectBinaries) if len(sys.argv) > 4 else None

			exit_code = build_project(config, binary)
			if exit_code != 0:
				exit(exit_code)

		else:
			throw_error(Messages.INVALID_TARGET, target.value)

	elif command == BuilderCommands.CLEAN:
		if target == Targets.ENGINE:
			binaries = deserialize_args(4) if len(sys.argv) > 4 else None
			
			config = deserialize_arg(3, O3DE_Configs)
			remove_build = deserialize_arg(4, bool)
			remove_install = deserialize_arg(5, bool)

			exit_code = clean_engine(config, remove_build, remove_install)
			if exit_code != 0:
				exit(exit_code)

		elif target == Targets.PROJECT:
			config = deserialize_arg(3, O3DE_Configs)
			force= deserialize_arg(4, bool)
			
			exit_code = clean_project(config, force)
			if exit_code != 0:
				exit(exit_code)
			
		else:
			throw_error(Messages.INVALID_TARGET, target.value)

	elif command == BuilderCommands.INIT:
		if target == Targets.ENGINE:
			generate_engine_configurations()

		elif target == Targets.PROJECT:
			project_name = deserialize_arg(3, str)
			engine_version = deserialize_arg(4, str)

			generate_project_configurations(project_name, engine_version)

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
				write_project_setting(setting_section, setting_index, setting_name, None, False)
			elif setting_value is None:
				read_project_setting(setting_section, setting_index, setting_name)
			else:
				preview = deserialize_arg(8, bool)
				if preview is None:
					preview = False

				write_project_setting(setting_section, setting_index, setting_name, setting_value, preview)

		else:
			throw_error(Messages.INVALID_TARGET, target.value)

	else:
		throw_error(Messages.INVALID_COMMAND, command.value)


if __name__ == "__main__":
	main()
