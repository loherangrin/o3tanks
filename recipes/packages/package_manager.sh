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

		("${MESSAGES_INVALID_ARGUMENTS}")
			echo 'One or more argument are missing.\nSyntax: <category> <section> [<other_section> ...]'
			;;

		("${MESSAGES_INVALID_CATEGORY}")
			echo 'Invalid category: %s'
			;;

		("${MESSAGES_INVALID_COMMAND}")
			echo 'Invalid command: %s'
			;;

		("${MESSAGES_INVALID_EXTERNAL_REPOSITORY}")
			echo 'Unable to parse the external repository for a package: %s'
			;;

		("${MESSAGES_INVALID_OPERATING_SYSTEM}")
			echo 'Unsupported operating system: %s'
			;;

		("${MESSAGES_MISSING_CFG}")
			echo "Unable to retrieve a configuration file for '%s' packages on '${OPERATING_SYSTEM_NAME} ${OPERATING_SYSTEM_VERSION}' operating system"
			;;

		("${MESSAGES_MISSING_KEYRING}")
			echo "Unable to find the keyring at '%s' for the repository '%s'"
			;;

		("${MESSAGES_MISSING_OPERATING_SYSTEM}")
			echo 'Unable to calculate the current operating system'
			;;

		("${MESSAGES_MISSING_PYTHON}")
			echo "Unable to find 'python' or 'python3'"
			;;

		(*)
			echo "${message_id}"
			;;
	esac

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

# --- APT FUNCTIONS ---

add_apt_repository()
{
	local repository_name="${1}"
	local repository_url="https://${2}"

	local source_file="/etc/apt/sources.list.d/${repository_name}.list"
	if [ -f "${source_file}" ]; then
		return 0
	fi

	local prerequisite='ca-certificates'
	if ! is_apt_package_installed "${prerequisite}"; then
		apt-get update
		apt-get install -y --no-install-recommends \
			"${prerequisite}"
	fi

	local keyring_file="/usr/share/keyrings/${repository_name}-archive-keyring.gpg"
	if ! [ -f "${keyring_file}" ]; then
		throw_error "${MESSAGES_MISSING_KEYRING}" "${keyring_file}" "${repository_url}"
	fi

	echo \
		"deb [signed-by=${keyring_file}] ${repository_url} ${OPERATING_SYSTEM_CODENAME} main" \
	> "${source_file}"

	echo "${source_file}"
}

is_apt_package_installed()
{
	local package_name="${1}"

	local status
	status=$(dpkg-query --show --showformat='${db:Status-Status}' "${package_name}" 2> /dev/null)

	if ! [ "${status}" = 'installed' ]; then
		return 1
	fi

	return 0
}

port_apt_package()
{
	local repository="${1}"
	local package="${2}"

	local generated_files
	local other_source_file="/etc/apt/sources.list.d/${repository}.list"
	if ! [ -f "${other_source_file}" ]; then
		local main_source_file="/etc/apt/sources.list"

		cp "${main_source_file}" "${other_source_file}"
		sed --in-place "s/${OPERATING_SYSTEM_CODENAME}/${repository}/g" "${other_source_file}"

		generated_files="${other_source_file}"
	else
		generated_files=''
	fi

	local pinning_file="/etc/apt/preferences.d/${repository}"
	
	local is_first_pin
	local tmp_pinning_file="${pinning_file}"
	if ! [ -f "${pinning_file}" ]; then
		is_first_pin='true'
	else
		is_first_pin='false'
		tmp_pinning_file="${tmp_pinning_file}.tmp"
	fi

	echo \
			"Package: ${package}\n" \
			"Pin: release n=${repository}\n" \
			'Pin-Priority: 990\n' \
			'' \
		> "${tmp_pinning_file}"
	
	if [ "${is_first_pin}" = 'true' ]; then
		echo \
				'Package: *\n' \
				"Pin: release n=${repository}\n" \
				'Pin-Priority: -1\n' \
			>> "${pinning_file}"

		generated_files="${generated_files} ${pinning_file}"
	else
		cat "${pinning_file}" >> "${tmp_pinning_file}"
		mv "${tmp_pinning_file}" "${pinning_file}"
	fi

	echo "${generated_files}"
}

