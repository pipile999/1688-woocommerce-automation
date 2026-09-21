每次进入项目先读取根目录 SITE.md，站点身份与生产入口以它为准。禁止跨站读取凭证、缓存或业务规则。

# FASTENER 项目入口

每次新会话先依次读取 PROJECT.md、RULES.md、DECISIONS.md、CURRENT_STATE.md、TASK_QUEUE.md，再执行 NEXT ACTION。不依赖旧聊天。
本项目唯一根目录 D:/codex/fastener-site。与旧站业务、商品、凭据、缓存及发布目标隔离。
禁止查看、记录或泄露密码和 TOKEN；不读取旧站 .env、认证文件及浏览器密码。
每次结束更新 CURRENT_STATE.md 与 TASK_QUEUE.md。先思考，精准修改，简洁优化，目标驱动；复用已验证模块。

所有进入本项目的任务共享以上五份文件，并先读 03_products/skills/fastenhardware-1688-product-import/SKILL.md。读完后按职责读取 00_CONTROL.md、01_research/AGENT.md、02_site/AGENT.md、03_products/AGENT.md 或 04_growth/AGENT.md；入口只做路由，不复制另一套规则。总控汇总所有模块，业务任务按需读取上游交接表及logs/handoffs.csv。具体归档、接收回执和低Token规则见根RULES.md第24–29条。
当前会话持续执行依赖已满足的 TODO，领取时改 RUNNING，完成改 DONE，真实缺输入/访问条件才改 BLOCKED。一个 BLOCKED 不能停止其他任务。只有当前所有可执行任务完成或剩余任务全部真实阻塞才能结束。
并行会话只修改自己的任务行和工作区；写共同文件前重读并保留他人新增内容。不要把另一个会话 RUNNING 的任务重复领取。发现陈旧 RUNNING 先检查产物和日志再接手。
短命令“继续调查/继续建站/继续上20个/看看哪些页面有潜力”按对应入口续接；不得重复询问文件已有的价格、图片、SKU、Model、SEO 或发布规则。
