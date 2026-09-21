2026-09-21 生效：先读 SITE.md。生产仅用 fastenhardware-1688-product-import 与 sites/fastenhardware/runner.py。下文 Legacy/core hash 引用均为历史，不再用于生产路由；以新 Skill 独立规则为准。

# 已确认决定

- 2026-09-18工作区整理：保留现有Project「紧固件独立站」与唯一根目录，在该Project直接创建00–04五个长期任务；全部local共享目录，无新项目/工作树。根RULES为唯一规则，四模块AGENT只做路由；跨模块交接用产物引用/hash/回执，禁止伪造已发布ID。按用户最新要求默认五项汇报。旧研究与Skill副本保留，修改前副本见logs/workspace_setup_20260918。

- 2026-09-18：项目根目录 D:/codex/fastener-site，与旧独立站业务隔离；依据用户完整任务。
- 2026-09-18：B2B 工业采购及 RFQ 为核心，WooCommerce 继续管理商品和变体。
- 2026-09-18：温州森达所有真实在售产品 MUST-LIST；缺少店铺 URL 不阻塞研究。
- 2026-09-18：定价继承 source_price / 0.7 / 6.7；本机 core.py 与新旧 Skill 一致，Decimal 两位 ROUND_HALF_UP。
- 2026-09-18：GitHub 核验提交 a46a8f4b013f90815c847a0fdb939534ad2a4aa8（2026-09-16）；本机另有 09-18 更新且安装 Skill 与工作目录 Skill SHA256 一致，作为较新有效规则快照保留，不能冒称已提交 GitHub。
- 2026-09-18：本项目标准主图输出 600/800 正方形，原图保留；最终图片规则的稀疏素材例外保留。

- 2026-09-18：按用户授权自主确定首版技术方案 GeneratePress FREE + WordPress原生区块 + WooCommerce；依据官方主题资料与维护范围，不宣称实测最快。
- 2026-09-18：首版英文全球B2B，US为SERP/Planner观察样本；AU/UK/UAE/SA是市场验证池，不是已承诺销量或国家门页计划。
- 2026-09-18：机会矩阵唯一文件01_research/product_matrix.csv，20个方向；首批优先验证hex bolts/self-drilling/threaded rod及配套nuts/washers，不锈钢为材料簇。A/B/C为研究优先级，森达所有真实在售仍MUST。
- 2026-09-18：同意图同主URL，hex screws/hex bolts不造重复类；标准/材料仅依据真实商品，Application不替代Product分类。
- 2026-09-18：取得27条可见Planner指标记录；只向精确匹配关键词写入区间，全部organic KD保持UNVERIFIED。无付费广告投放。

尚待真实输入：品牌/经营主体、域名或新站目标、RFQ收件人、真实SKU/供应证明。首版研究与模板已完成不等于部署/发布完成。上述实施选择由本轮任务授权作出，不冒称用户逐项确认。

- 2026-09-18：实际新站目标由用户指定为 https://fastenhardware.com/；新站已登录核验，替代旧的域名待输入状态；不操作旧业务站。
- 2026-09-18：用户要求先完成底座，再交付A工业制造/B国际供应商/C工程采购目录三套视觉方案；每套含桌面/手机首页、分类、商品；交付后STOP等待选择，禁止继续正式页面。视觉方案不能改变既定Research/SEO分类与URL结构。
- 2026-09-18：使用GeneratePress FREE/native Blocks方向；初始应用备份成功后启用主题及LiteSpeed，建设期noindex；不购买升级或重型Builder。公司主体、RFQ收件人、真实SKU证据仍待输入。

- 2026-09-18：用户偏好A+C混合，要求新增OPTION D预览，尚未最终确认视觉，禁止正式部署。保留A工业视觉并提升目录直达、Mega Menu、产品搜索及全页固定联系。
- 2026-09-18：最新询盘规则覆盖旧RFQ：可见Name/Email/Company/WhatsApp or Phone/Message，仅Email必填；自动页面/产品/分类上下文；首版关闭附件；WhatsApp/Sales Email无真实配置就留空，不使用管理邮箱。RFQ_SPEC.md更新v2，旧v1存档。后台记录+通知、防垃圾及真实邮件送达测试在后续正式实施时验收，不将本地演示当线上成功。

