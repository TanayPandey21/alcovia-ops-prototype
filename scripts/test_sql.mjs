// Loads schema + seed + views into an in-memory Postgres 16 (PGlite) and runs every metric query.
// npm install && npm test
import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs';
const db = new PGlite();
for (const f of ['db/schema.sql', 'db/seed/seed.sql', 'db/views.sql']) await db.exec(fs.readFileSync(f, 'utf8'));
let failed = 0;
for (const dir of ['metrics/gtm', 'metrics/student']) {
  for (const f of fs.readdirSync(dir).sort()) {
    try {
      const rows = (await db.exec(fs.readFileSync(`${dir}/${f}`, 'utf8'))).at(-1).rows;
      console.log(`ok   ${dir}/${f}  (${rows.length} rows)`);
    } catch (e) { failed++; console.log(`FAIL ${dir}/${f}: ${e.message}`); }
  }
}
process.exit(failed ? 1 : 0);
