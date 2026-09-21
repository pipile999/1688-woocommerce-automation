2026-09-21 生效：先读 SITE.md。生产仅用 fastenhardware-1688-product-import 与 sites/fastenhardware/runner.py。下文 Legacy/core hash 引用均为历史，不再用于生产路由；以新 Skill 独立规则为准。

# 长期执行规则

1. 新站业务独立；只复用旧站技术。禁止读取密码/TOKEN、旧 .env 或复制旧站认证配置；日志、文档及 Git 不保存秘密。需要登录由用户在登录界面完成。
2. 会话启动读取五份管理文件；结束更新 CURRENT_STATE.md 和任务状态。重要已确认决定才进入 DECISIONS.md。文件是长期依据。
3. 先复用 automation/legacy_skill/effective-skill；来源及版本差异见 LEGACY_SKILL_REFERENCE.md。用户本项目明确要求优先于旧业务默认值。不得凭旧仓库较早提交覆盖本机较新规则。
4. 定价固定 source_price / 0.7 / 6.7，继承 Decimal 两位小数 ROUND_HALF_UP；不得擅改或重复询问。每次重新读取真实源价格及 SKU。
5. 完整保留源 SKU、variation/spec ID、属性组合；Model 写 Offer ID；Source URL 仅后台保存。未知参数 UNKNOWN/UNVERIFIED，仅核实值进入公开页。不得编造标准、牌号、材料、认证、MOQ、包装、能力或库存。
6. 图片采用最终旧 Skill 的来源/去重/清理/OCR/增强浅水印检测/质量检查。主图仅同 offer 原始主图池，清晰正方形；本项目主图输出标准 600×600 或 800×800，不放大小源图伪装高清。保留原始高分辨率素材。详情长图不能进入主图或 Gallery。合格图仅 1–2 张也可。
7. Featured+Gallery 最多 5 张，全部角色独立成品通常最多 10 张，有真实 SKU 覆盖需要才记录例外。主图与详情不重复；仅一张可用图片时记录缺少独立详情素材，不能造图或重复填数。参数图转真实英文 HTML 表及有用干净裁图。不同英文文件名，ALT 描述实际内容。
8. 水印清除必须保持产品真实结构；严重背景污染使用已验证 rembg 流程，不留涂抹。用最高分辨率原图编辑，最后自适应 WebP 压缩，中文与污染残留未解决不标 PASS。
9. 发布继承完整关键检查，默认通过后直接 publish；FAIL 阻止该商品发布，普通 WARNING 留痕并继续批次。REST 回读 parent 和所有 variations；图片 HTTP 200 + image Content-Type；同 offer 溯源、SKU、价格、Model、分类、图片映射均验证。
10. 导入选择新站实时已有最准确分类，不在导入脚本中随意建类。研究后的新站分类建设属于已授权建站任务，与逐商品导入分开执行。未知 POST 结果先核对，禁止盲目重发创建。
11. 确定性任务用软件批量执行。精确缓存包含 offer、原 URL、素材 SHA、规格 hash、规则版本；禁止语义/跨 offer 缓存。新项目拥有独立缓存、媒体映射及检查点。离线回放不等于实时采集、模型执行或发布成功。
12. 森达所有真实在售商品 MUST；无链接仅 SENDA STORE COLLECTION = BLOCKED — STORE URL REQUIRED，其他工作继续。最终可叠加 HIGH OPPORTUNITY/NORMAL/SUPPORTING/LOW SEARCH，不因搜索量低删除。
13. 研究必须保留来源、日期、国家、口径、单位及验证状态；HS 汇总不能直接证明特定材质/标准的需求。缺少 Volume/KD 不编造；Ads competition 不是 organic KD。搜索工具结果不冒充指定国家 Google 实时排名。
14. 综合出口、搜索、B2B、批量、工程、复购、OEM、利润、中国供应优势、竞争、森达匹配评估。没有依据不打分；HIGH/MEDIUM/LOW 也须解释。A/B/C/MUST 分类在证据齐全后确定。
15. 产品、分类、材料、应用、标准、技术内容按一个主要意图一个主 URL 映射。无证据不强改标题；优先采购决策内容，禁止批量垃圾博客和互相争词。
16. 研究后可扩展真实供应商；不为凑数量铺货。不能假称制造商、认证或供货能力。WooCommerce 承载商品，前台优先 RFQ 而非小额零售。
17. 主题只比较免费 GeneratePress/Astra/Blocksy/Storefront；先核实当前兼容性，不堆视觉插件。域名未购买不阻塞准备；Staging 上线前限制索引，正式发布再解除并验证。
18. 上线后记录 URL、关键词、曝光、点击、CTR、排名、RFQ/Qualified RFQ；优先已有曝光且位置约 5–30 的页面，再优化高意图低表现页面。不能承诺收录、排名或成交。
19. D:/codex/fastener-site 是所有项目会话的唯一长期共同上下文；任何任务先读根目录五份管理文件以及 automation/legacy_skill/LEGACY_SKILL_REFERENCE.md、manifest.json，再读对应入口和工作区。五个入口全部继承根规则；03每批还须读取并应用有效SKILL.md及相关rules。规则变化按hash核实差异，不复用旧认证或悄悄覆盖快照。
20. Task 状态仅 TODO/RUNNING/BLOCKED/DONE；独立列明依赖和阻塞理由。领取 TODO→RUNNING；遇阻→BLOCKED 并继续下一个依赖已满足的 TODO。不得因森达、登录或服务器一项缺失停止其他研究、设计和本地准备。
21. 单轮持续到所有可执行任务完成，或剩余任务全部确实需要输入/登录/授权；禁止“第一批完成”提前停止。不能把尚可自主完成的任务人为标 BLOCKED。
22. 共同文件更新前重读，保留其他会话变更。入口引用 CURRENT_STATE/TASK_QUEUE 获取进度，不自行维护第二份状态真相。状态 DONE 必须限定实际交付范围；设计完成不等于部署、Google指标或发布通过。
23. 聊天过程保持简短；默认最终只用 DONE / BLOCKED / KEY RESULT / NEED FROM USER / NEXT 五项报告（按2026-09-18最新要求替代旧六项格式）。项目文件共享不代表无关联会话自动加载或后台调度；新用户要求优先。
24. 自动归档：市场/词/竞品→01_research；网站/WP/页面→02_site；1688/商品/图片/上传→03_products；GSC/SEO/内容/转化→04_growth；跨模块决定→DECISIONS；当前概况→CURRENT_STATE；任务状态→TASK_QUEUE；执行/交接审计→logs。复用脚本→automation相应模块，临时文件→work；根只放入口和管理资料。原有成果不因整理迁移或覆盖。
25. 数据交接：01_research/handoffs/research.csv→02/03/04；02_site/handoffs/site.csv→03/04；03_products/handoffs/products.csv→04；04_growth/handoffs/feedback.csv→01/02/03。表中引用权威文件和证据，不复制完整研究；所有ID/URL/指标只填真实核验值。未知ID留空并标UNVERIFIED，计划URL标PLANNED，不当已发布。
26. 完成有下游影响的成果时，生产模块更新自身交接表，并向logs/handoffs.csv追加event_id、任务ID、生产/消费模块、artifact_path、SHA256、证据、时间。下游每次启动检查尚未消费的事件，核验文件/hash后读取增量，在logs/handoff_receipts.csv追加接收记录。交接待接收不等于源任务BLOCKED；不会自动发送消息或唤醒聊天。
27. Growth反馈必须含真实周期/国家/设备/URL/指标证据及建议接收模块；01据此调整机会优先级，02处理架构/争词，03处理具体商品。新增工作以唯一Task ID写TASK_QUEUE；禁止以反馈直接覆盖原稿或随机全站重写。
28. 低Token：每次读短共享文件与入口，按任务读取相关行/增量；先检查交接hash/规则版本/既有结果，证据未变不重复分析。采集、下载、价格、SKU、CSV、尺寸/压缩、REST/HTTP、去重、状态及日志优先复用纯软件；LLM仅处理判断/文案/异常语义。缓存规则沿用第11条，当前价格/库存和访问条件不能因旧缓存被当已核验。
29. 多任务共享目录：领取时写任务状态和owner到执行日志，提交前重读共享文件；只改本任务行。发现别人RUNNING不重复执行。只读入口初始化不改任务状态、不发起采集/部署；用户业务短指令后按队列持续执行。旧需求归档保留追溯，冲突以当前用户指令和本根规则为准。
30. OPTION C为唯一视觉母版；C V3只扩展可读性、CTA、同一产品多规格/多产品Quote List和询盘国家/语言，不重设计或改Research分类/URL。Email唯一必填；Quote不是付款购物车，首期不配置任何支付网关；客户可快速单产品询盘或WhatsApp。
31. English为唯一商品数据库/SEO主源，旧最终Skill核心不变；多语言与RFQ在输出之后适配，不让Skill创建15份产品。保留真实SKU/产品及变体ID；语言不能参与Quote行唯一键；服务器重新读取商品/规格，不能信任前台提交的SKU/名称/价格。未知属性隐藏，不补造。
32. 准备EN/ES/RU/PT/DE/FR/IT/PL/TR/AR/KK/UZ/VI/TH/ID，可扩展。Translation Available与SEO Index Enabled独立，按页面L0–L3 allowlist控制，见02_site/multilingual/ARCHITECTURE.md。建设期noindex优先；正式上线先EN，其余不批量index/sitemap；有资格数不等于Google实际收录数。索引页self-canonical、互惠hreflang，禁止IP强制跳语言或?lang作为主SEO路径。不开自动大规模index。
33. Fastener词表须审校；SKU/Model/Offer ID/标准编号/材料牌号/强度数字/螺纹/尺寸/数字单位不可机器改写。Supplier Store/Offer ID/1688 URL只供管理员，不进入翻译请求、前台、公开API、SEO、Schema或公开素材名。展示层过滤不能只靠CSS。
34. RFQ先持久保存再通知，保留原始Message、Country、Language、Source、全部商品/变体/数量及URL；国家用可信服务器GeoIP，失败Unknown仍提交，禁止从语言猜国家，不收集无关精确位置。通知只发指定销售邮箱，API受理不等于收件成功。不得查看任何GeoIP/SMTP密钥。新站部署及真实送达与本机/桩测试分开验收。
35. 一个主要翻译方案，不堆插件；本轮选TranslatePress，多语言/SEO付费扩展未购买。每页仅加载当前语言，Arabic真RTL。按真实GSC国家/查询/页面/曝光/点击/CTR/排名及合格RFQ形成候选，按分类→应用→高机会产品推进；不依据假数据或页面数量扩张。本次C V3预览与方案测试后STOP，等用户确认；不批量上传森达。
