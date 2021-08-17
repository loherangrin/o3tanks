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
import subprocess


# --- FUNCTIONS (PROJECT) ---

def open_project():
	throw_error(Messages.UNSUPPORTED_LINUX_EDITOR)


def run_project(binary, config):
	project_name = read_json_property(O3DE_PROJECT_SOURCE_DIR / "project.json", "project_name")
	if project_name is None:
		throw_error(Messages.INVALID_PROJECT_NAME)

	if binary == O3DE_ProjectBinaries.CLIENT:
		binary_name = "GameLauncher"
		throw_error(Messages.UNSUPPORTED_LINUX_CLIENT)
	elif binary == O3DE_ProjectBinaries.SERVER:
		binary_name = "ServerLauncher"
	else:
		throw_error(Messages.INVALID_BINARY, binary.value)

	binary_file = O3DE_PROJECT_BIN_DIR / config.value / ("{}.{}".format(project_name, binary_name))	
	if not binary_file.is_file():
		throw_error(Messages.MISSING_BINARY, str(binary_file), config.value, binary.value)

	try:
		subprocess.run([ O3DE_CLI_FILE, "register", "--this-engine" ], stdout = subprocess.DEVNULL, check = True)
		subprocess.run([ O3DE_CLI_FILE, "register", "--project-path", O3DE_PROJECT_SOURCE_DIR ], stdout = subprocess.DEVNULL, check = True)	

	except subprocess.CalledProcessError as error:
		throw_error(Messages.UNCOMPLETED_REGISTRATION, error.returncode, "\n{}\n{}".format(error.stdout, error.stderr))

	result = subprocess.run([ binary_file ])
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
		open_project()

	elif command == RunnerCommands.RUN:
		binary = deserialize_arg(2, O3DE_ProjectBinaries)
		config = deserialize_arg(3, O3DE_Configs)

		run_project(binary, config)

	else:
		throw_error(Messages.INVALID_COMMAND, command.value)


if __name__ == "__main__":
	main()
