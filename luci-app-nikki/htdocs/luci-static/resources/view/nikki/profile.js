'use strict';
'require form';
'require view';
'require uci';
'require ui';
'require tools.nikki as nikki';

function readLocalFile(file) {
    if (file.text) {
        return file.text();
    }

    return new Promise(function (resolve, reject) {
        const reader = new FileReader();

        reader.onload = function () {
            resolve(reader.result);
        };
        reader.onerror = function () {
            reject(reader.error || new Error(_('读取配置文件失败。')));
        };
        reader.readAsText(file, 'UTF-8');
    });
}

return view.extend({
    load: function () {
        return Promise.all([
            uci.load('nikki')
        ]);
    },
    render: function (data) {
        let m, s, o, so;

        m = new form.Map('nikki');

        s = m.section(form.NamedSection, 'config', 'config', _('Profile'));

        o = s.option(form.FileUpload, '_profile_files', _('配置文件'));
        o.browser = true;
        o.enable_upload = true;
        o.enable_download = true;
        o.root_directory = nikki.profilesDir;
        o.write = function (section_id, formvalue) {
            return true;
        };

        o = s.option(form.DummyValue, '_upload_activate_profile', _('上传并重载'));
        o.cfgvalue = function () {
            const fileInput = E('input', {
                'type': 'file',
                'accept': '.yaml,.yml',
                'style': 'max-width: 360px;'
            });
            const status = E('span', { 'style': 'margin-left: 8px;' });
            const button = E('button', {
                'class': 'cbi-button cbi-button-positive',
                'style': 'margin-left: 8px;',
                'click': function (ev) {
                    ev.preventDefault();

                    const file = fileInput.files[0];

                    if (!file) {
                        ui.addNotification(null, E('p', _('请先选择一个配置文件。')), 'danger');
                        return Promise.reject(_('请先选择一个配置文件。'));
                    }

                    const profileName = file.name.replace(/^.*[\\/]/, '');

                    if (!profileName || profileName.indexOf('..') >= 0 || !profileName.match(/\.ya?ml$/)) {
                        ui.addNotification(null, E('p', _('请选择有效的 .yaml 或 .yml 配置文件。')), 'danger');
                        return Promise.reject(_('请选择有效的 .yaml 或 .yml 配置文件。'));
                    }

                    button.disabled = true;
                    status.textContent = _('正在上传并重载...');

                    return readLocalFile(file).then(function (content) {
                        return nikki.writefile(nikki.profilesDir + '/' + profileName, content, 0o644);
                    }).then(function () {
                        return nikki.activateProfile(profileName);
                    }).then(function (res) {
                        if (!res.success) {
                            return Promise.reject(res.message || _('启用配置文件失败。'));
                        }

                        return nikki.status().then(function (running) {
                            if (!running) {
                                return Promise.reject(_('配置文件已选中，重载命令已完成，但 Nikki 未运行。'));
                            }

                            ui.addNotification(null, E('p', _('已选中并重载成功：') + (res.profile_name || profileName)), 'info');
                            status.textContent = _('已完成');
                            return Promise.resolve();
                        });
                    }).catch(function (e) {
                        const message = e?.message || e || _('启用配置文件失败。');
                        ui.addNotification(null, E('p', _('启用配置文件失败：') + message), 'danger');
                        status.textContent = _('失败');
                        return Promise.reject(message);
                    }).finally(function () {
                        button.disabled = false;
                    });
                }
            }, [ _('上传并选中重载') ]);

            return E('div', { 'class': 'cbi-input-group' }, [
                fileInput,
                button,
                status
            ]);
        };

        s = m.section(form.GridSection, 'subscription', _('Subscription'));
        s.addremove = true;
        s.anonymous = true;
        s.sortable = true;
        s.modaltitle = _('Edit Subscription');

        o = s.option(form.Value, 'name', _('Subscription Name'));
        o.rmempty = false;

        o = s.option(form.Value, 'used', _('Used'));
        o.modalonly = false;
        o.optional = true;
        o.readonly = true;

        o = s.option(form.Value, 'total', _('Total'));
        o.modalonly = false;
        o.optional = true;
        o.readonly = true;

        o = s.option(form.Value, 'expire', _('Expire At'));
        o.modalonly = false;
        o.optional = true;
        o.readonly = true;

        o = s.option(form.Value, 'update', _('Update At'));
        o.modalonly = false;
        o.optional = true;
        o.readonly = true;

        o = s.option(form.Button, 'update_subscription');
        o.editable = true;
        o.inputstyle = 'positive';
        o.inputtitle = _('Update');
        o.modalonly = false;
        o.onclick = function (_, section_id) {
            return nikki.updateSubscription(section_id);
        };

        o = s.option(form.Value, 'info_url', _('Subscription Info Url'));
        o.modalonly = true;

        o = s.option(form.Value, 'url', _('Subscription Url'));
        o.modalonly = true;
        o.rmempty = false;

        o = s.option(form.Value, 'user_agent', _('User Agent'));
        o.default = 'clash';
        o.modalonly = true;
        o.rmempty = false;
        o.value('clash');
        o.value('clash.meta');
        o.value('mihomo');

        o = s.option(form.ListValue, 'prefer', _('Prefer'));
        o.default = 'remote';
        o.modalonly = true;
        o.rmempty = false;
        o.value('remote', _('Remote'));
        o.value('local', _('Local'));

        return m.render();
    }
});
