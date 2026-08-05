#!/bin/sh

. "$IPKG_INSTROOT/etc/nikki/scripts/include.sh"

# check nikki.config.init
init=$(uci -q get nikki.config.init); [ -z "$init" ] && return

# remove nikki.config.init
uci del nikki.config.init

# commit
uci commit nikki

# exit with 0
exit 0
