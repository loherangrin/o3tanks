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


class EngineResultType(AutoEnum):
	OK = enum.auto()
	MISSING = enum.auto()
	INVALID = enum.auto()
	NOT_FOUND = enum.auto()
	DIFFERENT = enum.auto()
 
class EngineResult(typing.NamedTuple):
	type: EngineResultType
	value: str = None


class User(typing.NamedTuple):
	name: str
	group: str
	uid: int
	gid: int
