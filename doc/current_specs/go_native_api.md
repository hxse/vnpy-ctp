# Linux Go 原生 C ABI

## 制品与加载

`go-v<版本>` Release 包含 `vnpy-ctp-go-native-linux-amd64.tar.gz`、`manifest.json` 和 `SHA256SUMS`。
版本来自 `meson.build`，并带有同次 `main` 提交的完整 SHA。清单绑定 C ABI 版本、Linux amd64/glibc 2.28、
CTP API 6.7.13、厂商完整构建串、原库 SHA256、构建工具链和归档及其成员摘要。

归档的 `include/vnctp_go.h` 是 C ABI 入口，厂商数据类型与它一起交付。`lib/` 含适配器与两个原始 SDK 动态库。
Go 用 cgo 链接 `-lvnctp_go`，并让动态加载器找到 `lib/`。适配器从自身所在目录加载两个厂商库。
先核对 `vnctp_go_abi_version()` 和两个 `vnctp_go_*_sdk_version()`，再创建句柄。

## 调用、回报与释放

每个 TdApi 或 MdApi 有独立句柄、队列和命令锁。创建时传入调用者专用的 flow 目录及生产模式。
交易启动接收私有与公共话题类型，前置地址需为 SDK 支持的地址。交易请求使用头文件的固定枚举和对应
厂商请求结构，调用时提供实际字节长度与正的原生请求编号。返回 `0` 表示接纳调用，厂商非零返回原样传递。
请求缓冲归调用者，C ABI 将请求复制后送入厂商方法。回调复制到句柄的队列，回包里不保存外部指针。

`poll` 最多写入调用者给定数量的事件，返回交付数量，等待超时返回 `0`。`data_size=0` 表明没有业务行，
`has_error` 标明原回调是否提供 `RspInfo`。回调类型、请求编号、终止标志和断线原因独立返回。
按事件类型和大小读取对应的 `vnctp_go_payload` 成员。字符数组保留厂商字节，业务层负责 GB18030 解码。
控制队列溢出返回 `VNCTP_GO_OVERFLOW`，调用者应废弃整代句柄及其未完成结果。

行情先交付控制事件。活跃合约最多 64 个，每个合约留一条最先到达的有效待交付报价。
订阅调用明确失败时释放本次预留槽，退订成功回报或断线时释放对应槽。报价被取走后同槽可接收下一条。

调用者先停止接纳新工作并收尾在途请求，再调用 `stop`。`stop` 唤醒 `poll`、解除 SPI 并确认厂商 API 释放。
所有调用退出且 `stop` 成功后执行 `destroy`，然后释放该句柄的 flow 占用。
原生释放发生异常时返回 `VNCTP_GO_NATIVE_FAILURE`，调用者保留所有权并交由进程退出完成清理。

## 构建与验收

SDK 原仓使用 `just build-go-native` 可在固定 manylinux 环境离线构建。Go 工具链版本见 `native/go/.go-version`。
门禁覆盖同请求号的不同队列、回调字段复制、控制溢出、报价槽和停止唤醒。cgo 探针从最终归档编译、
加载两个厂商 API，并在隔离网络验证版本、参数错误、未连接查询与实际释放。
独立 GitHub Actions 按同一规则构建和发布。 [发布规则](release.md)
