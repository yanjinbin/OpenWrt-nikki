#!/bin/sh

# 从当前 fork 安装魔改后的 LuCI/RPC/服务脚本文件，无需重新编译软件包。

set -e

RAW_BASE="${NIKKI_RAW_BASE:-https://github.com/yanjinbin/OpenWrt-nikki/raw/refs/heads/main}"
GITHUB_PROXY="${GITHUB_PROXY-https://gh-proxy.com/}"
DESTDIR="${DESTDIR:-}"
RESTART_SERVICES="${RESTART_SERVICES:-1}"
CACHE_BUSTER="${NIKKI_CACHE_BUSTER:-$(date +%s)}"

if [ -z "$DESTDIR" ]; then
	ucode -e 'import { cursor } from "uci"; import { mkstemp } from "fs";' >/dev/null 2>&1 || { echo "请先安装 ucode、ucode-mod-fs 和 ucode-mod-uci 软件包"; exit 1; }
	command -v flock >/dev/null || { echo "请先安装 flock 软件包"; exit 1; }
	[ -f /usr/share/libubox/jshn.sh ] || { echo "请先安装 jshn 软件包"; exit 1; }
fi

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
	local mode="${3:-0644}"
	local tmp_path="${target_path}.tmp"
	local full_target_path="${DESTDIR}${target_path}"
	local full_tmp_path="${DESTDIR}${tmp_path}"

	echo "下载 $source_path"
	mkdir -p "$(dirname "$full_target_path")"
	wget -O "$full_tmp_path" "$(raw_url "$source_path")"
	mv -f "$full_tmp_path" "$full_target_path"
	chmod "$mode" "$full_target_path"
}

download "luci-app-nikki/htdocs/luci-static/resources/tools/nikki.js" \
	"/www/luci-static/resources/tools/nikki.js"

download "luci-app-nikki/htdocs/luci-static/resources/view/nikki/app.js" \
	"/www/luci-static/resources/view/nikki/app.js"

download "luci-app-nikki/htdocs/luci-static/resources/view/nikki/profile.js" \
	"/www/luci-static/resources/view/nikki/profile.js"

download "luci-app-nikki/htdocs/luci-static/resources/view/nikki/schedule.js" \
	"/www/luci-static/resources/view/nikki/schedule.js"

download "luci-app-nikki/root/usr/share/luci/menu.d/luci-app-nikki.json" \
	"/usr/share/luci/menu.d/luci-app-nikki.json"

download "luci-app-nikki/root/usr/share/rpcd/acl.d/luci-app-nikki.json" \
	"/usr/share/rpcd/acl.d/luci-app-nikki.json"

if [ ! -f "${DESTDIR}/etc/config/nikki_schedule" ]; then
	download "nikki/files/nikki_schedule.conf" "/etc/config/nikki_schedule" 0600
fi

download "nikki/files/ucode/proxy_schedule.uc" \
	"/etc/nikki/ucode/proxy_schedule.uc" 0755

download "nikki/files/ucode/schedule.uc" \
	"/etc/nikki/ucode/schedule.uc" 0755

download "luci-app-nikki/root/usr/share/rpcd/ucode/luci.nikki" \
	"/usr/share/rpcd/ucode/luci.nikki"

download "nikki/files/nikki.init" \
	"/etc/init.d/nikki" 0755

echo "写入重载后清除旧连接默认开关"
if [ -z "$(uci -q get nikki.procd)" ]; then
	uci set nikki.procd='procd'
fi
if [ -z "$(uci -q get nikki.procd.clear_connections_on_reload)" ]; then
	uci set nikki.procd.clear_connections_on_reload='1'
	uci commit nikki
fi

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

if [ -z "$DESTDIR" ] && /etc/init.d/nikki status >/dev/null 2>&1; then
	if ! grep -q '#nikki subscription update' /etc/crontabs/root; then
		echo '0 * * * * /etc/init.d/nikki update_subscriptions #nikki subscription update' >> /etc/crontabs/root
		/etc/init.d/cron restart
	fi
	/etc/init.d/nikki update_subscriptions
	# 刷新调度任务，无需重启 Mihomo；间隔与服务脚本保持一致。
	schedule_cron='* * * * *'
	sed -i '/#nikki proxy schedule$/d' /etc/crontabs/root
	echo "$schedule_cron /etc/init.d/nikki schedule_proxies #nikki proxy schedule" >> /etc/crontabs/root
	/etc/init.d/cron restart
	/etc/init.d/nikki schedule_proxies --force
fi
