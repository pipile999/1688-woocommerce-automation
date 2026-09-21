当前生产身份先读 SITE.md；数据路径以 sites/mypakg 为根，旧 data/output 仅为历史，不自动续跑。

# 1688-woocommerce-automation：共享项目上下文

## 项目身份

- 网站：https://mypakg.com
- 平台：WordPress + WooCommerce。
- 业务：1688商品采集、内容和图片处理、上架，以及本站SEO与付费流量规划。
- GitHub：pipile999/1688-woocommerce-automation。
- 共同工作目录：`D:\codex\新建文件夹\1688-woocommerce-automation-main`。
- Codex现有项目显示名称：`1688-woocommerce-automation-main`；这是同一项目，不新建第二个项目。
- 三个任务分区共享该目录、Skill、程序、数据、配置和本文件，但有各自聊天记录。

## 先读入口，按需加载，不复制规则

任务开始先读本文件，再读取有关的现有来源；不重新生成另一套商品规则。

1. `自动上架/skills/mypakg-1688-product-import/SKILL.md`：已有正式处理规则入口。
2. 同Skill的 `rules/images.md`：图片质量、来源绑定、角色、去重、修复规则。
3. `rules/woocommerce-safety.md`：身份映射、SKU/variation、价格/Model、分类、REST安全与验收。
4. `rules/keyword-research.md`、`rules/seo-and-conversion.md`：真实关键词证据、SEO与标题门槛。
5. `rules/local-runner.md`：本地优先、成本、缓存与断点规则。
6. `README.md`：项目结构和历史入门说明。其MVP/Draft等旧说明不得覆盖最新版Skill及用户最新指令。

以上 rules 路径均相对于 `自动上架/skills/mypakg-1688-product-import/`。只读当前任务必要部分；不因进入SEO或广告分区而启动完整采集/图片流程。

## 三个分区的默认职责

### 自动上架

1688采集 → 图片处理 → 翻译/内容 → SKU/价格/Model → 分类 → WooCommerce发布；执行现有Skill，不重建架构。
已有任务「自动上架」继续使用。保留已经确定的SKU、价格公式、Model、来源绑定、分类、图片及验收规则，具体以原Skill为准。

### SEO优化

只处理本站关键词调研、Product Title、Slug、Meta Title、Meta Description、Rank Math、产品页/分类页SEO、内链、文章、GSC分析与自然流量优化。
先依据真实关键词/搜索数据判断；候选词必须基于真实商品属性，未验证候选不能声称有搜索需求。缺数据为DATA_UNAVAILABLE，无明显改善则KEEP_CURRENT_TITLE。
复用现有Keyword Research / SEO Title Runner及cache/map；不默认逐商品调用LLM或Vision。
“看下SEO”默认诊断，不授权网站写入。优化请求按具体对象和范围执行，不能扩展为全站重写。现有Slug/URL默认保留，改Slug须明确授权并考虑重定向。

### 广告计划

只处理本站Google Ads等付费流量测试方案、预算、关键词、落地页、转化跟踪、广告数据分析，以及用真实广告效果识别重点SEO商品。
“给这批产品跑广告测试”首先准备对应产品的测试方案并核对现有数据与权限；没有明确确认预算、投放范围及启动授权，不启用广告、不提高预算、不产生实际广告花费。
不假造流量、点击、转化、ROAS或成本；不擅自安装/修改跟踪插件、标签或网站页面。

## 本地实现与历史结果索引

- 上架入口：`auto_import_runner.py`、`app/auto_import_runner.py`；三个Windows BAT是已有启动/续跑/结果入口。
- 关键词/标题：`app/keyword_research.py`、`app/google_keyword_planner.py`、`app/seo_title_builder.py`。
- Title-only：`app/title_only_runner.py`；不要默认重跑其固定历史批次，先核对当次目标与checkpoint。
- 关键词证据和全站关键词映射：`data/keyword-cache.json`、`data/keyword-map.json`、`data/google-seo-test/`。
- 历史商品原始数据/处理结果：`output/<offer_id>/`；历史批次manifest、audit、checkpoint位于`output/`的对应批次目录。
- 最近Title-only审计：`output/title-only-20260918/summary.json`、`checkpoint.json`和商品子目录；这是历史证据，不是实时状态。
- 历史范围/映射审计：`output/strict-reaudit-20260915/`；更新产品前必须重新验证映射，不把历史PASS当作当前授权。
- 本地环境由既有程序加载`sites/mypakg/.env`等私有配置；不得展示其值，浏览器登录不等于具备API权限。
- 当前根目录不是Git工作树；`.submit_repo/`是现有提交副本。需要提交时先核对差异，不能假设根目录文件已同步/已推送。

## 共同执行边界

- 当前用户明确指令优先；职责只提供上下文，不授予无范围的网站修改或广告支出权限。
- 不因分区切换重复采集、重做图片、重新查询已有效缓存的词或重跑已完成批次。
- 先看checkpoint与目标商品证据，再执行；正常WARNING按原规则隔离继续，映射不唯一不猜测。
- 三分区可能同时工作；写入前重新核对商品状态，避免覆盖另一个任务的新结果。
- 不触碰其它独立站项目。新的跨分区业务约定如需长期共享，应按用户授权更新本文件或已有规则引用，不复制冗长历史聊天。

## 上下文接入方式

根目录 `AGENTS.md` 要求三个分区每次任务先读取本文件；新分区初始化消息同时明确职责和共用目录。不依赖自动共享完整聊天历史。
机制参考：https://developers.openai.com/zh-Hans/docs/agent-configuration/agents-md
