'use strict';
'require baseclass';
'require form';
'require uci';
'require fs';
'require rpc';
'require request';

const callRCList = rpc.declare({
    object: 'rc',
    method: 'list',
    params: ['name'],
    expect: { '': {} }
});

const callRCInit = rpc.declare({
    object: 'rc',
    method: 'init',
    params: ['name', 'action'],
    expect: { '': {} }
});

const callFileWrite = rpc.declare({
    object: 'file',
    method: 'write',
    params: ['path', 'data', 'append', 'mode']
});

const callNikkiVersion = rpc.declare({
    object: 'luci.nikki',
    method: 'version',
    expect: { '': {} }
});

const callNikkiProfile = rpc.declare({
    object: 'luci.nikki',
    method: 'profile',
    params: ['defaults'],
    expect: { '': {} }
});

const callNikkiUpdateSubscription = rpc.declare({
    object: 'luci.nikki',
    method: 'update_subscription',
    params: ['section_id'],
    expect: { '': {} }
});

const callNikkiActivateProfile = rpc.declare({
    object: 'luci.nikki',
    method: 'activate_profile',
    params: ['profile_name'],
    expect: { '': {} }
});

const callNikkiAPI = rpc.declare({
    object: 'luci.nikki',
    method: 'api',
    params: ['method', 'path', 'query', 'body'],
    expect: { '': {} }
});

const callNikkiGetIdentifiers = rpc.declare({
    object: 'luci.nikki',
    method: 'get_identifiers',
    expect: { '': {} }
});

const callNikkiProxyScheduleStatus = rpc.declare({ object: 'luci.nikki', method: 'proxy_schedule_status', expect: { '': {} } });

const callNikkiProxyGroups = rpc.declare({
    object: 'luci.nikki',
    method: 'proxy_groups',
    expect: { '': {} }
});

const callNikkiDebug = rpc.declare({
    object: 'luci.nikki',
    method: 'debug',
    expect: { '': {} }
});

const homeDir = '/etc/nikki';
const profilesDir = `${homeDir}/profiles`;
const subscriptionsDir = `${homeDir}/subscriptions`;
const mixinFilePath = `${homeDir}/mixin.yaml`;
const runDir = `${homeDir}/run`;
const runProfilePath = `${runDir}/config.yaml`;
const providersDir = `${runDir}/providers`;
const ruleProvidersDir = `${providersDir}/rule`;
const proxyProvidersDir = `${providersDir}/proxy`;
const logDir = `/var/log/nikki`;
const appLogPath = `${logDir}/app.log`;
const coreLogPath = `${logDir}/core.log`;
const debugLogPath = `${logDir}/debug.log`;
const nftDir = `${homeDir}/nftables`;

