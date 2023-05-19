#!/bin/sh

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


set -eu

# --- I/O FUNCTIONS ---

get_message_text()
{
	case ${message_id} in
		("${MESSAGES_BIN_DIR_NOT_FOUND}")
			echo 'Unable to calculate where the script is running'
			;;

		("${MESSAGES_ERROR_MAKEPKG}")
			echo 'An error occurred while building an AUR package: %s'
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

		("${MESSAGES_INVALID_PACMAN_REPOSITORY}")
			echo "Unsupported external 'pacman' repository for a package: %s"
			;;

		("${MESSAGES_INVALID_ZYPPER_REPOSITORY}")
			echo "Unsupported additional 'zypper' repository for a package: %s"
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
	local repository_url="${2}"
	local keyring_url="${3}"

	local source_file="/etc/apt/sources.list.d/${repository_name}.list"
	if [ -f "${source_file}" ]; then
		return 0
	fi

	local keyring_name="${repository_name}-archive-keyring.gpg"
	local keyring_file="/usr/share/keyrings/${keyring_name}"

	if ! [ -f "${keyring_file}" ]; then
		if ! [ -f "${TMP_DIR}/${keyring_name}" ]; then
			apt-get update > /dev/null
			apt-get install -y --no-install-recommends \
				ca-certificates \
				gnupg \
				wget \
			> /dev/null

			if ! [ -d "${TMP_DIR}" ]; then
				mkdir --parents "${TMP_DIR}"
			fi

			wget \
				--output-document - \
				"${keyring_url}" \
			| gpg --dearmor - > "${TMP_DIR}/${keyring_name}"

			if ! [ -f "${TMP_DIR}/${keyring_name}" ]; then
				throw_error "${MESSAGES_MISSING_KEYRING}" "${TMP_DIR}/${keyring_name}" "${repository_url}"
			fi
		fi

		if [ "${INSTALL_EXTERNAL_PACKAGES}" = 'false' ]; then
			return 0
		fi

		mv "${TMP_DIR}/${keyring_name}" "${keyring_file}"
	fi

	if [ "${INSTALL_EXTERNAL_PACKAGES}" = 'false' ]; then
		return 0
	fi

	apt-get update  > /dev/null
	apt-get install -y --no-install-recommends \
		ca-certificates \
	 > /dev/null

	echo \
		"deb [signed-by=${keyring_file}] ${repository_url} ${OPERATING_SYSTEM_CODENAME} main" \
	> "${source_file}"

	echo "${source_file} ${keyring_file}"
	return 0
}

port_apt_package()
{
	local repository="${1}"
	local package="${2}"

	if [ "${OPERATING_SYSTEM_CODENAME}" = "${repository}" ] || [ "${INSTALL_EXTERNAL_PACKAGES}" = 'false' ]; then
		return 0
	fi

	local generated_files
	local external_source_file="/etc/apt/sources.list.d/${repository}.list"
	if ! [ -f "${external_source_file}" ]; then
		local main_source_file="/etc/apt/sources.list"

		cp "${main_source_file}" "${external_source_file}"
		sed --in-place "s/${OPERATING_SYSTEM_CODENAME}/${repository}/g" "${external_source_file}"

		if [ "${OPERATING_SYSTEM_NAME}" = "${OS_NAMES_DEBIAN}" ]; then
			case ${repository} in
				('buster')
					sed --in-place "s@${repository}-security@${repository}/updates@g" "${external_source_file}"
					;;

				('sid')
					sed --in-place --regexp-extended "s@^.+${repository}[^ ]+ main\$@@g" "${external_source_file}"
					;;
			esac
		fi

		generated_files="${external_source_file}"
	else
		generated_files=''
	fi

	local external_pinning_file="/etc/apt/preferences.d/${repository}"
	
	local is_first_pin
	local tmp_external_pinning_file="${external_pinning_file}"
	if ! [ -f "${external_pinning_file}" ]; then
		is_first_pin='true'
	else
		is_first_pin='false'
		tmp_external_pinning_file="${tmp_external_pinning_file}.tmp"
	fi

	cat <<-EOF > "${tmp_external_pinning_file}"
		Package: ${package}
		Pin: release n=${repository}
		Pin-Priority: 990

		EOF
	
	if [ "${is_first_pin}" = 'true' ]; then
		cat <<-EOF >> "${external_pinning_file}"
			Package: *
			Pin: release n=${repository}
			Pin-Priority: -1
			EOF

		generated_files="${generated_files} ${external_pinning_file}"
	else
		cat "${external_pinning_file}" >> "${tmp_external_pinning_file}"
		mv "${tmp_external_pinning_file}" "${external_pinning_file}"
	fi

	echo "${generated_files}"
	return 0
}

