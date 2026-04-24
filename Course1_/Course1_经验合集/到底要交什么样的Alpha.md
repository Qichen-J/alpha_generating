【新人指南】到底要交什么样的Alpha？ 置顶的
234 人关注

XZ23611
Osmosis AllocatorGold consultant
7个月前 已编辑于
到底要交什么样的Alpha？——新人指南
在Alpha开发与提交的过程中，许多新人常常会问：“到底什么样的Alpha才值得提交？”这是一个复杂的问题，因为Alpha的质量并没有一个单一的“金标准”可以作为绝对的判断依据。新人常见的错误是过度依赖某一两个单一指标，比如 Sharpe、Fitness 或 Margin，认为只要这些指标表现良好，Alpha就一定值得提交。

然而，判断一个Alpha是否值得提交更像是诊断病情——不能仅仅依靠一个指标或单一的维度来做出决定。单一指标可能会提供片面的信息，而忽略了Alpha整体表现的复杂性和多样性。这种过度依赖单一指标的思维方式，往往会导致新人在Alpha提交过程中出现偏差。

数量与质量的平衡：螺旋上升的原则
在Alpha的开发与提交过程中，数量和质量是两个不可分割的重要维度。许多新人在实践中常常犯两个极端的错误：要么过度关注质量而忽视数量，要么完全不管质量，只追求数量。这两种错误都会对Alpha的整体表现产生负面影响。

数量不足的问题
如果过度追求质量而导致提交的Alpha数量不足，可能会出现以下问题：

Portfolio不稳定：
Alpha的数量不足会导致整体Portfolio的表现缺乏多样性，从而增加OS（Out-of-Sample）结果的不稳定性。
缺乏真实水平的验证：
单个Alpha的表现可能具有偶然性，只有通过足够的数量才能更接近整体的真实水平，避免因个别Alpha的异常表现而影响整体判断。
质量不足的问题
另一方面，如果完全忽视质量，只追求数量，也会带来风险：

Portfolio表现受损：
大量低质量的Alpha会拉低整体Portfolio的表现，导致Margin、Sharpe等关键指标下降。
资源浪费：
提交大量低质量Alpha不仅浪费了开发时间，也可能对平台的审核资源造成压力。
螺旋上升的原则
数量和质量并非对立，而是一个螺旋上升的过程。新人在初期阶段可以优先解决数量的问题，通过提交足够数量的Alpha来建立基础，然后逐步提高质量要求，最终实现数量与质量的平衡。

新人建议：
每个月提交的Alpha数量不要少于 40个。这一数量可以帮助新人更接近整体的真实水平，同时避免因单月表现异常而影响长期结果。
数量的意义：足够的数量可以为Portfolio提供多样性，降低单个Alpha表现异常对整体的影响。
质量的提升：在数量达到一定基础后，可以逐步提高Alpha的质量要求，例如优化Turnover、Margin等关键指标。
平台的“最低标准”与其意义
在Alpha提交过程中，平台设定了一些“最低标准”，这是每位新人必须满足的基本要求。这些标准的存在并非是为了限制，而是为了确保Alpha在实际应用中具有一定的可行性和质量。然而，许多新人在实践中往往只关注如何通过这些指标，而忽略了这些要求背后的逻辑和意义。

Turnover的要求
Turnover 是一个重要的指标，它衡量了Alpha的换手率。平台要求Turnover不能高于 70%，这是为了避免交易频率过高导致交易成本过高，从而影响 Margin 的表现。换手率过高会显著增加手续费，最终削弱Alpha的盈利能力。

进阶建议：

当你的水平到达一定程度，建议将Turnover控制在 30% 以下。
当你已经不再断粮，建议将这一指标进一步降低至 15% 以下。
特殊情况：

如果Turnover较高，但 Margin 同时表现非常优秀（例如Margin超过 10），这种情况下高换手率是可以接受的。
Turnover的下限
平台同时要求Turnover不能低于 1%，这一点常常让新人感到困惑。事实上，这一要求的意义在于避免Alpha的持仓过于稳定。换手率过低会导致Position长期不变，而这与对冲基金的核心理念相悖。对冲基金的本质是通过动态调整持仓来捕捉市场机会，而过低的换手率可能意味着Alpha缺乏足够的市场反应能力。

Sub Universe与Robust Test的重要性
在Alpha的评估过程中，Sub Universe 是一个关键的测试维度。平台要求Alpha在较小的股票范围（Sub Universe）中仍然保持一定的表现，这一要求的最低标准是 50% 的Sharpe。这意味着，如果Alpha在当前的Universe（例如Top3000股票）中表现良好，那么在更小的Universe（例如Top1000股票）中，它的Sharpe也必须达到至少50%的水平。

