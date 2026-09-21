# 03｜森达·产品上架

职责：森达及补充供应商1688采集、SKU/Variation/Model/价格/图片、中文水印处理、SEO、Woo上传分类、Publish、Validation。
必读共享文件（均相对项目根）：PROJECT.md、RULES.md、DECISIONS.md、CURRENT_STATE.md、TASK_QUEUE.md；03_products/skills/fastenhardware-1688-product-import/SKILL.md。 本入口继承根规则，不另立业务规则。
输入：01_research/product_matrix.csv及handoffs/research.csv；02_site/handoffs/site.csv；senda/senda_offers.csv和当前批次检查点；04_growth/handoffs/feedback.csv。
输出及对应目录：raw/processed/images/import/reports按offer隔离；handoffs/products.csv交接Product ID/URL/关键词/分类/发布及验证给04。
依赖和禁止事项：P任务；每批读取并应用03_products/skills/fastenhardware-1688-product-import/SKILL.md及相关rules，版本变化先核对差异；复用旧Pipeline不重设计。不把研究方向当SKU；FAIL不可发布。
短指令：森达全部开始上；继续下一批20个；再上50个；检查刚上传的产品。先读共享文件和本模块任务行，再按需读证据；不重复询问已明确规则。
交接：依根RULES.md写模块交接表与logs/handoffs.csv；消费上游最新有效文件，不复制出第二份权威资料。当前进度仅见CURRENT_STATE/TASK_QUEUE。
