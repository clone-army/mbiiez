// Exercise browser confirmation using mocked requests; no real game commands.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('mbiiez/web/static/js/node-context.js', 'utf8');
async function scenario(command, error, accept, expectedForces, expectedPrompts) {
  const sent = [], prompts = [];
  const context = {
    URL, Headers, Request,
    location: {href: 'https://panel.example/dashboard', origin: 'https://panel.example'},
    document: {querySelector: () => null, addEventListener: () => {}},
    window: {
      fetch: async (url, options) => {
        const data = JSON.parse(options.body); sent.push(data.force);
        const failure = error && !data.force;
        return {ok: !failure, clone: () => ({json: async () => ({error})})};
      },
      confirm: text => {prompts.push(text); return accept;}
    }
  };
  // Browsers expose window.fetch as the global fetch.
  context.fetch = (...args) => context.window.fetch(...args);
  vm.runInNewContext(source, context);
  const result = await context.window.mbiiInstanceCommand('/instance/legends/command', 'legends', command);
  assert.deepEqual(sent, expectedForces);
  assert.equal(prompts.length, expectedPrompts);
  if (expectedPrompts) assert.match(prompts[0], /People are playing on legends/);
  if (expectedPrompts && !accept) assert.equal(result, null);
}
(async () => {
  const occupied = 'eu: Players are online; explicit force is required (400)';
  await scenario('restart', occupied, true, [false, true], 1);
  await scenario('restart', occupied, false, [false], 1);
  await scenario('stop', occupied, true, [false, true], 1);
  await scenario('restart', null, true, [false], 0);
  await scenario('start', null, true, [false], 0);
  await scenario('restart', 'Access denied', true, [false], 0);
  console.log('6 browser command scenarios passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
