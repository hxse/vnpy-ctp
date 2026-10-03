# 原生交易 API

## 来源与边界

原生绑定从 ccxt-proxy2 的 6.7.11.4+ccxtproxy.2 补丁包复制，源包 SHA256 为 `385d1187e5c5c1d93ae799332d71f929e6bc399b4c4fb192a6ff3ace610b4588`。原始上游来源见 `vendor/origin.json`，复制时的文件校验值见 `vendor/migration.sha256`。

`native/` 的 CTP 头文件和生成式 C++ 绑定属于可识别来源的第三方代码，不按手写文件的行数上限机械拆分。后续平台适配记录在 `patches/portable-native.patch`。仓库中的原生 CTP 库保持上游字节并校验；wheel 依赖修复工具可调整加载路径、依赖名称和平台签名，最终产物另行计算 SHA256，不修改 SDK 算法。

本仓库只提供 `vnpy_ctp.TdApi` 和 `vnpy_ctp.api.TdApi`。打包路径仍为 `vnpy_ctp/api/vnctptd.<ABI>.<so|pyd>`。没有完整网关、行情扩展、vnpy 框架或 GUI 依赖。

Linux/Windows 沿用原来的交易调用和回调实现。补丁包括：exit 释放 GIL 后等待原生线程；终止标志原子化；回调 payload 由 shared_ptr 持有；终止时清空队列并拒绝迟到入队；在持有 GIL 时使用 Python GB18030 解码器。

macOS 使用同一 GB18030 路径，退出 iconv 全局状态。Windows 用 SDKDDKVer.h 替代上游缺失的 targetver.h，并显式使用 UTF-8 编译。

## 平台与加载

Linux 仅使用现有 x86_64 ELF 库；Windows 仅使用现有 x64 DLL/import library；macOS 使用自带 x86_64/arm64 的 Framework。Linux wheel 由 manylinux_2_28 构建并修复依赖。Windows 用 delvewheel，macOS 用 delocate，产物安装测试在修复后执行。

构建必须按真实目标架构选择原生库；不改标签冒充其他平台，不自动模拟。安装依赖为空，加载入口不能间接导入 vnpy 或 Qt。

## macOS 能力差异

macOS 绑定使用配套 macOS 头文件，不能用新版 Linux 头文件套用旧 Framework 的虚函数布局。

当前缺少的请求/配置接口为：

- RegisterWechatUserSystemInfo、SubmitWechatUserSystemInfo。
- ReqQryUserSession、ReqQryInvestorInfoCommRec、ReqQryCombLeg。
- ReqOffsetSetting、ReqCancelOffsetSetting、ReqQryOffsetSetting。

对应的不可用绑定和回调不注册，调用方不能依赖其存在。完整列表在 `native/capabilities.json`，发布清单携带同一数据。

Mac 的 RspUserLogin 没有 LoginDRIdentityID、UserDRIdentityID、LastLoginTime、ReserveInfo；InvestorPosition 和 TradingAccount 没有 OptionValue。响应只转换实际存在的字段，不填造值。

Mac 原生 CreateFtdcTraderApi 只有路径参数。Python 保持 `createFtdcTraderApi(path, True)` 两个显式参数的写法，但 false 明确抛 ValueError，不默默忽略不支持的模式开关。

## 离线验证

必须从已经安装的 wheel 导入真实扩展，不能在测试中再次用源码替换它。无交易前置循环创建/init/exit；只请求无前置查询并断言连接失败码；断线竞态只连接 127.0.0.1 的假 TCP 前置，不认证、不登录。

公共头文件探针验证实际 C++ GB18030 解码、非法字节替换、排队数据释放、终止后拒绝入队及 TerminatedError。DLL 探针在独立子进程中加载，进程退出后才删除目录，避免 Windows 文件锁。

HTTP 响应模型、账户管理、下单风控和服务路由仍属于消费项目。本仓库不导入 ccxt-proxy2，不复制其配置或业务测试。
