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


from ..utils.filesystem import is_directory_empty
from ..utils.subfunctions import get_script_filename
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


class O3DE_ProjectTemplates(ObjectEnum):
	MINIMAL = "MinimalProject"
	STANDARD = "DefaultProject"


# --- FUNCTIONS ---

def get_default_root_dir():
	path = "/home/{}/o3de".format(USER_NAME)

	return (pathlib.PosixPath(path) if RUN_CONTAINERS else pathlib.PurePosixPath(path))


# --- CONSTANTS ---

O3DE_REPOSITORY_HOST = "https://github.com"
O3DE_REPOSITORY_URL = O3DE_REPOSITORY_HOST + "/o3de/o3de.git"

O3DE_ROOT_DIR = init_from_env("O3DE_DIR", pathlib.Path, get_default_root_dir())

O3DE_ENGINE_SOURCE_DIR = init_from_env("O3DE_ENGINE_DIR", pathlib.Path, O3DE_ROOT_DIR / "engine")
O3DE_ENGINE_REPOSITORY_DIR = O3DE_ENGINE_SOURCE_DIR / ".git"
O3DE_ENGINE_BUILD_DIR = O3DE_ENGINE_SOURCE_DIR / "build"
O3DE_ENGINE_INSTALL_DIR = O3DE_ENGINE_SOURCE_DIR / "install"
if RUN_CONTAINERS and O3DE_ENGINE_INSTALL_DIR.is_dir() and not is_directory_empty(O3DE_ENGINE_INSTALL_DIR):
	O3DE_ENGINE_BIN_DIR = O3DE_ENGINE_INSTALL_DIR / "bin" / OPERATING_SYSTEM.family.value
	O3DE_ENGINE_SCRIPTS_DIR = O3DE_ENGINE_INSTALL_DIR / "scripts"
else:
	O3DE_ENGINE_BIN_DIR = O3DE_ENGINE_BUILD_DIR / "bin"
	O3DE_ENGINE_SCRIPTS_DIR = O3DE_ENGINE_SOURCE_DIR / "scripts"
O3DE_CLI_FILE = O3DE_ENGINE_SCRIPTS_DIR / get_script_filename("o3de")

O3DE_GEMS_DIR = init_from_env("O3DE_GEMS_DIR", pathlib.Path, O3DE_ROOT_DIR / "gems")
O3DE_GEMS_EXTERNAL_DIR = init_from_env("O3DE_GEMS_EXTERNAL_DIR", pathlib.Path, O3DE_GEMS_DIR / ".external")

O3DE_PACKAGES_DIR = init_from_env("O3DE_PACKAGES_DIR", pathlib.Path, O3DE_ROOT_DIR / "packages")

O3DE_PROJECT_SOURCE_DIR = init_from_env("O3DE_PROJECT_DIR", pathlib.Path, O3DE_ROOT_DIR / "project")
O3DE_PROJECT_BUILD_DIR = O3DE_PROJECT_SOURCE_DIR / "build" / OPERATING_SYSTEM.family.value
O3DE_PROJECT_BIN_DIR = O3DE_PROJECT_BUILD_DIR / "bin"

O3DE_DEFAULT_VERSION = "development"
O3DE_DEFAULT_CONFIG = O3DE_Configs.PROFILE
