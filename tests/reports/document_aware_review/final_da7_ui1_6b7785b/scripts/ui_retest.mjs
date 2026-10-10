// Final DA-7 + UI1 retest - REAL frontend (Vite dev server, live mode) driven in Microsoft Edge via playwright-core.
// NON-DESTRUCTIVE: never clicks "Move files"; no approve/undo. Scans the fresh UI-L root created by api_retest.py.
// playwright-core is installed in the session scratchpad (not the repo); pass its folder as PW_DIR.
//
//   $env:PW_DIR = '<scratchpad>\uidriver'; node tests\reports\document_aware_review\final_da7_ui1_6b7785b\scripts\ui_retest.mjs
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync, existsSync } from 'node:fs'
import { homedir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(path.join(process.env.PW_DIR, 'package.json'))
const { chromium } = require('playwright-core')
const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'ui')
const BASE = path.join(homedir(), 'AppData', 'Local', 'Temp', 'ghostos-final-da7ui1')
const ROOT = path.join(BASE, 'UI-L')
const API = 'http://127.0.0.1:8000'
if (existsSync(OUT)) { console.error(`STOP: ${OUT} exists`); process.exit(1) }
mkdirSync(OUT, { recursive: true })

const redact = (s) => (typeof s === 'string' ? s.split(BASE).join('<TEST_BASE>').split(BASE.replaceAll('\\', '\\\\')).join('<TEST_BASE>') : s)
const results = []
const rec = (id, check, expected, actual, ok, note = '') => {
  const status = typeof ok === 'string' ? ok : ok ? 'PASS' : 'FAIL'
  results.push({ id, method: 'UI (Edge + real frontend, live backend)', check, expected, actual: redact(JSON.stringify(actual)), status, note })
  console.log(`[${status}] ${id} ${check}\n      expected: ${expected}\n      actual:   ${redact(JSON.stringify(actual))}${note ? `\n      note: ${note}` : ''}`)
}
const net = []
let shot = 0
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
page.on('response', async (res) => {
  const req = res.request()
  if (!req.url().startsWith(API + '/api/') || req.url().endsWith('/api/status')) return
  let body = null
  try { body = await res.json() } catch { body = null }
  net.push({ at: new Date().toISOString(), method: req.method(), url: req.url().replace(API, ''), request_body: redact(req.postData() ?? null), status: res.status(), response: body })
})
const snapPng = async (name) => page.screenshot({ path: path.join(OUT, `${String(++shot).padStart(2, '0')}_${name}.png`) })
const patches = () => net.filter((n) => n.method === 'PATCH')

