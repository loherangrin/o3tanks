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


from .globals.o3de import *
from .globals.o3tanks import *
from .utils.filesystem import *
from .utils.input_output import *
from .utils.serialization import *
from .utils.subfunctions import *
import pygit2
import re


# --- TYPES ---

class FetchCallbacks(pygit2.RemoteCallbacks):
	def transfer_progress(self, stats):
		if (stats.total_objects > 0 and stats.indexed_objects < stats.total_objects) or (stats.total_deltas == 0):
			progress = stats.indexed_objects / stats.total_objects * 100
			print_msg(Level.INFO, "Fetching new objects: {:.0f}% ({}/{})".format(progress, stats.indexed_objects, stats.total_objects))

		elif (stats.total_deltas > 0):
			progress = stats.indexed_deltas / stats.total_deltas * 100
			print_msg(Level.INFO, "Indexing: {:.0f}% ({}/{})".format(progress, stats.indexed_deltas, stats.total_deltas))


# --- SUBFUNCTIONS ---

def get_current_branches(repository):
	local_branch_name = repository.head.shorthand
	if local_branch_name == "HEAD":
		throw_error(Messages.NO_UPDATES_IF_DETACHED)

	local_branch = repository.branches.local.get(local_branch_name)
	if local_branch is None:
		throw_error(Messages.INVALID_LOCAL_BRANCH)

	remote_branch = local_branch.upstream
	if remote_branch is None:
		throw_error(Messages.INVALID_LOCAL_BRANCH, local_branch.name)

	return (local_branch, remote_branch)


# --- FUNCTIONS ---

def clone_repository(url, reference):
	if O3DE_ENGINE_REPOSITORY_DIR.is_dir():
		throw_error(Messages.SOURCE_ALREADY_EXISTS)

	if is_commit(reference):
		branch = None
		commit_hash = reference
	else:
		branch = reference
		commit_hash = None

	repository = pygit2.clone_repository(url, O3DE_ENGINE_SOURCE_DIR, checkout_branch = branch)

	if commit_hash is not None:
		commit = repository.get(commit_hash)
		repository.checkout_tree(commit)
		repository.set_head(commit.id)

	if url != O3DE_REPOSITORY_URL:
		matches = re.match(r"^{}/([a-zA-Z0-9\-]+)/([a-zA-Z0-9\.\-]+)$".format(O3DE_REPOSITORY_HOST), url)
		if matches is not None:
			fork_username = matches.group(1)

			official_remote_name = "upstream"
			repository.remotes.create(official_remote_name, O3DE_REPOSITORY_URL)

			lfs_url = read_cfg_property(O3DE_ENGINE_SOURCE_DIR / ".lfsconfig", CfgPropertyKey("lfs", "url"))
			if lfs_url is None:
				throw_error(Messages.LFS_NOT_FOUND, official_remote_name)
			
			matches = re.match(r"^(https://[a-zA-Z0-9\.\-]+/api/v[0-9]+).*$", lfs_url)
			if matches is None:
				throw_error(Messages.INVALID_LFS, lfs_url)

			lfs_endpoint = matches.group(1)
			repository.config["lfs.url"] = "{}/fork/{}".format(lfs_endpoint, fork_username)


def fetch_branch():
	if not O3DE_ENGINE_REPOSITORY_DIR.is_dir():
		throw_error(Messages.SOURCE_NOT_FOUND)

	repository = pygit2.Repository(O3DE_ENGINE_REPOSITORY_DIR)
	local_branch, remote_branch = get_current_branches(repository)

	remote = repository.remotes[remote_branch.remote_name]
	progress = remote.fetch(
		refspecs = [ "{}:{}".format(local_branch.name, remote_branch.name) ],
		callbacks = FetchCallbacks()
	)

	local_commit = local_branch.peel().id

	remote_branch = repository.branches.remote.get(remote_branch.shorthand)	
	remote_commit = remote_branch.peel().id	

	changes = repository.ahead_behind(local_commit, remote_commit)
	return changes


def merge_branch():
	if not O3DE_ENGINE_REPOSITORY_DIR.is_dir():
		throw_error(Messages.SOURCE_NOT_FOUND)

	repository = pygit2.Repository(O3DE_ENGINE_REPOSITORY_DIR)
	local_branch, remote_branch = get_current_branches(repository)
	
	remote_commit = remote_branch.peel().id
	result = repository.merge_analysis(remote_commit)

	if result[0] != (pygit2.GIT_MERGE_ANALYSIS_NORMAL | pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD):
		throw_error(Messages.FAST_FORWARD_ONLY)

	local_branch.set_target(remote_branch.target)
	repository.checkout(local_branch.name)


# --- MAIN ---

def main():
	if DEVELOPMENT_MODE:
		print_msg(Level.WARNING, Messages.IS_DEVELOPMENT_MODE)

	if len(sys.argv) < 2:
		throw_error(Messages.EMPTY_COMMAND)

	command = deserialize_arg(1, UpdaterCommands)

	if command is None:
		throw_error(Messages.INVALID_COMMAND, sys.argv[1])

	elif command == UpdaterCommands.INIT:
		repository_url = deserialize_arg(2, str)
		repository_reference = deserialize_arg(3, str)

		clone_repository(repository_url, repository_reference)

	elif command in [ UpdaterCommands.REFRESH, UpdaterCommands.UPGRADE ]:
		n_ahead, n_behind = fetch_branch()

		if n_behind == 0:
			print_msg(Level.INFO, Messages.NO_UPDATES)

		elif command == UpdaterCommands.REFRESH:
			print_msg(Level.INFO, Messages.UPDATES_AVAILABLE, n_behind)

		elif n_behind > 0:
			merge_branch()

		else:
			throw_error(Messages.UNCOMPLETED_REFRESH)

	else:
		throw_error(Messages.INVALID_COMMAND, command.value)


if __name__ == "__main__":
	main()
