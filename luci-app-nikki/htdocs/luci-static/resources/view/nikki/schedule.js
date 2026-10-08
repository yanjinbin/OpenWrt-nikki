'use strict';
'require form';
'require view';
'require uci';
'require poll';
'require tools.nikki as nikki';

return view.extend({
    load: function () {
        return Promise.all([
            uci.load('nikki_schedule'),
            nikki.getProxyGroups().catch(function () { return { error: true, groups: {} }; }),
            nikki.getProxyScheduleStatus().catch(function () { return {}; })
        ]);
    },
    render: function (data) {
        const status = data[1];
        const groups = status.groups || {};
        let runtime = data[2] || {};
        const m = new form.Map('nikki_schedule', _('Proxy Group Schedule'),
            _('Use router local time. The start time is inclusive and the end time is exclusive. Overnight periods are supported.'));
        let s, o;

        s = m.section(form.NamedSection, 'config', 'config');
        o = s.option(form.ListValue, 'proxy_schedule_interval', _('Check Interval (minutes)'));
        o.default = '1';
        o.rmempty = false;
        for (const interval of [1, 5, 10, 15, 30, 60]) o.value(String(interval));
        o.description = _('Checks run at clock-aligned intervals. A switch can be delayed by up to one interval. Nikki also checks after startup.');

        o = s.option(form.DummyValue, '_router_time', _('Router Local Time'));
        o.cfgvalue = function () { return E('span', { id: 'nikki-schedule-time' }, runtime.time || status.time || _('Unavailable')); };

        if (status.error) {
            o = s.option(form.DummyValue, '_api_error', _('Mihomo API'));
            o.cfgvalue = function () {
                return _('Cannot read proxy groups. Check that Nikki and its API are running. Saved names are preserved; reload this page to fetch the choices.');
            };
        }

        o = s.option(form.DummyValue, '_last_check', _('Last Check'));
        o.cfgvalue = function () { return E('span', { id: 'nikki-schedule-check' }, runtime.local_time || _('Waiting for check')); };

        s = m.section(form.GridSection, 'proxy_schedule', _('Schedules'),
            _('During the period, enabled schedules override manual selections at the next check. Outside the period, selections stay unchanged. Existing connections stay open. Other traffic using the same group is also affected.'));
        s.addremove = true;
        s.anonymous = true;
        s.modaltitle = _('Edit Schedule');
        s.render = function () {
            return Promise.resolve(form.GridSection.prototype.render.apply(this, arguments)).then(function (node) {
                const table = node.querySelector('.cbi-section-table');
                if (table) {
                    const scroll = E('div', { 'style': 'overflow-x: auto;' });
                    table.parentNode.insertBefore(scroll, table);
                    scroll.appendChild(table);
                }
                return node;
            });
        };

        const enabled = s.option(form.Flag, 'enabled', _('Enable'));
        enabled.default = '0';
        enabled.rmempty = false;
        enabled.editable = true;

        const group = s.option(form.ListValue, 'group', _('Proxy Group'));
        group.rmempty = false;
        function renderChoices(option, id, index, current, names) {
            option.keylist = ['', ...names];
            option.vallist = [_('-- Please choose --'), ...names];
            // Keep a saved choice visible during API failures or subscription changes.
            if (current && !names.includes(current)) {
                option.keylist.push(current);
                option.vallist.push(current + ' (' + _('Unavailable') + ')');
            }
            return form.ListValue.prototype.renderWidget.call(option, id, index, current);
        }
        group.renderWidget = function (id, index, current) {
            return renderChoices(this, id, index, current, Object.keys(groups));
        };

        function value(section, id, name) {
            return section.formvalue(id, name) ?? uci.get('nikki_schedule', id, name);
        }

        function periods(start, end) {
            if (![start, end].every(time => typeof time === 'string' && /^([01]\d|2[0-3]):[0-5]\d$/.test(time) && time.length === 5) || start === end)
                return [];
            const minute = time => Number(time.slice(0, 2)) * 60 + Number(time.slice(3));
            const from = minute(start), to = minute(end);
            return from < to ? [[from, to]] : [[from, 1440], [0, to]];
        }

        function validatePeriod(section, id, override = {}) {
            const field = name => Object.hasOwn(override, name) ? override[name] : value(section, id, name);
            if (field('enabled') !== '1') return true;
            const name = field('group');
            const ranges = periods(field('start_time'), field('end_time'));
            for (const other of s.cfgsections()) {
                if (other === id || value(s, other, 'enabled') !== '1' || value(s, other, 'group') !== name) continue;
                const start = value(s, other, 'start_time'), end = value(s, other, 'end_time');
                if (ranges.some(range => periods(start, end).some(peer => range[0] < peer[1] && peer[0] < range[1])))
                    return _('This period overlaps with another enabled schedule:') + ' ' + name + ' (' + start + '–' + end + ').';
            }
            return true;
        }

        s.handleModalSave = function (modalMap, ev) {
            const node = this.getActiveModalMap();
            node.querySelector('[data-schedule-error]')?.remove();
            const error = validatePeriod(modalMap.children[0], modalMap.section);
            if (error !== true) {
                node.prepend(E('div', { 'class': 'alert-message error', 'data-schedule-error': '' }, [
                    E('strong', {}, _('Cannot save schedule')),
                    E('p', {}, error)
                ]));
                return Promise.resolve();
            }
            return form.GridSection.prototype.handleModalSave.call(this, modalMap, ev);
        };

        function validateGroups(section) {
            for (const scope of new Set([s, section])) {
                for (const id of s.cfgsections()) {
                    for (const option of scope.children.filter(o => ['enabled', 'group', 'start_time', 'end_time'].includes(o.option)))
                        option.getUIElement?.(id)?.triggerValidation();
                }
            }
        }
        enabled.onchange = function () { validateGroups(this.section); };
        enabled.validate = function (id) {
            // Checkbox validators receive the input value even when unchecked.
            return validatePeriod(this.section, id, { enabled: this.formvalue(id) });
        };
        group.validate = function (id, name) {
            if (!status.error && value(this.section, id, 'enabled') === '1' && !Object.hasOwn(groups, name))
                return _('Select a running Selector group.');
            return validatePeriod(this.section, id, { group: name });
        };

        const start = s.option(form.Value, 'start_time', _('Start Time'));
        const end = s.option(form.Value, 'end_time', _('End Time'));
        start.default = '18:00';
        end.default = '22:00';
        for (const option of [start, end]) {
            option.rmempty = false;
            option.renderWidget = function () {
                const node = form.Value.prototype.renderWidget.apply(this, arguments);
                const input = node.querySelector('input');
                input.type = 'time';
                input.step = '60';
                return node;
            };
            option.validate = function (id, time) {
                if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(time) || time.length !== 5)
                    return _('Use HH:MM in 24-hour format.');
                const other = this.option === 'start_time' ? 'end_time' : 'start_time';
                if (time === value(this.section, id, other)) return _('Start and end times must differ.');
                return validatePeriod(this.section, id, { [this.option]: time });
            };
            option.onchange = function (ev, id) {
                validateGroups(this.section);
            };
        }

        const inside = s.option(form.ListValue, 'inside', _('During Period'));
        inside.rmempty = false;
        inside.renderWidget = function (id, index, current) {
            const names = groups[value(this.section, id, 'group')]?.all || [];
            return renderChoices(this, id, index, current, names);
        };
        inside.validate = function (id, name) {
            if (status.error || value(this.section, id, 'enabled') !== '1') return true;
            return groups[value(this.section, id, 'group')]?.all?.includes(name) || _('Select an option from this proxy group.');
        };

        group.onchange = function (ev, id, name) {
            const names = groups[name]?.all || [];
            // GridSection clones options into the edit dialog; use that dialog's controls.
            for (const option of this.section.children.filter(o => o.option === 'inside')) {
                const widget = option.getUIElement(id);
                if (!widget) continue;
                const current = widget.getValue();
                const select = widget.node.querySelector('select');
                select.replaceChildren(E('option', { value: '' }, _('-- Please choose --')),
                    ...names.map(value => E('option', { value }, value)));
                widget.setValue(names.includes(current) ? current : '');
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
            validateGroups(this.section);
        };

        function ruleStatus(id) {
            if (uci.get('nikki_schedule', id, 'enabled') !== '1') return _('Disabled');
            if (!runtime.running) return _('Nikki is stopped');
            if (runtime.stale) return _('Waiting for check');
            const result = (runtime.rules || []).find(row => row.section === id);
            const globalError = (runtime.rules || []).find(row => !row.section && row.error);
            if (!result) return globalError ? _(globalError.error) : _('Waiting for check');
            if (['enabled', 'group', 'inside', 'start_time', 'end_time'].some(
                key => (result.config?.[key] || '') !== (uci.get('nikki_schedule', id, key) || '')))
                return _('Waiting for check');
            if (result.error) return _(result.error);
            if (result.period === 'outside') return _('Outside period; selection unchanged');
            return (result.changed ? _('Switched to') : _('Selection matches')) + ': ' + result.current;
        }
        o = s.option(form.DummyValue, '_status', _('Schedule Status'));
        o.textvalue = function (id) { return E('span', { 'data-schedule-id': id }, ruleStatus(id)); };
        o.cfgvalue = o.textvalue;

        poll.add(function () {
            return nikki.getProxyScheduleStatus().then(function (result) {
                runtime = result;
                const clock = document.getElementById('nikki-schedule-time');
                const checked = document.getElementById('nikki-schedule-check');
                if (clock) clock.textContent = runtime.time || _('Unavailable');
                if (checked) checked.textContent = runtime.local_time || _('Waiting for check');
                document.querySelectorAll('[data-schedule-id]').forEach(function (node) {
                    node.textContent = ruleStatus(node.getAttribute('data-schedule-id'));
                });
            }).catch(function () {
                document.querySelectorAll('[data-schedule-id]').forEach(function (node) {
                    node.textContent = _('Status unavailable');
                });
            });
        }, 15);
        return m.render();
    }
});
