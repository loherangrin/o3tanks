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


from ..globals.o3tanks import DEVELOPMENT_MODE, DISPLAY_ID, REAL_USER, USER_NAME, USER_GROUP, get_version_number
from .filesystem import is_directory_empty
from .input_output import Level, Messages, get_verbose, print_msg, throw_error
from .serialization import serialize_list
from .types import User
import docker
import grp
import os
import pathlib
import pwd
import re


# --- VARIABLES ---

DOCKER_CLIENT = None
IN_CONTAINER = None
REAL_VOLUMES_DIR = None

IMAGE_PREFIX = "o3tanks"
VOLUME_PREFIX = IMAGE_PREFIX


# --- FUNCTIONS (GENERIC) ---

def check_container_client():
	global DOCKER_CLIENT
	if DOCKER_CLIENT is not None:
		print_msg(Level.WARNING, Messages.DOCKER_ALREADY_RUNNING)
		return

	try:
		DOCKER_CLIENT = docker.from_env(timeout = 7200)

	except:
		throw_error(Messages.MISSING_DOCKER)


def close_container_client():
	if DOCKER_CLIENT is not None:
		DOCKER_CLIENT.close()


def get_build_arguments():
	container_user = get_container_user()

	return {
		"USER_NAME": container_user.name,
		"USER_GROUP": container_user.group,
		"USER_UID": str(container_user.uid),
		"USER_GID": str(container_user.gid)
	}


def get_container_user(user_namespace = True):
	if is_in_container():
		if user_namespace:
			user_info =  pwd.getpwnam(USER_NAME)
			group_info = grp.getgrgid(user_info.pw_uid)

			container_uid = user_info.pw_uid
			container_gid = group_info.gr_gid

		else:
			container_uid = REAL_USER.uid
			container_gid = REAL_USER.gid

	else:
		host_user = get_current_user()

		if is_rootless_runtime() and not user_namespace:
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


def get_current_user():
	uid = os.getuid()
	gid = os.getgid()

	name = pwd.getpwuid(uid).pw_name
	group = grp.getgrgid(gid).gr_name

	return User(name, group, uid, gid)


def get_environment_variables():
	return {
		"O3TANKS_DEV_MODE": str(DEVELOPMENT_MODE).lower(),
		"O3TANKS_VERBOSE": get_verbose()
	}


def get_real_volumes_dir():
	global REAL_VOLUMES_DIR
	return REAL_VOLUMES_DIR


def is_rootless_runtime():
	info = DOCKER_CLIENT.info()
	security_options = info.get("SecurityOptions")
	has_rootless_flag = ("name=rootless" in security_options)

	return has_rootless_flag


def is_in_container():
	global IN_CONTAINER
	if IN_CONTAINER is None:
		IN_CONTAINER = pathlib.Path("/.dockerenv").is_file()

	return IN_CONTAINER


def print_bytes_stream(stream, stdout, stderr):
	stdout_line = ''
	stderr_line = ''
	for bytes_chunk in stream:
		if isinstance(bytes_chunk, tuple):
			if stdout:
				stdout_line = __print_bytes_stream(stdout_line, bytes_chunk[0])

			if stderr:
				stderr_line = __print_bytes_stream(stderr_line, bytes_chunk[1])
		else:
			if stdout or stderr:
				stdout_line = __print_bytes_stream(stdout_line, bytes_chunk)


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


def print_string_stream(stream):
	for string_chunk in stream:
		data = string_chunk.get("stream")
		if data is not None:
			for line in data.splitlines():
				print_msg(Level.INFO, line)


def set_real_volumes_dir(value):
	global REAL_VOLUMES_DIR
	REAL_VOLUMES_DIR = (pathlib.PurePath(value) / "volumes") if is_in_container() else None


# --- FUNCTIONS (CONTAINERS) ---

def copy_to_container(container, from_path, to_path, content_only = False):
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


def exec_in_container(container, command, stdout = False, stderr = False):
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
		print_bytes_stream(logs, stdout, stderr)
		return True
	
	else:
		return (exit_code == 0)


def run_detached_container(image_name, wait, environment = {}, mounts = [], network_disabled = False):
	if wait:
		entrypoint = "/bin/sh",
		command = [ "-c", "tail --follow /dev/null" ]
	else:
		entrypoint = None
		command = []

	full_environment = get_environment_variables()
	if len(environment) > 0:
		full_environment.update(environment)

	new_container = DOCKER_CLIENT.containers.run(
		image_name,
		entrypoint = entrypoint,
		command = command,
		network_disabled = network_disabled,
		auto_remove = True,
		detach = True,
		environment = full_environment
	)

	return new_container


