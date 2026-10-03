# 自动 wheel 发布

## 触发与版本

`.github/workflows/wheels.yml` 响应所有分支的 push 和 workflow_dispatch。只处理本次 HEAD；标签推送不触发。每个 commit 使用独立并发组，同一提交重跑不并行覆盖；不同提交互不取消。

基础版本的唯一声明在 meson.build；pyproject.toml 通过 meson-python 动态取得版本。CI 将完整 commit SHA 追加为 `.g<SHA>`，不使用本机时间、短 SHA 或运行次数。相同提交得到相同版本和 Release 标签；重跑不能覆盖已发布版本。

## 矩阵与测试

4 个系统/架构目标与 CPython 3.10～3.14 组成 20 个单元：Linux x86_64、Windows x64、macOS x86_64 和 macOS arm64。各自使用真实对应架构的运行器，Linux 在 manylinux_2_28 中编译。

prepare 先检查原生库来源、必须保留的补丁、单元测试和 lint。已完整发布的提交可直接复用；草稿继续构建。网络失败不能当成 Release 不存在，只有按标签查询的 HTTP 404 表示尚未创建。

每个单元构建 wheel、修复动态库依赖，再运行 tests/native/check_wheel.py。构建/测试失败使该发布失败；不以允许失败、静默跳过或移除验证换取矩阵成功。

## 发布与完整性

只有所有矩阵目标成功，release 作业才取得 contents:write 权限。构建作业只读源码，不使用交易账户或消费项目配置。

发布前检查文件名、内部 METADATA/WHEEL、Python ABI、平台、唯一交易扩展、原生库存在性和空依赖列表。要求恰好覆盖 20 个不同单元；拒绝重复、缺失、额外平台、版本错配和夹带行情/网关模块。

正式附件为 20 个 wheel、SHA256SUMS、manifest.json。manifest 包含版本、commit、上游版本、平台能力差异和各 wheel 的 URL、大小、SHA256。

先创建草稿，上传所有附件并核对 GitHub 计算的 digest，再发布。上传失败不发布半套版本；同一提交草稿可重跑。已发布版本只核验复用，不删除、替换附件或移动标签。仓库可启用 immutable releases，将此约束同时交由 GitHub 执行。

Actions Artifact 仅在作业之间传递，保留七天。正式下载来自 Release 固定版本链接，不依赖 Artifact 保留期，也不使用 latest 自动升级。

## 开发与消费

开发入口为 just setup/test/check/build/test-native。普通 test 不编译 SDK或访问网络；test-native 必须显式传入已生成 wheel，安装时 --no-deps，随后执行离线原生验证。

本项目的产物生产和 ccxt-proxy2 的消费切换分阶段进行：本次只交付新仓库与发布能力，原项目不修改。消费方以后锁定 Release URL、版本和 SHA256，检查接口兼容性，并显式禁用源码编译回退。

GitHub 的仓库或 Release 被删除、访问权限改变、服务不可达都可能使下载失败；长期链接不等于永久在线保证。已经校验过的本地安装缓存可由消费方正常复用。
