import test from 'node:test'
import assert from 'node:assert/strict'
import { uploadDocument, dictionaryLookup, aiLookup } from '../src/services/api.js'

test('upload surfaces server rejection and preserves the multipart boundary', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/documents/upload')
    assert.ok(options.body instanceof FormData)
    assert.equal(options.headers['Content-Type'], undefined)
    return new Response(JSON.stringify({ detail: 'Only PDF files are supported' }), { status: 400 })
  })
  await assert.rejects(uploadDocument(new Blob(['invalid'])), /Only PDF files are supported/)
})

test('upload surfaces an HTTP error even if the response is not JSON', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('Bad Gateway', { status: 502, statusText: 'Bad Gateway' }))
  await assert.rejects(uploadDocument(new Blob(['pdf'])), /Bad Gateway/)
})

test('lookup requests support cancellation and preserve the AI request body', async (t) => {
  const controller = new AbortController()
  const body = { word: 'test', paragraph_id: 2 }
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options })
    assert.equal(options.signal, controller.signal)
    return new Response('{}')
  })
  await dictionaryLookup('a/b', { signal: controller.signal })
  await aiLookup(body, { signal: controller.signal })
  assert.equal(calls[0].url, '/api/dictionary/a%2Fb')
  assert.equal(calls[1].options.method, 'POST')
  assert.deepEqual(JSON.parse(calls[1].options.body), body)
})