def run_foreground_container(image_name, command = [], environment = {}, interactive = True, mounts = [], display = False, network_disabled = False):
	full_environment = get_environment_variables()
	
	if display:
		if DISPLAY_ID < 0:
			throw_error(Messages.MISSING_DISPLAY)

		x11_socket = pathlib.Path("/tmp/.X11-unix/X{}".format(DISPLAY_ID))
		if not is_in_container() and not x11_socket.is_socket():
			throw_error(Messages.INVALID_DISPLAY, DISPLAY_ID, x11_socket)

		real_container_user = get_container_user(False)

		full_environment["O3TANKS_REAL_USER_UID"] = real_container_user.uid
		full_environment["O3TANKS_DISPLAY_ID"] = DISPLAY_ID
		full_environment["DISPLAY"] = ":{}".format(DISPLAY_ID)

		mounts.append(docker.types.Mount(type = "bind", source = str(x11_socket),  target = str(x11_socket)))

	if len(environment) > 0:
		full_environment.update(environment)

	try:
		exit_status = None
		container = DOCKER_CLIENT.containers.run(
				image_name,
				command = serialize_list(command),
				network_disabled = network_disabled,
				auto_remove = True,
				detach = True,
				mounts = mounts,
				environment = full_environment
			)

		logs = container.attach(stdout = True, stderr = True, stream = True)
		print_bytes_stream(logs, stdout = True, stderr = True)

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


# --- FUNCTIONS (IMAGES) ---

def build_image_from_archive(tar_file, image_name, recipe, stage = None):
	if not tar_file.is_file():
		throw_error(Messages.CONTEXT_NOT_FOUND, tar_file)

	print_msg(Level.INFO, Messages.BUILD_IMAGE_FROM_ARCHIVE, image_name, tar_file)

	if image_name.endswith(":development"):
		stage += "_dev"

	try:
		with tar_file.open() as tar_handler:
			tar_handler.seek(0)

			new_image, logs = DOCKER_CLIENT.images.build(
				fileobj = tar_handler,
				dockerfile = recipe,
				custom_context = True,		
				tag = image_name,
				target = stage,
				buildargs = get_build_arguments()
			)

			print_string_stream(logs)

	except docker.errors.BuildError as error:
		new_image = None
		print_msg(Level.ERROR, str(error))

	finally:
		tar_handler.close()

	return new_image


def build_image_from_directory(context_dir, image_name, recipe, stage = None):
	if not context_dir.is_dir():
		throw_error(Messages.CONTEXT_NOT_FOUND, context_dir)

	print_msg(Level.INFO, Messages.BUILD_IMAGE_FROM_DIRECTORY, image_name, context_dir)

	if image_name.endswith(":development"):
		stage += "_dev"

	try:
		new_image, logs = DOCKER_CLIENT.images.build(
			path = str(context_dir),
			dockerfile = str(context_dir / recipe),
			tag = image_name,
			target = stage,
			buildargs = get_build_arguments()
		)

		print_string_stream(logs)

	except docker.errors.BuildError as error:
		new_image = None
		print_msg(Level.ERROR, str(error))

	return new_image


def get_image_name(image_id, engine_version = None, engine_config = None):
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


def image_exists(image_name):
	try:
		image = DOCKER_CLIENT.images.get(image_name)	
		return True
	
	except docker.errors.ImageNotFound:
		return False


def remove_image(image_name):
	if image_exists(image_name):
		DOCKER_CLIENT.images.remove(image_name)

	return True


# --- FUNCTIONS (VOLUMES) ---

def create_volume(name):
	DOCKER_CLIENT.volumes.create(name)


def get_volume_name(volume_id, engine_version = None):
	volume = VOLUME_PREFIX + '-' + volume_id.value
	
	if engine_version is not None:
		volume += "_{}".format(engine_version)

	return volume


def get_volume_path(volume_name):
	if volume_name is None:
		return None

	try:
		volume = DOCKER_CLIENT.volumes.get(volume_name)
		path = volume.attrs.get("Mountpoint")
		if path is not None:
			path = pathlib.Path(path)
			
			if is_in_container():
				try:
					path = pathlib.Path("/var/lib/docker/volumes") / path.relative_to(REAL_VOLUMES_DIR)
				except:
					throw_error(Messages.VOLUMES_DIR_NOT_FOUND)

		return path

	except docker.errors.NotFound:
		volume = None


def get_volumes(filter):
	return DOCKER_CLIENT.volumes.list(filters = { "name": filter })


def is_volume_empty(volume_name):
	volume_dir = get_volume_path(volume_name)

	if volume_dir is None:
		throw_error(Messages.VOLUME_NOT_FOUND, volume_name)
	
	return is_directory_empty(volume_dir)


def remove_volume(volume_name):
	try:
		volume = DOCKER_CLIENT.volumes.get(volume_name)
		volume.remove()

	except docker.errors.NotFound:
		pass


def volume_exists(volume_name):
	try:
		volume = DOCKER_CLIENT.volumes.get(volume_name)
		return True

	except docker.errors.NotFound:
		return False
