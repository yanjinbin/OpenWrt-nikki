'use strict';

import { popen, mkstemp, readfile, writefile, rename, open } from 'fs';

function shell_quote(value) {
	return "'" + replace(value, /'/g, "'\\''") + "'";
};

export function path_encode(value) {
	let result = '';
	for (let i = 0; i < length(value); i++) {
		const ch = substr(value, i, 1);
		result += match(ch, /^[A-Za-z0-9_.~-]$/) ? ch : sprintf('%%%02X', ord(value, i));
	}
	return result;
};

function curlquote(value) {
	return '"' + replace(replace(value, /\\/g, '\\\\'), /"/g, '\\"') + '"';
};

// Keep credentials out of argv, RPC results, logs and named temporary files.
// mkstemp() unlinks the file immediately; curl reads the inherited descriptor.
export function proxy_api(profile, method, path, body) {
	let tls = !profile?.['external-controller'] && !!profile?.['external-controller-tls'];
	let socket = profile?.['external-controller-unix'];
	let url;
	if (type(socket) == 'string' && length(socket)) {
		url = 'http://localhost';
	} else {
		let controller = profile?.['external-controller'] || profile?.['external-controller-tls'];
		let address = match(controller || '', /^(\[[0-9a-fA-F:.%]+\]|[A-Za-z0-9._-]*):([0-9]+)$/);
		if (!address || int(address[2], 10) < 1 || int(address[2], 10) > 65535)
			return { ok: false, error: 'Mihomo API is not configured.' };
		let host = address[1];
		if (host == '' || host == '0.0.0.0') host = '127.0.0.1';
		if (host == '[::]') host = '[::1]';
		url = (tls ? 'https://' : 'http://') + host + ':' + address[2];
	}
	let secret = profile.secret ?? '';
	let bad_secret = type(secret) != 'string';
	for (let i = 0; i < length(secret); i++)
		if (ord(secret, i) < 32 || ord(secret, i) == 127) bad_secret = true;
	if (bad_secret)
		return { ok: false, error: 'Mihomo API is not configured.' };
	let config = mkstemp();
	if (!config) return { ok: false, error: 'Mihomo API request failed.' };
	config.write('header = ' + curlquote('Authorization: Bearer ' + secret) + '\n');
	config.flush();
	config.seek(0);
	let command = 'curl -q --silent --fail --noproxy \x27*\x27 --connect-timeout 2 --max-time 5 --globoff --path-as-is' +
		(tls && !socket ? ' --insecure' : '') + (socket ? ' --unix-socket ' + shell_quote(socket) : '') + ' --config /dev/fd/' + config.fileno() +
		' --request ' + shell_quote(method) + ' --header \x27Content-Type: application/json\x27' +
		(body != null ? ' --data-binary ' + shell_quote(sprintf('%J', body)) : '') +
		' --write-out \x27\\n%{http_code}\x27 --url ' + shell_quote(url + path) + ' 2>/dev/null';
	let process = popen(command);
	let output = process ? process.read('all') : '';
	let code = process ? process.close() : -1;
	config.close();
	let pos = rindex(output, '\n');
	let status = int(substr(output, pos + 1));
	if (code != 0 || status < 200 || status >= 300)
		return { ok: false, error: 'Mihomo API request failed.' };
	if (method == 'PUT') return { ok: true };
	try {
		return { ok: true, data: json(substr(output, 0, pos)) };
	} catch (e) {
		return { ok: false, error: 'Mihomo API request failed.' };
	}
};

function request(profile, method, path, body) {
	const result = proxy_api(profile, method, path, body);
	if (!result.ok) die(result.error);
	return result.data;
};

export function get_groups(profile) {
	const proxies = request(profile, 'GET', '/proxies', null)?.proxies;
	if (type(proxies) != 'object') die('Mihomo API returned no proxy groups.');
	const groups = {};
	for (let name, proxy in proxies) {
		if (proxy.type == 'Selector' && type(proxy.all) == 'array')
			groups[name] = { type: proxy.type, all: proxy.all, now: proxy.now };
	}
	return groups;
};

function minutes(value) {
	if (type(value) != 'string' || length(value) != 5 || !match(value, /^([01][0-9]|2[0-3]):[0-5][0-9]$/))
		return null;
	return int(substr(value, 0, 2), 10) * 60 + int(substr(value, 3, 2), 10);
};

export function plan(rules, proxies, minute) {
	const enabled = filter(rules, rule => rule.enabled == '1');
	const counts = {};
	for (let rule in enabled) counts[rule.group] = (counts[rule.group] ?? 0) + 1;
	return map(enabled, function(rule) {
		const result = { section: rule['.name'], group: rule.group, changed: false, config: rule };
		const start = minutes(rule.start_time);
		const end = minutes(rule.end_time);
		const proxy = proxies[rule.group];
		if (!rule.group || !rule.inside || !rule.outside || start == null || end == null || start == end)
			result.error = 'Set a group, two selections and distinct HH:MM times.';
		else if (counts[rule.group] > 1)
			result.error = 'Only one enabled schedule is allowed per group.';
		else if (proxy?.type != 'Selector' || type(proxy.all) != 'array')
			result.error = 'The proxy group is missing or is not a Selector.';
		else if (index(proxy.all, rule.inside) < 0 || index(proxy.all, rule.outside) < 0)
			result.error = 'A scheduled selection is missing from the group.';
		else {
			const inside = start < end ? minute >= start && minute < end : minute >= start || minute < end;
			result.period = inside ? 'inside' : 'outside';
			result.current = proxy.now;
			result.target = inside ? rule.inside : rule.outside;
			result.changed = proxy.now != result.target;
		}
		return result;
	});
};

export function reconcile(rules, minute, profile) {
	if (!length(filter(rules, rule => rule.enabled == '1'))) return [];
	let groups;
	try {
		groups = get_groups(profile);
	} catch (e) {
		return [{ error: e.message, changed: false }];
	}
	const results = plan(rules, groups, minute);
	for (let result in results) {
		if (result.error || !result.changed) continue;
		try {
			request(profile, 'PUT', '/proxies/' + path_encode(result.group), { name: result.target });
			result.current = result.target;
		} catch (e) {
			result.error = e.message;
			result.changed = false;
		}
	}
	return results;
};

export const schedule_status_path = '/var/run/nikki/proxy_schedule.json';

export function read_schedule_status() {
	try { return json(readfile(schedule_status_path) || '{}'); } catch (e) { return {}; }
};

export function check_due(previous, signature, now, minute, interval, force) {
	// Retry failures and changed settings on the next minute, even with a long interval.
	return force || previous.signature != signature ||
		length(filter(previous.rules || [], result => !!result.error)) > 0 ||
		minute % interval == 0 || !previous.checked_at || now < previous.checked_at ||
		now - previous.checked_at >= interval * 60;
};

export function save_schedule_status(status) {
	const previous = read_schedule_status();
	for (let result in status.rules) {
		const old = filter(previous.rules || [], item => item.section == result.section)[0];
		if (!result.changed && (!result.error || result.error == old?.error)) continue;
		const log = open('/var/log/nikki/app.log', 'a');
		// JSON encoding prevents names with newlines from forging log records.
		log?.write(sprintf('[%s] [Schedule] %J\n', status.local_time,
			{ section: result.section, group: result.group, target: result.target, error: result.error }));
		log?.close();
	}
	if (writefile(schedule_status_path + '.new', sprintf('%J', status)) != null)
		rename(schedule_status_path + '.new', schedule_status_path);
};
