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


from ..globals.o3de import O3DE_ENGINE_BUILD_DIR, O3DE_ENGINE_INSTALL_DIR, O3DE_ENGINE_SOURCE_DIR, O3DE_PACKAGES_DIR, O3DE_PROJECT_SOURCE_DIR
from ..globals.o3tanks import DATA_DIR, DEVELOPMENT_MODE, DISPLAY_ID, GPU_DRIVER_NAME, OPERATING_SYSTEM, REAL_USER, RUN_CONTAINERS, ROOT_DIR, USER_NAME, USER_GROUP, GPUDrivers, Images, OperatingSystems, Volumes, get_version_number
from .filesystem import clear_directory, is_directory_empty
from .input_output import Level, Messages, get_verbose, print_msg, throw_error
from .serialization import serialize_list
from .types import AutoEnum, User
import abc
import enum
import os
import pathlib
import re

if OPERATING_SYSTEM is OperatingSystems.LINUX:
	import grp
	import pwd

elif OPERATING_SYSTEM is OperatingSystems.WINDOWS:
	import getpass

else:
	throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM)


# --- TYPES ---

class ContainerBackend(AutoEnum):
	NONE = enum.auto()
	DOCKER = enum.auto()


# --- ABSTRACT BASE CLIENT ---

class ContainerClient(abc.ABC):

	def __init__(self, backend, in_container):
		self._backend = backend
		self._in_container = in_container


	# --- GENERIC (BASE) ---

	def _get_build_arguments(self):
		container_user = self.get_container_user()

		return {
			"USER_NAME": container_user.name,
			"USER_GROUP": container_user.group,
			"USER_UID": str(container_user.uid),
			"USER_GID": str(container_user.gid)
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
		if OPERATING_SYSTEM is OperatingSystems.LINUX:
			uid = os.getuid()
			gid = os.getgid()

			name = pwd.getpwuid(uid).pw_name
			group = grp.getgrgid(gid).gr_name

		elif OPERATING_SYSTEM is OperatingSystems.WINDOWS:
			uid = None
			gid = None

			name = getpass.getuser()
			group = None

		else:
			throw_error(Messages.INVALID_OPERATING_SYSTEM, OPERATING_SYSTEM)

		return User(name, group, uid, gid)


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
	def run_detached_container(self, image_name, wait, environment = {}, mounts = [], network_disabled = False):
		raise NotImplementedError


	@abc.abstractmethod
	def run_foreground_container(self, image_name, command = [], environment = {}, interactive = True, mounts = [], display = False, gpu = False, network_disabled = False):
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

		return image


	@abc.abstractmethod
	def image_exists(self, image_name):
		raise NotImplementedError


	@abc.abstractmethod
	def remove_image(self, image_name):
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

		return User(USER_NAME, USER_GROUP, container_uid, container_gid)


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
			cmd = serialize_list(command),
			stream = (stdout or stderr),
			socket = False,
			demux = (stdout and stderr)
		)

		if (stdout or stderr):
			ContainerClient._print_bytes_stream(logs, stdout, stderr)
			return True
		
		else:
			return (exit_code == 0)


	def run_detached_container(self, image_name, wait, environment = {}, binds = {}, volumes = {}, network_disabled = False):
		if wait:
			entrypoint = "/bin/sh",
			command = [ "-c", "tail --follow /dev/null" ]
		else:
			entrypoint = None
			command = []

		full_environment = ContainerClient._get_environment_variables()
		if len(environment) > 0:
			full_environment.update(environment)

		mounts = DockerContainerClient._calculate_mounts(binds, volumes)

		new_container = self._client.containers.run(
			image_name,
			entrypoint = entrypoint,
			command = command,
			network_disabled = network_disabled,
			auto_remove = True,
			detach = True,
			mounts = mounts,
			environment = full_environment
		)

		return new_container


	def run_foreground_container(self, image_name, command = [], environment = {}, interactive = True, binds = {}, volumes = {}, display = False, gpu = False, network_disabled = False):
		full_environment = ContainerClient._get_environment_variables()

		mounts = DockerContainerClient._calculate_mounts(binds, volumes)

		if display:
			if DISPLAY_ID < 0:
				throw_error(Messages.MISSING_DISPLAY)

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
		if gpu:
			if GPU_DRIVER_NAME is None:
				print_msg(Level.WARNING, Messages.MISSING_GPU)

			elif GPU_DRIVER_NAME is GPUDrivers.NVIDIA_PROPRIETARY:
				device_requests.append(docker.types.DeviceRequest(count = -1, capabilities = [ [ "gpu", "display", "graphics", "video" ] ]))

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

		try:
			exit_status = None
			container = self._client.containers.run(
					image_name,
					command = serialize_list(command),
					network_disabled = network_disabled,
					auto_remove = True,
					detach = True,
					devices = devices,
					device_requests = device_requests,
					mounts = mounts,
					environment = full_environment
				)

			logs = container.attach(stdout = True, stderr = True, stream = True)
			ContainerClient._print_bytes_stream(logs, stdout = True, stderr = True)

			exit_status = container.wait()

		finally:
			if (exit_status is None) and (container is not None):
				container.kill()

		exit_code = exit_status.get("StatusCode")
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

		if image_name.endswith(":development"):
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

		if image_name.endswith(":development"):
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
			full_command += serialize_list(command)

		return full_command


	def _calculate_mounts_mapping(self, binds, volumes):
		mapping = {}

		for from_path, to_path in volumes.items():
			engine_volume_type = None
			if to_path == str(O3DE_ENGINE_SOURCE_DIR):
				engine_volume_type = Volumes.SOURCE
			elif to_path == str(O3DE_ENGINE_BUILD_DIR):
				engine_volume_type = Volumes.BUILD
			elif to_path == str(O3DE_ENGINE_INSTALL_DIR):
				engine_volume_type = Volumes.INSTALL
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


	def exec_in_container(self, container, command, stdout = False, stderr = False):
		throw_error(Messages.UNSUPPORTED_CONTAINERS_AND_NO_CLIENT)


	def run_detached_container(self, image_name, wait, environment = {}, binds = {}, volumes = {}, network_disabled = False):
		if wait:
			throw_error(Messages.UNSUPPORTED_CONTAINERS_AND_NO_CLIENT)

		full_command = self._calculate_command(image_name, [])

		full_environment = NoneContainerClient._get_environment_variables()
		if len(environment) > 0:
			full_environment.update(environment)

		mapping = self._calculate_mounts_mapping(binds, volumes)
		full_environment.update(mapping)

		handler = NoneContainerClient._execute_python(full_command, full_environment, wait = False)
		return handler


	def run_foreground_container(self, image_name, command = [], environment = {}, interactive = True, binds = {}, volumes = {}, display = False, gpu = False, network_disabled = False):
		full_command = self._calculate_command(image_name, command)

		full_environment = NoneContainerClient._get_environment_variables()

		if display and (OPERATING_SYSTEM is OperatingSystems.LINUX):
			if DISPLAY_ID < 0:
				throw_error(Messages.MISSING_DISPLAY)

			x11_socket = pathlib.Path("/tmp/.X11-unix/X{}".format(DISPLAY_ID))
			if not x11_socket.is_socket():
				throw_error(Messages.INVALID_DISPLAY, DISPLAY_ID, x11_socket)

			full_environment["O3TANKS_DISPLAY_ID"] = str(DISPLAY_ID)
			full_environment["DISPLAY"] = ":{}".format(DISPLAY_ID)

		if len(environment) > 0:
			full_environment.update(environment)

		mapping = self._calculate_mounts_mapping(binds, volumes)
		full_environment.update(mapping)

		result = NoneContainerClient._execute_python(full_command, full_environment, wait = True)

		exit_code = result.returncode
		if exit_code != 0:
			print_msg(Level.ERROR, Messages.CONTAINER_ERROR, image_name, exit_code)
			return False

		return True


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


	# --- VOLUMES (NONE) ---

	def _calculate_volume_path(self, volume_name):
		if volume_name is None:
			return None

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
