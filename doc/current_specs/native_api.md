# 原生交易 API

## 来源与边界

原生绑定从 ccxt-proxy2 的 6.7.11.4+ccxtproxy.2 补丁包复制，源包 SHA256 为 `385d1187e5c5c1d93ae799332d71f929e6bc399b4c4fb192a6ff3ace610b4588`。当前厂商 API 升级为 6.7.13；原始上游及各平台新 SDK 来源见 `vendor/origin.json`，当前厂商输入校验值见 `vendor/sdk.sha256`。`vendor/migration.sha256` 只保留迁移历史，不能用作当前 SDK 校验。

`native/` 的 CTP 头文件和生成式 C++ 绑定，以及 `assessment/` 的完整网关/常量，属于上述可识别来源的第三方代码，不按手写文件的行数上限机械拆分。历史平台适配见 `patches/portable-native.patch`，当前实现以源码为准。仓库中的原生 CTP 库保持上游字节并校验；wheel 依赖修复工具可调整加载路径、依赖名称和平台签名，最终产物另行计算 SHA256，不修改 SDK 算法。

默认发布 wheel 只提供 `vnpy_ctp.TdApi` 和 `vnpy_ctp.api.TdApi`。打包路径仍为 `vnpy_ctp/api/vnctptd.<ABI>.<so|pyd>`。没有完整网关、行情扩展、vnpy 框架或 GUI 依赖。

各平台共用交易调用和回调实现。补丁包括：exit/release 释放 GIL 后等待原生线程并允许重复关闭；Create 后未 Init 及析构也安全释放；终止标志原子化；回调 payload 由 shared_ptr 持有；终止时清空队列并拒绝迟到入队；在持有 GIL 时使用 Python GB18030 解码器。GetApiVersion 为不创建 API 的静态方法。

macOS 使用同一 GB18030 路径，退出 iconv 全局状态。Windows 用 SDKDDKVer.h 替代上游缺失的 targetver.h，并显式使用 UTF-8 编译。

## 平台与加载

Linux 仅使用现有 x86_64 ELF 库；Windows 仅使用现有 x64 DLL/import library；macOS 使用自带 x86_64/arm64 的 Framework。Linux wheel 由 manylinux_2_28 构建并修复依赖。Windows 用 delvewheel，macOS 用 delocate，产物安装测试在修复后执行。

Windows 显式启用 Visual Studio 环境并选择 cl，不能误用运行器 PATH 中的 MinGW 链接 MSVC C++ 库。macOS 同时设置 build_rpath 与 install_rpath：meson-python 从构建目录装配 wheel，不能只依赖 meson install 才生效的路径配置。

macOS 在 delocate 完成后，对 wheel 内每个 Mach-O 做本机 ad-hoc 签名并严格验证，再重建 wheel 的 RECORD。既有厂商签名或路径修复后的签名不能直接当作有效；不禁用系统签名检查，不修改仓库中的厂商原始文件。

构建必须按真实目标架构选择原生库；不改标签冒充其他平台，不自动模拟。安装依赖为空，加载入口不能间接导入 vnpy 或 Qt。

## 平台构建身份与人工评测

`vendor/sdk.json` 记录 API 6.7.13 与各平台完整构建串/原始库摘要；发布清单携带同一数据。Linux/Windows 的完整串为 `v6.7.13_20260225 14:16:30.12079`，macOS 为 `v6.7.13_MacOS_20260529 15:38:00`。它们的 API 版本相同，不能要求跨平台完整构建串相同。

macOS 使用配套 6.7.13 头文件及 universal Framework。旧版缺少的接口和字段已经由新版 SDK 提供，不再屏蔽；生产模式 true/false 均传递原生工厂。能力清单仍由 `native/capabilities.json` 提供。

人工评测按同一源码提交用 `python -m scripts.release.version <commit> --stamp --assessment`，再以 `uv build --wheel --config-setting=setup-args=-Dfull_gateway=true --config-setting=compile-args=-j1` 构建。版本末尾增加 `.assessment`，和生产精简包分开缓存、安装；默认发布矩阵不接受该变体。
该变体共用同一交易扩展，额外编译配套 6.7.13 行情库及上游完整 CtpGateway，供隔离 GUI 环境使用；不改变默认生产包。行情回调同样复用 shared_ptr 队列、GB18030 解码和安全退出。

## 离线验证

必须从已经安装的 wheel 导入真实扩展，不能在测试中再次用源码替换它。无交易前置循环创建/init/exit；只请求无前置查询并断言连接失败码；断线竞态只连接 127.0.0.1 的假 TCP 前置，不认证、不登录。

公共头文件探针验证实际 C++ GB18030 解码、非法字节替换、排队数据释放、终止后拒绝入队及 TerminatedError。DLL 探针在独立子进程中加载，进程退出后才删除目录，避免 Windows 文件锁。

HTTP 响应模型、账户管理、下单风控和服务路由仍属于消费项目。本仓库不导入 ccxt-proxy2，不复制其配置或业务测试。
