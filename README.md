# vnpy-ctp 交易 wheel

从 `ccxt-proxy2` 迁出的定制 CTP 交易绑定。保留原生交易 API 和项目已有修复，独立构建跨平台 wheel；不安装完整 VeighNa、GUI 或行情扩展。

上游为 `vnpy/vnpy_ctp` 6.7.11.4。迁移基线为 `6.7.11.4+ccxtproxy.2`，原始源码包的 SHA256、原生库校验值及补丁在 `vendor/`、`patches/` 中保存。本仓库的打包和平台适配修订从 `+ccxtproxy.3` 开始。

## 自动构建与下载

每次向任意分支 push 后，Actions 为该次推送的 HEAD 构建、测试并发布一个独立版本；一次 push 中包含多个提交时，只构建最终 HEAD。也支持手动重跑。发布创建的标签不再次触发构建。

版本由 `meson.build` 中的基础版本和完整 Git SHA 唯一确定：

```text
6.7.11.4+ccxtproxy.3.g<完整提交 SHA>
```

20 个目标全部通过后，工作流将 wheel、`SHA256SUMS`、`manifest.json` 上传到草稿 Release，核对 GitHub 返回的文件摘要后自动发布。同一提交已经发布时复用；不覆盖已发布文件。失败保留未公开草稿供重跑恢复。

[下载已发布版本](https://github.com/hxse/vnpy-ctp/releases)。`manifest.json` 包含每个 wheel 的平台、Python ABI、固定下载 URL、文件大小和 SHA256。消费方应锁定具体版本及摘要，不跟随 `latest` 自动升级。

```bash
# 从指定 Release 的 manifest.json 中选择匹配的 URL。
uv pip install --only-binary=:all: '完整的 .whl 下载地址'
```

下载地址属于 Release 附件，不依赖 Actions 中七天后清理的中转 Artifact。Release 长期保存，不承诺仓库被删除后仍可访问。

## 支持范围

| 平台 | 架构 | 构建目标 |
| --- | --- | --- |
| Linux glibc / manylinux_2_28 | x86_64 | CPython 3.10、3.11、3.12、3.13、3.14 |
| Windows | x64 | CPython 3.10～3.14 |
| macOS 11 及以上 | x86_64 | CPython 3.10～3.14 |
| macOS 11 及以上 | arm64 | CPython 3.10～3.14 |

不构建当前原生库未支持的 Linux/Windows arm64、32 位平台或 musl，也不将普通 CPython wheel 标记为 free-threaded / abi3。

macOS 附带的原生 SDK 比 Linux/Windows 接口较少。实际差异见 [平台规范](doc/current_specs/native_api.md)，同时写入发布清单；不存在的接口不提供虚假实现。

## 使用

```python
from vnpy_ctp import TdApi, __version__

api = TdApi()
print(__version__, api.getApiVersion())
```

原始低层交易方法和回调保留。`createFtdcTraderApi`、`init`、`exit` 等属于原生 SDK 生命周期；使用者负责及时释放实例。仓库测试不登录任何账户、不发送真实交易。

`ccxt-proxy2` 当前仍使用自己的固定源码包；本次迁移未修改该项目。后续消费新 wheel 时，须单独更新其版本检查、依赖链接和接口兼容校验。

## 开发与验证

```bash
just setup
just test
just check
just build
just test-native '.wheelhouse/vnpy_ctp-6.7.11.4+ccxtproxy.3-cp313-cp313-linux_x86_64.whl'
```

以上是 Linux / Python 3.13 开发机的完整写法。宿主 `.venv` 只用于本仓库开发；本地构建用于验证当前系统，公开的多平台 wheel 由 Actions/cibuildwheel 构建和修复。Linux CI 使用 manylinux，Windows/macOS 使用各自原生运行器。

测试分两层：普通单元测试验证版本、平台集合和发布失败语义；安装 wheel 后验证真实扩展加载、无前置生命周期、假 TCP 断线与 GIL 竞争、队列清理和 GB18030 解码。平台测试失败不能通过禁用该测试伪装成功。

详细规范见 [原生 API](doc/current_specs/native_api.md) 和 [发布流程](doc/current_specs/release.md)。
