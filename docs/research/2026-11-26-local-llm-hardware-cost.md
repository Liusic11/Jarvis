# 本地跑 LLM 的硬件成本评估

调研日期：2026-11-26。价格为当日电商和官网参考价。

## 结论

- 问题不在「PC」这个形态，而在「装了游戏显卡的台式机不适合 24 小时开机」。
- 对 JARVIS 当前要跑的 7B–8B 模型，DGX Spark 和 Mac Studio 都没必要，先不买。
- 噪音和发热是真问题，电费不是。

## 电费（按 ¥0.6/度，24 小时开机）

| 机器 | 空载功耗 | 一年电费 |
|---|---|---|
| 游戏显卡台式机（RTX 3090 实测） | 62W；模型驻留时 85–110W | 约 ¥315–580 |
| 迷你主机、Mac mini | 6–14W | 约 ¥32–74 |
| DGX Spark | 44–45W | 约 ¥231 |

台式机的三个真实麻烦：

1. 有程序占着显卡时，显卡回不到最低功耗，风扇一直转。
2. 不能关机：睡眠、Windows 更新重启都会让服务掉线。
3. 热量：100W 相当于一直开着一个取暖器。

Ollama 默认 5 分钟后卸载空闲模型（`keep_alive`），可以缓解待机功耗。

## 方案对比

| 方案 | 价格 | 能跑多大 | 特点 |
|---|---|---|---|
| 现有 RTX 3070 Ti 台式机 | ¥0 | 8B 够用 | 最快，但吵、不能关 |
| Mac mini M4 Pro 64GB | 约 ¥1.7 万 | 7–8B 约 40 tok/s，32B 约 12 tok/s | 空载 6W，推理 45–60W，安静；带宽 273GB/s |
| Strix Halo 迷你主机（GMKtec EVO-X2 128GB） | ¥2.3 万（2025-12 低价 ¥1.6 万） | 8B 42–53 tok/s，70B 约 5 tok/s，MoE 120B 约 31 tok/s | 空载 8–14W，推理 150–160W；带宽 256GB/s；没有 CUDA |
| Mac Studio M4 Max 128GB | ¥3.7 万（官方翻新，2TB）；¥16,499 起（36GB） | 70B 级 | 带宽 546GB/s，同容量里最快 |
| DGX Spark 128GB | 约 ¥3.1 万–6 万 | 200B 级；8B 39 tok/s，70B 约 5–11 tok/s | 额定 240W，负载低于 40dBA；带宽 273GB/s；有 CUDA 生态 |

补充：

- 2026 年内存在涨价，价格波动很大。EVO-X2 海外价从 6 月的 $1,999 涨到 10 月的 $3,649。
- DGX Spark 有 64GB 的 OEM 版本（华硕、微星、技嘉等），2026 年 10 月起发售，国内价格未查到。
- 这些大内存机器的卖点是「装得下大模型」，不是「跑得快」。8B 模型在独显上反而更快。

## 决策规则

1. 现在不买，先用 RTX 3070 Ti 台式机跑 Phase 8 的评测。
2. 评测达标（正例工具名 ≥ 90%），继续用现有机器。
3. 不达标说明要换更大的模型，再买：
   - 32B 级够用：Mac mini，约 ¥1.7 万。
   - 要 70B 或更大的 MoE：Mac Studio 或 Strix Halo。
   - DGX Spark 只在想顺便学 CUDA 生态时才值。

## 来源

- [NVIDIA DGX Spark 开箱与深度解析](https://forums.developer.nvidia.cn/t/ai-nvidia-dgx-spark/27889)
- [DGX Spark 博主评测汇总（功耗、噪音）](https://post.m.smzdm.com/p/a46w2dl8/)
- [DGX Spark 64GB 版本](https://blogs.nvidia.cn/blog/local-ai-dgx-spark-64gb-sync/)
- [京东 DGX Spark 商品页](https://item.m.jd.com/product/10217347602297.html)
- [Apple 中国 Mac 全系价格](https://www.apple.com.cn/hardware/?focus=great-ideas)
- [翻新 Mac Studio M4 Max 128GB](https://www.apple.com.cn/shop/product/g1cdach/a)
- [Mac mini M4 Pro 64GB 价格](https://wiki.m.smzdm.com/p/5vv41ne/)
- [EVO-X2 国内价格](https://wiki.m.smzdm.com/p/wyezpmz/)
- [EVO-X2 评测（2026-06）](https://dev.to/jovan_chan_9500711396d4e6/gmktec-evo-x2-review-2026-a-sub-2000-mini-pc-that-runs-235b-models-on-ryzen-ai-max-395-57e5)
- [EVO-X2 评测（2026-10 更新）](https://datahardware.ai/blog/gmktec-evo-x2-review-2026)
- [本地 LLM 实测功耗](https://futurion.blog/how-much-electricity-does-running-a-local-llm-use/)
- [Ollama 本地 FAQ](https://docs.ollama.com/faq.md)
