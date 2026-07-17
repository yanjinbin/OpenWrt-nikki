#!/bin/sh

# 从 0 安装原版 Nikki，并应用当前 fork 的 LuCI/RPC 魔改补丁。

set -e

UPSTREAM_RAW_BASE="${NIKKI_UPSTREAM_RAW_BASE:-https://github.com/nikkinikki-org/OpenWrt-nikki/raw/refs/heads/main}"
PATCH_RAW_BASE="${NIKKI_PATCH_RAW_BASE:-https://github.com/yanjinbin/OpenWrt-nikki/raw/refs/heads/main}"
GITHUB_PROXY="${GITHUB_PROXY:-https://gh-proxy.com/}"
CACHE_BUSTER="${NIKKI_CACHE_BUSTER:-$(date +%s)}"

raw_url() {
	local base="$1"
	local path="$2"
	local url

	if [ -n "$GITHUB_PROXY" ]; then
		url="${GITHUB_PROXY}${base}/${path}"
	else
		url="${base}/${path}"
	fi

	case "$url" in
		*\?*) printf "%s&ts=%s" "$url" "$CACHE_BUSTER" ;;
		*) printf "%s?ts=%s" "$url" "$CACHE_BUSTER" ;;
	esac
}

echo "安装原版 Nikki 基础包"
wget -O - "$(raw_url "$UPSTREAM_RAW_BASE" "install.sh")" | ash

echo "应用当前 fork 的 LuCI 魔改补丁"
wget -O - "$(raw_url "$PATCH_RAW_BASE" "install-luci-patch.sh")" | ash

echo "安装完成"
