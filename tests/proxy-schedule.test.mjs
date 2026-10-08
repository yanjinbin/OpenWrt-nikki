import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../luci-app-nikki/htdocs/luci-static/resources/view/nikki/schedule.js', import.meta.url), 'utf8');

function render(status = {}, rows = [{ '.name': 'first', enabled: '1', group: '油管' }], runtime = {}) {
    const options = {};
    class Value {
        constructor(name) { this.option = name; this.choices = []; }
        value(value) { this.choices.push(value); }
        formvalue(id) { return rows.find(row => row['.name'] === id)?.[this.option]; }
        cfgvalue(id) { return this.formvalue(id); }
        renderWidget() { return this.keylist; }
    }
    const form = { Value, ListValue: Value, Flag: Value, DummyValue: Value,
        GridSection: class { handleModalSave() { return Promise.resolve("saved"); } },
        Map: class {
            section() {
                return { children: [], cfgsections: () => rows.map(row => row['.name']),
                    formvalue: (id, name) => rows.find(row => row['.name'] === id)?.[name],
                    option(type, name) {
                        const option = options[name] = new type(name);
                        option.section = this;
                        this.children.push(option);
                        return option;
                    } };
            }
            render() { return options; }
        }
    };
    const view = new Function('view', 'form', '_', 'uci', 'poll', 'E', source)(
        { extend: value => value }, form, value => value, { get: (_, id, name) => rows.find(row => row['.name'] === id)?.[name] }, { add() {} }, (tag, attrs, text) => ({ tag, attrs, text }));
    view.render([null, { groups: { '油管': { all: ['🇺🇸-ai专用-dmit', '高质量节点-select'] },
        'Other': { all: ['DIRECT'] } }, ...status }, runtime]);
    return options;
}

test('polling intervals are explicit with a one-minute default', () => {
    const option = render().proxy_schedule_interval;
    assert.equal(option.default, '1');
    assert.deepEqual(option.choices, ['1', '5', '10', '15', '30', '60']);
});

test('targets use the selected group and preserve exact Unicode names', () => {
    const options = render();
    assert.deepEqual(options.inside.renderWidget('first'), ['', '🇺🇸-ai专用-dmit', '高质量节点-select']);
    assert.equal(options.inside.validate('first', '🇺🇸-ai专用-dmit'), true);
    assert.notEqual(options.inside.validate('first', 'DIRECT'), true);
    const changes = [];
    for (const option of [options.inside]) {
        option.getUIElement = () => ({ getValue: () => '🇺🇸-ai专用-dmit',
            node: { querySelector: () => ({ replaceChildren: (...nodes) => changes.push(nodes.map(node => node.attrs.value)), dispatchEvent() {} }) },
            setValue: value => changes.push(value) });
    }
    options.group.onchange(null, 'first', 'Other');
    assert.deepEqual(changes, [['', 'DIRECT'], '']);
});

test('overlapping enabled periods are rejected, disabled overlaps are allowed', () => {
    const rows = [{ '.name': 'first', enabled: '1', group: '油管', start_time: '18:00', end_time: '23:00' },
        { '.name': 'second', enabled: '1', group: '油管', start_time: '22:00', end_time: '06:00' }];
    const options = render({}, rows);
    assert.notEqual(options.group.validate('first', '油管'), true);
    assert.notEqual(options.enabled.validate('first', '1'), true);
    rows[1].enabled = '0';
    assert.equal(options.group.validate('first', '油管'), true);
});

test('time format, equal boundaries, and midnight periods are validated', () => {
    const options = render({}, [{ '.name': 'first', start_time: '22:00', end_time: '06:00' }]);
    assert.equal(options.start_time.validate('first', '22:00'), true);
    for (const value of ['6:00', '24:00', '22:60', '22:00\n', '06:00'])
        assert.notEqual(options.start_time.validate('first', value), true);
});

test('API failure preserves saved names and exposes a recovery message', () => {
    const options = render({ error: true, groups: {} });
    assert.equal(options.group.validate('first', '油管'), true);
    assert.equal(options.inside.validate('first', 'saved target'), true);
    assert.match(options._api_error.cfgvalue(), /Saved names are preserved/);
});

