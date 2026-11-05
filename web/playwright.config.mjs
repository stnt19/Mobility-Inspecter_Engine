import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'e2e',workers:1,timeout:60000,
 use:{baseURL:'http://127.0.0.1:8766',viewport:{width:1280,height:800},launchOptions:{args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']}},
 webServer:{command:(process.env.PYTHON|| (process.platform==='win32'?'".venv\\Scripts\\python.exe"':'python'))+' -m engine.server --port 8766 --data .validation/e2e',cwd:'..',url:'http://127.0.0.1:8766/api/health',reuseExistingServer:false},
 outputDir:'../.validation/browser-results'
});
