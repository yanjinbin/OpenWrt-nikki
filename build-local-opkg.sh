#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
src="$repo_dir"
out="$repo_dir/dist-local"
work="$repo_dir/.local-opkg"
tar_bin=$(command -v gtar || command -v tar)

rm -rf "$work" "$out"
mkdir -p "$out" "$repo_dir/.local-binaries/extracted"

make_pkg() {
    name="$1"; version="$2"; depends="$3"; source_dir="$4"
    root="$work/$name"; pkg="$out/${name}_${version}_all.ipk"
    rm -rf "$root"; mkdir -p "$root/control" "$root/data"
    printf '2.0\n' > "$root/debian-binary"
    cat > "$root/control/control" <<EOF
Package: $name
Version: $version
Architecture: all
Section: net
Priority: optional
Maintainer: yanjinbin
Depends: $depends
Description: $name
EOF
    (cd "$root/control" && "$tar_bin" --format=ustar --owner=0 --group=0 --numeric-owner -czf ../control.tar.gz control)
    (cd "$root/data" && "$tar_bin" --format=ustar --owner=0 --group=0 --numeric-owner -czf ../data.tar.gz .)
    (cd "$root" && "$tar_bin" --format=ustar --owner=0 --group=0 --numeric-owner -czf "$pkg" ./debian-binary ./control.tar.gz ./data.tar.gz)
    printf '%s\n' "$pkg"
}

nikki_root="$work/nikki/data"
mkdir -p "$nikki_root"
mkdir -p "$nikki_root/etc/nikki/profiles" "$nikki_root/etc/nikki/subscriptions" "$nikki_root/etc/nikki/run/providers/rule" "$nikki_root/etc/nikki/run/providers/proxy"
cp "$src/nikki/files/mixin.yaml" "$nikki_root/etc/nikki/mixin.yaml"
cp -R "$src/nikki/files/ucode" "$nikki_root/etc/nikki/"
cp -R "$src/nikki/files/scripts" "$nikki_root/etc/nikki/"
cp -R "$src/nikki/files/nftables" "$nikki_root/etc/nikki/"
mkdir -p "$nikki_root/etc/config" "$nikki_root/etc/init.d" "$nikki_root/etc/uci-defaults" "$nikki_root/lib/upgrade/keep.d"
cp "$src/nikki/files/nikki.conf" "$nikki_root/etc/config/nikki"
cp "$src/nikki/files/nikki.init" "$nikki_root/etc/init.d/nikki"
chmod 0755 "$nikki_root/etc/init.d/nikki" "$nikki_root/etc/nikki/scripts/"*.sh "$nikki_root/etc/nikki/ucode/"* "$nikki_root/etc/uci-defaults/"*.sh 2>/dev/null || true
cp "$src/nikki/files/nikki.upgrade" "$nikki_root/lib/upgrade/keep.d/nikki"
cp "$src/nikki/files/uci-defaults/"*.sh "$nikki_root/etc/uci-defaults/"
mkdir -p "$nikki_root/usr/libexec" "$nikki_root/usr/bin"
gzip -dc "$repo_dir/.local-binaries/mihomo.gz" > "$nikki_root/usr/libexec/mihomo"
chmod 0755 "$nikki_root/usr/libexec/mihomo"
tar -xzf "$repo_dir/.local-binaries/yq.tar.gz" -C "$repo_dir/.local-binaries/extracted"
yq_bin=$(find "$repo_dir/.local-binaries/extracted" -type f -name 'yq_linux_arm64' | head -1)
cp "$yq_bin" "$nikki_root/usr/bin/yq"; chmod 0755 "$nikki_root/usr/bin/yq"
ln -sf /usr/libexec/mihomo "$nikki_root/usr/bin/mihomo"

nikki_version=$(sed -n 's/^PKG_VERSION:=//p' "$src/nikki/Makefile")-$(sed -n 's/^PKG_RELEASE:=//p' "$src/nikki/Makefile")
nikki_pkg="$out/nikki_${nikki_version}_aarch64_cortex-a53.ipk"
mkdir -p "$work/nikki/control"
printf '2.0\n' > "$work/nikki/debian-binary"
printf 'Package: nikki\nVersion: %s\nArchitecture: aarch64_cortex-a53\nSection: net\nPriority: optional\nMaintainer: yanjinbin\nDepends: curl firewall4 ip-full kmod-inet-diag kmod-nft-socket kmod-nft-tproxy kmod-tun kmod-dummy\nDescription: Transparent Proxy with Mihomo on OpenWrt\n' "$nikki_version" > "$work/nikki/control/control"
printf '/etc/config/nikki\n/etc/nikki/mixin.yaml\n' > "$work/nikki/control/conffiles"
(cd "$work/nikki/control" && "$tar_bin" --format=ustar --owner=0 --group=0 --numeric-owner -czf ../control.tar.gz control conffiles)
(cd "$nikki_root" && "$tar_bin" --format=ustar --owner=0 --group=0 --numeric-owner -czf ../data.tar.gz .)
(cd "$work/nikki" && "$tar_bin" --format=ustar --owner=0 --group=0 --numeric-owner -czf "$nikki_pkg" ./debian-binary ./control.tar.gz ./data.tar.gz)

luci_root="$work/luci-app-nikki/data"
mkdir -p "$luci_root/www"; cp -R "$src/luci-app-nikki/htdocs/." "$luci_root/www/"; cp -R "$src/luci-app-nikki/root/." "$luci_root/"
luci_version=$(sed -n 's/^PKG_VERSION:=//p' "$src/luci-app-nikki/Makefile")-1
mkdir -p "$work/luci-app-nikki/control"
printf '2.0\n' > "$work/luci-app-nikki/debian-binary"
printf 'Package: luci-app-nikki\nVersion: %s\nArchitecture: all\nSection: luci\nPriority: optional\nMaintainer: yanjinbin\nDepends: luci-base, nikki\nDescription: LuCI Support for Nikki\n' "$luci_version" > "$work/luci-app-nikki/control/control"
(cd "$work/luci-app-nikki/control" && "$tar_bin" --format=ustar --owner=0 --group=0 --numeric-owner -czf ../control.tar.gz control)
(cd "$luci_root" && "$tar_bin" --format=ustar --owner=0 --group=0 --numeric-owner -czf ../data.tar.gz .)
(cd "$work/luci-app-nikki" && "$tar_bin" --format=ustar --owner=0 --group=0 --numeric-owner -czf "$out/luci-app-nikki_${luci_version}_all.ipk" ./debian-binary ./control.tar.gz ./data.tar.gz)

printf '%s\n' "$out"/*.ipk
