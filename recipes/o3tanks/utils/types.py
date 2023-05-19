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


import enum
import typing


# --- TYPES ---

class AutoEnum(enum.Enum):
	def __repr__(self):
		return "<{}.{}>".format(self.__class__.__name__, self.name)

	@classmethod
	def has_key(cls, key):
		return (key in cls.__members__)		


class ObjectEnum(AutoEnum):
	@classmethod
	def from_value(cls, value):
		for name, member in cls.__members__.items():
			if value == member.value:
				return member
	
		return None

	@classmethod
	def has_value(cls, value):
		return (cls.from_value(value) is not None)


class CfgPropertyKey(typing.NamedTuple):
	section: str
	name: str


class JsonPropertyKey(typing.NamedTuple):
	section: str
	index: int
	name: str

	def is_single(self):
		return (
			self.name is not None and
			((self.index is None) or (self.index >= 0))
		)

	def is_all(self):
		return (self.name is None) and (self.index is None)

	def is_any(self):
		return self.index == -1

	def print(self):
		if self.section is not None:
			output = self.section
			if (self.index is not None):
				output += "[{}]".format(self.index)

		else:
			output = ""

		if self.name is not None:
			output += ".{}".format(self.name)

		return output


class OSFamilies(ObjectEnum):
	LINUX = "Linux"
	MAC = "MacOS"
	WINDOWS = "Windows"


class OSNames(ObjectEnum):
	pass


class LinuxOSNames(OSNames):
	ARCH = "arch"
	DEBIAN = "debian"
	FEDORA = "fedora"
	OPENSUSE_LEAP = "opensuse-leap"
	UBUNTU = "ubuntu"


class OperatingSystem(typing.NamedTuple):
	family: OSFamilies
	name: OSNames
	version: str


class Repository(typing.NamedTuple):
	url: str
	branch: str = None
	revision: str = None


class RepositoryResultType(AutoEnum):
	OK = enum.auto()
	INVALID = enum.auto()
	NOT_FOUND = enum.auto()
 
class RepositoryResult(typing.NamedTuple):
	type: RepositoryResultType
	value: Repository = None


class DependencyResultType(AutoEnum):
	OK = enum.auto()
	MISSING = enum.auto()
	INVALID = enum.auto()
	NOT_FOUND = enum.auto()
	DIFFERENT = enum.auto()
 
class DependencyResult(typing.NamedTuple):
	type: DependencyResultType
	value: any = None


class User(typing.NamedTuple):
	name: str
	group: str
	uid: int
	gid: int
