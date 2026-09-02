# 1688 → WooCommerce Automation

一个面向 WooCommerce 独立站卖家的自动化上品项目。

## 当前 MVP 目标

1. 输入一个 1688 商品链接。
2. 自动提取 1688 Offer ID，并写入 `Model`。
3. 保留原始 1688 URL 作为溯源链接。
4. 按固定公式计算售价：`1688价格 / 0.7 / 6.7`。
5. 完整保留 SKU / Variations，不允许 AI 修改 SKU 结构。
6. 清洗描述中的供应商、公司、品牌、联系方式等信息，只保留中性产品信息。
7. 创建 WooCommerce Draft 产品。
8. 预留图片自动筛选、OCR、Inpainting、WebP 压缩、Google Ads 关键词和图片 SEO 命名模块。

## 示例

输入：

`https://detail.1688.com/offer/605518859055.html?_t=1788338308253`

自动得到：

- Model: `605518859055`
- source_url: 原始 1688 链接
- 销售价: `1688价格 / 0.7 / 6.7`

## 快速开始

```bash
cp .env.example .env
pip install -r requirements.txt
python -m app.main --url "https://detail.1688.com/offer/605518859055.html"
```

项目会先以“生成 WooCommerce Draft payload”为主，配置 WooCommerce API 后即可直接创建草稿商品。

## 图片处理计划

后续模块会按以下规则执行：

- 大面积牛皮癣 / 大面积水印 / 广告图：删除
- 工厂图、公司图、员工图、证书图、二维码、联系方式图：删除
- 尽量只保留产品主图、细节图、使用场景图
- 小面积水印：定位 → Mask → Inpainting 补背景 → 质量检查
- 不优先裁边
- 最终转 WebP，最长边约 1600–2000 px，质量 80–85，删除 EXIF
- 图片 SEO 文件名数量必须与最终保留图片数量一致

## 安全

所有 API Key 和 WooCommerce 密钥都通过环境变量配置，禁止写入代码仓库。
