"""vague_wording：空泛词词形只给逐句复核的候选，不进入放行判定。"""
import pytest

from ai_filler_lint import analyze, detect_vague_wording, effective_policy


@pytest.mark.parametrize("subtype, sentence", [
    ("V01", "哪一天动手，要看六月初的天气。"),
    ("V02", "部队照原计划走。"),
    ("V05", "约德尔没有退：“那么第15集团军抽走以后，加莱的空当谁来填？"),
    ("V06", "支队五千人，到这时死伤已经一千五百多，河口和海滩要守，炮兵要人护，一木手里能动的只剩一个中队。"),
    ("V07", "苏联几个月内就会垮掉，\"他说，\"到那时候联邦再动手，就只能跟在德国后面收拾残局了。"),
    ("V08", "先用飞机把公路南边一块地方炸烂，第7军的步兵穿过去拿下马里尼和圣吉勒，再放装甲部队出去，一路往西南取库唐斯，截断半岛西边德军的退路，一路往南、往东南把口子撑开。"),
    ("V10", "朗维尔以南的公路两边是开阔的麦田，一直铺到海边的沙丘，海上的军舰这会儿正忙着打海滩，等登陆部队上了岸，就会腾出手来，伞兵的观察员不会看不见路上的卡车和坦克。"),
    ("V11", "美国人从犹他往西、往北打，科唐坦半岛随时会被拦腰切断，瑟堡要当要塞守，守到最后，施利本的部队不许往瑟堡里退，顶不住了才许往后让一步。"),
    ("N01", "全印度的英国皇家空军只有两个运输中队，用的是旧客机改装的道格拉斯和哈德逊，一天往英帕尔送的东西，连第4军一天的口粮也不够。"),
    ("R01", "那一下改变了局面。"),
    ("Q01", "后面的波次乱了。"),
    ("Q02", "主力那一路走得顺当，则里拉路面的石头被骡帮的蹄铁磨得发亮。"),
    ("Q06", "中间那颗要了命，它从舰岛后面穿过飞行甲板的钢板和木铺板，穿过机库甲板、第二甲板和底下一层薄装甲，延时引信走完，在后部涡轮发电机舱后面的主控制室里炸开。"),
    ("C01", "情况正在变。"),
    ("C02", "九月三十日，古德里安的第2装甲集群从格卢霍夫一带率先出击，两天后，台风行动在整条中央战线上全面铺开。"),
])
def test_vague_wording_positive(subtype, sentence):
    assert subtype in {hit["subtype"] for hit in detect_vague_wording(sentence)}


@pytest.mark.parametrize("sentence", [
    "他自己动手。", "她亲自动手。", "他动手写字。", "她动手做饭。", "他动手拆门。",
    "她动手修车。", "他动手画图。", "她动手打人。", "他扣动手中扳机。", "他摇动手轮。",
    "他们没有退路。", "可以动用部队。", "决心不能动摇。", "发挥主观能动性。",
    "她收拾行装。", "他收拾行李。", "她收拾包袱。", "他收拾餐具。", "她收拾屋子。",
    "他收拾房间。", "她把桌面收拾整齐。", "她把行李收拾干净。", "他收拾掉屋子里的行装。",
    "潜艇放鱼雷。", "飞机投放武器。", "飞机投放出去。", "他们放飞了鸽子。",
    "他支撑住了。", "她撑着桌子。", "这些东西。", "那些东西。", "一件东西。",
    "他买东西。", "他卖东西。", "她看东西。", "她吃东西。", "什么东西。", "东西：粮食、药品。",
    "这东西。", "那套东西。", "东西两边。", "他抓着栏杆站稳。", "他扶着桌子站稳。",
    "她抓住栏杆站稳。", "她扶住桌子站稳。", "他脚下站稳了。",
    "二十七日，第18团清了马里尼，第1师往库唐斯打，德国人在高地、篱墙和路口设防，补给车队要坦克护着才走得过去。",
    "厄斯金在北非带过这个师，那时候侧翼敞着是常事，沙漠里一眼望得出十几公里；这里隔一道篱墙就什么也看不见。",
    "运输船停在萨沃岛西南等他的\"海峡已清\"，三点以前等不到，就掉头往南，登陆推迟一天。",
    "戈林没有再提建国，只咬住粮食不放。",
    "抵达雷多的英国、印度兵有四千多人，大多赤脚，枪也扔了；进山的一万二千多人中，另有两千多人折返，在曼西和加迈的东联哨所投降，其余没能出来。",
])
def test_vague_wording_exclusions(sentence):
    assert detect_vague_wording(sentence) == []


def test_vague_wording_sentence_location_and_observe_policy():
    text = '# 动手\n他说：“动手，动手，稳住。”\n一样东西。'
    hits = detect_vague_wording(text)
    assert [(h["subtype"], h["location"]) for h in hits] == [("V01", "L2"), ("Q01", "L2"), ("N01", "L3")]
    assert all(text[h["start"]:h["end"]] == h["span"] == h["matched"] for h in hits)
    assert hits[0]["snippet"] == '他说：“动手，动手，稳住。”'
    assert effective_policy("vague_wording", "zh", "vague_wording")["lifecycle"] == "observe"
    assert not effective_policy("vague_wording", "en", "vague_wording")["registered"]
    assert not effective_policy("vague_wording", "en")["registered"]
    result = analyze(text, lang="zh")
    candidates = [h for h in result["hits"] if h["family"] == "vague_wording"]
    assert len(candidates) == 3 and all(not h["per_sentence"] for h in candidates)
    assert not any(a["family"] == "vague_wording" for a in result["cluster_alerts"] + result["observed_alerts"])
