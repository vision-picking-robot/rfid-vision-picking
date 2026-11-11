package com.visionlab.galaxyremote

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.view.Gravity
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity(), NfcAdapter.ReaderCallback {

    private lateinit var webView: WebView
    private lateinit var urlInput: EditText
    private lateinit var modeStatusText: TextView
    private var nfcAdapter: NfcAdapter? = null

    // 기본값: false (전용 하드웨어 RFID 리더기 우선 시연 정책에 따라 보조 모드 선택 시에만 가동)
    @Volatile
    private var phoneNfcModeEnabled: Boolean = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        nfcAdapter = NfcAdapter.getDefaultAdapter(this)
        val prefs = getSharedPreferences("e0509_remote_prefs", Context.MODE_PRIVATE)
        val savedHost = prefs.getString("server_host", "192.168.0.10:8000") ?: "192.168.0.10:8000"

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0B1120"))
        }

        // 상단 서버 연결 바 (동일 Wi-Fi 로봇 PC IP 입력)
        val topBar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(24, 20, 24, 16)
            setBackgroundColor(Color.parseColor("#162032"))
        }

        urlInput = EditText(this).apply {
            setText(savedHost)
            hint = "로봇PC IP:8000 (예: 192.168.0.10:8000)"
            setTextColor(Color.WHITE)
            setHintTextColor(Color.parseColor("#64748B"))
            textSize = 13f
            setSingleLine(true)
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }

        val connectBtn = Button(this).apply {
            text = "서버 연결"
            textSize = 12f
            setBackgroundColor(Color.parseColor("#0284C7"))
            setTextColor(Color.WHITE)
            setOnClickListener {
                val host = urlInput.text.toString().trim().removePrefix("http://").removePrefix("https://").trimEnd('/')
                prefs.edit().putString("server_host", host).apply()
                connectToServer(host)
            }
        }

        topBar.addView(urlInput)
        topBar.addView(connectBtn)

        modeStatusText = TextView(this).apply {
            text = "📡 현재 모드: 전용 리더기 우선 (폰 NFC 대기 중)"
            setTextColor(Color.parseColor("#38BDF8"))
            textSize = 12f
            setPadding(28, 8, 28, 12)
            setBackgroundColor(Color.parseColor("#0F172A"))
        }

        webView = WebView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun onReceivedError(
                    view: WebView?,
                    request: WebResourceRequest?,
                    error: WebResourceError?
                ) {
                    if (request?.isForMainFrame == true) {
                        loadOfflineGuidePage(urlInput.text.toString().trim())
                    }
                }
            }
            addJavascriptInterface(GalaxyBridge(), "GalaxyNativeBridge")
        }

        root.addView(topBar)
        root.addView(modeStatusText)
        root.addView(webView)
        setContentView(root)

        connectToServer(savedHost)
    }

    private fun connectToServer(host: String) {
        val targetUrl = "http://$host/remote"
        Toast.makeText(this, "로봇 서버 연결 중: $targetUrl", Toast.LENGTH_SHORT).show()
        webView.loadUrl(targetUrl)
    }

    private fun loadOfflineGuidePage(host: String) {
        val html = """
            <!DOCTYPE html>
            <html lang="ko">
            <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
            <style>
              body { background:#0b1120; color:#f8fafc; font-family:sans-serif; padding:20px; text-align:center; }
              .card { background:#162032; border:1px solid #28354a; border-radius:14px; padding:20px; margin-top:20px; }
              h2 { color:#38bdf8; font-size:1.1rem; margin-bottom:10px; }
              p { color:#94a3b8; font-size:0.88rem; line-height:1.5; margin-bottom:12px; }
              code { display:block; background:#090d16; padding:10px; border-radius:8px; color:#22c55e; margin:10px 0; font-size:0.82rem; }
            </style></head>
            <body>
              <div class="card">
                <h2>🤖 로봇 PC 서버($host) 대기 중</h2>
                <p>1. 갤럭시 폰과 로봇 노트북을 <b>같은 Wi-Fi</b>에 연결하세요.</p>
                <p>2. 로봇 노트북에서 아래 명령으로 서버를 실행하세요:</p>
                <code>python scripts/start_lab.py --host 0.0.0.0</code>
                <p>3. 상단 입력창에 로봇 노트북의 Wi-Fi IP(예: <code>192.168.0.x:8000</code>)를 입력하고 <b>[서버 연결]</b>을 누르세요.</p>
              </div>
            </body></html>
        """.trimIndent()
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null)
    }

    private fun updateNfcReaderState() {
        val adapter = nfcAdapter ?: return
        runOnUiThread {
            if (phoneNfcModeEnabled) {
                val flags = NfcAdapter.FLAG_READER_NFC_A or
                        NfcAdapter.FLAG_READER_NFC_B or
                        NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK
                adapter.enableReaderMode(this, this, flags, null)
                modeStatusText.text = "📱 현재 모드: 갤럭시 뒷면 직접 NFC 태깅 활성화됨 (보조 모드)"
                modeStatusText.setTextColor(Color.parseColor("#C084FC"))
            } else {
                adapter.disableReaderMode(this)
                modeStatusText.text = "📡 현재 모드: 전용 하드웨어 리더기 우선 (폰 NFC 비활성)"
                modeStatusText.setTextColor(Color.parseColor("#38BDF8"))
            }
        }
    }

    override fun onResume() {
        super.onResume()
        updateNfcReaderState()
    }

    override fun onPause() {
        super.onPause()
        nfcAdapter?.disableReaderMode(this)
    }

    override fun onTagDiscovered(tag: Tag?) {
        if (!phoneNfcModeEnabled || tag == null) return
        val uidBytes = tag.id ?: return
        val uidHex = uidBytes.joinToString("") { "%02X".format(it) }
        vibratePhone(180)
        runOnUiThread {
            Toast.makeText(this, "📱 NFC 태그 인식: $uidHex", Toast.LENGTH_SHORT).show()
            webView.evaluateJavascript("if(window.onNativeNfcTag){window.onNativeNfcTag('$uidHex');}", null)
        }
    }

    private fun vibratePhone(durationMs: Long) {
        try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vm.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(durationMs, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                vibrator.vibrate(durationMs)
            }
        } catch (_: Exception) {
        }
    }

    inner class GalaxyBridge {
        @JavascriptInterface
        fun vibrate(ms: Long) {
            vibratePhone(ms)
        }

        @JavascriptInterface
        fun setNfcEnabled(enabled: Boolean) {
            phoneNfcModeEnabled = enabled
            updateNfcReaderState()
        }

        @JavascriptInterface
        fun promptNfcScan() {
            phoneNfcModeEnabled = true
            updateNfcReaderState()
            runOnUiThread {
                Toast.makeText(
                    this@MainActivity,
                    "갤럭시 뒷면 중앙에 상자 RFID/NFC 태그를 접촉하세요.",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }
}
