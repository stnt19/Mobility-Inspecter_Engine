package com.mobility.engine;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.*;
import android.widget.TextView;
import android.widget.Toast;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Android lifecycle, camera permission, file picker and export shell. */
public final class MainActivity extends Activity {
    private WebView web;
    private String origin;
    private ValueCallback<Uri[]> picker;
    private PermissionRequest cameraRequest;
    private String pendingJson;
    private static final int PICK = 100, EXPORT = 101, CAMERA = 102;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        TextView loading = new TextView(this);
        loading.setText("비전 점검 · Python 엔진 준비 중…");
        loading.setPadding(32, 48, 32, 32);
        setContentView(loading);
        new Thread(() -> {
            try {
                // A versioned directory avoids serving a previous APK's scripts.
                File assets = new File(getFilesDir(), "tablet-web-v6");
                copyAssets("web", assets);
                synchronized (MainActivity.class) {
                    if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
                }
                String url = Python.getInstance().getModule("engine.android").callAttr("start",
                    new File(getFilesDir(), "python-inspection").getAbsolutePath(), assets.getAbsolutePath()).toString();
                runOnUiThread(() -> { if (!isDestroyed()) open(url); });
            } catch (Exception e) {
                android.util.Log.e("InspectionPython", "Startup failed", e);
                runOnUiThread(() -> loading.setText("Python 엔진을 시작하지 못했습니다. 앱을 다시 실행해 주세요.\n" + e.getMessage()));
            }
        }, "python-startup").start();
    }

    private void copyAssets(String source, File target) throws IOException {
        String[] children = getAssets().list(source);
        if (children != null && children.length > 0) {
            if (!target.isDirectory() && !target.mkdirs()) throw new IOException("Cannot create asset directory");
            for (String name : children) copyAssets(source + "/" + name, new File(target, name));
        } else {
            try (InputStream in = getAssets().open(source); OutputStream out = new FileOutputStream(target)) {
                byte[] block = new byte[65536]; int n;
                while ((n = in.read(block)) != -1) out.write(block, 0, n);
            }
        }
    }

    private boolean local(Uri uri) {
        return origin != null && (uri.getScheme() + "://" + uri.getAuthority()).equals(origin);
    }

    @android.annotation.SuppressLint("SetJavaScriptEnabled")
    private void open(String url) {
        Uri uri = Uri.parse(url); origin = "http://" + uri.getAuthority();
        web = new WebView(this);
        web.setBackgroundColor(0xfff4f6f8);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(true);
        web.getSettings().setMediaPlaybackRequiresUserGesture(true);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest r) { return !local(r.getUrl()); }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest r) {
                if (local(r.getUrl())) return null;
                return new WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", null, new ByteArrayInputStream(new byte[0]));
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> {
                    if (!local(request.getOrigin())) { request.deny(); return; }
                    boolean video = false;
                    for (String resource : request.getResources()) if (resource.equals(PermissionRequest.RESOURCE_VIDEO_CAPTURE)) video = true;
                    if (!video) { request.deny(); return; }
                    if (cameraRequest != null) cameraRequest.deny();
                    cameraRequest = request;
                    if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) grantCamera();
                    else requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA);
                });
            }
            @Override public void onPermissionRequestCanceled(PermissionRequest request) { if (cameraRequest == request) cameraRequest = null; }
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (picker != null) picker.onReceiveValue(null);
                picker = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE);
                boolean image = false;
                for (String type : params.getAcceptTypes()) if (type.startsWith("image/")) image = true;
                intent.setType(image ? "image/*" : "*/*");
                try { startActivityForResult(intent, PICK); }
                catch (Exception e) { picker.onReceiveValue(null); picker = null; }
                return true;
            }
            @Override public boolean onJsConfirm(WebView view, String url, String message, JsResult result) {
                new AlertDialog.Builder(MainActivity.this).setMessage(message)
                    .setPositiveButton("계속", (d,w) -> result.confirm()).setNegativeButton("취소", (d,w) -> result.cancel())
                    .setOnCancelListener(d -> result.cancel()).show(); return true;
            }
        });
        web.addJavascriptInterface(new Object() {
            @JavascriptInterface public void saveJson(String text) {
                if (text.length() > 2 * 1024 * 1024) return;
                runOnUiThread(() -> {
                    if (pendingJson != null || isDestroyed()) return;
                    pendingJson = text;
                    Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                        .setType("application/json").putExtra(Intent.EXTRA_TITLE, "engine-inspection.json");
                    try { startActivityForResult(intent, EXPORT); }
                    catch (Exception e) { pendingJson = null; }
                });
            }
        }, "AndroidExport");
        web.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom()); return insets;
        });
        setContentView(web); web.loadUrl(url);
    }

    private void grantCamera() {
        if (cameraRequest != null) { cameraRequest.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE}); cameraRequest = null; }
    }
    @Override public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code == CAMERA && cameraRequest != null) {
            if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) grantCamera();
            else { cameraRequest.deny(); cameraRequest = null; }
        }
    }
    @Override protected void onActivityResult(int code, int result, Intent data) {
        super.onActivityResult(code, result, data);
        Uri uri = result == RESULT_OK && data != null ? data.getData() : null;
        if (code == PICK && picker != null) { picker.onReceiveValue(uri == null ? null : new Uri[]{uri}); picker = null; }
        if (code == EXPORT) {
            String text = pendingJson; pendingJson = null;
            if (uri != null && text != null) try (OutputStream out = getContentResolver().openOutputStream(uri)) {
                if (out == null) throw new IOException("파일을 열 수 없습니다.");
                out.write(text.getBytes(StandardCharsets.UTF_8));
                Toast.makeText(this, "검사 기록 내보내기 완료", Toast.LENGTH_SHORT).show();
            } catch (Exception e) { Toast.makeText(this, "내보내기 실패", Toast.LENGTH_LONG).show(); }
        }
    }
    @Override protected void onPause() {
        if (web != null) { web.evaluateJavascript("window.stopInspectionCamera?.()", null); web.onPause(); }
        super.onPause();
    }
    @Override protected void onResume() { super.onResume(); if (web != null) web.onResume(); }
    @Override public void onBackPressed() {
        if (web == null) { super.onBackPressed(); return; }
        web.evaluateJavascript("Boolean(window.inspectionDirty?.())", result -> {
            if ("true".equals(result)) new AlertDialog.Builder(this).setMessage("저장하지 않은 변경 사항을 버리고 나갈까요?")
                .setPositiveButton("나가기", (d,w) -> finish()).setNegativeButton("계속 검사", null).show();
            else finish();
        });
    }
    @Override protected void onDestroy() {
        if (picker != null) picker.onReceiveValue(null);
        if (cameraRequest != null) cameraRequest.deny();
        if (web != null) { web.removeJavascriptInterface("AndroidExport"); web.destroy(); }
        super.onDestroy();
    }
}
