# Copyright 2021-2023 Matteo Grasso
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


from ..globals.o3de import O3DE_ENGINE_BUILDS_DIR, O3DE_ENGINE_INSTALL_DIR, O3DE_ENGINE_SOURCE_DIR, O3DE_GEMS_DIR, O3DE_GEMS_EXTERNAL_DIR, O3DE_PACKAGES_DIR, O3DE_PROJECT_SOURCE_DIR
from ..globals.o3tanks import DATA_DIR, DEVELOPMENT_MODE, DISPLAY_ID, GPU_CARD_IDS, GPU_DRIVER_NAME, GPU_RENDER_OFFLOAD, OPERATING_SYSTEM, REAL_USER, RUN_CONTAINERS, ROOT_DIR, USER_NAME, USER_GROUP, USER_HOME, GPUDrivers, Images, Volumes, get_version_number
from .filesystem import clear_directory, is_directory_empty
from .input_output import Level, Messages, get_verbose, print_msg, throw_error
from .serialization import serialize_list
from .types import AutoEnum, LinuxOSNames, OSFamilies, User
import abc
import enum
import os
import pathlib
import re

if OPERATING_SYSTEM.family in [ OSFamilies.LINUX, OSFamilies.MAC ]:
	import grp
	import pwd

elif OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
	import getpass

else:
	throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM.family)


# --- TYPES ---

class ContainerBackend(AutoEnum):
	NONE = enum.auto()
	DOCKER = enum.auto()


class ContainerRunMode(AutoEnum):
	BACKGROUND = enum.auto()
	FOREGROUND = enum.auto()
	STANDBY = enum.auto()


# --- ABSTRACT BASE CLIENT ---

