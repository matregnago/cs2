#!/bin/bash

# plugins download
metamod_download_url="$(curl https://api.github.com/repos/alliedmodders/metamod-source/releases | jq -r '.[0] | .assets[].browser_download_url | select(contains ("linux"))')"
cssharp_download_url="$(curl https://api.github.com/repos/roflmuffin/CounterStrikeSharp/releases/latest | jq -r '.assets[].browser_download_url | select(contains ("runtime-linux"))')"
matchzy_download_url="$(curl https://api.github.com/repos/shobhit-pathak/MatchZy/releases/latest | jq -r '.assets[].browser_download_url | select(contains ("cssharp") | not)')"
inv_sim_download_url="$(curl https://api.github.com/repos/ianlucas/cs2-css-inventory-simulator/releases/latest | jq -r '.assets[].browser_download_url')"

mods_dir="mods"
rm -rf "$mods_dir"
mkdir "$mods_dir"

wget -O "${mods_dir}/metamod.tar.gz" "$metamod_download_url"
wget -O "${mods_dir}/cssharp.zip" "$cssharp_download_url"
wget -O "${mods_dir}/matchzy.zip" "$matchzy_download_url"
wget -O "${mods_dir}/inv_sim.zip" "$inv_sim_download_url"

csgo_dir="csgo"
mkdir -p "$csgo_dir"

tar -xf "${mods_dir}/metamod.tar.gz" -C "$csgo_dir"
unzip -o "${mods_dir}/cssharp.zip" -d "$csgo_dir"
unzip -o "${mods_dir}/matchzy.zip" -d "$csgo_dir"
unzip -o "${mods_dir}/inv_sim.zip" -d "$csgo_dir"

rm -rf "$mods_dir"

# config cssharp to support the inventory simulator plugin
css_config_dir="${csgo_dir}/addons/counterstrikesharp/configs"
css_core_example="${css_config_dir}/core.example.json"
css_core="${css_config_dir}/core.json"

cat "$css_core_example" | jq '.FollowCS2ServerGuidelines = false' > $css_core

# copy my matchzy settings
cp -r "cfg" "$csgo_dir/"

# patch gameinfo
# Credits to: https://github.com/kus/cs2-modded-server/blob/8c8f89b1fbdb50033430c0eb5a5257a6d8c813af/scripts/patch-gameinfo.sh

# Define the file name
FILE="game/csgo/gameinfo.gi"

# Define the pattern to search for and the line to add
PATTERN="Game_LowViolence[[:space:]]*csgo_lv // Perfect World content override"
LINE_TO_ADD="\t\t\tGame\tcsgo/addons/metamod"

# Use a regular expression to ignore spaces when checking if the line exists
REGEX_TO_CHECK="^[[:space:]]*Game[[:space:]]*csgo/addons/metamod"

# Check if the line already exists in the file, ignoring spaces
if grep -qE "$REGEX_TO_CHECK" "$FILE"; then
    echo "The line is already in the file."
else
    # If the line isn't there, use awk to add it after the pattern
    awk -v pattern="$PATTERN" -v lineToAdd="$LINE_TO_ADD" '{
        print $0;
        if ($0 ~ pattern) {
            print lineToAdd;
        }
    }' "$FILE" > tmp_file && mv tmp_file "$FILE"
    echo "Line added successfully."
fi

echo "pre-hook: noop"
