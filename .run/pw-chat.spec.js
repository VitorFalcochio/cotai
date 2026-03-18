const { test } = require('@playwright/test');

test('inspect new-request', async ({ page }) => {
  page.on('console', msg => console.log('CONSOLE', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('PAGEERROR', err.message));
  page.on('request', req => {
    if (req.url().includes('/chat/') || req.url().includes('/health') || req.url().includes('supabase')) {
      console.log('REQUEST', req.method(), req.url());
    }
  });
  page.on('response', res => {
    if (res.url().includes('/chat/') || res.url().includes('/health') || res.url().includes('supabase')) {
      console.log('RESPONSE', res.status(), res.url());
    }
  });
  await page.goto('http://127.0.0.1:5500/frontend/pages/new-request.html', { waitUntil: 'networkidle' });
  console.log('URL', page.url());
  console.log('BUTTON', await page.locator('#chatComposerSubmit').count());
  console.log('FORM', await page.locator('#chatComposerForm').count());
  console.log('BODYCLASS', await page.locator('body').getAttribute('class'));
});
