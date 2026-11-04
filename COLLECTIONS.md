# 新增卡册

所有卡册使用同一数据协议和界面组件，路径固定为顶层卡册 → 宇宙 → 系列 → 卡片。顶层沿用大封面，内部卡册与卡片共用 2:3 的 `CardFace`。没有子系列的宇宙也显式提供一个系列，不跳级。

卡片可选字段：`rarity_badge` 为实际品质标识图片 URL（没有标识可留空），`splash` 为完整原画 URL，`description` 为背景描述。所有卡册自动使用同一卡面和详情展示。卡面不显示 R / SR / SSR 文字；`rarity` 仅控制抽取概率、颜色及重复卡分解（R=5，SR=20，SSR=50 日光精华）。每张卡只保留一张。英雄联盟将限定、传说、神话映射到用户提供的原始标识，高于神话的皮肤沿用神话图像。

同一个系列出现在多个宇宙时，“绝无仅有”按顶层卡册与系列 ID 去重，仅统计集齐的非空叶子系列。

1. 在 `server/plugins/__init__.py` 注册内容插件，`parent` 为 `collection`；这决定每个用户的安装权限。
2. 在 `server/content/card-albums.json` 的 `albums` 数组添加顶层条目，参照下方结构。内部节点 ID 需在本册内唯一；卡片 ID 需全局唯一并保持稳定，推荐使用内容前缀。
3. 在 `server/content/cards.json` 的 `cards` 数组追加卡片，填写 `album_id` 与 `series_ids`。卡图存放在 `server/content/cards/{id}.webp`，`image` 使用 `/api/plugins/collection/image/{id}`。不要复用其他卡片 ID，以免覆盖已有收藏。
4. 添加实际海报文件，重启 API。无需新增卡册页面、图片路由、抽卡路由或品质展示组件。

```json
{
  "id": "new-content",
  "name": "新卡册",
  "kind": "album",
  "content_plugin": "new-content",
  "cover_card_id": "new-content-cover",
  "poster": "posters/new-content.webp",
  "pack": {
    "title": "卡包主题",
    "subtitle": "海报角色",
    "art_caption": "海报说明",
    "caption": "卡包介绍"
  },
  "children": [{
    "id": "world",
    "name": "宇宙名称",
    "kind": "universe",
    "cover_card_id": "new-content-cover",
    "children": [{
      "id": "series",
      "name": "系列名称",
      "kind": "series",
      "cover_card_id": "new-content-cover"
    }]
  }]
}
```

对应卡片示例：

```json
{
  "id": "new-content-cover",
  "name": "卡片名称",
  "rarity": "R",
  "album_id": "new-content",
  "series_ids": ["series"],
  "image": "/api/plugins/collection/image/new-content-cover"
}
```

每个抽卡等级必须有实际卡片。`pack.cost` 和 `pack.probabilities` 可分别覆盖全局价格、概率；省略时使用管理员全局配置。价格为正整数，概率为非负整数且合计 100。不配置 `pack` 的卡册只提供浏览，不开放抽取。

同一卡片可以属于多个系列，宇宙与顶层的总数和已收集数按卡片 ID 去重。卸载内容插件后，卡片、海报、历史和抽卡接口均执行对应的安装权限检查。持有数量和抽卡记录的原始卡片 ID 不变。

英雄联盟导入器使用用户提供的 `universes.json`、`skinlines.json`、`albums.json` 生成层次与封面；不将其分类规则写进通用渲染器。原基础英雄分支为「符文大陆」宇宙，其原生卡片在「英雄原貌」系列中。独立系列按同名的一系列宇宙展示，保持层次一致。
