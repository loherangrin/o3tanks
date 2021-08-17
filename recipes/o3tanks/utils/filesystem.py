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


from .input_output import Messages, throw_error
from .types import ObjectEnum
import configparser
import json
import shutil


# --- FUNCTIONS ---

def calculate_size(path):
	if path is None:
		return -1

	if path.is_file():
		bytes_size = path.stat().st_size

	elif path.is_dir():
		bytes_size = 0
		for child in path.iterdir():
			bytes_size += calculate_size(child)

	else:
		bytes_size = 0

	return bytes_size


def clear_directory(path):
	if not path.is_dir():
		return False

	for content in path.iterdir():
		if content.is_dir():
			shutil.rmtree(content)
		else:
			content.unlink()

	return True


def copy_all(from_path, to_path):
	shutil.copytree(from_path, to_path, symlinks = True)


def format_size(bytes_size):
	if bytes_size < 0:
		return "-"

	value = bytes_size
	units = [ '', 'k', 'M', 'G' ]
	for unit in units:
		if (value < 1000) or (unit == units[len(units) - 1]):
			return "{:.1f} {}B".format(value, unit)

		value /= 1000


def is_directory_empty(path):
	if path is None or not path.is_dir():
		throw_error(Messages.INVALID_DIRECTORY)

	return not any(path.iterdir())


def read_cfg_property(file, key):
	if not file.is_file():
		return None

	cfg = configparser.ConfigParser()
	cfg.read(file)

	if isinstance(key, ObjectEnum):
		key = key.value
	if key.section in cfg:
		value = cfg[key.section].get(key.name, '')
		if len(value) == 0:
			value = None
	else:
		value = None

	return value


def read_cfg_properties(file, *keys):
	if not file.is_file():
		return {}

	cfg = configparser.ConfigParser()
	with file.open('rt') as file_handler:
		cfg.read_file(file_handler)

	values = {}
	for key in keys:
		if isinstance(key, ObjectEnum):
			key = key.value
		if key.section in cfg:
			value = cfg[key.section].get(key.name, '')
			if len(value) > 0:
				values[key] = value

	return values


def read_json_property(file, key):
	if not file.is_file():
		return None

	data = json.loads(file.read_bytes(), parse_float = True, parse_int = True)

	value = data.get(key)
	if len(value) == 0:
		value = None

	return value


def write_cfg_property(file, key, value):
	cfg = configparser.ConfigParser()
	if file.is_file():
		with file.open('rt') as file_handler:
			cfg.read_file(file_handler)

	if isinstance(key, ObjectEnum):
		key = key.value
	if value is not None:
		if not key.section in cfg:
			cfg[key.section] = {}

		cfg[key.section][key.name] = value
		do_write = True

	else:
		try:
			do_write = cfg.remove_option(key.section, key.name)
			
			if do_write and (len(cfg[key.section]) == 0):
				cfg.remove_section(key.section)
		
		except configparser.NoSectionError:
			do_write = False

	if do_write:
		with file.open('wt') as file_handler:
			cfg.write(file_handler)
