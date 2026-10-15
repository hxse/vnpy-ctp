# 自动 wheel 发布

## 触发与版本

`.github/workflows/wheels.yml` 响应 `main` 的 push，并保留 `workflow_dispatch` 网页手动入口。日常只在 `main` 提交和同步，不创建任务或功能分支；其他分支及标签推送不触发构建。网页手动运行时选择 `main`。每个 commit 使用独立并发组，同一提交重跑不并行覆盖；不同提交互不取消。

基础版本的唯一声明在 meson.build；pyproject.toml 通过 meson-python 动态取得版本。CI 将完整 commit SHA 追加为 `.g<SHA>`，不使用本机时间、短 SHA 或运行次数。相同提交得到相同版本和 Release 标签；重跑不能覆盖已发布版本。

源文件和发布元数据显式使用 UTF-8 读写，不依赖 Windows 默认代码页；工作流同时为工具子进程启用 Python UTF-8 模式。

## 矩阵与测试

4 个系统/架构目标与 CPython 3.10～3.14 组成 20 个单元：Linux x86_64、Windows x64、macOS x86_64 和 macOS arm64。各自使用真实对应架构的运行器，Linux 在 manylinux_2_28 中编译。

prepare 先检查原生库来源、必须保留的补丁、单元测试和 lint。已完整发布的提交可直接复用；草稿继续构建。网络失败不能当成 Release 不存在，只有按标签查询的 HTTP 404 表示尚未创建。

每个单元构建 wheel、修复动态库依赖，再运行 tests/native/check_wheel.py。构建/测试失败使该发布失败；不以允许失败、静默跳过或移除验证换取矩阵成功。

## 发布与完整性

只有所有矩阵目标成功，release 作业才取得 contents:write 权限。构建作业只读源码，不使用交易账户或消费项目配置。

发布前检查文件名、内部 METADATA/WHEEL、Python ABI、平台、唯一交易扩展、原生库存在性和空依赖列表。要求恰好覆盖 20 个不同单元；拒绝重复、缺失、额外平台、版本错配和夹带行情/网关模块。

正式附件为 20 个 wheel、SHA256SUMS、manifest.json。manifest 包含版本、commit、绑定上游版本、厂商 API 版本/各平台完整构建串与原库摘要、平台能力差异和各 wheel 的 URL、大小、SHA256。厂商元数据来自 vendor/sdk.json，不能只靠 wheel 发行版本推断 API。

先创建草稿，上传所有附件并核对 GitHub 计算的 digest，再发布。上传失败不发布半套版本；同一提交草稿可重跑。已发布版本只核验复用，不删除、替换附件或移动标签。仓库可启用 immutable releases，将此约束同时交由 GitHub 执行。

Actions Artifact 仅在作业之间传递，保留七天。正式下载来自 Release 固定版本链接，不依赖 Artifact 保留期，也不使用 latest 自动升级。

## 开发与消费

开发入口为 just setup/test/check/build/test-native。普通 test 不编译 SDK或访问网络；test-native 必须显式传入已生成 wheel，安装时 --no-deps，随后执行离线原生验证。

消费方锁定 Release URL、版本和 SHA256，并核对实际厂商 API 版本。缺失 wheel 是否允许固定提交的源码构建由消费方决定；网络或摘要失败不能被解释成目标缺失。
人工评测完整变体以同一固定提交从源码构建，版本增加 .assessment；它不进入默认发布矩阵，也不能通过精简生产 wheel 的校验。

GitHub 的仓库或 Release 被删除、访问权限改变、服务不可达都可能使下载失败；长期链接不等于永久在线保证。已经校验过的本地安装缓存可由消费方正常复用。
