/* Read only the selected model credential; no persona, memory, or user sessions. */
'use strict';
const fs = require('fs');
const path = require('path');
const {createRequire} = require('module');
const cli = process.env.LINGSHU_DSH_CLI;
const probe = process.argv[2] === '--probe';
function fail(code) {
  process.stdout.write(JSON.stringify({type:'error', message:code})+'\n');
  process.exit(1);
}
if (!cli || !fs.existsSync(cli)) fail('RUNTIME_NOT_FOUND');
try {
  const localRequire = createRequire(cli);
  if (!process.env.DEEPSEEK_API_KEY && process.env.LINGSHU_DSH_CREDENTIALS) {
    const file = process.env.LINGSHU_DSH_CREDENTIALS;
    if (fs.existsSync(file)) {
      const {parseDocument} = localRequire('yaml');
      const doc = parseDocument(fs.readFileSync(file, 'utf8'), {uniqueKeys:true});
      if (doc.errors.length) fail('CREDENTIAL_FORMAT');
      const data = doc.toJS();
      const value = data?.version === 1 ? data.refs?.DEEPSEEK_API_KEY : data?.DEEPSEEK_API_KEY;
      if (typeof value === 'string' && value.trim()) process.env.DEEPSEEK_API_KEY = value;
    }
  }
  if (probe) {
    const metadata = localRequire('@deepseek-ai/dsh-headless/package.json');
    process.stdout.write(JSON.stringify({installed:true, version:metadata.version,
      credential_ready:!!process.env.DEEPSEEK_API_KEY})+'\n');
    process.exit(0);
  }
  if (!process.env.DEEPSEEK_API_KEY) fail('MISSING_CREDENTIAL');
  // The supported desktop CLI owns its module roots and profile composition.
  process.argv = [process.argv[0], cli, ...process.argv.slice(2)];
  import(require('url').pathToFileURL(cli).href).then(module => module.runDesktopCli(
    path.resolve(path.dirname(cli), '../../../..'),
    path.join(path.dirname(process.execPath), 'resources', 'runtime')
  )).catch(()=>fail('HARNESS_START_FAILED'));
} catch { fail('HARNESS_CONFIG_FAILED'); }
