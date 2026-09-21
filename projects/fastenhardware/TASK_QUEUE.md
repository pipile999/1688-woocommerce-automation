# 共享执行队列

状态只用 TODO/RUNNING/BLOCKED/DONE。一个任务 BLOCKED 只影响其真实依赖者；持续领取依赖已满足的 TODO。产物设计不等于部署成功。共同文件更新前重读，保留其他会话变更。

| ID | 状态 | 依赖 | 任务与验收 / 阻塞原因 |
|---|---|---|---|
| M01 | DONE | — | 初始化与有效旧 Skill 引用/hash |
| M02 | DONE | M01 | 共同记忆、四个 AGENT 入口、连续执行规则 |
| M03 | DONE | M02 | 长期工作区整理：五个Project任务API创建、共享local目录、总控+四入口、交接/归档/低Token规则及原成果保全校验；logs/workspace_entries.json |
| R01 | DONE | — | 六HS6的2023/24可比数据、2024市场和2025口径边界；market/EXPORT_MARKET_REPORT.md |
| R02 | DONE | — | 4组真实Google页面、20方向意图映射；keywords/KEYWORD_RESEARCH.md；非全国家全词排名审计 |
| R03 | DONE | R02 | 实测自然结果6个竞争页特征审阅；competitors/SERP_COMPETITORS.md |
| R04 | DONE | R01,R02,R03 | product_matrix.csv 20方向证据矩阵；真实供货/利润未验证，不是20个商品 |
| R05 | DONE | R04 | opportunities/FIRST_BATCH.md 优先采集方向及入选门槛 |
| R06 | DONE | — | Planner实测27条可见记录，4个矩阵精确词有范围；其余量与全部KD UNVERIFIED |
| S01 | DONE | R04 | categories/ARCHITECTURE.md与url_map.csv、navigation/及seo_structure/ |
| S02 | DONE | — | 四免费主题官方资料比较；选GeneratePress FREE，未跑线上性能 |
| S03 | DONE | S01,S02 | 4页静态预览/区块草稿、绑定说明、RFQ结构；未接后端 |
| S04 | DONE | — | 已检查Hostinger登录、已连接WP目标、本地运行条件；无Fastener可部署目标 |
| S05 | DONE | S03 | BUILD_PACKAGE.md、安装清单、本地浏览器/离线验证；不是WordPress安装完成 |
| S06 | DONE | S14 | C V3正式框架、10页面17分类、Woo/RFQ/15语言架构、备份与SEO上线；插件1.0.6，Site Health Good；最终邮件/域名回执另列S07/S13 |
| P01 | BLOCKED | — | SENDA STORE COLLECTION：STORE URL REQUIRED |
| P02 | BLOCKED | P01 | 森达加工：缺真实源数据 |
| P03 | DONE | — | hash锁定旧core复用及隔离预检；5组离线测试通过；整套live整合另列P07 |
| P04 | BLOCKED | P02,P03,S06 | 新站已就绪；森达缺真实源数据，且本轮禁止批量发布 |
| P05 | DONE | R05 | 5条供应线索；实访海盐英杰1688显示7条候选offer；非已审核SKU |
| P06 | BLOCKED | P08,P07,S06 | 新站API与Draft验收已就绪；缺真实详情/变体/图，后续发布需明确批次授权 |
| P07 | DONE | S06 | 独立新站 API + 原Runner单品601268094114直传Draft PASS；74/81/1SKU/6图，原REST/HTTP/渲染通过；78源文件hash不变；03_products/reports/LEGACY_LIVE_ACCEPTANCE_20260919.md |
| P08 | BLOCKED | P05 | 补充供应商详情采集：1688实际出现滑块验证，需用户在浏览器完成；不绕过 |
| S07 | BLOCKED | S06 | 技术/移动端/真实17变体/RFQ69保存已通过；仅待用户确认RFQ69实际收件和域名注册邮件验证；Unknown已允许不阻塞 |
| G01 | DONE | — | GSC CSV分析器及测试、事件契约、1篇英文RFQ清单、内容/内链计划 |
| G02 | BLOCKED | S07 | 新站与sitemap已上线；待域名注册验证、最终验收及GSC所有权/访问条件；未宣称Google已收录 |
| G03 | BLOCKED | G02 | 真实表现优化：无新站观测数据 |
| G04 | BLOCKED | P02或P08 | 技术型采购文章：缺真实标准/材料/钻穿/包装/测试依据；通用RFQ清单已完成 |
| S09 | DONE | S01,S03 | A/B/C 各首页+分类+商品共9页，桌面/手机预览及交互检查完成；02_site/design-selection/index.html；STOP等待用户选择，禁止正式页面搭建 |
| S10 | DONE | S09 | OPTION D A+C Hybrid：首页/分类/商品+Desktop/Mobile预览，Mega Menu、搜索、固定联系、Email-only询盘上下文已验证；02_site/design-selection/d/preview.html；STOP等待视觉确认，未部署 |
| S11 | DONE | S09 | C V2唯一母版预览+真实旧档案离线兼容审计完成；3图少数据/10SKU普通/49SKU丰富，15组响应式检查PASS；真实上传/邮件/WhatsApp/供应商后台链路未通过上线验收，见c-v2/README.md；STOP待确认 |
| S12 | DONE | S11 | C V3本地预览/持久RFQ测试服务/WordPress插件候选/15语言策略与词表完成；17核心测试+16PHP契约+18响应布局+3候选测试；真实线上未验收，见c-v3/README.md；STOP待确认 |
| S14 | DONE | S12 | C V3真实1/10/6/49规格修复；66真Woo变体ID/图片价格点击通过、18组字体布局通过、27个Core hash不变；缺专图WARNING；本地Demo STOP待检查 |
| S13 | BLOCKED | S06,P07 | 正式C V3/API/SEO/15语言架构通过，所有验收商品Draft匿名404；整体最终验收只缺RFQ实际收件/域名验证回执；不批量上架 |
| S08 | BLOCKED | — | sales@fastenhardware.com / WhatsApp +8618664184619 已配置；真实经营主体信息仍缺，不编造公司事实 |

