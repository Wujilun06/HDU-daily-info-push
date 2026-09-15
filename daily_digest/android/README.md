# 安卓 APK 工程（WebView 壳）

本工程是一个最小的 Android 应用外壳：打开后只加载一个网址——也就是电脑每天生成的
`output/index.html`（通过 `serve.py` 暴露出来的局域网/公网地址）。因此**内容每天自动更新，无需重新打包**。

## 一、构建 APK 需要的环境

| 组件 | 作用 | 本机现状 |
|------|------|----------|
| JDK 17 | 编译 Kotlin/Java | ✅ 已安装（Eclipse Adoptium jdk-17） |
| Android SDK（含 platform / build-tools） | 打包 APK | ❌ 未安装 |
| Gradle（或用工程里的 gradle wrapper） | 构建工具 | ❌ 未安装 |
| 签名 keystore | 正式发布签名（调试可用 debug 签名） | ❌ 未创建 |

> 简单说：**本机现在缺 Android SDK 和 Gradle**，所以无法在此直接产出 .apk 文件。
> 装齐后一次 `./gradlew assembleRelease` 即可。

## 二、两种方式生成 APK

### 方式 A：本机安装 SDK 后由我构建（需你授权联网下载约 1GB+）
1. 安装 Android SDK command-line tools，接受 license
2. 安装 build-tools 与 platform（api 34）
3. 用 gradle wrapper 执行 `assembleRelease`
4. 产物在 `app/build/outputs/apk/release/`

### 方式 B：你用 Android Studio（最省心）
1. 安装 Android Studio（已含 SDK + Gradle）
2. 打开本 `android/` 目录
3. 改 `app/src/main/res/values/strings.xml` 里的 `start_url` 为你电脑地址
4. Build → Build Bundle(s) / APK(s) → Build APK

## 三、零构建替代方案（推荐先试）
手机 Chrome 打开生成好的网页 → 「添加到主屏幕」，即获得一个桌面 App 图标，
点开即用、内容每日更新，无需任何 Android 环境。功能与 APK 等价。

## 四、配置要点
- `strings.xml` 的 `start_url`：改成 `http://电脑局域网IP:8080/index.html`
  （用 `python serve.py 8080` 启动；手机需连同一 WiFi）
- 公网访问可加 ngrok / frpc 穿透，再把 `start_url` 改成公网地址
- 正式发布请把 `app/build.gradle` 的 `signingConfig` 换成自有 keystore