Sub Universe的原理
这一要求的核心逻辑是为了避免Alpha的信号仅来源于流动性较低的小市值股票。如果一个Alpha在Top3000股票中表现良好，但在Top1000股票中完全失效，这通常表明其收益主要依赖于流动性较低的那2000只股票。这种情况可能会导致Alpha在实际应用中面临较大的风险，例如流动性不足或交易成本过高。

Robust Test的概念
Robust Test 是一个更广泛的概念，旨在通过调整各种参数来测试Alpha的稳定性和敏感性。具体来说，Robust Test可以包括以下两种方式：

调整Settings中的指标：
例如修改交易成本、滑点、或其他市场环境参数，观察Alpha的表现是否稳定。
调整Expression中的参数：
修改Alpha表达式中的关键参数，测试结果的敏感性。
如果结果收敛性较好，说明Alpha具有较强的鲁棒性；如果结果发散性较强，则表明Alpha可能过于依赖某些特定条件。
实践建议
前期阶段：
在Alpha开发的初期，可以暂时不需要过多关注Robust Test，重点放在满足平台的最低要求（如Sub Universe的表现）。
后期阶段：
随着经验的积累，可以逐步加强Robust Test的强度，通过调整参数和环境来验证Alpha的稳定性。
IS测试与长期稳定性：Alpha的“望诊”
在Alpha的评估过程中，IS Ladder Testing（针对Regular Alpha）和2-Year Testing（针对Atom Alpha）是平台用于检测Alpha稳定性的重要工具。这些测试的核心目标是通过观察Alpha的PNL表现，评估其长期稳定性。这一过程类似于“望诊”，通过观察PNL的形状来判断Alpha的健康状况。

PNL的理想形状
最理想的PNL表现是一条从左下角到右上角的稳定直线。这种形状表明Alpha在长期内具有持续的盈利能力和较低的波动性，是稳定性和可靠性的最佳体现。

新人阶段的目标：
对于新人来说，能够通过平台的IS Ladder Testing或2-Year Testing已经是一个不错的开始。这表明Alpha在基本稳定性方面达到了平台的最低要求。
进阶要求
在进阶阶段，可以通过以下标准来进一步评估Alpha的长期稳定性：

过去10年的表现：
在过去10年中，Alpha的Sharpe超过 1 的年份不少于 X年（具体标准可根据个人目标设定）。
最近两年的表现：
特别关注最近两年的PNL表现，尤其是 2022年 的表现。
为什么要有PPAC？低相关性与Portfolio的多样性
在Alpha开发与提交的过程中，平台引入了 PPAC 的机制，这不仅是为了给新人提供一个更宽松的探索环境，更重要的是为了强调 低相关性 和 Portfolio的多样性 对整体表现的重要性。

Portfolio的概念：你的军队
为了更直观地理解Portfolio的意义，可以将它比喻为一支军队。以往的Alpha评估标准过度追求 Sharpe 和 Fitness 等单一指标，这就像你的军队里清一色都是身高体壮的步兵。虽然这些步兵看起来很强壮，但缺乏多样性会让你的军队在面对复杂战场时显得单薄。

要让你的军队更有战斗力，就需要补充更多的兵种，例如：

斥候：负责侦查，提供灵活性。
炮兵：提供远程打击能力。
后勤兵：确保资源供应，维持军队的稳定性。
同样的道理，Alpha的Portfolio也需要多样性。一个多样化的Portfolio可以更好地应对不同的市场环境（OS），从而提升整体的稳定性和表现。

Self Correlation是一个很直观指标，新人的时候0.7是平台的要求。PPAC的要求是Pool内0.5的要求。值得一提的是这里的SC会随着提交数量的变多而更难有低的表现

0.5-0.7 之间的sc是可以通过的标准
0.3-0.5 之间的sc已经是很不错的了，通常对portfolio有一些提升
0.3以下的sc通常是很低的了
经济学意义与OS表现：从Alpha描述开始
在Alpha开发与提交过程中，经济学意义 是决定OS（Out-of-Sample）表现的关键因素之一。许多老师常常强调这一点，因为具有经济学意义的Alpha往往能够更好地适应不同的市场环境，展现出更强的稳定性和可靠性。

写Description的重要性
对于新人来说，写好Alpha的 Description（描述）是一个非常重要的环节。这不仅是对Alpha逻辑的总结，也是开发者学习和思考的过程。可以将Description视为自己的学习日记，通过记录Alpha的核心逻辑和设计思路，帮助自己更好地理解经济学意义。

