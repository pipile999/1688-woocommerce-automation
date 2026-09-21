2026-09-21 生效：先读 SITE.md。生产仅用 fastenhardware-1688-product-import 与 sites/fastenhardware/runner.py。下文 Legacy/core hash 引用均为历史，不再用于生产路由；以新 Skill 独立规则为准。

# FASTENER B2B INDEPENDENT WEBSITE

独立长期项目，2026-09-18 建立。完整原始需求保存在 PROJECT_BRIEF.txt。

目标链路：真实市场调查 → WordPress/WooCommerce → 真实产品 → Google 收录 → B2B 自然流量 → 合格询盘 → 成交。
核心定位 Industrial Fastener Supplier；Manufacturer、Solar、High Tensile 等细分定位由研究和真实供应能力验证后决定。
目标客户：进口商、分销商、批发商、工业采购、建筑公司、工程承包商、OEM、制造商、采购公司、大型项目采购。
商业模式：大宗、批发、工程、OEM、定制、分销和长期供货询盘；前台以 Request a Quote / Get Bulk Pricing / Send Your Drawing / Project Pricing / Contact Sales 为核心。
核心供应商：温州森达紧固件，有既往合作。所有真实在售商品必须最终上架，搜索需求只影响优化优先级。
技术路线：WordPress + WooCommerce 商品数据库；免费轻量主题；继承旧 1688 自动化、图片处理、SKU、定价及 REST 验证。先 Staging，再正式域名。
KPI：Organic Impressions、Qualified Organic Traffic、RFQ、Qualified RFQ、Orders；商品数、文章数、Rank Math 分数不是最终 KPI。
第一阶段约 80–150 个有意义的核心页面仅作研究参考，不是硬性数量，也不能限制森达全量。
长期依据：本目录五份管理文件；完整规则追溯到 PROJECT_BRIEF.txt 与 automation/legacy_skill。

长期入口：00｜项目总控 → 00_CONTROL.md；01｜市场调查·选品 → 01_research/AGENT.md；02｜网站建设 → 02_site/AGENT.md；03｜森达·产品上架 → 03_products/AGENT.md；04｜SEO·流量优化 → 04_growth/AGENT.md。UI任务归属/ID见logs/workspace_entries.json；全部直接使用本目录，不另建项目或工作树。
启动与交接的唯一规则在RULES.md，AGENTS.md负责路由。根管理文件为权威，模块入口只列职责/输入输出/依赖。业务状态与UI任务是否闲置分别记录。

## 2026-09-19 正式部署授权
C V3 为唯一正式母版，已获上线授权。正式域名 https://fastenhardware.com；销售邮箱 sales@fastenhardware.com；WhatsApp +8618664184619。本轮仅框架与验收，不批量上架。国家 Unknown 暂时接受。Legacy API 为新站独立托管连接，当前只允许商品读取、Draft 写入与图片上传；禁止旧站凭据复用。

2026-09-19验收：独立连接/原Legacy直传/商品读写四项PASS；原78个Python文件不变。产品74/变体81完成Draft验收，其他三组样本也撤回Draft。部署明细见02_site/deployment_report.md。仅邮件实际送达/域名验证等待用户回执；本轮STOP。