class ContainerClient(abc.ABC):

	def __init__(self, backend, in_container):
		self._backend = backend
		self._in_container = in_container


	# --- GENERIC (BASE) ---

	def _get_build_arguments(self):
		container_user = self.get_container_user()

		if OPERATING_SYSTEM.name is LinuxOSNames.ARCH:
			os_image = "archlinux"
		elif OPERATING_SYSTEM.name is LinuxOSNames.OPENSUSE_LEAP:
			os_image = OPERATING_SYSTEM.name.value.replace('-', '/')
		else:
			os_image = OPERATING_SYSTEM.name.value

		os_version = (OPERATING_SYSTEM.version if OPERATING_SYSTEM.version is not None else "latest")
		os_image = "{}:{}".format(os_image, os_version)

		if OPERATING_SYSTEM.name is LinuxOSNames.ARCH:
			locale = "en_US.utf8"
		elif OPERATING_SYSTEM.name in [ LinuxOSNames.DEBIAN, LinuxOSNames.UBUNTU ]:
			locale = "C.UTF-8"
		elif OPERATING_SYSTEM.name in [ LinuxOSNames.FEDORA, LinuxOSNames.OPENSUSE_LEAP ]:
			locale = "C.utf8"
		else:
			locale = "POSIX"

		return {
			"LOCALE": locale,
			"OS_IMAGE": os_image,
			"OS_NAME": OPERATING_SYSTEM.name.value,
			"OS_VERSION": os_version,
			"USER_NAME": container_user.name,
			"USER_GROUP": container_user.group,
			"USER_UID": str(container_user.uid),
			"USER_GID": str(container_user.gid),
			"USER_HOME": str(container_user.home)
		}


	@staticmethod
	def _get_environment_variables():
		environment = {
			"O3TANKS_DEV_MODE": str(DEVELOPMENT_MODE).lower(),
			"O3TANKS_VERBOSE": str(get_verbose())
		}

		if DATA_DIR is not None:
			environment["O3TANKS_DATA_DIR"] = str(DATA_DIR)

		return environment


	@staticmethod
	def _print_bytes_stream(stream, stdout, stderr):
		stdout_line = ''
		stderr_line = ''
		for bytes_chunk in stream:
			if isinstance(bytes_chunk, tuple):
				if stdout:
					stdout_line = ContainerClient.__print_bytes_stream(stdout_line, bytes_chunk[0])

				if stderr:
					stderr_line = ContainerClient.__print_bytes_stream(stderr_line, bytes_chunk[1])
			else:
				if stdout or stderr:
					stdout_line = ContainerClient.__print_bytes_stream(stdout_line, bytes_chunk)


	@staticmethod
	def __print_bytes_stream(input_line, bytes_chunk):
		if bytes_chunk is None:
			return input_line

		output_line = input_line
		string_chunk = bytes_chunk.decode("utf-8")
		if '\n' in string_chunk:
			for char in string_chunk:
				if char == '\n':
					print_msg(Level.INFO, output_line)
					output_line = ''
				else:
					output_line += char
		else:
			output_line += string_chunk

		return output_line


	@staticmethod
	def _print_string_stream(stream):
		for string_chunk in stream:
			data = string_chunk.get("stream")
			if data is not None:
				for line in data.splitlines():
					print_msg(Level.INFO, line)


	@staticmethod
	def calculate_is_in_container():
		global RUN_CONTAINERS
		if RUN_CONTAINERS:
			return DockerContainerClient.calculate_is_in_container()
		else:
			NoneContainerClient.calculate_is_in_container()


	@abc.abstractmethod
	def close(self):
		raise NotImplementedError


	@abc.abstractmethod
	def get_container_user(self, user_namespace = True):
		raise NotImplementedError


	def get_current_user(self):
		if OPERATING_SYSTEM.family in [ OSFamilies.LINUX, OSFamilies.MAC ]:
			uid = os.getuid()
			gid = os.getgid()

			name = pwd.getpwuid(uid).pw_name
			group = grp.getgrgid(gid).gr_name

		elif OPERATING_SYSTEM.family is OSFamilies.WINDOWS:
			uid = None
			gid = None

			name = getpass.getuser()
			group = None

		else:
			throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM.family)

		home = str(pathlib.Path.home())

		return User(name, group, uid, gid, home)


	def is_in_container(self):
		return self._in_container


	@abc.abstractmethod	
	def is_rootless_runtime(self):
		raise NotImplementedError


	@staticmethod
	def open():
		global RUN_CONTAINERS
		if RUN_CONTAINERS:
			return DockerContainerClient()
		else:
			return NoneContainerClient()


	# --- CONTAINERS (BASE) ---

	@abc.abstractmethod
	def copy_to_container(self, container, from_path, to_path, content_only = False):
		raise NotImplementedError


	@abc.abstractmethod
	def exec_in_container(self, container, command, stdout = False, stderr = False):
		raise NotImplementedError


	@abc.abstractmethod
	def get_container(self, id):
		raise NotImplemented


	@abc.abstractmethod
	def run_container(self, image_name, command = [], environment = {}, interactive = True, mounts = [], display = False, gpu = False, network_disabled = False, network_name = None):
		raise NotImplementedError


	# --- IMAGES (BASE) ---

	@abc.abstractmethod
	def build_image_from_archive(self, tar_file, image_name, recipe, stage = None, arguments = {}):
		raise NotImplementedError


	@abc.abstractmethod
	def build_image_from_directory(self, context_dir, image_name, recipe, stage = None, arguments = {}):
		raise NotImplementedError


	@abc.abstractmethod
	def get_image_name(self, image_id, engine_version = None, engine_config = None):
		image = "{}-{}".format(IMAGE_PREFIX, image_id.value)

		if engine_version is not None:
			image += "_{}".format(engine_version)

		if engine_config is not None:
			image += "_{}".format(engine_config.value)

		if DEVELOPMENT_MODE:
			image += ":development"
		else:
			image += ":{}".format(get_version_number())

		if OPERATING_SYSTEM.name is not None:
			image += "_{}".format(OPERATING_SYSTEM.name.value)

			if OPERATING_SYSTEM.version is not None:
				image += "_{}".format(OPERATING_SYSTEM.version)

		if (GPU_DRIVER_NAME is not None) and (image_id in [ Images.RUNNER, Images.INSTALL_RUNNER ]):
			image += "_{}".format(GPU_DRIVER_NAME.value)

		return image


	@abc.abstractmethod
	def image_exists(self, image_name):
		raise NotImplementedError


	@abc.abstractmethod
	def remove_image(self, image_name):
		raise NotImplementedError


	# --- NETWORKS (BASE) ---

	@abc.abstractmethod
	def get_network_range(self, network_name):
		raise NotImplementedError


	# --- VOLUMES (BASE) ---

	@abc.abstractmethod
	def create_volume(self, name):
		raise NotImplementedError


	def get_volume_name(self, volume_id, engine_version = None):
		volume = VOLUME_PREFIX + '-' + volume_id.value
		
		if engine_version is not None:
			volume += "_{}".format(engine_version)

		return volume


	@abc.abstractmethod
	def get_volume_path(self, volume_name):
		raise NotImplementedError


	@abc.abstractmethod
	def list_volumes(self, filter):
		raise NotImplementedError


	def is_volume_empty(self, volume_name):
		volume_dir = self.get_volume_path(volume_name)

		if volume_dir is None:
			throw_error(Messages.VOLUME_NOT_FOUND, volume_name)

		return is_directory_empty(volume_dir)


	@abc.abstractmethod
	def remove_volume(self, volume_name):
		raise NotImplementedError


	@abc.abstractmethod
	def volume_exists(self, volume_name):
		raise NotImplementedError


