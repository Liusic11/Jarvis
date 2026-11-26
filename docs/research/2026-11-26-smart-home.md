# 智能家居调研

调研日期：2026-11-26。价格为当日电商参考价。导购文里不少是品牌软文，数字当量级看。

## 结论

- 对 JARVIS 最省事的是米家：小米官方的 Xiaomi Home 集成扫码登录就能把设备导入 Home Assistant，覆盖 20 多类设备。
- 有小米中枢网关时可以走局域网控制，延迟低且断网可用。
- 蓝牙和红外设备不被 Xiaomi Home 集成支持，所以空调要选原生 Wi-Fi 机型。

## 品类

| 品类 | 能做到什么程度 | 参考价 | 接入 HA |
|---|---|---|---|
| 音箱 | 语音控制、场景、多房间音乐；HomePod 兼作 HomeKit 中枢 | HomePod mini 2 ¥1,099；HomePod 2 ¥2,699 | HomePod 可走 Siri 快捷指令；小爱只有社区方案 |
| 灯光 | 开关、亮度、色温、场景联动；前提取决于开关底盒有没有零线 | Aqara 零火开关 ¥86–159；米家灯泡二三十元；无主灯调光每路加 ¥100–200 | Aqara 同时接米家和 HomeKit |
| 窗帘 | 定时、语音、场景开合；窗帘盒旁要留插座 | 窗帘伴侣 ¥329；电机套装含安装 ¥499 | 可以 |
| 空调 | 开关、调温、模式；高端机带离线语音和人体感知 | 米家巨省电 Pro ¥2,000–2,500；HomeKit 原生机型 ¥3,000–4,000 起 | 原生 Wi-Fi 机型可以 |
| 老空调 | 只能发指令，读不到状态，延迟高 | 空调伴侣约 ¥189 | 红外设备不支持 |
| 扫地机器人 | 开始、暂停、回充；高端机有自清洁基站、避障、拖地 | 米家入门 ¥1,300–2,200；石头 P20 Max ¥2,968；追觅 S60 Pro 约 ¥4,500 | 米家机型最省心 |
| 洗衣机 | 远程启动、查看剩余时间、洗完通知（因机型而异） | 小米热泵洗烘一体 ¥1,499 起；主力档 ¥2,299 | 米家机型通过官方集成 |
| 传感器 | 人体、温湿度、存在感知、水浸，是自动化的触发器 | 人体 ¥49–99；存在传感器 FP2 ¥599；水浸 ¥99–119 | 可以 |
| 门锁 | 指纹开锁、离家布防；解锁是高危操作 | Aqara D100 ¥2,299 起 | 可以 |

## 生态

| 生态 | 特点 | 入门成本 |
|---|---|---|
| 米家 | 设备最全、最便宜 | 基础全屋 ¥3,000–8,000 |
| HomeKit | 本地运行、隐私最好；设备少、单价高 | 两室一厅通常 2 万以上 |
| 华为 | 前装体验好、价格最高 | 后装 ¥9,999 起，前装 3 万起 |
| Aqara | HomeKit 的最佳补充，比米家贵一截 | 约 ¥4,000 起 |

全屋找公司做的档位：

| 档位 | 预算 | 内容 |
|---|---|---|
| 入门尝鲜 | ¥5,000–15,000 | 无线为主、后装优先，灯光、窗帘、空调 |
| 舒适实用 | ¥15,000–35,000 | 全屋灯光、窗帘、门锁、安防、语音 |
| 品质进阶 | ¥35,000–80,000 | 有线加无线，调光调色、环境自适应 |
| 旗舰定制 | ¥80,000 以上 | 全有线，本地服务器 |

三居室包工做的三档：约 2.5 万（门锁、开关、窗帘、网关）、约 4.5 万（加调光、新风联动）、约 8 万（无主灯、AI 场景）。

## JARVIS 演示设备清单

按现在计划的 18 个工具配一套：

| 项目 | 价格 |
|---|---|
| Aqara 网关 M1S | ¥239 |
| 智能开关 E1 零火双键 ×2 | ¥180 |
| 空调伴侣（老空调用） | ¥189 |
| 窗帘伴侣 E1 | ¥329 |
| 人体传感器 | ¥99 |
| 小计 | 约 ¥1,000 |
| 扫地机（米家入门） | ¥1,300–2,200 |
| HomePod mini 2 | ¥1,099 |
| 合计 | 约 ¥3,400–4,400 |

注意：空调伴侣和传感器价格来自较旧的小米商城页面，下单前要核对。

## 来源

- [HomePod mini 2 新闻稿](https://www.apple.com.cn/newsroom/2026/10/apple-announces-the-next-generation-of-homepod-mini/)
- [小米商城 Aqara 配件价格](https://home.mi.com/app/shop/content?id=t539c10390e1c77c6)
- [小米商城卧室套装价格](https://home.mi.com/app/shop/content?id=tb12610398570bdd6)
- [Aqara 价格汇总（2026-11）](https://biggo.hk/s/AQARA/?m=cp)
- [Aqara 传感器美国价格](https://us.aqara.com/collections/smart-home-sensor)
- [ha_xiaomi_home 教程](https://blog.csdn.net/gitblog_00984/article/details/152191728)
- [Xiaomi Home 集成完整指南](https://blog.csdn.net/gitblog_00010/article/details/161003834)
- [米家设备接入 HA 进阶](https://blog.csdn.net/gitblog_06834/article/details/162857158?index=related)
- [四大智能家居平台对比](https://blog.csdn.net/weixin_28523493/article/details/158361219)
- [HomeKit、米家、华为怎么选](https://post.m.smzdm.com/p/apq5r057/)
- [全屋智能预算规划指南](https://bbs.csdn.net/weixin_31960565/article/details/100391365)
- [全屋智能三档预算](https://www.ithome.com/1/022/453.htm)
- [小户型全屋智能方案](https://hebei.ifeng.com/c/8y5lnnk4JOm)
- [智能空调选购（2026-11-23）](https://cj.sina.com.cn/articles/view/7879849679_1d5acf6cf06801smv4?froms=ttmp)
- [智能空调选购（2026-11-24）](https://k.sina.com.cn/article_7879922989_1d5ae152d06801zv67.html)
- [扫地机器人五强实测](https://k.sina.com.cn/article_7879849100_1d5acf48c06801q8ft.html)
- [扫地机器人测评排行（2026-11-21）](https://k.sina.com.cn/article_7879996109_1d5af32cd06802y9em.html)
- [扫地机器人价位档（2026-11-05）](https://cj.sina.com.cn/articles/view/7879923088_1d5ae159006801f0lm?froms=ttmp)
- [洗烘一体机三档预算](https://k.sina.com.cn/article_7879923161_1d5ae15d906801smxe.html)
- [洗衣机热销榜](https://k.sina.com.cn/article_7879849070_1d5acf46e06803u1oh.html)
