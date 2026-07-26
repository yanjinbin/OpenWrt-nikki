#!/bin/sh

# 从当前 fork 安装魔改后的 LuCI/RPC 文件，无需重新编译软件包。

set -e

RAW_BASE="${NIKKI_RAW_BASE:-https://github.com/yanjinbin/OpenWrt-nikki/raw/refs/heads/main}"
GITHUB_PROXY="${GITHUB_PROXY:-https://gh-proxy.com/}"
DESTDIR="${DESTDIR:-}"
RESTART_SERVICES="${RESTART_SERVICES:-1}"
CACHE_BUSTER="${NIKKI_CACHE_BUSTER:-$(date +%s)}"

raw_url() {
	local url
	if [ -n "$GITHUB_PROXY" ]; then
		url="${GITHUB_PROXY}${RAW_BASE}/$1"
	else
		url="${RAW_BASE}/$1"
	fi

	case "$url" in
		*\?*) printf "%s&ts=%s" "$url" "$CACHE_BUSTER" ;;
		*) printf "%s?ts=%s" "$url" "$CACHE_BUSTER" ;;
	esac
}

download() {
	local source_path="$1"
	local target_path="$2"
	local tmp_path="${target_path}.tmp"
	local full_target_path="${DESTDIR}${target_path}"
	local full_tmp_path="${DESTDIR}${tmp_path}"

	echo "下载 $source_path"
	mkdir -p "$(dirname "$full_target_path")"
	wget -O "$full_tmp_path" "$(raw_url "$source_path")"
	mv -f "$full_tmp_path" "$full_target_path"
	chmod 0644 "$full_target_path"
}

download "luci-app-nikki/htdocs/luci-static/resources/tools/nikki.js" \
	"/www/luci-static/resources/tools/nikki.js"

download "luci-app-nikki/htdocs/luci-static/resources/view/nikki/profile.js" \
	"/www/luci-static/resources/view/nikki/profile.js"

download "luci-app-nikki/root/usr/share/rpcd/ucode/luci.nikki" \
	"/usr/share/rpcd/ucode/luci.nikki"

if [ "$RESTART_SERVICES" = "1" ]; then
	echo "重启 rpcd 和 uhttpd"
	/etc/init.d/rpcd restart
	/etc/init.d/uhttpd restart
else
	echo "跳过服务重启"
fi

echo "清理 LuCI 缓存"
rm -rf "${DESTDIR}"/tmp/luci-indexcache* "${DESTDIR}"/tmp/luci-modulecache*

echo "安装完成"
