"""验证启动脚本使用的前端目录及 API 与页面路由边界。"""
import unittest
from pathlib import Path
import httpx
from app.main import app, _FRONTEND_DIST


class StaticRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def test_frontend_and_api_routes(self):
        expected = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
        self.assertEqual(Path(_FRONTEND_DIST), expected)
        self.assertTrue((expected / 'index.html').is_file(), '请先构建前端')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            for path in ('/', '/reader/synthetic'):
                response = await client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('<div id="root">', response.text)
            response = await client.get('/api/health')
            self.assertEqual(response.json(), {'status': 'ok'})
            response = await client.get('/api/missing')
            self.assertEqual(response.status_code, 404)
            response = await client.get('/%2e%2e/package.json')
            self.assertEqual(response.status_code, 404)