test('modal copies resolve sibling values and widgets from their own section', () => {
    const options = render();
    const calls = [];
    const section = {
        formvalue: (_, name) => ({ group: 'Other', enabled: '1', start_time: '22:00', end_time: '06:00' })[name],
        children: ['inside'].map(name => ({ option: name, getUIElement: () => ({
            getValue: () => 'old', node: { querySelector: () => ({ replaceChildren: (...nodes) => calls.push(nodes.map(node => node.attrs.value)), dispatchEvent() {} }) },
            setValue: value => calls.push(value)
        }) }))
    };
    const group = { ...options.group, section };
    group.onchange(null, 'first', 'Other');
    assert.deepEqual(calls, [['', 'DIRECT'], '']);
    const inside = { ...options.inside, section };
    assert.deepEqual(inside.renderWidget('first'), ['', 'DIRECT']);
    assert.equal(inside.validate('first', 'DIRECT'), true);
    const start = { ...options.start_time, section };
    assert.notEqual(start.validate('first', '06:00'), true);
    assert.equal(start.validate('first', '22:00'), true);
});

test('saved choices remain selectable while discovery is unavailable', () => {
    const options = render({ error: true, groups: {} });
    assert.deepEqual(options.group.renderWidget('first', 0, '油管'), ['', '油管']);
    assert.deepEqual(options.inside.renderWidget('first', 0, 'saved target'), ['', 'saved target']);
    assert.match(options.inside.vallist[1], /Unavailable/);
    for (const name of ['group', 'inside'])
        assert.ok(source.includes("s.option(form.ListValue, '" + name + "'"));
});

test('an unchecked rule can be saved even when the checkbox input value is one', () => {
    const rows = [{ '.name': 'first', enabled: '0', group: '油管' },
        { '.name': 'second', enabled: '1', group: '油管' }];
    assert.equal(render({}, rows).enabled.validate('first', '1'), true);
});

test('only the in-period target is configurable', () => {
    assert.ok(render().inside);
    assert.equal(render().outside, undefined);
});

test('outside-period status reports no change and ignores legacy outside settings', () => {
    const row = { '.name': 'first', enabled: '1', group: '油管', inside: 'DIRECT', start_time: '18:00', end_time: '22:00', outside: 'old target' };
    const config = { ...row, outside: 'different legacy target' };
    const options = render({}, [row], { running: true, rules: [{ section: 'first', config, period: 'outside', current: 'manual' }] });
    assert.equal(options._status.textvalue('first').text, 'Outside period; selection unchanged');
});

test('same-group daily and overnight rules save when periods do not overlap', () => {
    const rows = [{ '.name': 'first', enabled: '1', group: '油管', start_time: '18:00', end_time: '23:00' },
        { '.name': 'second', enabled: '1', group: '油管', start_time: '23:01', end_time: '17:59' }];
    const options = render({}, rows);
    for (const row of rows) {
        assert.equal(options.group.validate(row['.name'], row.group), true);
        assert.equal(options.enabled.validate(row['.name']), true);
        assert.equal(options.start_time.validate(row['.name'], row.start_time), true);
        assert.equal(options.end_time.validate(row['.name'], row.end_time), true);
    }
    assert.match(options.start_time.validate('second', '22:59'), /18:00.*23:00/);
    assert.equal(options.start_time.validate('second', '23:00'), true);
});

test('modal save shows an overlap message and permits corrected periods', async () => {
    const rows = [{ '.name': 'first', enabled: '1', group: '油管', start_time: '18:00', end_time: '23:00' },
        { '.name': 'second', enabled: '1', group: '油管', start_time: '23:01', end_time: '17:59' }];
    const options = render({}, rows);
    const section = options.group.section;
    const notices = [];
    section.getActiveModalMap = () => ({ querySelector: () => null, prepend: node => notices.push(node) });
    const current = { ...rows[1], start_time: '22:59' };
    const modal = { section: 'second', children: [{ formvalue: (_, key) => current[key] }] };
    assert.equal(await section.handleModalSave(modal), undefined);
    assert.equal(notices[0].text[0].text, 'Cannot save schedule');
    assert.match(notices[0].text[1].text, /油管.*18:00.*23:00/);
    current.start_time = '23:01';
    assert.equal(await section.handleModalSave(modal), 'saved');
});
