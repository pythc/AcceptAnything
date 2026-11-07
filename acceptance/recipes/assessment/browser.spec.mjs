import {test, expect} from '../../../validation/node_modules/@playwright/test/index.mjs';
import AxeBuilder from '../../../validation/node_modules/@axe-core/playwright/dist/index.mjs';

test('BROWSER-ADMIN: guest protection, login, round persistence and logout', async ({page}, info) => {
  await test.step('未登录访问后台必须进入登录页', async () => {
    await page.goto('/admin'); await expect(page).toHaveURL(/\/login/);
  });
  await test.step('空表单与错误密码被拒绝', async () => {
    await page.getByRole('button', {name: '登录', exact:true}).click();
    await expect(page.getByText('请输入密码', {exact:true})).toBeVisible();
    await page.locator('#account input, input#account').fill('admin@acceptance.test');
    await page.locator('#password input, input#password').fill('Wrong-Synthetic-Password');
    await page.getByRole('button', {name:'登录', exact:true}).click();
    await expect(page.getByText('账号或密码错误', {exact:true})).toBeVisible();
  });
  await test.step('合成管理员登录并创建轮次，刷新后仍存在', async () => {
    await page.locator('#password input, input#password').fill('Acceptance-Synthetic-Only-2026');
    await page.getByRole('button', {name:'登录',exact:true}).click();
    await expect(page).toHaveURL(/\/admin/);
    await page.getByRole('link', {name:'考核批次',exact:true}).click();
    const title = '自动验收-' + process.env.ACCEPTANCE_RUN;
    await page.getByRole('textbox', {name:'轮次名称',exact:true}).fill(title);
    await page.getByRole('button', {name:'创建轮次',exact:true}).click();
    await expect(page.getByRole('group', {name:'轮次筛选'}).getByRole('button', {name: title+' 0 个批次',exact:true})).toBeVisible();
    await page.reload();
    await expect(page.getByRole('group', {name:'轮次筛选'}).getByRole('button', {name: title+' 0 个批次',exact:true})).toBeVisible();
    await info.attach('round-persisted', {body: await page.screenshot(), contentType:'image/png'});
  });
  await test.step('退出后直接访问后台必须重新登录', async () => {
    await page.getByRole('button', {name:'退出登录',exact:true}).click();
    await page.goto('/admin'); await expect(page).toHaveURL(/\/login/);
  });
});

test('BROWSER-A11Y: login labels and accessible names', async ({page}, info) => {
  await page.goto('/login');
  const report = await new AxeBuilder({page}).withRules(['label','button-name','link-name']).analyze();
  await info.attach('axe-result', {body: JSON.stringify(report), contentType:'application/json'});
  expect(report.incomplete).toHaveLength(0);
  expect(report.violations).toHaveLength(0);
});
