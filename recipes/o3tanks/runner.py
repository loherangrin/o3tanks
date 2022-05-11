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
import random
import socket
import subprocess
import time
import typing


# --- CONSTANTS ---

DEFAULT_ASSET_PROCESSOR_LISTENING_PORT = 45643
DEFAULT_SERVER_PORT = 33450

MIN_VALID_EXECUTION_TIME = 15 #sec
MAX_NEW_PORT_ATTEMPTS = 10

# --- TYPES ---

class InstanceAddress(typing.NamedTuple):
	ip: str
	port: int


# --- SUBFUNCTIONS ---

def clear_instance(binary):
	lock_file = O3DE_PROJECT_SOURCE_DIR / get_instance_lock_path(binary)
	if lock_file.is_file():
		lock_file.unlink()


def discover_instance(binary):
	lock_file = O3DE_PROJECT_SOURCE_DIR / get_instance_lock_path(binary)
	if not lock_file.is_file():
		return None

	instance_ip = read_json_property(lock_file, InstanceProperties.IP.value)
	instance_port = read_json_property(lock_file, InstanceProperties.PORT.value)
	if (instance_ip is None) or (instance_port is None):
		throw_error(Messages.INVALID_INSTANCE_FILE, str(lock_file))

	return InstanceAddress(instance_ip, instance_port)


def get_default_instance_port(binary):
	if binary is O3DE_EngineBinaries.ASSET_PROCESSOR:
		return DEFAULT_ASSET_PROCESSOR_LISTENING_PORT
	elif binary is O3DE_ProjectBinaries.SERVER:
		return DEFAULT_SERVER_PORT
	else:
		throw_error(Messages.INVALID_BINARY, binary)


def get_engine_binary(engine_config, engine_workflow, binary_name):
	if engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
		engine_build_dir = get_build_path(O3DE_ENGINE_BUILDS_DIR, O3DE_Variants.NON_MONOLITHIC)
		binary_dir = get_build_bin_path(engine_build_dir, engine_config)
	elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		binary_dir = get_install_bin_path(O3DE_ENGINE_INSTALL_DIR, engine_config, O3DE_Variants.NON_MONOLITHIC)
	elif engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE:
		project_build_dir = get_build_path(O3DE_PROJECT_BUILDS_DIR, O3DE_Variants.NON_MONOLITHIC)
		binary_dir = get_build_bin_path(project_build_dir, engine_config)
	else:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow)

	return (binary_dir / get_binary_filename(binary_name))


def get_instance_lock_path(binary):
	if binary is O3DE_EngineBinaries.ASSET_PROCESSOR:
		return ASSET_PROCESSOR_LOCK_PATH
	elif binary is O3DE_ProjectBinaries.SERVER:
		return SERVER_LOCK_PATH
	else:
		throw_error(Messages.INVALID_BINARY, binary)


def get_project_binary(engine_config, engine_variant, engine_workflow, binary_name):
	if engine_workflow is O3DE_BuildWorkflows.ENGINE_CENTRIC:
		engine_build_dir = get_build_path(O3DE_ENGINE_BUILDS_DIR, engine_variant)
		binary_dir = get_build_bin_path(engine_build_dir, engine_config)

	elif engine_workflow in [ O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK, O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE ]:
		project_build_dir = get_build_path(O3DE_PROJECT_BUILDS_DIR, engine_variant)
		binary_dir = get_build_bin_path(project_build_dir, engine_config)

	else:
		throw_error(Messages.INVALID_BUILD_WORKFLOW, engine_workflow)

	return (binary_dir / get_binary_filename(binary_name))


