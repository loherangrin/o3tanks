#!/bin/sh

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


set -eu

# --- I/O FUNCTIONS ---

get_message_text()
{
	case ${message_id} in		
		("${MESSAGES_BIN_DIR_NOT_FOUND}")
			echo 'Unable to calculate where the script is running'
			;;

		("${MESSAGES_INVALID_DIRECTORY}")
			echo 'Expecting a directory, but none was found at: %s'
			;;

		("${MESSAGES_INVALID_OPERATING_SYSTEM}")
			echo 'The current operating system is not supported: %s'
			;;

		("${MESSAGES_INVALID_SYMLINK}")
			echo "Unable to resolve a broken symlink: %s"
			;;

		("${MESSAGES_INVALID_USER_NAMESPACE}")
			echo "Unable to calculate the user namespace for the container user"
			;;

		("${MESSAGES_MISSING_DOCKER}")
			echo "Unable to find 'docker'"
			;;

		("${MESSAGES_MISSING_NVIDIA_DOCKER}")
			echo "Unable to find 'nvidia-docker'. At least 'nvidia-container-toolkit' package is required to enable GPU acceleration.\n\nPlease refer to NVIDIA documentation:\nhttps://docs.nvidia.com/datacenter/cloud-native/container-toolkit/arch-overview.html"
			;;

		("${MESSAGES_MISSING_PYTHON}")
			echo "Unable to find 'python' or 'python3'"
			;;

		("${MESSAGES_UNSUPPORTED_CONTAINTERS_MODE}")
			echo "Containers are not supported on %s. Please unset any value for 'O3TANKS_NO_CONTAINERS' in your system variables"
			;;

		("${MESSAGES_VOLUMES_DIR_NOT_FOUND}")
			echo 'Unable to find the volumes storage at: %s'
			;;

		(*)
			echo "${message_id}"
			;;
	esac

	return 0
}

is_env_active()
{
	local env_value="${1:-}"

	local is_active
	case ${env_value} in
		("1"|"on"|"true")
			is_active='true'
			;;

		(*)
			is_active='false'
			;;
	esac

	echo "${is_active}"
	return 0
}

is_env_inactive()
{
	local env_value="${1:-}"

	local is_active
	is_active=$(is_env_active "${env_value}")

	local is_inactive
	is_inactive=$(not_bool_string "${is_active}")
	
	echo "${is_inactive}"
	return 0
}

is_tty()
{
	if ! [ -t 0 ] && [ -t 1 ]; then
		return 1 
	fi

	return 0
}

not_bool_string()
{
	if [ "${1}" = 'false' ]; then
		echo 'true'
	else
		echo 'false'
	fi

	return 0
}

print_msg()
{
	local level="${1}"
	local message_id="${2}"
	shift
	shift

	local message_prefix
	case ${level} in
		("${DEBUG}")
			message_prefix='DEBUG: '
			;;

		("${ERROR}")
			message_prefix='ERROR: '
			;;
		
		("${WARNING}")
			message_prefix='WARNING: '
			;;

		(*)
			message_prefix=''
			;;
	esac

	local message_text
	message_text="$(get_message_text ${message_id})"

	printf "${message_prefix}${message_text}\n" "$@"
}

throw_error()
{
    print_msg "${ERROR}" "$@"
    exit 1
}

# --- CONTAINER FUNCTIONS ---