# --- PYTHON FUNCTIONS ---

is_python_module_installed()
{
	local module_name="${1}"

	if ! ${PYTHON_BIN_FILE} -c "import ${module_name}" > /dev/null 2>&1 ; then
		return 1
	fi

	return 0
}

# --- INTERNAL FUNCTIONS ---

check_python()
{
	local python_bin_file
	if command -v python3 > /dev/null 2>&1 ; then
		python_bin_file='python3'
	elif command -v python > /dev/null 2>&1 ; then
		python_bin_file='python'
	else
		throw_error "${MESSAGES_MISSING_PYTHON}"
	fi

	readonly PYTHON_BIN_FILE="${python_bin_file}"
}

get_os_attribute()
{
	local os_attribute="${1}"
	local os_file="${2:-/etc/os-release}"

	awk \
		-F '=' \
		-v attribute="${os_attribute}" \
		'($1 == attribute) { value = tolower($2); gsub("\"", "", value); print value; exit }' \
		"${os_file}"
}

init_globals()
{
	readonly DEBUG=1
	readonly INFO=2
	readonly WARNING=3
	readonly ERROR=4

	readonly BIN_FILE="${0}"

	local bin_dir
	bin_dir=$(dirname "${BIN_FILE}")
	if ! [ -d "${bin_dir}" ]; then
		throw_error "${MESSAGES_BIN_DIR_NOT_FOUND}"
	fi
	readonly BIN_DIR="${bin_dir}"

	readonly CATEGORIES_PYTHON='python'
	readonly CATEGORIES_SYSTEM='system'

	readonly COMMANDS_HINT='hint'
	readonly COMMANDS_INSTALL='install'

	readonly MESSAGES_BIN_DIR_NOT_FOUND=1
	readonly MESSAGES_INVALID_ARGUMENTS=2
	readonly MESSAGES_INVALID_CATEGORY=3
	readonly MESSAGES_INVALID_COMMAND=4
	readonly MESSAGES_INVALID_EXTERNAL_REPOSITORY=5
	readonly MESSAGES_INVALID_OPERATING_SYSTEM=6
	readonly MESSAGES_MISSING_CFG=7
	readonly MESSAGES_MISSING_KEYRING=8
	readonly MESSAGES_MISSING_OPERATING_SYSTEM=9
	readonly MESSAGES_MISSING_PYTHON=10

	local os_name
	os_name=$(get_os_attribute 'ID')
	if [ -z "${os_name}" ]; then
		throw_error "${MESSAGES_MISSING_OPERATING_SYSTEM}"
	fi
	OPERATING_SYSTEM_NAME="${os_name}"

	local os_version
	os_version=$(get_os_attribute 'VERSION_ID')
	OPERATING_SYSTEM_VERSION="${os_version}"

	local os_codename
	os_codename=$(get_os_attribute 'VERSION_CODENAME')
	OPERATING_SYSTEM_CODENAME="${os_codename}"

	OPERATING_SYSTEM_FALLBACK='false'

	readonly OPERATING_SYSTEMS_UBUNTU='ubuntu'
}

