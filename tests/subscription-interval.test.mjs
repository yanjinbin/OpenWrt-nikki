import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const root = new URL('../luci-app-nikki/htdocs/luci-static/resources/', import.meta.url);
const source = path => readFileSync(new URL(path, root), 'utf8');
const nikki = new Function('baseclass', 'rpc', source('tools/nikki.js'))(
    { extend: value => value }, { declare: () => () => {} }
);

test('both views use the same subscription interval setting and validation', () => {
    const options = [];
    const subscriptions = [{ '.name': 'first', name: 'First' }, { '.name': 'second', name: 'Second' }];
    const form = {
        Map: class {
            section() {
                const section = {
                    tab() {},
                    option(type, name) {
                        const option = { option: name, value() {}, depends(...args) { this.dependency = args; } };
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
    const app = new Function('form', 'view', 'uci', 'poll', 'nikki', '_', source('view/nikki/app.js'))(
        form, { extend: value => value }, { sections: () => subscriptions }, { add() {} }, nikki, value => value
    );
    app.render([null, {}, true, []]);
    const intervals = options.filter(option => option.ucioption === 'update_interval');
    assert.equal(intervals.length, 2);
    const grid = nikki.configureSubscriptionInterval({});
    for (const [index, option] of intervals.entries()) {
        assert.equal(option.ucisection, subscriptions[index]['.name']);
        assert.equal(option.default, grid.default);
        assert.equal(option.datatype, grid.datatype);
        assert.equal(option.rmempty, false);
        assert.equal(option.retain, true);
        assert.deepEqual(option.dependency, ['nikki.config.profile', 'subscription:' + option.ucisection]);
    }
    assert.match(source('view/nikki/profile.js'), /nikki\.configureSubscriptionInterval\(o\)/);
});
