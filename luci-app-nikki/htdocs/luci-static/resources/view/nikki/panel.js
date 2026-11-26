'use strict';
'require view';
'require tools.nikki as nikki';

// Build the dashboard URL from the merged profile. The query string seeds the
// dashboard with the current API endpoint and secret, so it can log in without
// a manual setup even after the browser storage has been cleared.
function dashboardUrl(profile) {
    const uiName = profile['external-ui-name'];
    const apiListen = profile['external-controller'];
    const apiTLSListen = profile['external-controller-tls'];
    const apiSecret = profile['secret'] ?? '';
    if (!apiListen && !apiTLSListen) {
        return null;
    }

    const protocol = apiTLSListen ? 'https' : 'http';
    const listen = apiTLSListen || apiListen;
    const port = listen.substring(listen.lastIndexOf(':') + 1);
    const params = new URLSearchParams({
        host: window.location.hostname,
        hostname: window.location.hostname,
        port: port,
        secret: apiSecret
    });
    const uiPath = uiName ? `/ui/${uiName}/` : '/ui/';

    return `${protocol}://${window.location.hostname}:${port}${uiPath}?${params.toString()}`;
}

// A bookmarkable entry point for the dashboard. The URL is rebuilt from the
// running config on every visit, so it keeps working after the dashboard
// storage is cleared or the API port/secret changes.
return view.extend({
    load: function () {
        return nikki.profile({
            'external-ui-name': null,
            'external-controller': null,
            'external-controller-tls': null,
            'secret': null
        });
    },

    render: function (profile) {
        const url = dashboardUrl(profile);

        if (!url) {
            return E('p', { 'class': 'alert-message warning' }, _('API has not been configured'));
        }

        window.location.replace(url);

        return E([]);
    }
});
