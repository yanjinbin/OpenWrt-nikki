#!/bin/sh

# Install LuCI/RPC changes from this fork without rebuilding packages.

set -e

RAW_BASE="${NIKKI_RAW_BASE:-https://github.com/yanjinbin/OpenWrt-nikki/raw/refs/heads/main}"
GITHUB_PROXY="${GITHUB_PROXY:-https://gh-proxy.com/}"

raw_url() {
	if [ -n "$GITHUB_PROXY" ]; then
		printf "%s%s/%s" "$GITHUB_PROXY" "$RAW_BASE" "$1"
	else
		printf "%s/%s" "$RAW_BASE" "$1"
	fi
}

download() {
	local source_path="$1"
	local target_path="$2"
	local tmp_path="${target_path}.tmp"

	echo "download $source_path"
	mkdir -p "$(dirname "$target_path")"
	wget -O "$tmp_path" "$(raw_url "$source_path")"
	mv -f "$tmp_path" "$target_path"
	chmod 0644 "$target_path"
}

download "luci-app-nikki/htdocs/luci-static/resources/tools/nikki.js" \
	"/www/luci-static/resources/tools/nikki.js"

download "luci-app-nikki/htdocs/luci-static/resources/view/nikki/profile.js" \
	"/www/luci-static/resources/view/nikki/profile.js"

download "luci-app-nikki/root/usr/share/rpcd/ucode/luci.nikki" \
	"/usr/share/rpcd/ucode/luci.nikki"

echo "restart rpcd and uhttpd"
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart

echo "clear luci cache"
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache

echo "success"