根 CURRENT_STATE 为短摘要，本表为任务状态唯一来源。2026-09-19 S06/P07完成；S07/S13仅缺用户邮件/域名回执。四个样本已Draft，本轮STOP，不自动批量导入。

| P09 | DONE | P03 | 2026-09-20 三个桌面快捷方式已创建并实际零上传启动测试PASS；复用原Runner/UI与现有Python，78核心文件不变；automation/desktop/README.md；owner=03-desktop |

| P10 | BLOCKED | P09 | 桌面独立Publish：当前Windows环境未检测到新站独立Woo连接；既有Codex托管连接仅Draft。需本机提供新站发布环境，不读取旧.env或要求聊天发送凭证；本次未上传。 |

| P11 | BLOCKED | 正确紧固件源链接 | 2026-09-20 Excel前5个均实时采集完成，但实际为磨烟器/烟斗/烟丝罐；新站类目不匹配，0上传/0媒体写入，未处理第6个以后。独立profile已建；REPORT与audit见03_products/batches/20260920-first5；owner=03-first5 |

| P12 | BLOCKED | USER STOP 2026-09-20 | 用户明确搁置84/670395836059及其它4商品；禁止续传/删除/修改，checkpoint保留。 |

| P13 | BLOCKED | 后台浏览器操作超时 | root：唯一新商品182/673566601420已完成19SKU Draft，原Runner及独立REST/HTTP PASS；2主图+1详情图；旧7检查点/78核心不变。仅剩已准备插件的备份部署和来源字段/Related/字体/EN+ES桌面手机实测，非商品上传阻塞。FINAL_STOP已锁定，禁止第二件/旧5件。 |

| P14 | DONE | 2026-09-21 明确授权 | 两站 Skill、Runner、运行数据路径拆分，交叉 HARD STOP，离线隔离测试 PASS；0商品操作。 |
