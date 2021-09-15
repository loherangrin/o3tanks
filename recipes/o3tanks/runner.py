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
from .utils.types import *
import subprocess
import time


# -- SUBFUNCTIONS ---

def register_project():
	try:
		subprocess.run([ O3DE_CLI_FILE, "register", "--this-engine" ], stdout = subprocess.DEVNULL, check = True)
		subprocess.run([ O3DE_CLI_FILE, "register", "--project-path", O3DE_PROJECT_SOURCE_DIR ], stdout = subprocess.DEVNULL, check = True)

	except subprocess.CalledProcessError as error:
		throw_error(Messages.UNCOMPLETED_REGISTRATION, error.returncode, "\n{}\n{}".format(error.stdout, error.stderr))


def run_asset_processor(config):
	asset_processor_file = O3DE_PROJECT_BIN_DIR / config.value / "AssetProcessor"
	if not asset_processor_file.is_file():
		throw_error(Messages.MISSING_BINARY, str(asset_processor_file), config.value, asset_processor_file.value)

	asset_processor = run_binary(asset_processor_file, False)

	time.sleep(1)
	if asset_processor.poll() is not None:
		error_code = asset_processor.returncode
		if error_code == -6:
			throw_error(Messages.UNREACHABLE_X11_DISPLAY, DISPLAY_ID, REAL_USER.uid)
		else:
			throw_error(Messages.BINARY_ERROR, asset_processor_file)
	else:
		time.sleep(4)

	return asset_processor


def run_binary(binary_file, wait = True):
	command = [
		binary_file,
		"--engine-path={}".format(O3DE_ENGINE_SOURCE_DIR),
		"--project-path={}".format(O3DE_PROJECT_SOURCE_DIR),
		"--regset=/Amazon/AzCore/Bootstrap/engine_path={}".format(O3DE_ENGINE_SOURCE_DIR),
		"--regset=/Amazon/AzCore/Bootstrap/project_path={}".format(O3DE_PROJECT_SOURCE_DIR)
	]

	if wait:
		result = subprocess.run(command)
		return result

	else:
		handler = subprocess.Popen(command)
		return handler


# --- FUNCTIONS (PROJECT) ---

def open_project(config):
	binary_file = O3DE_PROJECT_BIN_DIR / config.value / "Editor"
	if not binary_file.is_file():
		throw_error(Messages.MISSING_BINARY, str(binary_file), config.value, binary_file.value)

	register_project()
	asset_processor = run_asset_processor(config)

	result = run_binary(binary_file)

	if asset_processor is not None:
		if result.returncode == 0:
			asset_processor.terminate()
		else:
			asset_processor.wait()

	exit(result.returncode)


def run_project(binary, config):
	project_name = read_json_property(O3DE_PROJECT_SOURCE_DIR / "project.json", "project_name")
	if project_name is None:
		throw_error(Messages.INVALID_PROJECT_NAME)

	if binary == O3DE_ProjectBinaries.CLIENT:
		binary_name = "GameLauncher"
		has_gui = True
	elif binary == O3DE_ProjectBinaries.SERVER:
		binary_name = "ServerLauncher"
		has_gui = False
	else:
		throw_error(Messages.INVALID_BINARY, binary.value)

	binary_file = O3DE_PROJECT_BIN_DIR / config.value / ("{}.{}".format(project_name, binary_name))	
	if not binary_file.is_file():
		throw_error(Messages.MISSING_BINARY, str(binary_file), config.value, binary.value)

	register_project()

	result = run_binary(binary_file, True)
	error_code = result.returncode
	if has_gui and (error_code == -6):
		throw_error(Messages.UNREACHABLE_X11_DISPLAY, DISPLAY_ID, REAL_USER.uid)

	exit(result.returncode)


# --- MAIN ---

def main():
	if DEVELOPMENT_MODE:
		print_msg(Level.WARNING, Messages.IS_DEVELOPMENT_MODE)

	if len(sys.argv) < 2:
		throw_error(Messages.EMPTY_COMMAND)

	command = deserialize_arg(1, RunnerCommands)

	if command is None:
		throw_error(Messages.INVALID_COMMAND, sys.argv[1])

	elif command == RunnerCommands.OPEN:
		config = deserialize_arg(2, O3DE_Configs)

		open_project(config)

	elif command == RunnerCommands.RUN:
		binary = deserialize_arg(2, O3DE_ProjectBinaries)
		config = deserialize_arg(3, O3DE_Configs)

		run_project(binary, config)

	else:
		throw_error(Messages.INVALID_COMMAND, command.value)


if __name__ == "__main__":
	main()