总结
Alpha的开发与提交是一项复杂的任务，既需要满足平台的最低要求，也需要从长期稳定性、Portfolio优化和经济学意义的角度进行深入思考。新人在实践中应避免过度依赖单一指标，重视数量与质量的平衡，关注整体Portfolio的表现，并通过写Description来梳理自己的思路和逻辑。希望这篇指南能够帮助新人更好地理解Alpha开发的核心原则，并逐步提升自己的能力。

----

2025年9月1日补充更新

之前论坛内大家的风向是要尽可能的降低turnover，从而潜在的提高fitness或者margin。随着近期的学习，发现之前自己对于turnover的理解是片面的。下面我们再来回过头看到底什么是turnover？

turnover 换手率，伴随着买入和卖出的调仓，调仓带来的两个影响

交易手续费
由于进入到真实的PRODUCT环境和combined performance，都是计算after cost的sharpe，所以这也是为什么我们之前觉得turnover越低越好，但这犯了本末倒置的错误。不该为了节省交易手续费，而让你的alpha变成“死鱼”, 一年下来只有2%的换手率，虽然手续费低了但也不一定是一个好的alpha

能带来returns 并保证一定margin的高换手应该是鼓励和提倡的
所以只要你的turnover不是瞎买卖 （经常有时候是因为缺失值和极端值，没有做平滑等因素而导致的过高换手），能够带来收益和sharpe的提升，就不该被放弃。开始做SA多了以后也会发现，高tvr的alpha对于组合策略的多样性也是很好的补充。通常个人的评判标准是 return/tvr > 0.3-0.4 && margin > 5-10% ，声明这只是个人的习惯非官方指导。

此外很多新顾问可以开始交PPA alpha以后往往会忽视product correlation，从最近研究小组和各类会议的倡导来看，如果想要拿weight，以及提高自己的vf等，还是要尽量控制自己的PC不要超过0.7. 如果PC 超过0.7是无法进入到实盘获得weight的，且往往收入会很低。 这也很好理解，平台已经有了一样的alpha，你的alpha没有任何新的价值，只是占用了算力和存储空间而已。


252
评论
153 条评论排序方式 

SX13432
Osmosis AllocatorMaster consultant
10个月前
写得真好，学习了~


42


TS24161
Gold consultant
10个月前
解释非常详细，很棒的分享！


34


LY60167
Gold consultant
10个月前
感谢分享，学习了！


30


SK10818
Gold consultant
10个月前
感谢大佬的分享


30


QZ33086
Gold consultant
10个月前
很有水平的一篇文章


27


YL36335
Gold consultant
10个月前
学到了


29


YY58435
Osmosis AllocatorExpert consultant
10个月前
如果Turnover较高，但 Margin 同时表现非常优秀（例如Margin超过 10），这种情况下高换手率是可以接受的。
请问这里提到的Margin超过10，是10‱的意思吗？

 


30


FL55634
10个月前
感谢分享


28


yangyanzu(YY97240)
10个月前
感谢大佬的分享


28


CW90254
Osmosis AllocatorMaster consultant
10个月前
感谢分享，学习了！


26


NS23220
Gold consultant
10个月前
Thanks for sharing


23


TD37298
Osmosis AllocatorExpert consultant
10个月前
除了文中提到的夏普比率、换手率、子投资域表现等，您认为在 alpha模型 的 过拟合检测 中，还有哪些高级且有效的量化方法或统计检验值得新人关注和应用？


31


MA70307
Osmosis AllocatorExpert consultant
10个月前
Thanks XZ23611 for sharing. I hope majority of us will be helped by this knowledge and put everything into practice

 


24


FF56620
Osmosis AllocatorMaster consultant
10个月前
给大佬点赞👍


22


SZ83096
Osmosis AllocatorGrandMaster consultant
10个月前
TD37298： 可以做下各种中性化测试，decay衰退测试以及官方推荐的rank,sign测试，提交alpha前，做下这些测试，看各种中心化和decay下alpha的表现是否一致。

------------------------------------------------------------------------------------------------------------------------------


80


FX97215
10个月前
好人一生平安

 


23


SS11281
Gold consultant
10个月前
给大佬点赞👍


21


XG36795
10个月前
👍


21


LJ86847
Osmosis AllocatorExpert consultant
10个月前
感谢大佬分享


20


XX54417
10个月前
感谢分享


19


AY96883
Osmosis AllocatorGold consultant
10个月前
Thanks for sharing

 


20