def register_instance(binary, port, randomize_if_exists):
	lock_file = O3DE_PROJECT_SOURCE_DIR / get_instance_lock_path(binary)

	hostname = socket.gethostname()

	try:
		ip = socket.gethostbyname(hostname)
	except Exception as e:
		ip = "127.0.0.1"

	is_free = False
	for i in range(MAX_NEW_PORT_ATTEMPTS):
		test_port = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			test_port.connect(("127.0.0.1", port))

			if not randomize_if_exists:
				return None

			port = port + random.randint(1, 99)

		except:
			is_free = True
			break

		finally:
			test_port.close()
	
	if not is_free:
		throw_error(Messages.EXCEED_MAX_PORT_ATTEMPTS, MAX_NEW_PORT_ATTEMPTS)

	write_json_property(lock_file, InstanceProperties.HOSTNAME.value, hostname)
	write_json_property(lock_file, InstanceProperties.IP.value, ip)
	write_json_property(lock_file, InstanceProperties.PORT.value, port)

	return InstanceAddress(ip, port)


def run_binary(engine_workflow, binary_file, options = {}, arguments = [], rendering = False, wait = True):
	command = [ str(binary_file) ]

	if rendering and (GPU_DRIVER_NAME is None):
		command.append("--rhi=null")

	for option_name, option_value in options.items():
		if option_value is not None:
			command.append("--{}={}".format(option_name, option_value))
		else:
			command.append("--{}".format(option_name))

	if rendering and (GPU_DRIVER_NAME is None):
		command.append("-NullRenderer")

	for argument in arguments:
		command.append(argument)

	command = " ".join(command)
	if wait:
		result = subprocess.run(command, shell = True)
		return result
	else:
		handler = subprocess.Popen(command, shell = True)
		return handler


# --- FUNCTIONS (PROJECT) ---

def open_project(binary, config, force, arguments_and_options = None):
	if binary is O3DE_EngineBinaries.ASSET_BUNDLER:
		binary_name = "AssetBundler"
		if DISPLAY_ID < 0:
			binary_name = binary_name + "Batch"
			force = False

	elif binary is O3DE_EngineBinaries.ASSET_PROCESSOR:
		binary_name = "AssetProcessor"
		if DISPLAY_ID < 0:
			binary_name = binary_name + "Batch"
			force = False

	elif binary is O3DE_EngineBinaries.EDITOR:
		binary_name = "Editor"

	else:
		throw_error(Messages.INVALID_BINARY, binary.value)

	engine_variant = O3DE_Variants.NON_MONOLITHIC
	engine_build_dir = get_build_path(O3DE_ENGINE_BUILDS_DIR, engine_variant)
	engine_workflow = get_build_workflow(O3DE_ENGINE_SOURCE_DIR, engine_build_dir, O3DE_ENGINE_INSTALL_DIR)
	binary_file = get_engine_binary(config, engine_workflow, binary_name)
	if not binary_file.is_file():
		throw_error(Messages.MISSING_BINARY, str(binary_file), config.value, engine_variant.value, "")

	asset_processor = discover_instance(O3DE_EngineBinaries.ASSET_PROCESSOR)
	if binary is O3DE_EngineBinaries.ASSET_PROCESSOR:
		if (asset_processor is not None) and not force:
			throw_error(Messages.ASSET_PROCESSOR_ALREADY_RUNNING, str(ASSET_PROCESSOR_LOCK_PATH))

		asset_processor = register_instance(binary, DEFAULT_ASSET_PROCESSOR_LISTENING_PORT, True)
		old_gems = register_gems(O3DE_CLI_FILE, O3DE_PROJECT_SOURCE_DIR, O3DE_GEMS_DIR, O3DE_GEMS_EXTERNAL_DIR, show_unmanaged = True)

	elif binary is not O3DE_EngineBinaries.ASSET_BUNDLER:
		if asset_processor is None:
			throw_error(Messages.MISSING_ASSET_PROCESSOR)

	if engine_workflow is O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK:
		engine_dir = O3DE_ENGINE_INSTALL_DIR
	else:
		engine_dir = O3DE_ENGINE_SOURCE_DIR

	arguments = []
	options = {
		"engine-path": engine_dir,
		"project-path": O3DE_PROJECT_SOURCE_DIR,
		"regset=/Amazon/AzCore/Bootstrap/project_path": O3DE_PROJECT_SOURCE_DIR,
		"regset=/Amazon/AzCore/Bootstrap/engine_path": engine_dir
	}

	if binary is not O3DE_EngineBinaries.ASSET_BUNDLER:
		options["regset=/Amazon/AzCore/Bootstrap/remote_ip"] = asset_processor.ip
		options["regset=/Amazon/AzCore/Bootstrap/remote_port"] = asset_processor.port

	if binary is O3DE_EngineBinaries.ASSET_PROCESSOR:
		if NETWORK_SUBNET is not None:
			options["regset=/Amazon/AzCore/Bootstrap/allowed_list"] = NETWORK_SUBNET

	if arguments_and_options is not None:
		for value in arguments_and_options:
			arguments.append(value)

	result = run_binary(
		engine_workflow, binary_file,
		arguments = arguments,
		options = options,
		rendering = True if (binary is O3DE_EngineBinaries.EDITOR) else False,
		wait = True
	)

	if binary is O3DE_EngineBinaries.ASSET_PROCESSOR:
		clear_registered_gems(O3DE_PROJECT_SOURCE_DIR, old_gems)
		clear_instance(binary)

	exit_code = result.returncode
	if exit_code != 0:
		if (DISPLAY_ID >= 0) and (exit_code == -6):
			print_msg(Level.ERROR, Messages.UNREACHABLE_X11_DISPLAY, DISPLAY_ID, REAL_USER.uid)
		else:
			print_msg(Level.ERROR, Messages.BINARY_ERROR, binary_file)

	exit(exit_code)