build_image()
{
	local image_tag="${1}"
	local stage="${2:-}"

	local context_dir
	context_dir="${BIN_DIR}/${RECIPES_PATH}"
	if ! [ -d "${context_dir}" ]; then
		throw_error "${MESSAGES_CONTEXT_NOT_FOUND}"
	fi

	local stage_option
	if [ -n "${stage}" ]; then
		stage_option="--target ${stage}"

		case ${image_tag} in
			(*:development|*:development_*)
				stage_option="${stage_option}_dev"
				;;
		esac
	else
		stage_option=''
	fi

	local os_image
	case ${OPERATING_SYSTEM_NAME} in
		("${OS_NAMES_ARCH}")
			os_image="archlinux"
			;;

		(*)
			os_image="${OPERATING_SYSTEM_NAME}"
			;;
	esac

	local os_version
	if [ -n "${OPERATING_SYSTEM_VERSION}" ]; then
		os_version="${OPERATING_SYSTEM_VERSION}"
	else
		os_version='latest'
	fi
	os_image="${os_image}:${os_version}"

	local locale
	case ${OPERATING_SYSTEM_NAME} in
		("${OS_NAMES_ARCH}")
			locale='en_US.utf8'
			;;

		("${OS_NAMES_UBUNTU}")
			locale='C.UTF-8'
			;;

		(*)
			locale='POSIX'
			;;
	esac

	docker build \
		--tag "${image_tag}" \
		${stage_option} \
		--file "${context_dir}/Dockerfile.linux" \
		--build-arg LOCALE="${locale}" \
		--build-arg OS_IMAGE="${os_image}" \
		--build-arg OS_NAME="${OPERATING_SYSTEM_NAME}" \
		--build-arg OS_VERSION="${os_version}" \
		--build-arg USER_NAME="${USER_NAME}" \
		--build-arg USER_GROUP="${USER_GROUP}" \
		--build-arg USER_UID="${USER_UID}" \
		--build-arg USER_GID="${USER_GID}" \
		"${context_dir}"
}

get_docker_dir()
{
	local docker_dir
	docker_dir=$(docker info --format '{{ .DockerRootDir }}' 2> /dev/null) || true

	echo "${docker_dir}"
}

get_image_name()
{
	local image_id="${1}"
	local engine_version="${2:-}"
	local engine_config="${3:-}"

	if [ -n "${engine_version}" ]; then
		engine_version="_${engine_version}"
	fi

	if [ -n "${engine_config}" ]; then
		engine_config="_${engine_config}"
	fi

	local image_version
	if [ "${DEVELOPMENT_MODE}" = 'true' ]; then
		image_version="development"
	else
		image_version="${VERSION_MAJOR}.${VERSION_MINOR}.${VERSION_PATCH}"

		if [ -n "${VERSION_PRE_RELEASE}" ]; then
			image_version="${image_version}-${VERSION_PRE_RELEASE}"
		fi
	fi

	if [ -n "${OPERATING_SYSTEM_NAME}" ]; then
		image_version="${image_version}_${OPERATING_SYSTEM_NAME}"

		if [ -n "${OPERATING_SYSTEM_VERSION}" ]; then
			image_version="${image_version}_${OPERATING_SYSTEM_VERSION}"
		fi
	fi
	echo "${IMAGE_PREFIX}-${image_id}${engine_version}${engine_config}:${image_version}"
	return 0
}

image_exists()
{
	local image_tag="${1}"	

	if ! docker image inspect "${image_tag}" > /dev/null 2>&1 ; then
		return 1
	fi

	return 0
}

is_rootless_runtime()
{
	if docker info --format '{{ .SecurityOptions }}' | grep --quiet 'rootless' ; then
		return 0
	fi

	return 1
}

# --- FILESYSTEM FUNCTIONS ---