try {
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' })
  await snapPng('start')
  await page.getByRole('button', { name: 'try the demo files' }).first().click()
  await page.getByPlaceholder('C:\\Users\\you\\Documents\\Receipts').fill(ROOT)
  await snapPng('typed_root')
  await page.getByRole('button', { name: /Start reading/ }).click()
  await page.getByRole('button', { name: 'Review them one by one' }).waitFor({ timeout: 300000 })
  await snapPng('review_choice_dialog')
  const scanPost = net.find((n) => n.method === 'POST' && n.url === '/api/scan')
  const scanId = scanPost?.response?.scan_id
  rec('U0', 'UI scans the fresh typed root (not the committed fixtures)', 'POST /api/scan root = <TEST_BASE>/UI-L', scanPost?.request_body, Boolean(scanPost && scanPost.request_body.includes('<TEST_BASE>') && scanPost.request_body.includes('UI-L')))
  await page.getByRole('button', { name: 'Review them one by one' }).click()

  const docsResp = await (await fetch(`${API}/api/scans/${scanId}`)).json()
  const docs = Object.fromEntries(docsResp.documents.map((d) => [d.relative_path, d]))
  const brief = (d) => ({ status: d.status, flags: d.review_flags.map((f) => f.code), amount: d.classification?.amount ?? null, amount_text: d.classification?.amount_text ?? null, user_corrected: d.user_corrected, review_disposition: d.review_disposition })
  writeFileSync(path.join(OUT, 'ui_scan_initial.json'), redact(JSON.stringify(docsResp, null, 2)))

  for (const [id, rel, label] of [['U1', 'fu/receipts/bayside-office-mart.pdf', 'Bayside (amount_conflict, amount empty)'], ['U2', 'fu/receipts/kanto-stall-cash-note.txt', 'Cash note (missing_amount, amount empty)']]) {
    const d = docs[rel]
    if (!d || d.status !== 'needs_review') { rec(id, `${label}: Looks right blocked`, 'needs_review document in Check list', d ? brief(d) : 'missing', 'BLOCKED', 'precondition from live model not met'); continue }
    const name = rel.split('/').pop()
    await page.getByRole('listbox', { name: 'Files to check' }).getByText(name, { exact: false }).first().click()
    const panel = page.getByRole('complementary', { name: 'File details' })
    await panel.waitFor()
    const amountValue = await panel.getByLabel('Amount').inputValue().catch(() => '(no amount box)')
    const button = panel.getByRole('button', { name: /Looks right/ })
    const disabled = await button.isDisabled()
    const hint = await panel.getByText('Type the amount you actually paid to confirm it').isVisible().catch(() => false)
    await snapPng(`${name}_panel`)
    const before = patches().length
    await button.click({ force: true, timeout: 3000 }).catch(() => {})
    await page.waitForTimeout(1500)
    const sent = patches().slice(before)
    const after = (await (await fetch(`${API}/api/scans/${scanId}`)).json()).documents.find((x) => x.relative_path === rel)
    rec(id, `${label}: "Looks right" blocked, no malformed request`, 'amount box empty; button disabled; hint shown; forced click sends no PATCH; record unchanged',
      { amount_box: amountValue, disabled, hint_visible: hint, patches_sent: sent, before: brief(d), after: brief(after) },
      amountValue === '' && disabled && hint && sent.length === 0 && JSON.stringify(after) === JSON.stringify(d))
    await panel.getByRole('button', { name: 'Close file details' }).click()
  }

  const plan = await (await fetch(`${API}/api/scans/${scanId}/plan`)).json()
  const partial = await (await fetch(`${API}/api/scans/${scanId}/plan?mode=partial`)).json()
  writeFileSync(path.join(OUT, 'ui_plan_after.json'), redact(JSON.stringify({ plan, partial }, null, 2)))
  const flagged = ['fu/receipts/bayside-office-mart.pdf', 'fu/receipts/kanto-stall-cash-note.txt']
  const rows = plan.report_rows.filter((r) => flagged.includes(r.source_filename)).map((r) => [r.source_filename, r.status, r.amount])
  rec('U3', 'Flagged empty-amount documents stay out of expense rows and totals (UI session plan, blocking + partial)', 'not accepted, amount null; totals exclude them',
    { rows, totals: plan.totals, partial_totals: partial.totals, blocking: plan.blocking_review_count },
    rows.every(([, s, a]) => s !== 'accepted' && a === null) && partial.report_rows.filter((r) => flagged.includes(r.source_filename)).every((r) => r.status !== 'accepted'))
  await snapPng('files_after')
  rec('U4', 'No approve/undo/move request was sent by the UI run', 'no POST to /approve or /undo', net.filter((n) => /approve|undo/.test(n.url)).map((n) => n.url), !net.some((n) => /approve|undo/.test(n.url)))
} catch (e) {
  rec('UX', 'UI run', 'completes', String(e), 'BLOCKED', 'driver error')
  await snapPng('error').catch(() => {})
} finally {
  writeFileSync(path.join(OUT, 'network_log.json'), redact(JSON.stringify(net, null, 2)))
  writeFileSync(path.join(OUT, 'results_ui.json'), JSON.stringify(results, null, 2))
  await browser.close()
  const counts = results.reduce((a, r) => ({ ...a, [r.status]: (a[r.status] ?? 0) + 1 }), {})
  console.log(JSON.stringify(counts))
}