# --- PACMAN FUNCTIONS ---

port_pacman_package()
{
	local repository_name="${1}"
	local package="${2}"

	if ! [ "${repository_name}" = 'aur' ]; then
		throw_error "${MESSAGES_INVALID_PACMAN_REPOSITORY}" "${package}"
	fi

	local package_file="${TMP_DIR}/${package}.pkg.tar.zst"
	if ! [ -f "${package_file}" ]; then
		pacman --sync --noconfirm --needed \
			base-devel \
			tar \
			wget

		local archive_name="${package}.tar.gz"
		local archive_file="${TMP_DIR}/${archive_name}"
		if ! [ -f "${archive_file}" ]; then
			if ! [ -d "${TMP_DIR}" ]; then
				mkdir --parents "${TMP_DIR}"
			fi

			wget \
				--output-document="${archive_file}" \
				https://aur.archlinux.org/cgit/aur.git/snapshot/${archive_name}
		fi

		local previous_cwd=$(pwd)
		local source_dir="${TMP_DIR}/${package}"
		if ! [ -d "${source_dir}" ]; then
			cd "${TMP_DIR}"
			tar --extract -f "${archive_name}"

			local user_name="user"
			local user_group="user"
			chown --recursive "${user_name}:${user_group}" "${package}"
		fi

		local build_file=$(ls "${source_dir}" | grep '.pkg.tar.zst' | head -n 1)
		if ! [ -f "${build_file}" ]; then
			cd "${source_dir}"
			su "${user_name}" -c 'makepkg -f'

			build_file=$(ls "${source_dir}" | grep '.pkg.tar.zst' | head -n 1)

			if ! [ -f "${build_file}" ]; then
				throw_error "${MESSAGES_ERROR_MAKEPKG}" "${package}"
			fi
		fi

		mv "${build_file}" "${package_file}"
		cd "${previous_cwd}"

		rm --force --recursive "${source_dir}"
		rm --force "${archive_file}"
	fi

	if [ "${INSTALL_EXTERNAL_PACKAGES}" = 'false' ]; then
		return
	fi

	pacman --upgrade --noconfirm "${package_file}"

	rm --force "${package_file}"
}

# --- ZYPPER FUNCTIONS ---

add_zypper_repository()
{
	local repository_name="${1}"
	local repository_url="${2}"

	if zypper repos "${repository_url}" > /dev/null 2>&1 || [ "${INSTALL_EXTERNAL_PACKAGES}" = 'false' ]; then
		return 0
	fi

	zypper addrepo "${repository_url}" > /dev/null
	zypper --gpg-auto-import-keys refresh > /dev/null

	repository_alias=$(echo "${repository_name}" | sed 's/:/_/g')

	echo "${repository_alias}"
	return 0
}

# --- PACKAGES FUNCTIONS ---

is_deb_package_installed()
{
	local package_name="${1}"

	local status
	status=$(dpkg-query --show --showformat='${db:Status-Status}' "${package_name}" 2> /dev/null)

	if ! [ "${status}" = 'installed' ]; then
		return 1
	fi

	return 0
}

is_pkg_package_installed()
{
	local package_name="${1}"

	if ! pacman --query "${package_name}" > /dev/null 2>&1; then
		return 1
	fi

	return 0
}

