// 使用本机 Vite 和拦截的合成数据验证阅读流程，不访问真实后端或 AI。
const assert = require('node:assert/strict')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
;(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' })
  try {
    const page = await browser.newPage()
    const errors = []
    const writes = []
    let saved = { last_paragraph_id: 'para_2_1_001', chapter_status: { ch_1: 'completed', ch_2: 'in_progress', last_paragraph_id: 'para_2_1_001' } }
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/api/**', async route => {
      const req = route.request(), path = new URL(req.url()).pathname
      let data
      if (path === '/api/settings') data = {}
      else if (path === '/api/documents') data = { documents: [] }
      else if (path.endsWith('/structure')) data = { title: 'Synthetic reader', chapters: [1,2,3].map(i => ({ id: `ch_${i}`, title: `Chapter ${i}`, sections: [] })) }
      else if (path.includes('/progress/')) {
        if (req.method() === 'PUT') { saved = req.postDataJSON(); writes.push(saved) }
        data = saved
      } else if (path.includes('/chapters/')) {
        const n = Number(path.split('_').at(-1))
        if (n === 1) await new Promise(resolve => setTimeout(resolve, 300))
        data = { chapter_id: `ch_${n}`, title: `Content ${n}`, sections: [{ id: `sec_${n}_1`, paragraphs: [1,2].map(i => ({ id: `para_${n}_1_00${i}`, text: 'Alpha Beta reading context.' })) }] }
      } else if (path.includes('/dictionary/')) {
        const word = decodeURIComponent(path.split('/').at(-1))
        if (word === 'Alpha') await new Promise(resolve => setTimeout(resolve, 350))
        data = { found: true, word_lemma: word, dictionary_entries: [{ index: 0, zh: word + ' meaning' }] }
      } else if (path.endsWith('/lookup/ai')) data = { ai_context: { explanation: req.postDataJSON().word + ' explanation' } }
      else throw Error('Unexpected request: ' + path)
      await route.fulfill({ json: data })
    })
    await page.goto(process.env.READER_TEST_URL || 'http://127.0.0.1:5179/reader/test')
    await page.getByRole('heading', { name: 'Content 2', exact: true }).waitFor()
    await page.getByRole('button', { name: /Chapter 1/ }).click()
    await page.getByRole('button', { name: /Chapter 3/ }).click()
    await page.getByRole('heading', { name: 'Content 3', exact: true }).waitFor()
    await page.waitForTimeout(450)
    assert.equal(await page.locator('.chapter-title').textContent(), 'Content 3')
    await page.locator('.word-clickable').filter({ hasText: /^Alpha$/ }).first().click()
    await page.locator('.word-clickable').filter({ hasText: /^Beta$/ }).first().click()
    await page.locator('.wc-explain').filter({ hasText: 'Beta explanation' }).waitFor()
    await page.waitForTimeout(400)
    assert.equal(await page.locator('.wc-head h3').textContent(), 'Beta')
    await page.keyboard.press('Escape')
    assert.equal(await page.locator('.word-card').count(), 0)
    await page.getByRole('button', { name: /Chapter 1/ }).click()
    await page.getByRole('heading', { name: 'Content 1', exact: true }).waitFor()
    await page.waitForTimeout(100)
    await page.getByRole('button', { name: '← 文库' }).click()
    await page.waitForTimeout(150)
    assert.ok(writes.length > 0)
    assert.ok(writes.every(w => !('last_paragraph_id' in w.chapter_status)))
    assert.equal(writes.at(-1).chapter_status.ch_1, 'completed')
    assert.deepEqual(errors, [])
    console.log('PASS: restore chapter; ignore stale chapter/word responses; word card stays open; flush progress; preserve completed status; clean chapter status; no browser errors')
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
