#!/usr/bin/ucode

'use strict';

import { cursor } from 'uci';
import { access } from 'fs';
import { load_profile } from './include.uc';
import { reconcile, read_schedule_status, save_schedule_status, check_due } from './proxy_schedule.uc';

const uci = cursor();
if (uci.get('nikki', 'config', 'enabled') != '1' || !access('/var/run/nikki/started.flag')) exit(0);
const rules = [];
uci.foreach('nikki_schedule', 'proxy_schedule', rule => { push(rules, rule); });
let interval = int(uci.get('nikki_schedule', 'config', 'proxy_schedule_interval'), 10);
if (index([1, 5, 10, 15, 30, 60], interval) < 0) interval = 1;
const now = localtime();
const timestamp = time();
const signature = sprintf('%J', { interval, rules });
if (!check_due(read_schedule_status(), signature, timestamp, now.min, interval, index(ARGV, '--force') >= 0)) exit(0);
let results = [];
if (length(filter(rules, rule => rule.enabled == '1'))) {
	try {
		results = reconcile(rules, now.hour * 60 + now.min, load_profile());
	} catch (e) {
		results = [{ error: 'Cannot read the running Mihomo profile.', changed: false }];
	}
}
save_schedule_status({
	checked_at: timestamp, interval, signature,
	local_time: sprintf('%04d-%02d-%02d %02d:%02d:%02d', now.year, now.mon, now.mday, now.hour, now.min, now.sec),
	rules: results
});
