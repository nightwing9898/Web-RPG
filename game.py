import json
import os
import random
from datetime import datetime, timedelta


class JSONManager:
    def __init__(self, filename="economy.json"):
        self.filename = filename
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filename):
            with open(self.filename, mode="w", encoding="utf-8") as file:
                json.dump({}, file, ensure_ascii=False)

    def load_accounts(self):
        db = {}
        with open(self.filename, mode="r", encoding="utf-8") as file:
            data = json.load(file)
            for user_id, user_data in data.items():
                account = Useraccount(user_id)
                account.balance = user_data.get("balance", 0)
                account.backpack = user_data.get("backpack", [])
                account.last_daily = user_data.get("last_daily", None)
                account.last_work = user_data.get("last_work", None)
                account.luck_active = user_data.get("luck_active", False)
                db[user_id] = account
        return db

    def save_accounts(self, accounts_db):
        data_to_save = {}
        for user_id, account in accounts_db.items():
            data_to_save[user_id] = {
                "balance": account.balance,
                "backpack": account.backpack,
                "last_daily": account.last_daily,
                "last_work": account.last_work,
                "luck_active": account.luck_active,
            }
        with open(self.filename, mode="w", encoding="utf-8") as file:
            json.dump(data_to_save, file, indent=4, ensure_ascii=False)


class Useraccount:
    def __init__(self, user_id):
        self.user_id = user_id
        self.balance = 0
        self.backpack = []
        self.last_daily = None
        self.last_work = None
        self.luck_active = False

    def add_money(self, amount):
        if amount > 0:
            self.balance += amount
            return f"成功入帳 {amount} 元！目前餘額：{self.balance}"
        return "❌ 請輸入有效金額。入帳金額必須大於 0"

    def deduct_money(self, amount):
        if amount <= self.balance:
            self.balance -= amount
            return True, f"成功扣款 {amount} 元！目前餘額：{self.balance}"
        return False, "❌ 餘額不足，扣款失敗"

    def do_work(self):
        now = datetime.now()
        if self.last_work is not None:
            last_time = datetime.fromisoformat(self.last_work)
            time_difference = now - last_time
            if time_difference < timedelta(minutes=30):
                remaining = timedelta(minutes=30) - time_difference
                minutes, seconds = divmod(remaining.seconds, 60)
                return False, f"冷卻還有 {minutes} 分 {seconds} 秒。"
        self.balance += 100
        self.last_work = now.isoformat()
        return True, f"賺了 100 元。目前餘額：{self.balance} 元"

    def slots(self, bet_amount: int):
        if bet_amount <= 0:
            return False, "❌ 賭注必須大於 0 元！"
        if bet_amount > self.balance:
            return False, f"❌ 餘額不足！你目前只有 {self.balance} 元。"

        self.balance -= bet_amount
        multipliers = [0, 1, 2, 3, 10]
        weights = [50, 25, 15, 8, 2]
        applied_luck = self.luck_active
        if applied_luck:
            weights[0] = max(30, weights[0] - 15)
            weights[2] += 4
            weights[3] += 2
            weights[4] += 1

        result_multiplier = random.choices(multipliers, weights=weights, k=1)[0]
        win_amount = bet_amount * result_multiplier
        self.balance += win_amount
        if applied_luck:
            self.luck_active = False

        if result_multiplier == 0:
            return True, f"你失去了 {bet_amount} 元賭注。 (目前餘額: {self.balance})"
        if result_multiplier == 1:
            return True, f"🤝 沒輸沒贏！你拿回了 {bet_amount} 元賭注。 (目前餘額: {self.balance})"
        if result_multiplier >= 2 and result_multiplier < 10:
            if applied_luck:
                return True, f"🎉 幸運御守加持！開出 {result_multiplier} 倍獎勵，贏得 {win_amount} 元！ (目前餘額: {self.balance})"
            return True, f"🎉 恭喜！開出 {result_multiplier} 倍獎勵，贏得 {win_amount} 元！ (目前餘額: {self.balance})"
        if applied_luck:
            return True, f"🎰 **JACKPOT!!** 奇蹟出現！你中了 10 倍超大獎，幸運御守加持狂賺 {win_amount} 元！！ (目前餘額: {self.balance})"
        return True, f"🎰 **JACKPOT!!** 奇蹟出現！你中了 10 倍超大獎，狂賺 {win_amount} 元！！ (目前餘額: {self.balance})"

    def fight_monster(self):
        monsters = [
            ("小野豬", 50, 120),
            ("哥布林", 80, 180),
            ("殭屍", 100, 240),
            ("狼人", 140, 320),
            ("暗影騎士", 200, 420),
        ]
        monster, min_gold, max_gold = random.choice(monsters)
        applied_luck = self.luck_active
        success_chance = 0.8
        reward_multiplier = 1.0
        if applied_luck:
            success_chance += 0.15
            reward_multiplier += 0.3
            self.luck_active = False

        if random.random() < success_chance:
            reward = int(random.randint(min_gold, max_gold) * reward_multiplier)
            self.balance += reward
            if applied_luck:
                return True, f"🎉 你擊敗了 {monster}！幸運御守加持，獲得 {reward} 元獎勵。 (目前餘額: {self.balance})"
            return True, f"🎉 你擊敗了 {monster}！獲得 {reward} 元獎勵。 (目前餘額: {self.balance})"

        penalty = random.randint(10, 30)
        if applied_luck:
            penalty = max(1, penalty - 10)
        self.balance = max(0, self.balance - penalty)
        if applied_luck:
            return False, f"❌ 你被 {monster} 反擊，幸運御守減少損失，損失 {penalty} 元。 (目前餘額: {self.balance})"
        return False, f"❌ 你被 {monster} 反擊，損失 {penalty} 元。 (目前餘額: {self.balance})"

    def challenge_boss(self):
        bosses = [
            {"name": "熔岩巨獸", "min_reward": 800, "max_reward": 1200, "base_chance": 0.55},
            {"name": "暗影龍", "min_reward": 1200, "max_reward": 1800, "base_chance": 0.45},
            {"name": "神秘魔王", "min_reward": 1800, "max_reward": 2600, "base_chance": 0.35},
        ]
        boss = random.choice(bosses)
        applied_luck = self.luck_active
        success_chance = boss["base_chance"]
        reward_multiplier = 1.0
        if applied_luck:
            success_chance += 0.15
            reward_multiplier += 0.25
            self.luck_active = False

        if "新手冒險劍" in self.backpack:
            success_chance += 0.08

        success_chance = min(success_chance, 0.95)
        if random.random() < success_chance:
            reward = int(random.randint(boss["min_reward"], boss["max_reward"]) * reward_multiplier)
            self.balance += reward
            if applied_luck:
                return True, f"🏆 恭喜！你擊敗了 {boss['name']}，幸運御守加持，獲得 {reward} 元。 (目前餘額: {self.balance})"
            return True, f"🏆 恭喜！你擊敗了 {boss['name']}，獲得 {reward} 元。 (目前餘額: {self.balance})"

        loss = int(random.randint(100, 220) * (1 - success_chance))
        self.balance = max(0, self.balance - loss)
        if applied_luck:
            return False, f"⚔️ 你挑戰 {boss['name']} 失敗，但幸運御守保護你，僅損失 {loss} 元。 (目前餘額: {self.balance})"
        return False, f"⚔️ 你挑戰 {boss['name']} 失敗，損失 {loss} 元。 (目前餘額: {self.balance})"


