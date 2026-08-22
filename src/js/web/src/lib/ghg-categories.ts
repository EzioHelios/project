export type GhgCategoryNavigationItem = {
  code: string
  name: string
}

export type GhgCategoryNavigationGroup = {
  code: string
  shortName: string
  name: string
  items: GhgCategoryNavigationItem[]
}

export const GHG_CATEGORY_GROUPS: GhgCategoryNavigationGroup[] = [
  {
    code: "1",
    shortName: "类别1 · 直接排放",
    name: "类别1 直接排放与清除",
    items: [
      { code: "1.1", name: "固定燃烧" },
      { code: "1.2", name: "移动燃烧" },
      { code: "1.3", name: "工艺过程排放" },
      { code: "1.4", name: "逸散排放" },
      { code: "1.5", name: "土地利用与清除" },
    ],
  },
  {
    code: "2",
    shortName: "类别2 · 购入能源",
    name: "类别2 输入能源间接排放",
    items: [
      { code: "2.1", name: "购入电力" },
      { code: "2.2", name: "购入其他能源" },
    ],
  },
  {
    code: "3",
    shortName: "类别3 · 运输",
    name: "类别3 运输间接排放",
    items: [
      { code: "3.1", name: "上游运输与配送" },
      { code: "3.2", name: "下游运输与配送" },
      { code: "3.3", name: "员工通勤" },
      { code: "3.4", name: "商务旅行" },
      { code: "3.5", name: "客户和访客交通" },
    ],
  },
  {
    code: "4",
    shortName: "类别4 · 组织使用产品",
    name: "类别4 组织使用产品产生的间接排放",
    items: [
      { code: "4.1", name: "采购商品与服务" },
      { code: "4.2", name: "资本货物" },
      { code: "4.3", name: "燃料和能源相关活动" },
      { code: "4.4", name: "运营废物处置" },
      { code: "4.5", name: "上游租赁资产" },
    ],
  },
  {
    code: "5",
    shortName: "类别5 · 输出产品",
    name: "类别5 与组织输出产品使用相关的间接排放",
    items: [
      { code: "5.1", name: "售出产品加工" },
      { code: "5.2", name: "售出产品使用" },
      { code: "5.3", name: "售出产品报废处理" },
      { code: "5.4", name: "下游租赁资产" },
      { code: "5.5", name: "特许经营" },
      { code: "5.6", name: "投资" },
    ],
  },
  {
    code: "6",
    shortName: "类别6 · 其他间接排放",
    name: "类别6 其他间接排放",
    items: [{ code: "6.1", name: "其他经确认的间接排放" }],
  },
]

export function categoryRoute(code: string) {
  return `/carbon-mgmt/category/${code}`
}
