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
from ..utils.types import ObjectEnum
from .o3tanks import USER_NAME, init_from_env
import os
import pathlib


# --- TYPES ---

class O3DE_Configs(ObjectEnum):
	DEBUG = "debug"
	PROFILE = "profile"
	RELEASE = "release"


class O3DE_ProjectBinaries(ObjectEnum):
	CLIENT = "client"
	SERVER = "server"


# --- CONSTANTS ---

O3DE_REPOSITORY_HOST = "https://github.com"
O3DE_REPOSITORY_URL = O3DE_REPOSITORY_HOST + "/o3de/o3de.git"

O3DE_ROOT_DIR = init_from_env("O3DE_DIR", pathlib.Path, pathlib.PosixPath("/home/" + USER_NAME + "/o3de"))

O3DE_ENGINE_SOURCE_DIR = init_from_env("O3DE_ENGINE_DIR", pathlib.Path, O3DE_ROOT_DIR / "engine")
O3DE_ENGINE_REPOSITORY_DIR = O3DE_ENGINE_SOURCE_DIR / ".git"
O3DE_ENGINE_BUILD_DIR = O3DE_ENGINE_SOURCE_DIR / "build"
O3DE_ENGINE_INSTALL_DIR = O3DE_ENGINE_SOURCE_DIR / "install"
if O3DE_ENGINE_INSTALL_DIR.is_dir() and not is_directory_empty(O3DE_ENGINE_INSTALL_DIR):
	O3DE_ENGINE_BIN_DIR = O3DE_ENGINE_INSTALL_DIR / "bin" / "Linux"
	O3DE_ENGINE_SCRIPTS_DIR = O3DE_ENGINE_INSTALL_DIR / "scripts"
else:
	O3DE_ENGINE_BIN_DIR = O3DE_ENGINE_BUILD_DIR / "bin"
	O3DE_ENGINE_SCRIPTS_DIR = O3DE_ENGINE_SOURCE_DIR / "scripts"
O3DE_CLI_FILE = O3DE_ENGINE_SCRIPTS_DIR / "o3de.sh"

O3DE_PACKAGES_DIR = init_from_env("O3DE_PACKAGES_DIR", pathlib.Path, O3DE_ROOT_DIR / "packages")

O3DE_PROJECT_SOURCE_DIR = init_from_env("O3DE_PROJECT_DIR", pathlib.Path, O3DE_ROOT_DIR / "project")
O3DE_PROJECT_BUILD_DIR = O3DE_PROJECT_SOURCE_DIR / "build" / "Linux"
O3DE_PROJECT_BIN_DIR = O3DE_PROJECT_BUILD_DIR / "bin"

O3DE_DEFAULT_VERSION = "development"
O3DE_DEFAULT_CONFIG = O3DE_Configs.PROFILE