install_packages()
{
	local manual_installation="${1}"
	local category="${2}"
	shift
	shift

	local os_architecture
	local package_manager

	local search_command
	local setup_command
	local refresh_command
	local install_command
	local clean_command

	case ${category} in
		("${CATEGORIES_PYTHON}")
			check_python

			search_command="is_python_module_installed"
			setup_command=''
			refresh_command=''
			clean_command=''
			install_command="${PYTHON_BIN_FILE} -m pip install"
			if [ "${manual_installation}" = 'false' ]; then
				install_command="${install_command} --no-cache-dir"
			fi
			;;

		("${CATEGORIES_SYSTEM}")
			case ${OPERATING_SYSTEM_NAME} in
				("${OPERATING_SYSTEMS_UBUNTU}")
					os_architecture=$(dpkg --print-architecture)
					package_manager='apt'

					search_command='is_apt_package_installed'
					if [ "${manual_installation}" = 'true' ]; then
						setup_command=''
						refresh_command='apt update'
						install_command='apt install'
						clean_command=''
					else
						setup_command='export DEBIAN_FRONTEND=noninteractive'
						refresh_command='apt-get update'
						install_command='apt-get install -y --no-install-recommends'
						clean_command='rm --force --recursive /var/lib/apt/lists/*'
					fi
					;;

				(*)
					throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${OPERATING_SYSTEM_NAME}"
					;;
			esac
			;;

		(*)
			throw_error "${MESSAGES_INVALID_CATEGORY}" "${category}"
			;;
	esac

	local missing_packages
	local added_packages
	local ported_packages
	local version_operator

	if [ "${category}" = "${CATEGORIES_SYSTEM}" ]; then
		missing_packages=''
		added_packages=''
		ported_packages=''
		version_operator='='

		for package in "$@" ; do
			if [ "${manual_installation}" = 'true' ]; then
				local package_name
				package_name=$(extract_substring "${package}" "${version_operator}" '1')

				if ${search_command} "${package_name}" ; then
					continue
				fi
			fi

			case ${package} in
				(*${version_operator}${package_manager}:*)
					added_packages="${added_packages} ${package}"
					;;

				(*${version_operator}${OPERATING_SYSTEM_NAME}:*)
					ported_packages="${ported_packages} ${package}"
					;;

				(*)
					missing_packages="${missing_packages} ${package}"
					;;
			esac
		done

	elif [ "${category}" = "${CATEGORIES_PYTHON}" ]; then
		added_packages=''
		ported_packages=''
		version_operator='=='

		if [ "${manual_installation}" = 'true' ]; then
			missing_packages=''

			for package in "$@" ; do
				local package_name
				package_name=$(extract_substring "${package}" "${version_operator}" '1')

				if ${search_command} "${package_name}" ; then
					continue
				fi

				missing_packages="${missing_packages} ${package}"
			done
		else
			missing_packages="$@"
		fi

	else
		throw_error "${MESSAGES_INVALID_CATEGORY}" "${category}"
	fi

	if [ -n "${missing_packages}" ]; then
		if [ "${manual_installation}" = 'true' ]; then
			if [ "${category}" = "${CATEGORIES_SYSTEM}" ]; then
				echo 'main'
			fi

			if [ -n "${setup_command}" ]; then
				echo "${setup_command}"
			fi

			if [ -n "${refresh_command}" ]; then
				echo "${refresh_command}"
			fi

			echo "${install_command}${missing_packages}"

			if [ -n "${clean_command}" ]; then
				echo "${clean_command}"
			fi
		else
			if [ -n "${setup_command}" ]; then
				${setup_command}
			fi

			if [ -n "${refresh_command}" ]; then
				${refresh_command}
			fi

			${install_command} ${missing_packages}
		fi
	fi

	if [ -n "${added_packages}" ]; then
		install_added_packages "${manual_installation}" "${refresh_command}" "${install_command}" "${version_operator}" ${added_packages}
	fi

	if [ -n "${ported_packages}" ]; then
		install_ported_packages "${manual_installation}" "${refresh_command}" "${install_command}" "${version_operator}" ${ported_packages}
	fi

	if [ -n "${clean_command}" ] && [ "${manual_installation}" = 'false' ]; then
		${clean_command}
	fi

	if [ "${OPERATING_SYSTEM_FALLBACK}" = 'true' ] && [ "${category}" = "${CATEGORIES_SYSTEM}" ]; then
		echo 'fallback'
	fi
}