# --- DOCKER ---

class DockerContainerClient(ContainerClient):
	def __init__(self):
		super().__init__(
			ContainerBackend.DOCKER,
			DockerContainerClient.calculate_is_in_container()
		)

		global docker
		try:
			import docker

		except ModuleNotFoundError as error:
			throw_error(Messages.MISSING_MODULE, error.name)

		try:
			self._client = docker.from_env(timeout = 7200)

		except:
			throw_error(Messages.MISSING_DOCKER)


	# --- GENERIC (DOCKER) ---

	def close(self):
		self._client.close()


	def get_container_user(self, user_namespace = True):
		if self.is_in_container():
			if user_namespace:
				user_info =  pwd.getpwnam(USER_NAME)
				group_info = grp.getgrgid(user_info.pw_uid)

				container_uid = user_info.pw_uid
				container_gid = group_info.gr_gid

			else:
				container_uid = REAL_USER.uid
				container_gid = REAL_USER.gid

		else:
			host_user = self.get_current_user()

			if self.is_rootless_runtime() and not user_namespace:
				container_uid = None
				container_gid = None

				user_pattern = re.compile(r"^{}:(\d+):\d+$".format(host_user.name))
				with open("/etc/subuid") as subuid_handler:
					for entry in subuid_handler:
						matches = user_pattern.match(entry)
						if matches is not None:
							container_uid = matches.group(1)
							break

				group_pattern = re.compile(r"^{}:(\d+):\d+$".format(host_user.group))
				with open("/etc/subgid") as subgid_handler:
					for entry in subgid_handler:
						matches = group_pattern.match(entry)
						if matches is not None:
							container_gid = matches.group(1)
							break

				if (container_uid is None) or (container_gid is None):
					throw_error(Messages.INVALID_USER_NAMESPACE)

			else:
				container_uid = host_user.uid
				container_gid = host_user.gid

		return User(USER_NAME, USER_GROUP, container_uid, container_gid, USER_HOME)


	@staticmethod
	def calculate_is_in_container():
		return pathlib.Path("/.dockerenv").is_file()


	def is_rootless_runtime(self):
		info = self._client.info()
		security_options = info.get("SecurityOptions")
		has_rootless_flag = ("name=rootless" in security_options)

		return has_rootless_flag


	# --- CONTAINERS (DOCKER) ---

	@staticmethod
	def _calculate_mounts(binds, volumes):
		mounts = []

		for from_path, to_path in binds.items():
			mounts.append(docker.types.Mount(type = "bind", source = from_path, target = to_path))

		for volume_name, to_path in volumes.items():
			mounts.append(docker.types.Mount(type = "volume", source = volume_name, target = to_path))

		return mounts


	def copy_to_container(self, container, from_path, to_path, content_only = False):
		copied = False
		if content_only:
			root = str(from_path)
			files = None
		else:
			root = str(from_path.parent)
			if from_path.is_dir():
				files = sorted([ str(child.relative_to(root)) for child in from_path.glob("**/*")])
			else:
				files = [ from_path.name ]

		with docker.utils.build.create_archive(root, files = files) as tar_handler:
			copied = container.put_archive(str(to_path), tar_handler)

		return copied


	def exec_in_container(self, container, command, stdout = False, stderr = False):
		exit_code, logs = container.exec_run(
			stdin = False,
			stdout = (stdout or (not stdout and not stderr)),
			stderr = stderr,
			user = USER_NAME,
			cmd = serialize_list(command, False),
			stream = (stdout or stderr),
			socket = False,
			demux = (stdout and stderr)
		)

		if (stdout or stderr):
			ContainerClient._print_bytes_stream(logs, stdout, stderr)
			return True
		
		else:
			return (exit_code == 0)


	def get_container(self, id):
		try:
			container = self._client.containers.get(id)
			return container

		except docker.errors.NotFound:
			return None


	def run_container(self, mode, image_name, command = [], environment = {}, interactive = True, binds = {}, volumes = {}, display = False, gpu = False, network_disabled = False, network_name = None):
		full_environment = ContainerClient._get_environment_variables()

		mounts = DockerContainerClient._calculate_mounts(binds, volumes)

		if display and (DISPLAY_ID >= 0):
			x11_socket = pathlib.Path("/tmp/.X11-unix/X{}".format(DISPLAY_ID))
			if not self.is_in_container() and not x11_socket.is_socket():
				throw_error(Messages.INVALID_DISPLAY, DISPLAY_ID, x11_socket)

			real_container_user = self.get_container_user(False)

			full_environment["O3TANKS_REAL_USER_UID"] = str(real_container_user.uid)
			full_environment["O3TANKS_DISPLAY_ID"] = str(DISPLAY_ID)
			full_environment["DISPLAY"] = ":{}".format(DISPLAY_ID)

			mounts.append(docker.types.Mount(type = "bind", source = str(x11_socket),  target = str(x11_socket)))

		devices = []
		device_requests = []
		if gpu and (GPU_DRIVER_NAME is not None):
			full_environment["O3TANKS_GPU_DRIVER"] = GPU_DRIVER_NAME.value

			if GPU_DRIVER_NAME is GPUDrivers.NVIDIA_PROPRIETARY:
				gpu_request = docker.types.DeviceRequest(capabilities = [ [ "gpu", "display", "graphics", "video" ] ])
				if GPU_CARD_IDS is None:
					gpu_request.count = -1
				else:
					gpu_request.device_ids = GPU_CARD_IDS

				device_requests.append(gpu_request)

				vulkan_configs = [
					"/usr/share/vulkan/implicit_layer.d/nvidia_layers.json",
					"/usr/share/vulkan/icd.d/nvidia_icd.json"
				]

				for config_file in vulkan_configs:
					mounts.append(docker.types.Mount(type = "bind", source = config_file, target = config_file, read_only = True))

			elif GPU_DRIVER_NAME in [ GPUDrivers.AMD_OPEN, GPUDrivers.AMD_PROPRIETARY, GPUDrivers.INTEL ]:
				devices.append("/dev/dri:/dev/dri")

			else:
				print_msg(Level.WARNING, Messages.INVALID_GPU, GPU_DRIVER_NAME.value)

		if len(environment) > 0:
			full_environment.update(environment)

		if network_disabled:
			network_name = None
		elif network_name is not None:
			full_environment["O3TANKS_NETWORK_NAME"] = network_name

			network_subnet = self.get_network_range(network_name)
			if network_subnet is None:
				throw_error(Messages.INVALID_NETWORK, network_name)

			full_environment["O3TANKS_NETWORK_SUBNET"] = network_subnet

		if mode == ContainerRunMode.STANDBY:
			entrypoint = "/bin/sh",
			command = [ "-c", "tail --follow /dev/null" ]
		else:
			entrypoint = None

		exit_code = None
		try:
			container = self._client.containers.run(
					image_name,
					entrypoint = entrypoint,
					command = serialize_list(command, False),
					network_disabled = network_disabled,
					network = network_name,
					auto_remove = True,
					detach = True,
					devices = devices,
					device_requests = device_requests,
					mounts = mounts,
					environment = full_environment
				)

			if mode is ContainerRunMode.FOREGROUND:
				logs = container.attach(stdout = True, stderr = True, stream = True)
				ContainerClient._print_bytes_stream(logs, stdout = True, stderr = True)

				exit_status = container.wait()
				exit_code = exit_status.get("StatusCode")

			else:
				return container

		finally:
			if (mode is ContainerRunMode.FOREGROUND) and (exit_code is None) and (container is not None):
				container.kill()

		if exit_code is None:
			throw_error(Messages.EXIT_CODE_NOT_FOUND, image_name)
		elif exit_code != 0:
			print_msg(Level.ERROR, Messages.CONTAINER_ERROR, image_name, exit_code)
			return False

		return True


	# --- IMAGES (DOCKER) ---

	def build_image_from_archive(self, tar_file, image_name, recipe, stage = None, arguments = {}):
		if not tar_file.is_file():
			throw_error(Messages.CONTEXT_NOT_FOUND, tar_file)

		print_msg(Level.INFO, Messages.BUILD_IMAGE_FROM_ARCHIVE, image_name, tar_file)

		if image_name.endswith(":development") or (":development_" in image_name):
			stage += "_dev"

		full_buildargs = self._get_build_arguments()
		if len(arguments) > 0:
			full_buildargs.update(arguments)

		try:
			with tar_file.open() as tar_handler:
				tar_handler.seek(0)

				new_image, logs = self._client.images.build(
					fileobj = tar_handler,
					dockerfile = recipe,
					custom_context = True,
					tag = image_name,
					target = stage,
					buildargs = full_buildargs
				)

				ContainerClient._print_string_stream(logs)

		except docker.errors.BuildError as error:
			new_image = None
			print_msg(Level.ERROR, str(error))

		finally:
			tar_handler.close()

		return new_image


	def build_image_from_directory(self, context_dir, image_name, recipe, stage = None, arguments = {}):
		if not context_dir.is_dir():
			throw_error(Messages.CONTEXT_NOT_FOUND, context_dir)

		print_msg(Level.INFO, Messages.BUILD_IMAGE_FROM_DIRECTORY, image_name, context_dir)

		if image_name.endswith(":development") or (":development_" in image_name):
			stage += "_dev"

		full_buildargs = self._get_build_arguments()
		if len(arguments) > 0:
			full_buildargs.update(arguments)

		try:
			new_image, logs = self._client.images.build(
				path = str(context_dir),
				dockerfile = str(context_dir / recipe),
				tag = image_name,
				target = stage,
				buildargs = full_buildargs
			)

			ContainerClient._print_string_stream(logs)

		except docker.errors.BuildError as error:
			new_image = None
			print_msg(Level.ERROR, str(error))

		return new_image


	def get_image_name(self, image_id, engine_version = None, engine_config = None):
		return super().get_image_name(image_id, engine_version, engine_config)


	def image_exists(self, image_name):
		try:
			image = self._client.images.get(image_name)	
			return True

		except docker.errors.ImageNotFound:
			return False


	def remove_image(self, image_name):
		if self.image_exists(image_name):
			self._client.images.remove(image_name)

		return True


	# --- NETWORKS (DOCKER) ---

	def get_network_range(self, network_name):
		try:
			network = self._client.networks.get(network_name)
			return network.attrs["IPAM"]["Config"][0]["Subnet"]

		except docker.errors.NotFound:
			return None


	# --- VOLUMES (DOCKER) ---

	def create_volume(self, name):
		self._client.volumes.create(name)


	def get_volume_path(self, volume_name):
		if volume_name is None:
			return None

		try:
			volume = self._client.volumes.get(volume_name)
			path = volume.attrs.get("Mountpoint")
			if path is not None:
				path = pathlib.Path(path)

				if self.is_in_container():
					try:
						path = pathlib.Path("/var/lib/docker/volumes") / path.relative_to(REAL_VOLUMES_DIR)
					except:
						throw_error(Messages.VOLUMES_DIR_NOT_FOUND)

			return path

		except docker.errors.NotFound:
			volume = None


	def list_volumes(self, filter):
		volumes = self._client.volumes.list(filters = { "name": filter })
		if len(volumes) == 0:
			return []

		volume_names = []
		for volume in volumes:
			volume_names.append(volume.name)

		return volume_names


	def remove_volume(self, volume_name):
		try:
			volume = self._client.volumes.get(volume_name)
			volume.remove()

		except docker.errors.NotFound:
			pass


	def volume_exists(self, volume_name):
		try:
			volume = self._client.volumes.get(volume_name)
			return True

		except docker.errors.NotFound:
			return False


