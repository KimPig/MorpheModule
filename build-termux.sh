#!/usr/bin/env bash

set -euo pipefail

pr() { echo -e "\033[0;32m[+] ${1}\033[0m"; }

repo_dir="${HOME}/MorpheModule"
output_dir="/sdcard/Download/MorpheModule"

pr "Requesting storage permission"
until
	yes | termux-setup-storage >/dev/null 2>&1
	ls /sdcard >/dev/null 2>&1
do sleep 1; done

pr "Installing build dependencies"
yes "" | pkg update -y
pkg install -y git curl jq openjdk-17 python zip unzip

if [ -d "${repo_dir}/.git" ]; then
	pr "Updating MorpheModule"
	git -C "$repo_dir" pull --ff-only
elif [ -e "$repo_dir" ]; then
	echo "ERROR: '$repo_dir' exists but is not a MorpheModule git checkout." >&2
	exit 1
else
	pr "Cloning MorpheModule"
	git clone https://github.com/KimPig/MorpheModule.git "$repo_dir"
fi

cd "$repo_dir"
python -m pip install --disable-pip-version-check -r requirements-apkmirror.txt

pr "Building modules and APKs"
./build.sh config.toml

mkdir -p "$output_dir"
cp -f build/* "$output_dir/"

pr "Outputs are available in $output_dir"
am start -a android.intent.action.VIEW -d "file://${output_dir}" -t resource/folder
