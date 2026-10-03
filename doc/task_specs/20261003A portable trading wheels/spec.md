# 独立交易 wheel 发布

## 任务边界

在用户已准备的 hxse/vnpy-ctp Git 仓库实施。复制 ccxt-proxy2 已打补丁的交易绑定、对应原生库和来源记录，迁入必要原生验证；创建可独立理解的文档、构建定义和自动发布工作流。

ccxt-proxy2 不删除、不修改、不切换依赖。HTTP 业务、账户、缓存和服务容器均不迁入。没有真实交易或行情验证。

交付应包括实际运行的构建/发布验证。目标为四个系统/架构、五个普通 CPython 版本共 20 个 wheel。原生库缺失的平台明确不支持，不以模拟或修改 wheel 标签虚构支持。

## 任务规范

SDK 沿用 6.7.11.4+ccxtproxy.2 的退出 GIL、回调所有权、终止队列及 GB18030 修复。新打包修订号为 ccxtproxy.3，原生库字节不变。平台链接单独处理；macOS 按配套头文件移除实际不存在的接口与字段，false 模式开关明确拒绝，中文解码复用相同 Python codec。

每次分支 push 自动构建该次 HEAD，完整 Git SHA 纳入版本号。来源、版本和平台集合在发布前校验。全部目标的修复后 wheel 安装测试通过才能公开 Release。先草稿、完整上传与摘要核验、再发布；已发布产物不可覆盖，同提交可幂等重跑。

详细有效约束在 doc/current_specs/native_api.md 与 doc/current_specs/release.md 中定义，不形成另一套发布入口。

## 公开接口与用户写法

```python
from vnpy_ctp import TdApi, __version__
api = TdApi()
print(__version__, api.getApiVersion())
```

```bash
just setup
just test
just check
just build
just test-native '.wheelhouse/vnpy_ctp-6.7.11.4+ccxtproxy.3-cp313-cp313-linux_x86_64.whl'
```

Git push 自动触发；发布版本为基础版本加 `.g<完整 commit SHA>`，标签为 `v<版本>`。公开 Release 提供 wheel、SHA256SUMS 和含固定 URL 的 manifest.json。错误平台、ABI、版本、重复/缺失单元、额外依赖和上传不完整均阻断发布。

## 测试、验证与阶段过渡

使用 just test 和 just check 验证版本计算、完整矩阵、结构/元数据、草稿恢复、已发布保护和来源校验。使用 just build 与 just test-native 对本机 wheel 做真实加载和离线生命周期检查。

原生测试必须覆盖无前置 init/exit、假 TCP 断线与 GIL 争用、排队/迟到回调的 payload 释放、GB18030 及非法字节；不替换已安装 wheel，不使用交易凭据。

用户已授权远端 Actions 构建与 Release 发布。推送后核对 Linux、Windows 和两个 macOS 架构的实际运行结果；失败先修复，不能将未测试的平台宣布为支持。应用消费暂留原链，退出条件为后续明确授权的消费迁移。
