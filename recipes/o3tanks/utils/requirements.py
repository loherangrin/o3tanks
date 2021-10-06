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


from ..globals.o3tanks import GPU_DRIVER_NAME, OPERATING_SYSTEM, RUN_CONTAINERS, GPUDrivers, Images, get_real_bin_file
from .input_output import Level, Messages, print_msg, throw_error
from .types import ObjectEnum, OSFamilies
import subprocess


# --- TYPES ---

class RequirementCommands:
	def __init__(self):
		self.is_default = False
		self.main_system_packages = []
		self.ported_system_packages = []
		self.external_system_packages = {}
		self.application_packages = []
		self.other_commands = []


	def empty(self):
		return (
			len(self.main_system_packages) == 0 and
			len(self.ported_system_packages) == 0 and
			len(self.external_system_packages) == 0 and
			len(self.application_packages) == 0 and
			len(self.other_commands) == 0
		)


class RequirementCategories(ObjectEnum):
	APPLICATION = "python"
	SYSTEM = "system"


class ApplicationPackageSections(ObjectEnum):
	CLI = Images.CLI.value
	UPDATER = Images.UPDATER.value


class SystemPackageSections(ObjectEnum):
	BASE = "base"
	DEVELOPMENT = "development"
	GPU_AMD = "gpu_amd"
	GPU_INTEL = "gpu_intel"
	RUNNER = Images.RUNNER.value
	RUNTIME = "runtime"
	SCRIPTS = "scripts"


# --- FUNCTIONS ---

def solve_unmet_requirements():
	if RUN_CONTAINERS:
		return RequirementCommands()

	all_sections = {
		RequirementCategories.APPLICATION: [ 
			ApplicationPackageSections.UPDATER
		],

		RequirementCategories.SYSTEM: [ 
			SystemPackageSections.BASE,
			SystemPackageSections.SCRIPTS,
			SystemPackageSections.RUNTIME,
			SystemPackageSections.DEVELOPMENT,
			SystemPackageSections.RUNNER
		],
	}

	if GPU_DRIVER_NAME in [ GPUDrivers.AMD_OPEN, GPUDrivers.AMD_PROPRIETARY ]:
		all_sections[RequirementCategories.SYSTEM].append(SystemPackageSections.GPU_AMD)
	elif GPU_DRIVER_NAME is GPUDrivers.INTEL:
		all_sections[RequirementCategories.SYSTEM].append(SystemPackageSections.GPU_INTEL)

	commands = RequirementCommands()

	if OPERATING_SYSTEM.family is OSFamilies.LINUX:
		packages_dir = get_real_bin_file().parent / "recipes" / "packages"
		package_manager_file = packages_dir / "package_manager.sh"

		for category, sections in all_sections.items():
			section_names = [section.value for section in sections]
			result = subprocess.run([ package_manager_file, "hint", category.value, *section_names ], stdout = subprocess.PIPE, stderr = subprocess.PIPE)

			if result.returncode != 0:
				if (result.stdout is not None) and (len(result.stdout) > 0):
					print_msg(Level.ERROR, result.stdout)

				if (result.stderr is not None) and (len(result.stderr) > 0):
					print_msg(Level.ERROR, result.stderr)

				throw_error(Messages.PACKAGE_MANAGER_ERROR, category.value, ' '.join(section_names))

			output_lines = result.stdout.decode("utf-8").splitlines()
			if category is RequirementCategories.SYSTEM:
				for line in output_lines:
					if line == "fallback":
						commands.is_default = True
					elif line == "main":
						target = commands.main_system_packages
					elif line == "port":
						target = commands.ported_system_packages
					elif line == "external":
						target = commands.external_system_packages
					elif line == "other":
						target = commands.other_commands
					elif isinstance(target, list):
						target.append(line)
					elif isinstance(target, dict):
						repository_url, install_command = line.split(' ', 1)

						if repository_url in target:
							unused, package_name = install_command.rsplit(' ', 1)
							target[repository_url] += " {}".format(package_name)
						else:
							target[repository_url] = install_command
					else:
						throw_error(Messages.INVALID_PACKAGE_MANAGER_RESULT, line)

			else:
				for line in output_lines:
					commands.application_packages.append(line)

	elif OPERATING_SYSTEM.family is OSFamilies.MAC:
		pass

	elif OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
		pass
	
	else:
		throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM.family)

	return commands
