import {test,expect} from '@playwright/test';
import path from 'node:path';
const fixture=name=>path.resolve('../.validation/fixtures',name);
test('tablet photo → Python inference → correction → SQLite reopen',async({page,request})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.locator('#beginInspection')).toBeVisible();
 await page.screenshot({path:'../.validation/tablet-home.png',fullPage:true});
 await page.locator('#modelImport').setInputFiles(fixture('model.zip'));
 await expect(page.locator('#resources')).toContainText('배터리');
 await page.locator('#beginInspection').click();await page.locator('#vehicleId').fill('TEST-TABLET');
 await page.locator('#selectInstead').click();await page.locator('#photo').setInputFiles(fixture('photo.png'));
 await expect(page.locator('#infer')).toBeEnabled();await page.locator('#infer').click();
 await expect(page.locator('#count')).toHaveText('2');
 await page.locator('#parts button').first().click();await page.locator('#editBox').click();
 await page.locator('#editClass').selectOption('air_cleaner');await page.locator('#editForm button[type=submit]').click();
 await page.locator('#sessionNote').fill('Python 저장 테스트');await page.locator('#saveSession').click();
 await expect(page.locator('#saveStatus')).toHaveText('기기 저장 완료');
 const list=await(await request.get('/api/sessions')).json();const saved=await(await request.get('/api/sessions/'+list[0].id)).json();
 expect(saved.vehicle_id).toBe('TEST-TABLET');expect(saved.original[0].class).toBe('battery');expect(saved.reviewed[0].class).toBe('air_cleaner');expect(saved.reviewed[0].score).toBeNull();
 await page.reload();await page.locator('#tabletHistory').click();await page.locator('#historyList button').first().click();
 await expect(page.locator('#sessionNote')).toHaveValue('Python 저장 테스트');await expect(page.locator('#vehicleId')).toHaveValue('TEST-TABLET');
 await page.screenshot({path:'../.validation/tablet-result.png',fullPage:true});
 expect(errors).toEqual([]);
});
test('camera captures coherent Python frame and stops when leaving',async({page})=>{
 await page.goto('/');await expect(page.locator('#resources')).toContainText('배터리');
 await page.locator('#beginInspection').click();await page.locator('#vehicleId').fill('CAMERA-TEST');await page.locator('#startCamera').click();
 await expect(page.locator('#freezeAnalysis')).toBeEnabled({timeout:30000});await page.locator('#freezeAnalysis').click();
 await expect(page.locator('#inspectionEditor')).toBeVisible();await expect(page.locator('#count')).toHaveText('2');
 expect(await page.locator('#liveVideo').evaluate(v=>v.srcObject)).toBeNull();
 await expect(page.locator('#appStatus')).toContainText('같은 프레임');
});
test('tablet target validation and narrow layout',async({page})=>{
 await page.setViewportSize({width:768,height:1024});await page.goto('/');await page.locator('#beginInspection').click();await page.locator('#startCamera').click();
 await expect(page.locator('#targetError')).toContainText('장비번호');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