is_rpm_package_installed()
{
	local package_name="${1}"
	local is_collection="${2}"

	if [ "${is_collection}" = 'true' ] && [ "${OPERATING_SYSTEM_NAME}" = "${OS_NAMES_OPENSUSE_LEAP}" ]; then
		local found='false'
		local result
		result=$(zypper --terse --no-refresh info --type pattern "${package_name}" 2> /dev/null | grep 'Installed[[:space:]]\+:[[:space:]]\+Yes') && found='true'

		if [ "${found}" = 'false' ] || [ -z "${result}" ]; then
			return 1
		fi

	elif ! rpm --query "${package_name}" > /dev/null 2>&1; then
		return 1
	fi

	return 0
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
	readonly MESSAGES_ERROR_MAKEPKG=2
	readonly MESSAGES_INVALID_ARGUMENTS=3
	readonly MESSAGES_INVALID_CATEGORY=4
	readonly MESSAGES_INVALID_COMMAND=5
	readonly MESSAGES_INVALID_EXTERNAL_REPOSITORY=6
	readonly MESSAGES_INVALID_OPERATING_SYSTEM=7
	readonly MESSAGES_INVALID_PACMAN_REPOSITORY=8
	readonly MESSAGES_INVALID_ZYPPER_REPOSITORY=9
	readonly MESSAGES_MISSING_CFG=10
	readonly MESSAGES_MISSING_KEYRING=11
	readonly MESSAGES_MISSING_OPERATING_SYSTEM=12
	readonly MESSAGES_MISSING_PYTHON=13

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

	readonly OS_NAMES_ARCH='arch'
	readonly OS_NAMES_DEBIAN='debian'
	readonly OS_NAMES_FEDORA='fedora'
	readonly OS_NAMES_OPENSUSE_LEAP='opensuse-leap'
	readonly OS_NAMES_UBUNTU='ubuntu'

	readonly TMP_DIR="/tmp/o3tanks/packages/external"
}

