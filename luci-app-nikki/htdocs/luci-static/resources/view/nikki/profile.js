'use strict';
'require form';
'require view';
'require uci';
'require ui';
'require tools.nikki as nikki';

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

        o = s.option(form.FileUpload, '_upload_profile', _('Upload Profile'));
        o.browser = true;
        o.enable_download = true;
        o.root_directory = nikki.profilesDir;
        o.write = function (section_id, formvalue) {
            return true;
        };

        o = s.option(form.Button, '_activate_profile');
        o.inputstyle = 'positive';
        o.inputtitle = _('Use Selected Profile and Reload');
        o.onclick = function (_, section_id) {
            const uploadOption = m.lookupOption('_upload_profile', section_id)[0];
            let profileName = uploadOption.formvalue(section_id);

            if (!profileName) {
                return Promise.reject(_('Please select a profile file first.'));
            }

            profileName = profileName.substring(profileName.lastIndexOf('/') + 1);

            if (!profileName || profileName.indexOf('..') >= 0 || !profileName.match(/\.ya?ml$/)) {
                return Promise.reject(_('Please select a valid .yaml or .yml profile file.'));
            }

            return nikki.activateProfile(profileName).then(function (res) {
                if (!res.success) {
                    return Promise.reject(res.message || _('Failed to activate profile.'));
                }

                return nikki.status().then(function (running) {
                    if (!running) {
                        return Promise.reject(_('Profile selected and reload command completed, but Nikki is not running.'));
                    }

                    ui.addNotification(null, E('p', _('Profile selected and service reloaded successfully: ') + (res.profile_name || profileName)), 'info');
                    return Promise.resolve();
                });
            }).catch(function (e) {
                const message = e?.message || e || _('Failed to activate profile.');
                ui.addNotification(null, E('p', _('Profile activation failed: ') + message), 'danger');
                return Promise.reject(message);
            });
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
