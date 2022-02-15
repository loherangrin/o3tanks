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


from ..utils.types import ObjectEnum
from .input_output import Messages, throw_error
import pathlib
import sys


# --- FUNCTIONS ---

def deserialize_arg(index, output_type):
	return deserialize_value(sys.argv[index], output_type)


def deserialize_args(index, container_type = list, data_type = str):
	if container_type is list:
		is_dict = False
	elif container_type is dict:
		is_dict = True
	else:
		throw_error(Messages.INVALID_DESERIALIZATION_CONTAINER, index, container_type.__name__)

	length = deserialize_value(sys.argv[index], int)
	if (length is None) or (length == 0):
		return {} if is_dict else []

	start_index = index + 1
	n_args = len(sys.argv)
	if start_index >= n_args:
		throw_error(Messages.INVALID_DESERIALIZATION_LENGTH, index, "start", start_index, n_args)

	if length > 0:
		end_index = start_index + length
		if end_index > n_args:
			throw_error(Messages.INVALID_DESERIALIZATION_LENGTH, index, "end", end_index, n_args)
	else:
		end_index = len(sys.argv)

	input = sys.argv[start_index:end_index]
	if is_dict:
		return deserialize_dict(input, data_type)
	else:
		return deserialize_list(input, data_type)


def deserialize_dict(input_dict, output_type):
	if not isinstance(input_dict, list):
		throw_error(Messages.INVALID_DESERIALIZATION_INPUT, input_dict, list.__name__, type(input_dict).__name__)

	output_dict = {}

	n_items = len(input_dict)
	i = 0
	while i < n_items - 1:
		input_key = input_dict[i]
		output_key = deserialize_value(input_key, str)

		input_value = input_dict[i+1]
		output_value = deserialize_value(input_value, output_type)

		output_dict[output_key] = output_value
		i = i + 2

	return output_dict


def deserialize_list(input_list, output_type):
	if not isinstance(input_list, list):
		throw_error(Messages.INVALID_DESERIALIZATION_INPUT, input_list, list.__name__, type(input_list).__name__)

	output_list = []
	for input_value in input_list:
		output_value = deserialize_value(input_value, output_type)
		output_list.append(output_value)

	return output_list


def deserialize_value(input_value, output_type):
	if not isinstance(input_value, str):
		throw_error(Messages.INVALID_DESERIALIZATION_INPUT, input_value, str.__name__, type(input_value).__name__)

	if input_value == 'null':
		output_value = None

	elif output_type is bool:
		if input_value == 'true':
			output_value = True
		elif input_value == 'false':
			output_value = False
		else:
			throw_error(Messages.INVALID_DESERIALIZATION_OUTPUT, input_value, output_type.__name__)

	elif (output_type is int) or (output_type is float):
		try:
			output_value = output_type(input_value)
		except ValueError:
			throw_error(Messages.INVALID_DESERIALIZATION_OUTPUT, input_value, output_type.__name__)

	elif issubclass(output_type, ObjectEnum):
		output_value = output_type.from_value(input_value)
		if output_value is None:
			throw_error(Messages.INVALID_DESERIALIZATION_OUTPUT, input_value, output_type.__name__)

	elif issubclass(output_type, pathlib.Path):
		output_value = pathlib.Path(input_value)

	elif issubclass(output_type, pathlib.PurePath):
		output_value = pathlib.PurePath(input_value)

	elif output_type is str:
		output_value = input_value

	else:
		throw_error(Messages.INVALID_DESERIALIZATION, input_value, output_type.__name__)
		
	return output_value


def serialize_dict(input_dict):
	if input_dict is None:
		return None
	elif not isinstance(input_dict, dict):
		throw_error(Messages.INVALID_SERIALIZATION_INPUT, input_dict, dict.__name__, type(input_dict).__name__)

	output_list = []

	input_length = len(input_dict)
	output_list.append(str(input_length * 2))

	for input_key, input_value in input_dict.items():
		output_key = serialize_value(input_key)
		output_list.append(output_key)

		output_value = serialize_value(input_value)
		if isinstance(input_value, list) or isinstance(input_value, dict):
			output_list.extend(output_value)
		else:
			output_list.append(output_value)

	return output_list


def serialize_list(input_list, prepend_length):
	if input_list is None:
		return None
	elif not isinstance(input_list, list):
		return serialize_list([ input_list ], prepend_length)

	output_list = []

	if prepend_length:
		input_length = len(input_list)
		output_list.append(str(input_length))

	for input_value in input_list:
		output_value = serialize_value(input_value)
		if isinstance(input_value, list) or isinstance(input_value, dict):
			output_list.extend(output_value)
		else:
			output_list.append(output_value)

	return output_list


def serialize_value(input_value):
	if input_value is None:
		output_value = "null"

	elif isinstance(input_value, bool):
		output_value = 'true' if input_value else 'false'

	elif isinstance(input_value, int) or isinstance(input_value, float):
		output_value = str(input_value)

	elif isinstance(input_value, str):
		output_value = input_value

	elif isinstance(input_value, ObjectEnum):
		output_value = input_value.value

	elif isinstance(input_value, dict):
		output_value = serialize_dict(input_value)

	elif isinstance(input_value, list):
		output_value = serialize_list(input_value, True)

	elif isinstance(input_value, pathlib.PurePath):
		output_value = str(input_value)

	else:
		throw_error(Messages.INVALID_SERIALIZATION, input_value, type(input_value).__name__)

	return output_value