install_packages()
{
	local manual_installation="${1}"
	local category="${2}"
	shift
	shift

	local package_manager

	local search_command
	local setup_command
	local refresh_command
	local install_collection_command
	local install_package_command
	local clean_command

	case ${category} in
		("${CATEGORIES_PYTHON}")
			check_python

			search_command="is_python_module_installed"
			setup_command=''
			refresh_command=''
			clean_command=''
			install_package_command="${PYTHON_BIN_FILE} -m pip install"
			install_collection_command=''
			if [ "${manual_installation}" = 'false' ]; then
				install_package_command="${install_package_command} --no-cache-dir"
			fi
			;;

		("${CATEGORIES_SYSTEM}")
			case ${OPERATING_SYSTEM_NAME} in
				("${OS_NAMES_ARCH}")
					package_manager='pacman'

					search_command='is_pkg_package_installed'
					setup_command=''
					if [ "${manual_installation}" = 'true' ]; then
						refresh_command=''
						install_package_command='pacman -S'
						clean_command=''
					else
						refresh_command='pacman --sync --refresh'
						install_package_command='pacman --sync --noconfirm --needed'
						clean_command='pacman --sync --noconfirm -cc'
					fi
					install_collection_command="${install_package_command}"
					;;
				
				("${OS_NAMES_DEBIAN}"|"${OS_NAMES_UBUNTU}")
					package_manager='apt'

					search_command='is_deb_package_installed'
					if [ "${manual_installation}" = 'true' ]; then
						setup_command=''
						refresh_command='apt update'
						install_package_command='apt install'
						clean_command=''
					else
						setup_command='export DEBIAN_FRONTEND=noninteractive'
						refresh_command='apt-get update'
						install_package_command='apt-get install --assume-yes --no-install-recommends'
						clean_command='rm --force --recursive /var/lib/apt/lists/*'
					fi
					install_collection_command="${install_package_command}"
					;;

				("${OS_NAMES_FEDORA}")
					package_manager='dnf'

					search_command='is_rpm_package_installed'
					setup_command=''
					if [ "${manual_installation}" = 'true' ]; then
						refresh_command=''
						install_package_command='dnf install'
						clean_command=''
					else
						refresh_command='dnf makecache'
						install_package_command='dnf install --assumeyes --nodocs --setopt install_weak_deps=false'
						clean_command='dnf clean all'
					fi
					install_collection_command="${install_package_command}"
					;;

				("${OS_NAMES_OPENSUSE_LEAP}")
					package_manager='zypper'

					search_command='is_rpm_package_installed'
					setup_command=''
					if [ "${manual_installation}" = 'true' ]; then
						refresh_command=''
						install_package_command='zypper install'
						install_collection_command="${install_package_command} -t pattern"
						clean_command=''
					else
						refresh_command='zypper refresh'
						install_package_command='zypper --no-refresh install --no-confirm --no-recommends'
						install_collection_command="${install_package_command} --type pattern"
						clean_command='zypper clean --all'
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

	local missing_collections
	local missing_packages
	local added_packages
	local ported_packages
	local version_operator

	if [ "${category}" = "${CATEGORIES_SYSTEM}" ]; then
		missing_collections=''
		missing_packages=''
		added_packages=''
		ported_packages=''
		version_operator='='

		for package in "$@" ; do
			local is_collection
			case ${package} in
				(@*)
					is_collection='true'

					if ! [ "${OPERATING_SYSTEM_NAME}" = "${OS_NAMES_FEDORA}" ]; then
						package=$(echo "${package}" | sed 's/^@//g')
					fi
					;;

				(*)
					is_collection='false'
					;;
			esac

			if [ "${manual_installation}" = 'true' ]; then
				local package_name
				package_name=$(extract_substring "${package}" "${version_operator}" '1')

				if ${search_command} "${package_name}" "${is_collection}" ; then
					continue
				fi
			fi

			if [ "${is_collection}" = 'true' ]; then
				missing_collections="${missing_collections} ${package}"
				continue
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
		missing_collections=''
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

	if [ -n "${missing_packages}" ] || [ -n "${missing_collections}" ]; then
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

			if [ -n "${missing_collections}" ]; then
				echo "${install_collection_command}${missing_collections}"
			fi

			if [ -n "${missing_packages}" ]; then
				echo "${install_package_command}${missing_packages}"
			fi

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

			if [ -n "${missing_collections}" ]; then
				${install_collection_command} ${missing_collections}
			fi

			if [ -n "${missing_packages}" ]; then
				${install_package_command} ${missing_packages}
			fi
		fi
	fi

	if [ -n "${added_packages}" ]; then
		install_added_packages "${manual_installation}" "${refresh_command}" "${install_package_command}" "${version_operator}" ${added_packages}
	fi

	if [ -n "${ported_packages}" ]; then
		install_ported_packages "${manual_installation}" "${refresh_command}" "${install_package_command}" "${version_operator}" ${ported_packages}
	fi

	if false && [ -n "${clean_command}" ] && [ "${manual_installation}" = 'false' ]; then
		${clean_command}
	fi

	local xkbcommon_default_dir="/usr/include/xkbcommon"
 	local xkbcommon_alternative_dir="/usr/include/libxkbcommon/xkbcommon"
	if [ -d "${xkbcommon_alternative_dir}" ] && ! [ -e "${xkbcommon_default_dir}" ]; then
		link_command="ln --symbolic ${xkbcommon_alternative_dir} ${xkbcommon_default_dir}"

		if [ "${manual_installation}" = 'true' ]; then
			echo 'other'
			echo "${link_command}"
		else
			${link_command}
		fi
	fi

	if [ "${manual_installation}" = 'true' ] && [ "${OPERATING_SYSTEM_FALLBACK}" = 'true' ] && [ "${category}" = "${CATEGORIES_SYSTEM}" ]; then
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
	local clean_command=''
	local clean_files=''
	for package in "$@" ; do
		local repository_1
		repository_1=$(extract_substring "${package}" ':' '2')
		
		local repository_2
		repository_2=$(extract_substring "${package}" ':' '3')

		local package_name
		package_name=$(extract_substring "${package}" "${version_operator}" '1')

		if [ -z "${repository_1}" ] || [ -z "${repository_2}" ] || [ -z "${package_name}" ]; then
			throw_error "${MESSAGES_INVALID_EXTERNAL_REPOSITORY}" "${package}"
		fi

		local package_version
		package_version=$(extract_substring "${package}" ':' '4')

		package_reference="${package_name}"
		if [ -n "${package_version}" ]; then
			package_reference="${package_reference}${version_operator}${package_version}"
		fi

		local repository_name
		local repository_url
		local keyring_url
		case ${OPERATING_SYSTEM_NAME} in
			("${OS_NAMES_DEBIAN}"|"${OS_NAMES_UBUNTU}")
				repository_name=$(echo "${repository_1}" | sed 's@[/\.]@_@g')
				repository_url="https://${repository_1}"
				keyring_url="https://${repository_2}.asc"
				;;

			("${OS_NAMES_OPENSUSE_LEAP}")
				repository_name=$(echo "${repository_1}" | sed 's@/@:@g')
				repository_url="https://download.opensuse.org/repositories/${repository_name}/openSUSE_${repository_2}/${repository_name}.repo"
				keyring_url=''
				;;

			(*)
				throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${OPERATING_SYSTEM_NAME}"
				;;
		esac

		if [ "${manual_installation}" = 'true' ]; then
			echo "${repository_url} ${install_command} ${package_reference}"
		else
			case ${OPERATING_SYSTEM_NAME} in
				("${OS_NAMES_DEBIAN}"|"${OS_NAMES_UBUNTU}")
					adding_command='add_apt_repository'
					clean_command='rm --force'
					;;

				("${OS_NAMES_OPENSUSE_LEAP}")
					adding_command='add_zypper_repository'
					clean_command='zypper removerepo'
					;;

				(*)
					throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${OPERATING_SYSTEM_NAME}"
					;;
			esac

			local configured='false'
			local config_files
			config_files=$(${adding_command} "${repository_name}" "${repository_url}" "${keyring_url}") && configured='true'

			if [ "${configured}" = 'false' ]; then
				print_msg '' "${config_files}"
				exit 1
			elif [ -n "${config_files}" ]; then
				clean_files="${clean_files} ${config_files}"
			fi

			packages="${packages} ${package_reference}"
		fi
	done

	if [ "${manual_installation}" = 'false' ] && [ "${INSTALL_EXTERNAL_PACKAGES}" = 'true' ]; then
		if [ -n "${packages}" ]; then
			${refresh_command}
			${install_command}${packages}
		fi

		if [ -n "${clean_command}" ] && [ -n "${clean_files}" ]; then
			${clean_command} ${clean_files}
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
	local clean_command='rm --force'
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
			local package_url

			case ${OPERATING_SYSTEM_NAME} in
				("${OS_NAMES_ARCH}")
					package_url="https://aur.archlinux.org/packages/${package_name}"
					;;

				("${OS_NAMES_DEBIAN}")
					package_url="https://packages.debian.org/${repository_name}/${package_name}"
					;;

				("${OS_NAMES_UBUNTU}")
					package_url="https://packages.ubuntu.com/${repository_name}/${package_name}"
					;;

				(*)
					throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${OPERATING_SYSTEM_NAME}"
					;;
			esac

			echo "${package_url}"

		else
			local porting_command
			local exec_subshell
			local skip_package

			case ${OPERATING_SYSTEM_NAME} in
				("${OS_NAMES_ARCH}")
					porting_command='port_pacman_package'
					exec_subshell='false'
					skip_package='true'
					;;

				("${OS_NAMES_DEBIAN}"|"${OS_NAMES_UBUNTU}")
					porting_command='port_apt_package'
					exec_subshell='true'
					skip_package='false'
					;;

				(*)
					throw_error "${MESSAGES_INVALID_OPERATING_SYSTEM}" "${OPERATING_SYSTEM_NAME}"
					;;
			esac

			if [ "${exec_subshell}" = 'true' ]; then
				local configured='false'
				local config_files
				config_files=$(${porting_command} "${repository_name}" "${package_name}") && configured='true'

				if [ "${configured}" = 'false' ]; then
					print_msg '' "${config_files}"
					exit 1
				elif [ -n "${config_files}" ]; then
					clean_files="${clean_files} ${config_files}"
				fi
			else
				${porting_command} "${repository_name}" "${package_name}"
			fi

			if [ "${skip_package}" = 'false' ]; then
				packages="${packages} ${package_name}"
				if [ -n "${package_version}" ]; then
					packages="${packages}${version_operator}${package_version}"
				fi
			fi
		fi
	done

	if [ "${manual_installation}" = 'false' ] && [ "${INSTALL_EXTERNAL_PACKAGES}" = 'true' ]; then
		if [ -n "${packages}" ]; then
			${refresh_command}
			${install_command}${packages}
		fi

		if [ -n "${clean_command}" ] && [ -n "${clean_files}" ]; then
			${clean_command} ${clean_files}
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

			local default_os_name="${OS_NAMES_UBUNTU}"
			local default_os_version="22.04"
			local default_os_codename="jammy"

			local install_external_packages
			if [ "${1}" = '--no-external' ]; then
				install_external_packages='false'
				shift
			else
				install_external_packages='true'
			fi
			readonly INSTALL_EXTERNAL_PACKAGES="${install_external_packages}"

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