- 2026-09-18最新：用户确定OPTION C第三版为唯一视觉母版，A/B/D不再继续。C V2只优化数据自适应、找产品和联系转化，禁止重新设计为A。预览与真实兼容审计后STOP等待确认，禁止正式部署/批量上传。
- 2026-09-18：模板适应旧最终Skill；不修改上传核心，不增加人工Fastener必填。现有Title/Images/Price/SKU/Short/Long即可完整渲染；未知参数/空模块不显示。Supplier/Offer ID/Original1688 URL为管理员内部信息，覆盖旧模板的公开Model展示约定；旧核心保持原样，展示层负责过滤。公开元数据/媒体泄漏防护仍需上线前真实验证。
- 2026-09-18：本轮获用户授权只读使用旧Skill已有真实产品档案作模板测试；不代表旧站操作或迁移授权。旧ID明确命名空间，不能作为Fastener ID。3图低数据样本为明确标注的真实数据最少字段投影；普通10SKU/丰富49SKU保留原数据。低/普通/丰富本地渲染PASS不等于live上传或邮件送达PASS。

- 2026-09-19：用户锁定C V3功能，在原C/C V2母版上放大可读文字/CTA，新增跨商品及跨变体Quote；不配置在线付款；Email唯一必填；RFQ后台先保存再通知、Country自动识别失败Unknown、保留Language/原文/完整规格。旧Skill核心不变。此次完成预览和方案测试后STOP等确认。
- 2026-09-19：15语言展示与逐页面SEO索引独立；English唯一商品主源；L0–L3及建设期noindex覆盖，其他14语言禁止首日批量index。选择TranslatePress为唯一翻译方案；免费仅2语言，付费扩展未购买。28×15词表非英语保持待专业审校。正式SEO钩子/缓存与邮件/GeoIP必须上线环境重新验收。
- 2026-09-19：C V3复用真实旧档案但无已核实Woo variation IDs，预览明确用本地handle，绝不当新站ID。Local RFQ ID与WordPress ID分离。完整产物及边界见c-v3/README.md。

## S14 / 2026-09-19
C V3只修复展示与真实档案映射，不重设计。禁止再生成Woo变体ID；OfferID/Original1688URL保留后台；SKU是变体识别字段。4组66规格，缺专属图WARNING，错误图片/属性/价格FAIL。真实旧站图片绑定差异单独记录，未修改旧站。旧Core 0变化。完成本地Demo后STOP，未正式建设。
- 2026-09-19正式授权：C V3最终通过，停止Demo，开始fastenhardware.com正式部署。先确认最新可恢复备份；允许3组真实旧Skill档案测试上传，禁止森达批量。EN正常SEO、其他14语言索引受控；缺联系配置不阻塞其他部署。完成上线验收后STOP。

2026-09-19 用户追加决定：MaxMind 暂缓，Country=Unknown 不阻塞上线。立即建立新站独立 API 并以 1 个真实档案测试最终 Legacy Runner；不修改核心，测试保留 Draft。已通过 WPVibe 托管授权，无密码/Secret/Token 暴露；项目插件对该命名连接施加 Draft/商品/图片白名单。

- 2026-09-20：用户授权仅扩展FastenHardware Product API的Product Categories管理，不扩展订单/用户/标签/发布；已许可打开同Chrome配置并部署。部署以恢复现有安全后台连接为前提。续传使用保存的本地source/images/checkpoint；已写58SKU禁止重复创建；所有5父商品保持Draft。

- 2026-09-20：fastenhardware独立规则强制canonical Offer ID→Model/Offer/source三项Woo meta，保留完整源URL，创建后独立REST GET不一致HARD FAIL。后台支持私有来源查询/链接；详情只以CSS控制桌面max900、手机max100%，超长图自适应，不降低母图清晰度、不替换缩略图。当前5品复用已有数据/checkpoint且保持Draft。部署状态见CURRENT_STATE。
