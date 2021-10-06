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


def get_setting_key(setting_section, setting_name):
	if not Settings.has_value(setting_section):
		throw_error(Messages.INVALID_SETTING_SECTION, setting_section)

	if setting_section == Settings.ENGINE.value:
		section = EngineSettings
	else:
		throw_error(Messages.INVALID_SETTING_SECTION, setting_section)

	setting_key = section.from_value(CfgPropertyKey(setting_section, setting_name))
	if setting_key is None:
		throw_error(Messages.INVALID_SETTING_NAME, setting_name)

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

		project_name = read_json_property(O3DE_PROJECT_SOURCE_DIR / "project.json", "project_name")
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

	write_project_setting(Settings.ENGINE.value, None, engine_version)


def read_project_setting(setting_section, setting_name):
	project_extra_dir = O3DE_PROJECT_SOURCE_DIR / PROJECT_EXTRA_PATH
	if not project_extra_dir.is_dir():
		throw_error(Messages.SETTINGS_NOT_FOUND)

	required_setting_keys = []
	if setting_name is not None:
		setting_key = get_setting_key(setting_section, setting_name)
		required_setting_keys.append(setting_key)

	else:
		if (setting_section == Settings.ENGINE.value) or (setting_section is None):
			for setting_key in EngineSettings:
				required_setting_keys.append(setting_key)

	if len(required_setting_keys) == 0:
		throw_error(Messages.INVALID_SETTING_SECTION, setting_section)

	for setting_key in required_setting_keys:
		settings_file = select_project_settings_file(O3DE_PROJECT_SOURCE_DIR, setting_key)
		setting_value = read_cfg_property(settings_file, setting_key)
		if setting_value is None:
			setting_value = ''

		if setting_name is not None:
			print_msg(Level.INFO, setting_value)
		else:
			print_msg(Level.INFO, "{} = {}".format(print_setting(setting_key), setting_value))


def write_project_setting(setting_section, setting_name, setting_value, show_preview = False):
	new_settings = {}
	if setting_name is not None:
		setting_key = get_setting_key(setting_section, setting_name)
		new_settings[setting_key] = setting_value

	else:
		if setting_section == Settings.ENGINE.value:
			new_settings[EngineSettings.VERSION] = setting_value

			if setting_value is not None:
				result_type, repository = get_engine_repository_from_source(O3DE_ENGINE_SOURCE_DIR)
				if result_type is not RepositoryResultType.OK:
					throw_error(Messages.INVALID_REPOSITORY)
			else:
				repository = Repository(None, None, None)

			new_settings[EngineSettings.REPOSITORY] = repository.url
			new_settings[EngineSettings.BRANCH] = repository.branch
			new_settings[EngineSettings.REVISION] = repository.revision

		else:
			throw_error(Messages.INVALID_SETTING_SECTION, setting_section)

	if len(new_settings) == 0:
		return True

	changed_settings = {}
	for setting_key, new_setting_value in new_settings.items():
		settings_file = select_project_settings_file(O3DE_PROJECT_SOURCE_DIR, setting_key)
		current_setting_value = read_cfg_property(settings_file, setting_key)

		if new_setting_value == current_setting_value:
			continue

		changed_settings[setting_key] = (settings_file, current_setting_value, new_setting_value)

	if len(changed_settings) == 0:
		return True

	if show_preview:
		print_msg(Level.INFO, Messages.CHANGED_SETTINGS)

		for setting_key, change in changed_settings.items():
			settings_file, current_setting_value, new_setting_value = change

			print_msg(Level.INFO, "- {}: {} -> {}".format(
				print_setting(setting_key),
				(current_setting_value if current_setting_value is not None else "<empty>"),
				(new_setting_value if new_setting_value is not None else "<empty>")
			))

		print_msg(Level.INFO, '')
		if not ask_for_confirmation(Messages.SAVE_QUESTION):
			return False

	check_project_settings()

	for setting_key, change in changed_settings.items():
		settings_file, current_setting_value, new_setting_value = change
		write_cfg_property(settings_file, setting_key, new_setting_value)


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
			setting_name = deserialize_arg(4, str)
			setting_value = deserialize_arg(5, str)
			clear = deserialize_arg(6, bool)

			if clear:
				write_project_setting(setting_section, setting_name, None, False)
			elif setting_value is None:
				read_project_setting(setting_section, setting_name)
			else:
				preview = deserialize_arg(7, bool)
				if preview is None:
					preview = False

				write_project_setting(setting_section, setting_name, setting_value, preview)

		else:
			throw_error(Messages.INVALID_TARGET, target.value)

	else:
		throw_error(Messages.INVALID_COMMAND, command.value)


if __name__ == "__main__":
	main()
