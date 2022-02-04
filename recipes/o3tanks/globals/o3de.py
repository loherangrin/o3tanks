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


from ..utils.filesystem import is_directory_empty
from ..utils.subfunctions import get_build_path, get_script_filename, has_build_config, has_install_config
from ..utils.types import ObjectEnum
from .o3tanks import OPERATING_SYSTEM, RUN_CONTAINERS, USER_NAME, init_from_env
import pathlib


# --- TYPES ---

class O3DE_Configs(ObjectEnum):
	DEBUG = "debug"
	PROFILE = "profile"
	RELEASE = "release"


class O3DE_GemTemplates(ObjectEnum):
	ASSETS_ONLY = "AssetGem"
	CODE_AND_ASSETS = "DefaultGem"


class O3DE_GemTypes(ObjectEnum):
	ASSETS_ONLY = "asset"
	CODE_AND_ASSETS = "code"


class O3DE_ProjectBinaries(ObjectEnum):
	CLIENT = "client"
	SERVER = "server"
	TOOLS = "tools"


class O3DE_ProjectTemplates(ObjectEnum):
	MINIMAL = "MinimalProject"
	STANDARD = "DefaultProject"


class O3DE_BuildWorkflows(ObjectEnum):
	ENGINE_CENTRIC = "engine"
	PROJECT_CENTRIC_ENGINE_SOURCE = "project"
	PROJECT_CENTRIC_ENGINE_SDK = "sdk"


# --- FUNCTIONS ---

def get_default_root_dir():
	path = "/home/{}/o3de".format(USER_NAME)

	return (pathlib.PosixPath(path) if RUN_CONTAINERS else pathlib.PurePosixPath(path))


def get_build_workflow(source_dir, build_dir, install_dir):
	if source_dir.is_dir() and (source_dir / ".git").is_dir() and (source_dir / "engine.json").is_file():
		build_workflow = O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SOURCE
	else:
		build_workflow = None

	for config in O3DE_Configs:
		if has_install_config(install_dir, config):
			build_workflow = O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK
			break

		elif is_directory_empty(install_dir) and has_build_config(build_dir, config):
			build_workflow = O3DE_BuildWorkflows.ENGINE_CENTRIC
			break

	return build_workflow


# --- CONSTANTS ---

O3DE_REPOSITORY_HOST = "https://github.com"
O3DE_REPOSITORY_URL = O3DE_REPOSITORY_HOST + "/o3de/o3de.git"

O3DE_ROOT_DIR = init_from_env("O3DE_DIR", pathlib.Path, get_default_root_dir())

O3DE_ENGINE_SOURCE_DIR = init_from_env("O3DE_ENGINE_DIR", pathlib.Path, O3DE_ROOT_DIR / "engine")
O3DE_ENGINE_REPOSITORY_DIR = O3DE_ENGINE_SOURCE_DIR / ".git"
O3DE_ENGINE_BUILD_DIR = O3DE_ENGINE_SOURCE_DIR / "build"
O3DE_ENGINE_INSTALL_DIR = O3DE_ENGINE_SOURCE_DIR / "install"
if RUN_CONTAINERS and O3DE_ENGINE_INSTALL_DIR.is_dir() and not is_directory_empty(O3DE_ENGINE_INSTALL_DIR):
	O3DE_ENGINE_SCRIPTS_DIR = O3DE_ENGINE_INSTALL_DIR / "scripts"
else:
	O3DE_ENGINE_SCRIPTS_DIR = O3DE_ENGINE_SOURCE_DIR / "scripts"
O3DE_CLI_FILE = O3DE_ENGINE_SCRIPTS_DIR / get_script_filename("o3de")

O3DE_GEMS_DIR = init_from_env("O3DE_GEMS_DIR", pathlib.Path, O3DE_ROOT_DIR / "gems")
O3DE_GEMS_EXTERNAL_DIR = init_from_env("O3DE_GEMS_EXTERNAL_DIR", pathlib.Path, O3DE_GEMS_DIR / ".external")

O3DE_PACKAGES_DIR = init_from_env("O3DE_PACKAGES_DIR", pathlib.Path, O3DE_ROOT_DIR / "packages")

O3DE_PROJECT_SOURCE_DIR = init_from_env("O3DE_PROJECT_DIR", pathlib.Path, O3DE_ROOT_DIR / "project")
O3DE_PROJECT_BUILD_DIR = get_build_path(O3DE_PROJECT_SOURCE_DIR, OPERATING_SYSTEM)
O3DE_PROJECT_BIN_DIR = O3DE_PROJECT_BUILD_DIR / "bin"

O3DE_DEFAULT_VERSION = "development"
O3DE_DEFAULT_CONFIG = O3DE_Configs.PROFILE
O3DE_DEFAULT_WORKFLOW = O3DE_BuildWorkflows.PROJECT_CENTRIC_ENGINE_SDK
