import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const root = new URL('../luci-app-nikki/htdocs/luci-static/resources/', import.meta.url);
const source = path => readFileSync(new URL(path, root), 'utf8');
function render(name) {
    const options = [];
    const subscriptions = [{ '.name': 'first', name: 'First' }, { '.name': 'second', name: 'Second' }];
    const form = {
        Value: class {
            renderWidget() { return { querySelector: () => this.input }; }
        },
        Map: class {
            section() {
                const section = {
                    tab() {},
                    option(type, name) {
                        const option = { option: name, choices: [], input: {},
                            value(...args) { this.choices.push(args); },
                            depends(...args) { this.dependency = args; } };
                        options.push(option);
                        return option;
                    },
                    taboption(tab, ...args) { return this.option(...args); }
                };
                return section;
            }
            render() { return options; }
        }
    };
    const nikki = new Function('baseclass', 'rpc', 'form', '_', source('tools/nikki.js'))(
        { extend: value => value }, { declare: () => () => {} }, form, value => value
    );
    const app = new Function('form', 'view', 'uci', 'poll', 'nikki', '_', source('view/nikki/' + name + '.js'))(
        form, { extend: value => value }, { sections: () => subscriptions }, { add() {} }, nikki, value => value
    );
    app.render([null, {}, true, []]);
    return options;
}

test('both views bind the same weekday, time, and enabled settings', () => {
    const app = render('app');
    const profile = render('profile');
    assert.equal(app.some(option => option.ucioption === 'update_interval'), false);
    for (const key of ['auto_update', 'update_weekdays', 'update_time']) {
        const options = app.filter(option => option.ucioption === key);
        assert.equal(options.length, 2);
        const grid = profile.find(option => option.ucioption === key);
        assert.ok(grid);
        assert.equal(grid.ucisection, undefined);
        for (const [index, option] of options.entries()) {
            assert.equal(option.ucisection, ['first', 'second'][index]);
            assert.deepEqual(option.default, grid.default);
            assert.equal(option.rmempty, false);
            assert.equal(option.retain, true);
            assert.deepEqual(option.dependency, ['nikki.config.profile', 'subscription:' + option.ucisection]);
        }
    }
});

test('weekday selection accepts multiple days and rejects empty or invalid days', () => {
    const option = render('profile').find(option => option.ucioption === 'update_weekdays');
    assert.deepEqual(option.default, ['0']);
    assert.deepEqual(option.choices.map(choice => choice[0]), ['1', '2', '3', '4', '5', '6', '0']);
    for (const value of [['0'], ['1', '3', '5'], '0 1', ['0', '1', '2', '3', '4', '5', '6']])
        assert.equal(option.validate(null, value), true);
    for (const value of [[], '', ['7'], ['01'], ['0', '*']])
        assert.notEqual(option.validate(null, value), true);
});

test('time uses a native picker with minute precision and strict validation', () => {
    const option = render('profile').find(option => option.ucioption === 'update_time');
    assert.equal(option.default, '04:00');
    option.renderWidget();
    assert.equal(option.input.type, 'time');
    assert.equal(option.input.step, '60');
    for (const value of ['00:00', '04:00', '23:59']) assert.equal(option.validate(null, value), true);
    for (const value of ['', '4:00', '24:00', '04:60', '04:00\n']) assert.notEqual(option.validate(null, value), true);
});