return baseclass.extend({
    homeDir: homeDir,
    profilesDir: profilesDir,
    subscriptionsDir: subscriptionsDir,
    mixinFilePath: mixinFilePath,
    runDir: runDir,
    runProfilePath: runProfilePath,
    ruleProvidersDir: ruleProvidersDir,
    proxyProvidersDir: proxyProvidersDir,
    appLogPath: appLogPath,
    coreLogPath: coreLogPath,
    debugLogPath: debugLogPath,

    addSubscriptionSchedule: function (section, subscription) {
        function add(type, key, label) {
            const name = subscription == null ? key : '_' + key + '_' + subscription;
            const option = section.option(type, name, label);
            option.rmempty = false;
            option.retain = true;
            option.editable = true;
            option.ucioption = key;
            if (subscription != null) {
                option.ucisection = subscription;
                option.depends('nikki.config.profile', 'subscription:' + subscription);
            }
            return option;
        }
        const enabled = add(form.Flag, 'auto_update', _('定时更新'));
        enabled.default = '1';

        const days = add(form.MultiValue, 'update_weekdays', _('更新星期'));
        days.default = ['0'];
        days.widget = 'checkbox';
        for (const [day, label] of [['1', _('周一')], ['2', _('周二')], ['3', _('周三')],
            ['4', _('周四')], ['5', _('周五')], ['6', _('周六')], ['0', _('周日')]])
            days.value(day, label);
        days.validate = function (id, value) {
            const selected = Array.isArray(value) ? value : String(value || '').split(/\s+/);
            return selected.length > 0 && selected.every(day => /^[0-6]$/.test(day)) || _('请选择至少一个星期。');
        };

        const time = add(form.Value, 'update_time', _('更新时间'));
        time.default = '04:00';
        time.description = _('按路由器本地时间执行，默认每周日凌晨 04:00。错过时点不补跑，失败等待下个选定时点。');
        time.renderWidget = function () {
            const node = form.Value.prototype.renderWidget.apply(this, arguments);
            const input = node.querySelector('input');
            input.type = 'time';
            input.step = '60';
            return node;
        };
        time.validate = function (id, value) {
            return value?.length === 5 && /^([01]\d|2[0-3]):[0-5]\d$/.test(value) || _('请输入 24 小时制时间 HH:MM。');
        };
    },

    status: async function () {
        return (await callRCList('nikki'))?.nikki?.running;
    },

    reload: function () {
        return callRCInit('nikki', 'reload');
    },

    restart: function () {
        return callRCInit('nikki', 'restart');
    },

    writefile: function (path, data, mode) {
        data = (data != null) ? String(data) : '';
        mode = (mode != null) ? mode : 0o644;

        const encoder = new TextEncoder();
        const decoder = new TextDecoder();
        const chunkSize = 8 * 1024;

        const bytes = encoder.encode(data);

        if (bytes.length <= chunkSize) {
            return callFileWrite(path, data, false, mode);
        }

        let promise = Promise.resolve();
        for(let offset = 0; offset < bytes.length; offset += chunkSize) {
            const chunkStart = offset;
            const chunkEnd = Math.min(offset + chunkSize, bytes.length);
            const isLastChunk = chunkEnd === bytes.length;
            const chunkBytes = bytes.slice(chunkStart, chunkEnd);
            const chunk = decoder.decode(chunkBytes, { stream: !isLastChunk });
            const append = offset > 0;
            promise = promise.then(() => callFileWrite(path, chunk, append, mode));
        }

        return promise;
    },

    version: function () {
        return callNikkiVersion();
    },

    profile: function (defaults) {
        return callNikkiProfile(defaults);
    },

    updateSubscription: function (section_id) {
        return callNikkiUpdateSubscription(section_id);
    },

    activateProfile: function (profile_name) {
        return callNikkiActivateProfile(profile_name);
    },

    updateDashboard: function () {
        return callNikkiAPI('POST', '/upgrade/ui');
    },

    openDashboard: async function () {
        const profile = await callNikkiProfile({
            'external-ui-name': null,
            'external-controller': null,
            'external-controller-tls': null,
            'secret': null
        });
        const uiName = profile['external-ui-name'];
        const apiListen = profile['external-controller'];
        const apiTLSListen = profile['external-controller-tls'];
        const apiSecret = profile['secret'] ?? '';
        if (!apiListen && !apiTLSListen) {
            return Promise.reject('API has not been configured');
        }

        let protocol;
        let port;
        if (apiTLSListen) {
            protocol = 'https';
            port = apiTLSListen.substring(apiTLSListen.lastIndexOf(':') + 1);
        } else {
            protocol = 'http';
            port = apiListen.substring(apiListen.lastIndexOf(':') + 1);
        }

        const params = {
            host: window.location.hostname,
            hostname: window.location.hostname,
            port: port,
            secret: apiSecret
        };
        const query = new URLSearchParams(params).toString();
        let url;
        if (uiName) {
            url = `${protocol}://${window.location.hostname}:${port}/ui/${uiName}/?${query}`;
        } else {
            url = `${protocol}://${window.location.hostname}:${port}/ui/?${query}`;
        }

        setTimeout(function () { window.open(url, '_blank') }, 0);

        return Promise.resolve();
    },

    getIdentifiers: function () {
        return callNikkiGetIdentifiers();
    },

    getProxyScheduleStatus: function () {
        return callNikkiProxyScheduleStatus();
    },

    getProxyGroups: function () {
        return callNikkiProxyGroups();
    },

    listProfiles: function () {
        return L.resolveDefault(fs.list(this.profilesDir), []);
    },

    listRuleProviders: function () {
        return L.resolveDefault(fs.list(this.ruleProvidersDir), []);
    },

    listProxyProviders: function () {
        return L.resolveDefault(fs.list(this.proxyProvidersDir), []);
    },

    getAppLog: function () {
        return L.resolveDefault(fs.read_direct(this.appLogPath));
    },

    getCoreLog: function () {
        return L.resolveDefault(fs.read_direct(this.coreLogPath));
    },

    clearAppLog: function () {
        return this.writefile(this.appLogPath, '');
    },

    clearCoreLog: function () {
        return this.writefile(this.coreLogPath, '');
    },

    debug: function () {
        return callNikkiDebug();
    },
})