class Item:
    def __init__(self, item_id: str, name: str, price: int, description: str):
        self.item_id = item_id
        self.name = name
        self.price = price
        self.description = description

    def use(self, account):
        raise NotImplementedError("此道具尚未實作使用效果")


class VirtualETF(Item):
    def __init__(self, item_id: str, name: str, price: int, description: str, base_yield: float):
        super().__init__(item_id, name, price, description)
        self.base_yield = base_yield

    def use(self, account):
        return False, f"📈 {self.name} 是被動資產，放在背包中即可每日產生利息。"

    def calculate_daily_interest(self, account):
        actual_yield = self.base_yield + random.uniform(-0.002, 0.004)
        interest = int(self.price * actual_yield)
        if interest > 0:
            account.balance += interest
            return interest, f"💰 ETF 配息：您的 {self.name} 帶來了 {interest} 元的收益！"
        return 0, f"📉 市場震盪：您的 {self.name} 今日沒有產生收益。"


class RenameCard(Item):
    def __init__(self, item_id: str, name: str, price: int, description: str):
        super().__init__(item_id, name, price, description)

    def use(self, account):
        return True, "✨ 成功啟用改名卡！請使用網站的改名功能更新暱稱。"


class HealthPotion(Item):
    def __init__(self, item_id: str, name: str, price: int, description: str):
        super().__init__(item_id, name, price, description)

    def use(self, account):
        return True, "你喝下了高級治癒藥水，感覺元氣滿滿。"


class LuckCharm(Item):
    def __init__(self, item_id: str, name: str, price: int, description: str):
        super().__init__(item_id, name, price, description)

    def use(self, account):
        account.luck_active = True
        return True, "🍀 你使用了幸運御守！下一次打怪、老虎機或挑戰 BOSS 將獲得幸運加成。"


class AutoMiner(Item):
    def __init__(self, item_id: str, name: str, price: int, description: str, base_power: int):
        super().__init__(item_id, name, price, description)
        self.base_power = base_power

    def use(self, account):
        return False, f"🤖 {self.name} 是自動化設備，放在背包裡即可自動運作。"

    def mine(self):
        return random.randint(self.base_power - 5, self.base_power + 5)


def get_shop_items():
    return {
        "新手冒險劍": (200, "增加些微攻擊力，新手的最愛。", "⚔️"),
        "高級治癒藥水": (50, "瞬間回復 50% 的生命值。", "🧪"),
        "幸運御守": (500, "據說能大幅提高打怪掉寶率。", "🔮"),
        "全自動採礦機": (1500, "挂機流必備，默默為你賺錢。", "🤖"),
        "虛擬ETF": (5000, "每日配息的被動資產", "📈"),
    }


def get_registered_items():
    return {
        "高級治癒藥水": HealthPotion("POT01", "高級治癒藥水", 50, "瞬間回復"),
        "改名卡": RenameCard("RN01", "改名卡", 1000, "更改暱稱"),
        "幸運御守": LuckCharm("LUCK01", "幸運御守", 500, "提升打怪與老虎機運氣的守護符。"),
        "虛擬ETF": VirtualETF("ETF01", "虛擬ETF", 5000, "被動配息", 0.01),
        "全自動採礦機": AutoMiner("MINE01", "全自動採礦機", 1500, "默默為你賺錢", 15),
    }