LG87838
Osmosis AllocatorMaster consultant
10个月前
非常全面的讲解了如何提交好的alpha，已经转给我推荐的新人。作为曾经vf0.03的老顾问，实在是不希望推荐的新人再走一遍弯路，导致低收入而弃圈。
这篇帖子里的步骤看起来很多，多数都可以实现程序化的自动操作，即时没实现程序化，养成习惯后也不会增加太多的提交时间。但获得的回报却是巨大的。
对于新顾问，奉劝各位不要像我当初一样觉得麻烦而忽略了这些细节，等vf更新了才想起来这些都没做。最早是atom全球第一的顾问写的vf记录贴，我看了觉得好像没关系，现在想起来真的是可惜。论坛里很多顾问分享的内容值得反复阅读。我现在的vf是0.6了，combined也从-0.03涨到了1.8……提升的主要途径就是反复读大佬们的帖子。
手机发帖，格式有点乱，见谅！


80


BW14163
Osmosis AllocatorGrandMaster consultant
10个月前
感谢分享


19


MS51256
Osmosis AllocatorGrandMaster consultant
10个月前
========================================================================================================================================================================
学到了，我提交的因子质量太差了，难怪我vf0.62
========================================================================================================================================================================


74


PN39025
Osmosis AllocatorMaster consultant
10个月前
我认为因为我不知道如何化解风险和准确预测未来的夏普下降点，所以我的夏普值不好，导致组合和价值因子较差。


21


RS23514
9个月前
感谢分享，学习了


19


AM12075
Osmosis AllocatorGrandMaster consultant
9个月前
==============================================================================

23年是负数的话敢交吗？

==============================================================================


40


ZH63852
Gold consultant
9个月前
学习了，讲解得很全面，之前很多不清楚的一下子明白了


16


QW53070
Osmosis AllocatorExpert consultant
9个月前
感谢分享


18


AC38598
Gold consultant
9个月前
随着学习的深入，每次回来重看都有新的感悟，感谢。

DZ94835
Osmosis AllocatorGold consultant
9个月前
有点懂了，要追求质量还要追求数量，哈哈，我交了一些alpha,有些fitness 大于1.5，还要margin 高一些，有时候好不容易找到一个alpha ，真的忍不住想要去交了 ，还是要多找些模版去运行，找到质量好一些，数量也要跟上，感谢大佬分享，让新人多多学习。 


13


ST57347
Gold consultant
9个月前
谢谢大佬解惑，解决了我现在的困境谢谢！


14


CG96890
Osmosis AllocatorGold consultant
9个月前
又学习了一些


10


FL55417
Gold consultant
9个月前
谢谢分享，学习了！


10


ZL15100
Osmosis AllocatorGold consultant
9个月前
学习了，谢谢分享


10


ML92493
Gold consultant
9个月前
在等一段时间看看


10


SZ20589
Master consultant
9个月前
感谢分享


46


YB55761
Gold consultant
9个月前
感谢分享，我是量化新人，目前还在用户阶段升金牌中，慢慢摸索，慢慢学习，加油


6


BS78500
Gold consultant
8个月前
多谢分享，学习了


7


CL11692
Osmosis AllocatorGold consultant
8个月前
感谢分享，学习了！


7


ZZ88452
Gold consultant
8个月前
经济学小白表示学会了，学没学废，不知道


7


DS54387
Osmosis AllocatorGold consultant
8个月前
感谢分享


7


TZ13685
Gold consultant
8个月前
感谢分享，希望早日成为顾问


7


CL50482
Gold consultant
8个月前
感谢分享


7


CY76111
Expert consultant
8个月前
学习了，感谢分享


7


MP68653
8个月前
很有帮助


7


MP68653
8个月前
感谢分享


7


LH94596
8个月前
感谢分享，学习了


7


WZ52329
Expert consultant
8个月前
感谢分享，受益匪浅


7


XQ52791
Gold consultant
8个月前
感谢分享，学到了


7


BZ32873
Gold consultant
8个月前
感谢大佬分享

 


7


HH90878
8个月前
感谢分享，跟随


7


XZ90935
8个月前
学习了不少知识，感谢分享！


7


XQ52791
Gold consultant
8个月前
  感谢分享，学到了


7


xiangguilin(GX18854)
8个月前
感谢分享

 


7


HH90878
8个月前
感谢分享，学习提升，加油！！！！！！


7


SW80151
8个月前
呜呜呜感谢分享！！！太有用了！


7


AW20905
Gold consultant
8个月前
感谢分享，开始按照内容实践一番


7


YangBiao(BY75699)
8个月前
SO GREAT.