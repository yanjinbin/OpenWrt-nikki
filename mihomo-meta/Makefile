include $(TOPDIR)/rules.mk

PKG_NAME:=mihomo-meta
PKG_VERSION:=1.19.27
PKG_RELEASE:=1

PKG_LICENSE:=GPL3.0+
PKG_MAINTAINER:=Joseph Mory <morytyann@gmail.com>

# ============ 预编译二进制方案 ============
# mihomo 不在 OpenWrt 内自行编译, 直接从 MetaCubeX/mihomo releases 拉取
# 对应平台和版本的预编译二进制打包成 apk/ipk
#   - 版本号: 构建工作流可通过 sed 覆盖 PKG_VERSION:= 行
#   - 平台:   默认按 OpenWrt 架构推导, 也可通过 MIHOMO_PLATFORM_OVERRIDE 覆盖

# 按 OpenWrt 架构推导 mihomo release 平台名 (R5C/R6S/E20C 等 rockchip armv8 -> arm64)
ifeq ($(ARCH),x86_64)
  MIHOMO_PLATFORM:=amd64
else ifneq ($(filter aarch64%,$(ARCH)),)
  MIHOMO_PLATFORM:=arm64
else ifneq ($(filter arm%,$(ARCH)),)
  MIHOMO_PLATFORM:=armv7
else ifeq ($(ARCH),i386)
  MIHOMO_PLATFORM:=386
else ifneq ($(filter mipsel_74kc%,$(ARCH)),)
  MIHOMO_PLATFORM:=mipsle-hardfloat
else ifneq ($(filter mipsel%,$(ARCH)),)
  MIHOMO_PLATFORM:=mipsle-softfloat
else ifneq ($(filter mips_74kc%,$(ARCH)),)
  MIHOMO_PLATFORM:=mips-hardfloat
else ifneq ($(filter mips64%,$(ARCH)),)
  MIHOMO_PLATFORM:=mips64
else ifneq ($(filter mips%,$(ARCH)),)
  MIHOMO_PLATFORM:=mips-softfloat
else ifneq ($(filter riscv64%,$(ARCH)),)
  MIHOMO_PLATFORM:=riscv64
else ifneq ($(filter loongarch64%,$(ARCH)),)
  MIHOMO_PLATFORM:=loong64
else
  $(error mihomo-meta: unsupported ARCH '$(ARCH)', please set MIHOMO_PLATFORM_OVERRIDE)
endif

# 构建工作流可通过 sed 将此行改为指定平台 (如 MIHOMO_PLATFORM_OVERRIDE:=amd64-v3)
MIHOMO_PLATFORM_OVERRIDE:=
MIHOMO_PLATFORM:=$(if $(MIHOMO_PLATFORM_OVERRIDE),$(MIHOMO_PLATFORM_OVERRIDE),$(MIHOMO_PLATFORM))

PKG_SOURCE:=mihomo-linux-$(MIHOMO_PLATFORM)-v$(PKG_VERSION).gz
PKG_SOURCE_URL:=https://github.com/MetaCubeX/mihomo/releases/download/v$(PKG_VERSION)
PKG_HASH:=skip

PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

define Package/mihomo-meta
  SECTION:=net
  CATEGORY:=Network
  TITLE:=A rule based proxy in Go (prebuilt).
  URL:=https://wiki.metacubex.one
  DEPENDS:=+ca-bundle +ip-full +kmod-inet-diag +kmod-tun
  PROVIDES:=mihomo
  CONFLICTS:=mihomo-alpha
  VARIANT:=meta
  DEFAULT_VARIANT:=1
  ALTERNATIVES:=\
    300:/usr/bin/mihomo:/usr/libexec/mihomo
endef

define Package/mihomo-meta/description
  A rule based proxy in Go. Prebuilt from MetaCubeX/mihomo releases.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	gzip -dc $(DL_DIR)/$(PKG_SOURCE) > $(PKG_BUILD_DIR)/mihomo
	chmod 0755 $(PKG_BUILD_DIR)/mihomo
endef

define Build/Compile
endef

define Package/mihomo-meta/install
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/mihomo $(1)/usr/libexec/mihomo
endef

$(eval $(call BuildPackage,mihomo-meta))