to_absolute_path()
{
	local relative_path="${1}"
	local resolve_symlinks="${2:-false}"

	if ! [ "${resolve_symlinks}" = 'true' ] ; then
		case ${relative_path} in
			(/*)
				echo "${relative_path}"
				return 0
				;;
		esac
	fi

	local absolute_path
	absolute_path=$(realpath --canonicalize-missing "${relative_path}")

	if [ "${resolve_symlinks}" = 'true' ] ; then
		while true ; do
			if ! [ -e "${absolute_path}" ] || ! [ -L "${absolute_path}" ]; then
				break
			fi

			absolute_path=$(realpath --canonicalize-missing "${absolute_path}")
		done
	fi

	echo "${absolute_path}"
	return 0	
}

# --- INTERNAL FUNCTIONS ---

calculate_user_namespace()
{
	local subid_type="${1}"
	local parent_name="${2}"

	local starting_subid
	starting_subid=$(cat "/etc/sub${subid_type}id" | awk -F ':' "/^${parent_name}:[0-9]+:[0-9]+\$/{print \$2;exit}")

	echo "${starting_subid}"
	return 0
}

check_docker()
{
	if ! command -v docker > /dev/null 2>&1 ; then
 		throw_error "${MESSAGES_MISSING_DOCKER}"
 	fi
}

check_cli()
{
	check_image "${IMAGES_CLI}" 'cli'
}

check_image()
{
	local image_id="${1}"
	local build_stage="${2}"

	local image_name
	image_name=$(get_image_name "${image_id}")

	if ! image_exists "${image_name}" ; then

		build_image "${image_name}" "${build_stage}"

		if ! image_exists "${image_name}" ; then
			throw_error "${MESSAGES_ERROR_BUILD_IMAGE}" "${image_name}"
		fi
	fi
}

check_nvidia_docker()
{
	if ! command -v nvidia-container-toolkit > /dev/null 2>&1 ; then
		throw_error "${MESSAGE_MISSING_NVIDIA_DOCKER}"
	fi
}

check_python()
{
	if command -v python3 > /dev/null 2>&1; then
		PYTHON_BIN_FILE='python3'
	elif command -v python > /dev/null 2>&1; then
		PYTHON_BIN_FILE='python'
	else
		throw_error "${MESSAGES_MISSING_PYTHON}"
	fi
}

extract_substring()
{
	local string="${1}"
	local delimiter="${2}"
	local index="${3}"

	substring=$(echo "${string}" | awk \
		-F "${delimiter}" \
		-v i="${index}" \
		'{ value = $i; gsub(" ", "", value); print value; exit }'
	)

	echo "${substring}"
}

get_gpu_driver()
{
	local gpu_driver
	gpu_driver=$(lspci -vmmnk | awk '/^Class:[[:space:]]+0300$/{is_vga=1;next}; is_vga && /^Driver:/{print $2;exit}')

	echo "${gpu_driver}"
}

get_os_family()
{
	local os_name
	os_name=$(uname -s)

	local os_family
	case ${os_name} in
		('Darwin')
			os_family="${OS_FAMILIES_MAC}"
			;;

		('Linux')
			os_family="${OS_FAMILIES_LINUX}"
			;;

		(*)
			throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${os_family}"
			;;
	esac

	echo "${os_family}"
	return 0
}

init_globals()
{
	readonly VERSION_MAJOR='0'
	readonly VERSION_MINOR='2'
	readonly VERSION_PATCH='0'
	readonly VERSION_PRE_RELEASE='wip'

	if [ "${VERSION_PRE_RELEASE}" = 'wip' ]; then
		if [ -z "${O3TANKS_DEV_MODE:-}" ]; then
			O3TANKS_DEV_MODE='true'
		fi
	fi

	readonly DEBUG=1
	readonly INFO=2
	readonly WARNING=3
	readonly ERROR=4

	local bin_file
	bin_file=$(to_absolute_path "${0}" 'true')
	if ! [ -f "${bin_file}" ]; then
		throw_error "${MESSAGES_INVALID_SYMLINK}" "${0}"
	fi
	readonly BIN_FILE="${bin_file}"
	readonly BIN_NAME=$(basename "${BIN_FILE}")

	local bin_dir
	bin_dir=$(dirname "${bin_file}")
	if ! [ -d "${bin_dir}" ]; then
		throw_error "${MESSAGES_BIN_DIR_NOT_FOUND}"
	fi
	readonly BIN_DIR="${bin_dir}"

	local is_development
	is_development=$(is_env_active "${O3TANKS_DEV_MODE:-}")
	readonly DEVELOPMENT_MODE="${is_development}"

	local display_id="${O3TANKS_DISPLAY_ID:-}"
	if [ -z "${display_id}" ]; then
		display_id="${DISPLAY:-}"
	fi
	case ${display_id} in
		(:*)
			display_id="${display_id#:}"
			;;
	esac
	readonly DISPLAY_ID="${display_id}"

	readonly COMMANDS_BUILD='build'
	readonly COMMANDS_CLEAN='clean'
	readonly COMMANDS_INIT='init'
	readonly COMMANDS_OPEN='open'
	readonly COMMANDS_RUN='run'
	readonly COMMANDS_SETTINGS='settings'

	readonly IMAGE_PREFIX='o3tanks'
	readonly IMAGES_CLI='cli'

	readonly MESSAGES_BIN_DIR_NOT_FOUND=1
	readonly MESSAGES_INVALID_DIRECTORY=2
	readonly MESSAGES_INVALID_OPERATING_SYSTEM=3
	readonly MESSAGES_INVALID_SYMLINK=4
	readonly MESSAGES_INVALID_USER_NAMESPACE=5
	readonly MESSAGES_MISSING_DOCKER=6
	readonly MESSAGES_MISSING_NVIDIA_DOCKER=7
	readonly MESSAGES_MISSING_PYTHON=8
	readonly MESSAGES_UNSUPPORTED_CONTAINTERS_MODE=9
	readonly MESSAGES_VOLUMES_DIR_NOT_FOUND=10

	readonly OS_FAMILIES_LINUX=1
	readonly OS_FAMILIES_MAC=2

	readonly OS_NAMES_ARCH='arch'
	readonly OS_NAMES_UBUNTU='ubuntu'

	readonly SHORT_OPTION_PROJECT='p'
	readonly LONG_OPTION_PROJECT='project'

	local host_os_family
	host_os_family=$(get_os_family)
	readonly HOST_OPERATING_SYSTEM="${host_os_family}"

	local no_containers_default
	if [ "${HOST_OPERATING_SYSTEM}" = "${OS_FAMILIES_MAC}" ]; then
		no_containers_default='true'
	else
		no_containers_default='false'
	fi

	local run_containers_all
	local run_containers_cli
	run_containers_all=$(is_env_inactive "${O3TANKS_NO_CONTAINERS:-$no_containers_default}")
	if [ "${run_containers_all}" = 'false' ]; then
		run_containers_cli='false'
	else
		if [ "${HOST_OPERATING_SYSTEM}" = "${OS_FAMILIES_MAC}" ]; then
			throw_error "${MESSAGES_UNSUPPORTED_CONTAINTERS_MODE}" "MacOS"
		fi

		run_containers_cli=$(is_env_inactive "${O3TANKS_NO_CLI_CONTAINER:-}")
	fi
	readonly RUN_CONTAINERS_ALL=${run_containers_all}
	readonly RUN_CONTAINERS_CLI="${run_containers_cli}"

	local os_family
	local os_name
	local os_version
	if [ "${RUN_CONTAINERS_ALL}" = 'true' ]; then
		os_family="${OS_FAMILIES_LINUX}"

		local os_value="${O3TANKS_CONTAINER_OS:-}"
		if [ -n "${os_value}" ]; then
			os_name=$(extract_substring "${os_value}" ':' '1')
			os_version=$(extract_substring "${os_value}" ':' '2')
		else
			os_name="${OS_NAMES_UBUNTU}"
			os_version='20.04'
		fi
	else
		os_family=''
		os_name=''
		os_version=''
	fi
	readonly OPERATING_SYSTEM_FAMILY="${os_family}"
	readonly OPERATING_SYSTEM_NAME="${os_name}"
	readonly OPERATING_SYSTEM_VERSION="${os_version}"

	local host_user_name
	local host_user_group
	local host_user_uid
	local host_user_gid
	host_user_name=$(id --user --real --name)
	host_user_group=$(id --group --real --name)
	host_user_uid=$(id --user --real)
	host_user_gid=$(id --group --real)
	readonly HOST_USER_NAME="${host_user_name}"
	readonly HOST_USER_GROUP="${host_user_group}"
	readonly HOST_USER_GID="${host_user_gid}"
	readonly HOST_USER_UID="${host_user_uid}"

	readonly USER_NAME='user'
	readonly USER_GROUP="${USER_NAME}"
	readonly USER_UID="${host_user_uid}"
	readonly USER_GID="${host_user_gid}"

	local real_user_name
	local real_user_group
	local real_user_uid
	local real_user_gid
	if [ "${RUN_CONTAINERS_CLI}" = 'true' ] && is_rootless_runtime ; then
		real_user_name='o3tanks'
		real_user_group="${real_user_name}"

		local starting_subuid
		local starting_subgid
		starting_subuid=$(calculate_user_namespace 'u' "${HOST_USER_NAME}")
		starting_subgid=$(calculate_user_namespace 'g' "${HOST_USER_GROUP}")
		if [ -z "${starting_subuid}" ] || [ -z "${starting_subgid}" ]; then
			throw_error "${MESSAGES_INVALID_USER_NAMESPACE}"
		fi

		real_user_uid=$((starting_subuid+host_user_uid-1))
		real_user_gid=$((starting_subgid+host_user_gid-1))
	else
		real_user_name="${HOST_USER_NAME}"
		real_user_group="${HOST_USER_GROUP}"
		real_user_uid="${HOST_USER_UID}"
		real_user_gid="${HOST_USER_GID}"
	fi
	readonly REAL_USER_NAME="${real_user_name}"
	readonly REAL_USER_GROUP="${real_user_group}"
	readonly REAL_USER_UID="${real_user_uid}"
	readonly REAL_USER_GID="${real_user_gid}"

	readonly O3DE_ROOT_DIR="/home/${USER_NAME}/o3de"
	readonly O3DE_PROJECT_DIR="${O3DE_ROOT_DIR}/project"

	readonly RECIPES_PATH='recipes'
	readonly SCRIPTS_PATH="${RECIPES_PATH}/o3tanks"

	readonly DATA_DIR="${O3TANKS_DATA_DIR:-}"
	readonly RECIPES_DIR="/home/${USER_NAME}/o3tanks_recipes"
	readonly SCRIPTS_DIR="/home/${USER_NAME}/o3tanks"
}

run_cli()
{
	if [ "${RUN_CONTAINERS_CLI}" = 'false' ]; then
		check_python
		
		export PYTHONPATH="${BIN_DIR}/${RECIPES_PATH}:${PYTHONPATH:-}"
		if [ -n "${DISPLAY_ID}" ]; then
			export O3TANKS_DISPLAY_ID="${DISPLAY_ID}"
		fi
		if [ "${RUN_CONTAINERS_ALL}" = 'false' ]; then
			export O3TANKS_NO_CONTAINERS='true'
		fi
		if [ -n "${DATA_DIR}" ]; then
			export O3TANKS_DATA_DIR="${DATA_DIR}"
		fi

		"${PYTHON_BIN_FILE}" -m "o3tanks.cli" "$0" "${BIN_FILE}" "-" "$@"
		return
	fi
	
	check_docker
	check_cli

	local docker_socket="/run/user/${HOST_USER_UID}/docker.sock"
	if ! [ -S "${docker_socket}" ]; then
		docker_socket="/run/docker.sock"

		if ! [ -S "${docker_socket}" ]; then
			throw_error "${MESSAGES_MISSING_DOCKER}"
		fi
	fi

	local docker_root_dir
	docker_root_dir=$(get_docker_dir)

	local docker_volumes_dir
	docker_volumes_dir="${docker_root_dir}/volumes"
	if ! [ -d "${docker_volumes_dir}" ]; then
		throw_error "${MESSAGES_VOLUMES_DIR_NOT_FOUND}"
	fi

	local project_mount
	case ${1:-} in
		("${COMMANDS_INIT}"|"${COMMANDS_BUILD}"|"${COMMANDS_CLEAN}"|"${COMMANDS_OPEN}"|"${COMMANDS_RUN}"|"${COMMANDS_SETTINGS}")
			local command="${1}"
			local new_args=''

			local project_dir=''
			local is_project_option='false'

			shift
			for arg in $@; do
				if [ "${is_project_option}" = 'true' ] && [ -z "${project_dir}" ]; then
					project_dir="${arg}"
					continue
				fi

				case ${arg} in
					("-${SHORT_OPTION_PROJECT}"|"--${LONG_OPTION_PROJECT}")
						is_project_option='true'
						;;

					(*)
						new_args="${new_args} ${arg}"
						;;
				esac
			done

			if [ "${is_project_option}" = 'false' ]; then
				project_dir='.'
			fi

			project_dir=$(to_absolute_path "${project_dir}" 'true')
			if ! [ -d "${project_dir}" ]; then
				throw_error "${MESSAGES_INVALID_DIRECTORY}" "${project_dir}"
			fi

			set -- "${command}" "--${LONG_OPTION_PROJECT}" "${project_dir}" ${new_args}

			project_mount="--mount type=bind,source=${project_dir},destination=${O3DE_PROJECT_DIR}"
			;;	

		(*)
			project_mount=''
			;;
	esac

	local dev_mount
	local dev_env
	if [ "${DEVELOPMENT_MODE}" = 'true' ]; then
		dev_mount="--mount type=bind,source=${BIN_DIR}/${RECIPES_PATH},destination=${RECIPES_DIR}"
		dev_mount="${dev_mount} --mount type=bind,source=${BIN_DIR}/${SCRIPTS_PATH},destination=${SCRIPTS_DIR}"

		dev_env="--env O3TANKS_DEV_MODE=true"
	else
		dev_mount=''
		dev_env=''
	fi

	local display_env
	if [ -n "${DISPLAY_ID}" ]; then
		display_env="--env O3TANKS_DISPLAY_ID=${DISPLAY_ID}"
	else
		display_env=''
	fi

	local gpu_env
	case ${1:-} in
		("${COMMANDS_OPEN}"|"${COMMANDS_RUN}")
			local gpu_driver
			gpu_driver=$(get_gpu_driver)

			if [ -n "${gpu_driver}" ]; then
				if [ "${gpu_driver}" = "nvidia" ]; then
					check_nvidia_docker
				fi

				gpu_env="--env O3TANKS_GPU=${gpu_driver}"
			else
				gpu_env=''
			fi
			;;

		(*)
			gpu_env=''
			;;
	esac

	local it_options
	if is_tty ; then
		it_options='--interactive --tty'
	else
		it_options=''
	fi

	local cli_image
	cli_image=$(get_image_name "${IMAGES_CLI}")

	docker run --rm ${it_options} \
		--network=none \
		--mount "type=bind,source=${docker_socket},destination=/run/docker.sock" \
		--mount "type=bind,source=${docker_volumes_dir},destination=/var/lib/docker/volumes" \
		--env O3TANKS_REAL_USER_NAME="${REAL_USER_NAME}" \
		--env O3TANKS_REAL_USER_GROUP="${REAL_USER_GROUP}" \
		--env O3TANKS_REAL_USER_UID="${REAL_USER_UID}" \
		--env O3TANKS_REAL_USER_GID="${REAL_USER_GID}" \
		${dev_env} \
		${dev_mount} \
		${display_env} \
		${gpu_env} \
		${project_mount} \
		"${cli_image}" \
		"$0" "${BIN_FILE}" "${docker_root_dir}" "$@"
}

# --- MAIN ---

main()
{
	init_globals "$@"

	run_cli "$@"
}

main "$@"
