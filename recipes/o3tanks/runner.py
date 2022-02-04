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
import time


# -- SUBFUNCTIONS ---

def get_engine_binary(engine_config, engine_workflow, binary_name):
	if engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
		binary_dir = get_build_config_path(O3DE_ENGINE_BUILD_DIR, engine_config)
	elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		binary_dir = get_install_config_path(O3DE_ENGINE_INSTALL_DIR, engine_config)
	elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
		binary_dir = get_build_config_path(O3DE_PROJECT_BUILD_DIR, engine_config)
	else:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow)

	return (binary_dir / get_binary_filename(binary_name))


def get_project_binary(engine_config, engine_workflow, binary_name):
	if engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
		binary_dir = get_build_config_path(O3DE_ENGINE_BUILD_DIR, engine_config)
	elif engine_workflow in [ O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK, O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE ]:
		binary_dir = get_build_config_path(O3DE_PROJECT_BUILD_DIR, engine_config)
	else:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow)

	return (binary_dir / get_binary_filename(binary_name))


def run_asset_processor(engine_config, engine_workflow):
	asset_processor_file = get_engine_binary(engine_config, engine_workflow, "AssetProcessor")
	if not asset_processor_file.is_file():
		throw_error(Messages.MISSING_BINARY, str(asset_processor_file), engine_config.value, "")

	asset_processor = run_binary(engine_workflow, asset_processor_file, rendering = False, wait = False)

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


def run_binary(engine_workflow, binary_file, rendering = False, wait = True):
	if engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		engine_dir = O3DE_ENGINE_INSTALL_DIR
	else:
		engine_dir = O3DE_ENGINE_SOURCE_DIR

	command = [
		binary_file,
		"--engine-path={}".format(engine_dir),
		"--project-path={}".format(O3DE_PROJECT_SOURCE_DIR),
		"--regset=/Amazon/AzCore/Bootstrap/engine_path={}".format(engine_dir),
		"--regset=/Amazon/AzCore/Bootstrap/project_path={}".format(O3DE_PROJECT_SOURCE_DIR)
	]

	if rendering and (GPU_DRIVER_NAME is None):
		command.append("--rhi=null")

	if wait:
		result = subprocess.run(command)
		return result
	else:
		handler = subprocess.Popen(command)
		return handler


# --- FUNCTIONS (PROJECT) ---

def open_project(config):
	engine_workflow = get_build_workflow(O3DE_ENGINE_SOURCE_DIR, O3DE_ENGINE_BUILD_DIR, O3DE_ENGINE_INSTALL_DIR)
	binary_file = get_engine_binary(config, engine_workflow, "Editor")
	if not binary_file.is_file():
		throw_error(Messages.MISSING_BINARY, str(binary_file), config.value, "")

	old_gems = register_gems(O3DE_CLI_FILE, O3DE_PROJECT_SOURCE_DIR, O3DE_GEMS_DIR, O3DE_GEMS_EXTERNAL_DIR, show_unmanaged = True)

	asset_processor = run_asset_processor(config, engine_workflow)

	result = run_binary(engine_workflow, binary_file, rendering = True, wait = True)

	if asset_processor is not None:
		if result.returncode == 0:
			asset_processor.terminate()
		else:
			asset_processor.wait()

	clear_registered_gems(O3DE_PROJECT_SOURCE_DIR, old_gems)

	exit(result.returncode)


def run_project(binary, config):
	project_name = read_json_property(O3DE_PROJECT_SOURCE_DIR / "project.json", JsonPropertyKey(None, None, "project_name"))
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

	engine_workflow = get_build_workflow(O3DE_ENGINE_SOURCE_DIR, O3DE_ENGINE_BUILD_DIR, O3DE_ENGINE_INSTALL_DIR)
	binary_file = get_project_binary(config, engine_workflow, "{}.{}".format(project_name, binary_name))
	if not binary_file.is_file():
		throw_error(Messages.MISSING_BINARY, str(binary_file), config.value, binary.value)

	old_gems = register_gems(O3DE_CLI_FILE, O3DE_PROJECT_SOURCE_DIR, O3DE_GEMS_DIR, O3DE_GEMS_EXTERNAL_DIR, show_unmanaged = True)

	result = run_binary(engine_workflow, binary_file, rendering = True, wait = True)
	error_code = result.returncode
	if has_gui and (error_code == -6):
		throw_error(Messages.UNREACHABLE_X11_DISPLAY, DISPLAY_ID, REAL_USER.uid)

	clear_registered_gems(O3DE_PROJECT_SOURCE_DIR, old_gems)

	exit(result.returncode)


# --- MAIN ---

def main():
	if DEVELOPMENT_MODE:
		print_msg(Level.WARNING, Messages.IS_DEVELOPMENT_MODE)

		if not RUN_CONTAINERS:
			print_msg(Level.WARNING, Messages.IS_NO_CONTAINERS_MODE)

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