# --- NONE ---

class NoneContainerClient(ContainerClient):
	def __init__(self):
		super().__init__(
			ContainerBackend.NONE,
			NoneContainerClient.calculate_is_in_container()
		)

		global subprocess
		import subprocess

		self._ENGINES_DIR = DATA_DIR / "engines"
		self._GEMS_DIR = DATA_DIR / "gems"
		self._PACKAGES_DIR = DATA_DIR / "packages"


	# --- GENERIC (NONE) ---

	def close(self):
		pass


	def get_container_user(self, user_namespace = True):
		current_user = self.get_current_user()
		return current_user


	@staticmethod
	def calculate_is_in_container():
		return False


	def is_rootless_runtime(self):
		current_user = self.get_current_user()

		return (current_user.uid != 0)


	# --- CONTAINERS (NONE) ---

	def _calculate_command(self, image_name, command):
		if not self.image_exists(image_name):
			throw_error(Messages.INVALID_IMAGE_IN_NO_CONTAINERS_MODE, image_name)

		full_command = [ "python3", "-m", "o3tanks.{}".format(image_name) ]
		if len(command) > 0:
			full_command += serialize_list(command, False)

		return full_command


	def _calculate_mounts_mapping(self, binds, volumes):
		mapping = {}

		for from_path, to_path in volumes.items():
			engine_volume_type = None
			if to_path == str(O3DE_ENGINE_SOURCE_DIR):
				engine_volume_type = Volumes.SOURCE
			elif to_path == str(O3DE_ENGINE_BUILDS_DIR):
				engine_volume_type = Volumes.BUILD
			elif to_path == str(O3DE_ENGINE_INSTALL_DIR):
				engine_volume_type = Volumes.INSTALL
			elif to_path == str(O3DE_GEMS_DIR):
				mapping["O3DE_GEMS_DIR"] = str(self._GEMS_DIR)
			elif to_path == str(O3DE_PACKAGES_DIR):
				mapping["O3DE_PACKAGES_DIR"] = str(self._PACKAGES_DIR)

			if engine_volume_type is not None:
				engine_version = self._get_engine_version_from_volume(from_path, engine_volume_type)
				mapping["O3DE_ENGINE_DIR"] = str(self._ENGINES_DIR / engine_version)

		for from_path, to_path in binds.items():
			if to_path == str(O3DE_PROJECT_SOURCE_DIR):
				mapping["O3DE_PROJECT_DIR"] = str(from_path)
			elif to_path == str(ROOT_DIR):
				mapping["O3TANKS_DIR"] = str(from_path)
			elif to_path.startswith(str(O3DE_GEMS_EXTERNAL_DIR)):
				mapping["O3DE_GEMS_EXTERNAL_DIR"] = pathlib.Path(from_path).anchor

		return mapping


	@staticmethod
	def _execute_python(command, environment, wait):
		for python_binary in [ "python3", "python", "py" ]:
			try:
				command[0] = python_binary

				if wait:
					result = subprocess.run(command, env = environment)
					return result

				else:
					handler = subprocess.Popen(command, env = environment)
					return handler

			except FileNotFoundError as error:
				pass

		throw_error(Messages.MISSING_PYTHON)


	def _get_engine_version_from_volume(self, volume_name, volume_type):
		volume_prefix = self.get_volume_name(volume_type)
		if not volume_name.startswith(volume_prefix):
			return None

		generic_volume = self.get_volume_name(volume_type, 'a')

		start_delimiter = len(volume_prefix)
		end_delimiter = len(generic_volume)
		volume_prefix_length = start_delimiter + (end_delimiter - start_delimiter - 1)

		engine_version = volume_name[volume_prefix_length:]
		return engine_version


	@staticmethod
	def _get_environment_variables():
		environment = os.environ.copy()

		global_variables = ContainerClient._get_environment_variables()
		if len(global_variables) > 0:
			environment.update(global_variables)

		return environment


	def copy_to_container(self, container, from_path, to_path, content_only = False):
		throw_error(Messages.UNSUPPORTED_CONTAINERS_AND_NO_CLIENT)


	def get_container(self, id):
		return -1


	def exec_in_container(self, container, command, stdout = False, stderr = False):
		throw_error(Messages.UNSUPPORTED_CONTAINERS_AND_NO_CLIENT)


	def run_container(self, mode, image_name, command = [], environment = {}, interactive = True, binds = {}, volumes = {}, display = False, gpu = False, network_disabled = False, network_name = None):
		if mode is ContainerRunMode.STANDBY:
			throw_error(Messages.UNSUPPORTED_CONTAINERS_AND_NO_CLIENT)

		full_command = self._calculate_command(image_name, command)

		full_environment = NoneContainerClient._get_environment_variables()

		if OPERATING_SYSTEM.family is OSFamilies.LINUX:
			if display and (DISPLAY_ID >= 0):
				x11_socket = pathlib.Path("/tmp/.X11-unix/X{}".format(DISPLAY_ID))
				if not x11_socket.is_socket():
					throw_error(Messages.INVALID_DISPLAY, DISPLAY_ID, x11_socket)

				full_environment["O3TANKS_DISPLAY_ID"] = str(DISPLAY_ID)
				full_environment["DISPLAY"] = ":{}".format(DISPLAY_ID)

			if gpu and (GPU_DRIVER_NAME is GPUDrivers.NVIDIA_PROPRIETARY) and GPU_RENDER_OFFLOAD:
				full_environment["__NV_PRIME_RENDER_OFFLOAD"] = str(1)
				full_environment["__VK_LAYER_NV_optimus"] = "NVIDIA_only"

		if len(environment) > 0:
			full_environment.update(environment)

		mapping = self._calculate_mounts_mapping(binds, volumes)
		full_environment.update(mapping)

		result = NoneContainerClient._execute_python(full_command, full_environment, wait = True)

		if mode is ContainerRunMode.FOREGROUND:
			exit_code = result.returncode
			if exit_code != 0:
				print_msg(Level.ERROR, Messages.CONTAINER_ERROR, image_name, exit_code)
				return False

			return True

		else:
			handler = NoneContainerClient._execute_python(full_command, full_environment, wait = False)
			return handler


	# --- IMAGES (NONE) ---

	def build_image_from_archive(self, tar_file, image_name, recipe, stage = None, arguments = {}):
		return None


	def build_image_from_directory(self, context_dir, image_name, recipe, stage = None, arguments = {}):
		return None


	def get_image_name(self, image_id, engine_version = None, engine_config = None):
		if image_id in [ Images.INSTALL_BUILDER, Images.INSTALL_RUNNER ]:
			return None

		return image_id.value


	def image_exists(self, image_name):
		return (image_name is not None) and Images.has_value(image_name)


	def remove_image(self, image_name):
		return True


	# --- NETWORKS (NONE) ---

	def get_network_range(self, network_name):
		throw_error(Messages.UNSUPPORTED_CONTAINERS_AND_NO_CLIENT)


	# --- VOLUMES (NONE) ---

	def _calculate_volume_path(self, volume_name):
		if volume_name is None:
			return None

		elif volume_name == self.get_volume_name(Volumes.GEMS):
			volume_dir = self._GEMS_DIR

		elif volume_name == self.get_volume_name(Volumes.PACKAGES):
			volume_dir = self._PACKAGES_DIR

		else:
			volume_dir = None

			for volume_type in [ Volumes.SOURCE, Volumes.BUILD, Volumes.INSTALL ]:
				engine_version = self._get_engine_version_from_volume(volume_name, volume_type)
				if engine_version is not None:
					volume_dir = self._ENGINES_DIR / engine_version

					if volume_type is not Volumes.SOURCE:
						volume_dir /= volume_type.value

					break

			if volume_dir is None:
				throw_error(Messages.INVALID_VOLUME_TYPE)

		return volume_dir


	def create_volume(self, name):
		volume_dir = self._calculate_volume_path(name)

		if volume_dir.is_dir():
			return
		elif volume_dir.exists():
			throw_error(Messages.INVALID_VOLUME_DIRECTORY, name, volume_dir)

		volume_dir.mkdir(parents = True)


	def get_volume_path(self, volume_name):
		volume_dir = self._calculate_volume_path(volume_name)

		if not volume_dir.exists():
			return None
		elif not volume_dir.is_dir():
			throw_error(Messages.INVALID_VOLUME_DIRECTORY, volume_name, volume_dir)

		return volume_dir


	def list_volumes(self, filter):
		if not self._ENGINES_DIR.is_dir():
			return []

		volume_names = []
		for child in self._ENGINES_DIR.iterdir():
			if not child.is_dir():
				continue

			engine_version = child.name

			volume_name = self.get_volume_name(Volumes.SOURCE, engine_version)
			if re.search(filter, volume_name):
				volume_names.append(volume_name)

		return volume_names


	def remove_volume(self, volume_name):
		volume_dir = self.get_volume_path(volume_name)
		if volume_dir is None:
			return

		cleared = clear_directory(volume_dir)
		if cleared:
			volume_dir.rmdir()
	

	def volume_exists(self, volume_name):
		volume_dir = self.get_volume_path(volume_name)

		if volume_dir is None:
			return False
		elif volume_dir.is_dir():
			return True
		else:
			throw_error(Messages.INVALID_VOLUME_DIRECTORY, volume_name, volume_dir)


# --- VARIABLES ---

REAL_VOLUMES_DIR = None

IMAGE_PREFIX = "o3tanks"
VOLUME_PREFIX = IMAGE_PREFIX


# --- FUNCTIONS (GENERIC) ---

def get_real_volumes_dir():
	global REAL_VOLUMES_DIR
	return REAL_VOLUMES_DIR


def set_real_volumes_dir(value):
	global REAL_VOLUMES_DIR
	REAL_VOLUMES_DIR = (pathlib.PurePath(value) / "volumes") if value is not None else None
