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


from .input_output import Level, Messages, ask_for_confirmation, print_msg, throw_error
from .types import JsonPropertyKey, ObjectEnum
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


def clear_directory(path, require_confirmation = False):
	if not path.is_dir():
		return False

	if require_confirmation:
		print_msg(Level.INFO, Messages.CLEAR_DIRECTORY, str(path))
		if not ask_for_confirmation(Messages.CONTINUE_QUESTION):
			exit(1)

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

	with file.open('rt') as file_handler:
		try:
			data = json.load(file_handler)

		except json.decoder.JSONDecodeError as error:
			throw_error(Messages.INVALID_SETTING_DATA, file, error)

	if isinstance(key, ObjectEnum):
		key = key.value
	if (data is not None) and key.section is not None:
		if not isinstance(data, dict):
			throw_error(Messages.INVALID_PROPERTY_KEY, key.print(), "dict")

		data = data.get(key.section)

	if (data is not None) and key.index is not None:
		if not key.is_any():
			if not isinstance(data, list):
				throw_error(Messages.INVALID_PROPERTY_KEY, key.print(), "list")

			data = data[key.index] if key.index < len(data) else None

		else:
			data = None

	if (data is not None) and key.name is not None:
		if not isinstance(data, dict):
			throw_error(Messages.INVALID_PROPERTY_KEY, key.print(), "dict")

		data = data.get(key.name)

	if (data is not None) and (
		(isinstance(data, str) and len(data.strip()) == 0) or
		(isinstance(data, list) and len(data) == 0) or
		(isinstance(data, dict) and len(data) == 0)
	):
		data = None

	return data


def remove_directory(path, require_confirmation = False):
	cleared = clear_directory(path, require_confirmation)
	if not cleared:
		return False

	path.rmdir()

	return True


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


def write_json_property(file, key, value, sort_keys = True):
	if (key.section is None) and (key.name is None):
		throw_error(Messages.MISSING_PROPERTY)

	data = read_json_property(file, JsonPropertyKey(None, None, None))
	if data is None:
		data = {}
	elif not isinstance(data, dict):
		throw_error(Messages.INVALID_PROPERTY_KEY, key.print(), "dict")

	if key.section is None:
		if value is not None:
			if isinstance(value, dict) or isinstance(value, list):
				throw_error(Messages.INVALID_PROPERTY_VALUE, key.print(), "literal")

			data[key.name] = value

		else:
			if not key.name in data:
				return
			del data[key.name]

	else:
		if isinstance(key, ObjectEnum):
			key = key.value

		if key.index is not None:
			if not key.section in data:
				if value is None:
					return
				data[key.section] = []
			elif not isinstance(data[key.section], list):
				throw_error(Messages.INVALID_PROPERTY_KEY, key.print(), "list")

			n_section = len(data[key.section])
			if key.index < 0:
				if value is None:
					return
				key = JsonPropertyKey(key.section, n_section, key.name)
				data[key.section].append({})
			elif key.index >= len(data[key.section]):
				if value is None:
					throw_error(Messages.INVALID_PROPERTY_INDEX, key.print(), n_section)
				while(key.index >= len(data[key.section])):
					data[key.section].append({})
			elif not isinstance(data[key.section][key.index], dict):
				throw_error(Messages.INVALID_PROPERTY_KEY, key.print(), "dict")

			if key.name is not None:
				if value is not None:
					if isinstance(value, dict) or isinstance(value, list):
						throw_error(Messages.INVALID_PROPERTY_VALUE, key.print(), "literal")
					data[key.section][key.index][key.name] = value
				else:
					if not key.name in data[key.section][key.index]:
						return
					del data[key.section][key.index][key.name]
			else:
				if value is not None:
					if not isinstance(value, dict):
						throw_error(Messages.INVALID_PROPERTY_VALUE, key.print(), "dict")
					data[key.section][key.index] = value
				else:
					if key.index >= len(data[key.section]):
						return
					del data[key.section][key.index]

		elif (key.name is not None):
			if not key.section in data:
				if value is None:
					return
				data[key.section] = {}
			elif not isinstance(data[key.section], dict):
				throw_error(Messages.INVALID_PROPERTY_KEY, key.print(), "dict")

			if value is not None:
				if isinstance(value, dict) or isinstance(value, list):
					throw_error(Messages.INVALID_PROPERTY_VALUE, key.print(), "literal")
				data[key.section][key.name] = value
			else:
				if not key.name in data[key.section]:
					return
				del data[key.section][key.name]
		else:
			if value is not None:
				if not (isinstance(value, dict) or isinstance(value, list)):
					throw_error(Messages.INVALID_PROPERTY_VALUE, key.print(), "literal")
				data[key.section] = value
			else:
				if not key.section in data:
					return
				del data[key.section]

	if len(data) == 0 and (value is not None):
		return

	if not file.parent.exists():
		file.parent.mkdir(parents = True)

	with file.open('wt') as file_handler:
		json.dump(data, file_handler, indent = 4, sort_keys = sort_keys)