def run_project(binary, config, variant, console_commands, console_variables):
	project_name = read_json_property(O3DE_PROJECT_SOURCE_DIR / "project.json", JsonPropertyKey(None, None, "project_name"))
	if project_name is None:
		throw_error(Messages.INVALID_PROJECT_NAME)

	if binary is O3DE_ProjectBinaries.CLIENT:
		binary_name = "GameLauncher"
		console_file_name = "client"
	elif binary is O3DE_ProjectBinaries.SERVER:
		binary_name = "ServerLauncher"
		console_file_name = "server"
	else:
		throw_error(Messages.INVALID_BINARY, binary.value)

	engine_build_dir = get_build_path(O3DE_ENGINE_BUILDS_DIR, variant)
	engine_workflow = get_build_workflow(O3DE_ENGINE_SOURCE_DIR, engine_build_dir, O3DE_ENGINE_INSTALL_DIR)
	binary_file = get_project_binary(config, variant, engine_workflow, "{}.{}".format(project_name, binary_name))
	if not binary_file.is_file():
		throw_error(Messages.MISSING_BINARY, str(binary_file), config.value, variant.value, binary.value)

	asset_processor = discover_instance(O3DE_EngineBinaries.ASSET_PROCESSOR)
	if asset_processor is None and not config is O3DE_Configs.RELEASE:
		throw_error(Messages.MISSING_ASSET_PROCESSOR)

	if binary is O3DE_ProjectBinaries.SERVER:
		port_value = console_variables.get(O3DE_ConsoleVariables.NETWORK_SERVER_LISTENING_PORT.value)
		if port_value is not None:
			try:
				server_port = int(port_value)
				randomize_port_if_used = False
			except:
				throw_error(Messages.INVALID_SERVER_PORT, port_value)

		else:
			server_port = DEFAULT_SERVER_PORT
			randomize_port_if_used = True

		server = register_instance(binary, server_port, randomize_port_if_used)
		if server is None:
			throw_error(Messages.SERVER_PORT_ALREADY_USED, server_port)

		console_variables[O3DE_ConsoleVariables.NETWORK_SERVER_LISTENING_PORT.value] = str(server.port)

	options = {}
	arguments = []

	if asset_processor is not None:
		options["regset=/Amazon/AzCore/Bootstrap/remote_ip"] = asset_processor.ip
		options["regset=/Amazon/AzCore/Bootstrap/remote_port"] = asset_processor.port

	for variable_name, variable_value in console_variables.items():
		arguments.append("+{}".format(variable_name))
		arguments.append(variable_value)

	for command in console_commands:
		matches = parse_console_command(command)
		if matches is None:
			throw_error(Messages.INVALID_CONSOLE_COMMAND, command)

		command_name = matches.group(1)
		arguments.append("+{}".format(command_name))

		command_arguments = matches.group(2)
		if command_arguments is not None:
			command_arguments = command_arguments.split(',')

			for command_argument in command_arguments:
				arguments.append(command_argument)

	console_file = O3DE_PROJECT_SOURCE_DIR / "{}.cfg".format(console_file_name)
	if console_file.is_file():
		n_commands = len(console_commands)
		n_variables = len(console_variables)

		if n_commands == 0 and n_variables == 0:
			options["console-command-file"] = console_file.name

		elif (
			(binary is O3DE_ProjectBinaries.SERVER and
				(n_commands == 0) and
				(n_variables == 1 and O3DE_ConsoleVariables.NETWORK_SERVER_LISTENING_PORT.value in console_variables)
			) or
			(binary is O3DE_ProjectBinaries.CLIENT and
				(n_commands == 0) and
				(n_variables == 2 and O3DE_ConsoleVariables.NETWORK_CLIENT_REMOTE_IP.value in console_variables and O3DE_ConsoleVariables.NETWORK_CLIENT_REMOTE_PORT.value in console_variables)
			)
		):
			arguments.append("+exec {}".format(console_file.name))

		else:
			print_msg(Level.WARNING, Messages.CONSOLE_FILE_NOT_LOADED, console_file.name)

	start_time = time.time()
	result = run_binary(engine_workflow, binary_file, options = options, arguments = arguments, rendering = True, wait = True)
	execution_time = time.time() - start_time

	exit_code = result.returncode
	if exit_code != 0:
		if (DISPLAY_ID >= 0) and (exit_code == -6):
			print_msg(Level.ERROR, Messages.UNREACHABLE_X11_DISPLAY, DISPLAY_ID, REAL_USER.uid)

		elif (exit_code == 134) and (execution_time < MIN_VALID_EXECUTION_TIME):
			result = run_binary(engine_workflow, binary_file, options = options, arguments = arguments, rendering = True, wait = True)
			exit_code = result.returncode

			if exit_code != 0:
				print_msg(Level.ERROR, Messages.BINARY_ERROR, binary_file)

		else:
			print_msg(Level.ERROR, Messages.BINARY_ERROR, binary_file)

	if binary is O3DE_ProjectBinaries.SERVER:
		clear_instance(binary)

	exit(exit_code)


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
		binary = deserialize_arg(2, O3DE_EngineBinaries)
		config = deserialize_arg(3, O3DE_Configs)
		force = deserialize_arg(4, bool) if len(sys.argv) > 4 else False

		if len(sys.argv) > 5:
			index = 5
			arguments_and_options = deserialize_args(index, list, str)
		else:
			arguments_and_options = []

		open_project(binary, config, force, arguments_and_options)

	elif command == RunnerCommands.RUN:
		binary = deserialize_arg(2, O3DE_ProjectBinaries)
		config = deserialize_arg(3, O3DE_Configs)
		variant = deserialize_arg(4, O3DE_Variants)

		index = 5
		console_commands = deserialize_args(index, list, str)

		index += len(console_commands) + 1
		console_variables = deserialize_args(index, dict, str)

		run_project(binary, config, variant, console_commands, console_variables)

	else:
		throw_error(Messages.INVALID_COMMAND, command.value)


if __name__ == "__main__":
	main()
