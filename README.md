# Nikki 配置文件上传增强补丁

这是基于原版 [OpenWrt-nikki](https://github.com/nikkinikki-org/OpenWrt-nikki) 的 LuCI patch。

本仓库不提供完整 Nikki 安装说明，只用于给已经安装原版 Nikki 的 OpenWrt 设备增加配置文件上传增强功能。

## 功能

- 保留原版“只上传配置文件”能力。
- 新增“上传并选中重载”联合按钮。
- 选择本地 `.yaml` / `.yml` 后，一键完成：
  - 上传到 `/etc/nikki/profiles/`
  - 设为当前 Nikki profile
  - 重载 Nikki
  - 检查 Nikki 运行状态
  - 显示成功或失败通知

## 安装

前提：设备上已经安装原版 Nikki / luci-app-nikki。

在 OpenWrt 设备 SSH 中执行：

```shell
wget -O - "https://gh-proxy.com/https://github.com/yanjinbin/OpenWrt-nikki/raw/refs/heads/main/install-luci-patch.sh?ts=$(date +%s)" | ash
```

脚本会覆盖以下运行文件：

```text
/www/luci-static/resources/tools/nikki.js
/www/luci-static/resources/view/nikki/profile.js
/usr/share/rpcd/ucode/luci.nikki
```

并自动执行：

```shell
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache
```

安装后强制刷新浏览器，进入：

```text
服务 -> Nikki -> 配置文件
```

## 卸载 / 回滚

重新安装原版 `luci-app-nikki` 即可回滚本补丁。

opkg 系统：

```shell
opkg update
opkg install --force-reinstall luci-app-nikki
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache
```

apk 系统：

```shell
apk update
apk fix luci-app-nikki
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache
```

## 注意事项

- 该补丁只修改 LuCI/RPC 文件，不替换 `nikki` 和 `mihomo` 核心包。
- 如果后续升级原版 `luci-app-nikki`，本补丁可能会被覆盖，需要重新执行安装命令。
- 如果 `gh-proxy.com` 不可用，可以去掉代理前缀，直接使用 GitHub raw 地址。
