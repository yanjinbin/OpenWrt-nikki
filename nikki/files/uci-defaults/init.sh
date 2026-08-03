#!/bin/sh

. "$IPKG_INSTROOT/etc/nikki/scripts/include.sh"

# check nikki.config.init
init=$(uci -q get nikki.config.init); [ -z "$init" ] && return

# fixed api secret and authentication password
uci set nikki.mixin.api_secret='666666'
uci set nikki.@authentication[0].password='666666'

# remove nikki.config.init
uci del nikki.config.init

# commit
uci commit nikki

# exit with 0
exit 0