install_added_packages()
{
	local manual_installation="${1}"
	local refresh_command="${2}"
	local install_command="${3}"
	local version_operator="${4}"
	shift
	shift
	shift
	shift

	if [ $# -eq 0 ]; then
		return 0
	fi

	if [ "${manual_installation}" = 'true' ]; then
		echo 'external'
	fi

	local packages=''
	local clean_files=''
	for package in "$@" ; do
		local repository_name
		repository_name=$(extract_substring "${package}" ':' '2')
		
		local repository_url
		repository_url=$(extract_substring "${package}" ':' '3')

		local package_name
		package_name=$(extract_substring "${package}" "${version_operator}" '1')

		if [ -z "${repository_name}" ] || [ -z "${repository_url}" ] || [ -z "${package_name}" ]; then
			throw_error "${MESSAGES_INVALID_EXTERNAL_REPOSITORY}" "${package}"
		fi

		local package_version
		package_version=$(extract_substring "${package}" ':' '4')

		package_reference="${package_name}"
		if [ -n "${package_version}" ]; then
			package_reference="${package_reference}${version_operator}${package_version}"
		fi

		if [ "${manual_installation}" = 'true' ]; then
			case ${OPERATING_SYSTEM_NAME} in
				("${OPERATING_SYSTEMS_UBUNTU}")
					echo "https://${repository_url} ${install_command} ${package_reference}"
					;;

				(*)
					throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${OPERATING_SYSTEM_NAME}"
					;;
			esac
		else
			case ${OPERATING_SYSTEM_NAME} in
				("${OPERATING_SYSTEMS_UBUNTU}")
					local configured='false'
					local config_files
					config_files=$(add_apt_repository "${repository_name}" "${repository_url}") && configured='true'

					if [ "${configured}" = 'false' ]; then
						print_msg '' "${config_files}"
						exit 1
					elif [ -n "${config_files}" ]; then
						clean_files="${clean_files} ${config_files}"
					fi
					;;

				(*)
					throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${OPERATING_SYSTEM_NAME}"
					;;
			esac

			packages="${packages} ${package_reference}"
		fi
	done

	if [ "${manual_installation}" = 'false' ]; then
		${refresh_command}
		${install_command}${packages}

		if [ -n "${clean_files}" ]; then
			rm --force ${clean_files}
		fi
	fi
}

install_ported_packages()
{
	local manual_installation="${1}"
	local refresh_command="${2}"
	local install_command="${3}"
	local version_operator="${4}"
	shift
	shift
	shift
	shift

	if [ $# -eq 0 ]; then
		return 0
	fi

	if [ "${manual_installation}" = 'true' ]; then
		echo 'port'
	fi

	local packages=''
	local clean_files=''
	for package in "$@" ; do
		local repository_name
		repository_name=$(extract_substring "${package}" ':' '2')
		
		local package_name
		package_name=$(extract_substring "${package}" "${version_operator}" '1')

		if [ -z "${repository_name}" ] || [ -z "${package_name}" ]; then
			throw_error "${MESSAGES_INVALID_EXTERNAL_REPOSITORY}" "${package}"
		fi

		local package_version
		package_version=$(extract_substring "${package}" ':' '3')

		if [ "${manual_installation}" = 'true' ]; then
			case ${OPERATING_SYSTEM_NAME} in
				("${OPERATING_SYSTEMS_UBUNTU}")
					echo "https://packages.ubuntu.com/${repository_name}/${os_architecture}/${package_name}/download"
					;;

				(*)
					throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${OPERATING_SYSTEM_NAME}"
					;;
			esac
		else
			case ${OPERATING_SYSTEM_NAME} in
				("${OPERATING_SYSTEMS_UBUNTU}")
					local configured='false'
					local config_files
					config_files=$(port_apt_package "${repository_name}" "${package_name}") && configured='true'

					if [ "${configured}" = 'false' ]; then
						print_msg '' "${config_files}"
						exit 1
					elif [ -n "${config_files}" ]; then
						clean_files="${clean_files} ${config_files}"
					fi
					;;

				(*)
					throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${OPERATING_SYSTEM_NAME}"
					;;
			esac

			packages="${packages} ${package_name}"
			if [ -n "${package_version}" ]; then
				packages="${packages}${version_operator}${package_version}"
			fi
		fi
	done

	if [ "${manual_installation}" = 'false' ]; then
		${refresh_command}
		${install_command}${packages}

		if [ -n "${clean_files}" ]; then
			rm --force ${clean_files}
		fi
	fi
}

list_packages()
{
	if [ $# -lt 2 ]; then
		throw_error "${MESSAGES_INVALID_ARGUMENTS}"
	fi

	local category="${1}"
	shift

	local cfg_file
	case ${category} in
		("${CATEGORIES_PYTHON}"|"${CATEGORIES_SYSTEM}")
			local category_dir="${BIN_DIR}/${category}"

			cfg_file="${category_dir}/${OPERATING_SYSTEM_NAME}_${OPERATING_SYSTEM_VERSION}.cfg"

			if [ -z "${OPERATING_SYSTEM_VERSION}" ] || ! [ -f "${cfg_file}" ]; then
				cfg_file="${category_dir}/${OPERATING_SYSTEM_NAME}.cfg"

				if ! [ -f "${cfg_file}" ]; then
					cfg_file="${category_dir}/any.cfg"

					if ! [ -f "${cfg_file}" ]; then
						throw_error "${MESSAGES_MISSING_CFG}" "${category}"
					fi
				fi
			fi
			;;

		(*)
			throw_error "${MESSAGES_INVALID_CATEGORY}" "${category}"
			;;
	esac

	local version_operator
	case ${category} in
		("${CATEGORIES_PYTHON}")
			version_operator='=='
			;;

		(*)
			version_operator='='
			;;
	esac

	local packages_delimiter=' '
	local is_first='1'

	while [ $# -gt 0 ]; do
		local section_name="${1}"
		shift

		awk \
			-v delimiter="${packages_delimiter}" \
			-v is_first="${is_first}" \
			-v operator="${version_operator}" \
			-v section="${section_name}" \
			'
			BEGIN {	section_pattern = "^\\[" section "\\]$"	}
			$0 ~ section_pattern { is_section = 1; next }
			is_section && /^\[/ { is_section = 0; next }
			is_section { printf "%s%s%s%s", (is_first ? "" : delimiter), $1, ($3 != "" ? operator : ""), $3; is_first = 0; next }
			' \
			"${cfg_file}"

		is_first='0'
	done
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

# --- MAIN ---

main()
{
	init_globals

	local command="${1:-}"
	shift

	case ${command} in
		("${COMMANDS_HINT}"|"${COMMANDS_INSTALL}")
			local manual_installation
			if [ "${command}" = "${COMMANDS_HINT}" ]; then
				manual_installation='true'
			else
				manual_installation='false'
			fi

			local default_os_name="${OPERATING_SYSTEMS_UBUNTU}"
			local default_os_version="20.04"
			local default_os_codename="focal"

			local category="${1}"
			while true ; do
				local success='false'
				local packages
				packages=$(list_packages "$@") && success='true'

				if [ "${success}" = 'true' ]; then
					break
				else
					if [ "${manual_installation}" = 'true' ] && [ "${category}" = "${CATEGORIES_SYSTEM}" ] && ( ! [ "${OPERATING_SYSTEM_NAME}" = "${default_os_name}" ] || ! [ "${OPERATING_SYSTEM_VERSION}" = "${default_os_version}" ] ); then
						OPERATING_SYSTEM_NAME="${default_os_name}"
						OPERATING_SYSTEM_VERSION="${default_os_version}"
						OPERATING_SYSTEM_CODENAME="${default_os_codename}"
						OPERATING_SYSTEM_FALLBACK='true'
					else
						print_msg '' "${packages}"
						exit 1
					fi
				fi
			done

			install_packages "${manual_installation}" "${category}" ${packages}
			;;

		(*)
			throw_error "${MESSAGES_INVALID_COMMAND}" "${command}"
			;;
	esac
}

main "$@"
