import os
import threading
import time
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from game import JSONManager, Useraccount, get_shop_items, get_registered_items

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "web_game_secret_key")
app.config["JSON_AS_ASCII"] = False

DB_FILE = "economy.json"
ETF_DIVIDEND_INTERVAL = 86400  # 測試用：每 60 秒結算一次 ETF 配息。若要改成每日請設定為 86400
AUTO_MINE_INTERVAL = 600  # 測試用：每 10 分鐘運行一次自動礦機。若要改成每日請設定為 86400

json_manager = JSONManager(DB_FILE)
accounts = json_manager.load_accounts()
shop_items = get_shop_items()
registered_items = get_registered_items()


def get_user_account(user_id):
    user_id = str(user_id)
    if user_id not in accounts:
        accounts[user_id] = Useraccount(user_id)
    return accounts[user_id]


def save_accounts():
    json_manager.save_accounts(accounts)


def etf_dividend_task():
    while True:
        time.sleep(ETF_DIVIDEND_INTERVAL)
        etf = registered_items.get("虛擬ETF")
        if not etf:
            continue
        changes = False
        for account in accounts.values():
            etf_count = account.backpack.count("虛擬ETF")
            if etf_count > 0:
                for _ in range(etf_count):
                    interest, _ = etf.calculate_daily_interest(account)
                    if interest > 0:
                        changes = True
        if changes:
            save_accounts()


def auto_mine_task():
    while True:
        time.sleep(AUTO_MINE_INTERVAL)
        miner = registered_items.get("全自動採礦機")
        if not miner:
            continue
        changes = False
        for account in accounts.values():
            miner_count = account.backpack.count("全自動採礦機")
            if miner_count > 0:
                total_mined = 0
                for _ in range(miner_count):
                    total_mined += miner.mine()
                if total_mined > 0:
                    account.balance += total_mined
                    changes = True
        if changes:
            save_accounts()


def require_login():
    player = session.get("player")
    if not player:
        flash("請先登入你的冒險者暱稱。", "warning")
        return None
    return player


def require_login_json():
    player = session.get("player")
    if not player:
        return None, jsonify({"success": False, "message": "請先登入你的冒險者暱稱。"}), 401
    return player, None, None


def account_to_dict(account):
    return {
        "balance": account.balance,
        "backpack": account.backpack,
        "last_work": account.last_work,
        "luck_active": account.luck_active,
    }


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            flash("請輸入有效的暱稱。", "danger")
            return redirect(url_for("index"))
        session["player"] = username
        flash(f"歡迎回來，{username}！", "success")
        return redirect(url_for("dashboard"))

    player = session.get("player")
    return render_template("index.html", player=player)


@app.route("/dashboard")
def dashboard():
    player = require_login()
    if not player:
        return redirect(url_for("index"))
    account = get_user_account(player)
    return render_template(
        "dashboard.html",
        player=player,
        account=account,
        account_data=account_to_dict(account),
        shop_items=shop_items,
    )


@app.route("/api/status")
def api_status():
    player, response, status_code = require_login_json()
    if response:
        return response, status_code
    account = get_user_account(player)
    return jsonify({"success": True, "account": account_to_dict(account), "shop_items": shop_items})


@app.route("/api/work", methods=["POST"])
def api_work():
    player, response, status_code = require_login_json()
    if response:
        return response, status_code
    account = get_user_account(player)
    success, reply_msg = account.do_work()
    if success:
        save_accounts()
    return jsonify({"success": success, "message": reply_msg, "account": account_to_dict(account)})


@app.route("/api/slots", methods=["POST"])
def api_slots():
    player, response, status_code = require_login_json()
    if response:
        return response, status_code
    amount = request.json.get("amount") if request.is_json else request.form.get("amount")
    try:
        bet_amount = int(amount)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "請輸入有效的押注金額。"}), 400
    account = get_user_account(player)
    success, reply_msg = account.slots(bet_amount)
    if success:
        save_accounts()
    return jsonify({"success": success, "message": reply_msg, "account": account_to_dict(account)})


@app.route("/api/fight", methods=["POST"])
def api_fight():
    player, response, status_code = require_login_json()
    if response:
        return response, status_code
    account = get_user_account(player)
    success, reply_msg = account.fight_monster()
    save_accounts()
    return jsonify({"success": success, "message": reply_msg, "account": account_to_dict(account)})


@app.route("/api/boss", methods=["POST"])
def api_boss():
    player, response, status_code = require_login_json()
    if response:
        return response, status_code
    account = get_user_account(player)
    success, reply_msg = account.challenge_boss()
    save_accounts()
    return jsonify({"success": success, "message": reply_msg, "account": account_to_dict(account)})


@app.route("/api/buy", methods=["POST"])
def api_buy():
    player, response, status_code = require_login_json()
    if response:
        return response, status_code
    data = request.json if request.is_json else request.form
    item_name = data.get("item_name")
    quantity = int(data.get("quantity", 1))
    if item_name not in shop_items:
        return jsonify({"success": False, "message": "商店裡沒有這件商品，請選擇正確的道具。"}), 400
    if quantity <= 0:
        return jsonify({"success": False, "message": "購買數量必須大於 0。"}), 400
    price, _, _ = shop_items[item_name]
    total_price = price * quantity
    account = get_user_account(player)
    if account.balance < total_price:
        return jsonify({"success": False, "message": f"你的餘額不足！購買 {quantity} 個 {item_name} 需要 {total_price} 元。"}), 400
    success, msg = account.deduct_money(total_price)
    if success:
        account.backpack.extend([item_name] * quantity)
        save_accounts()
        return jsonify({"success": True, "message": f"已成功購買 {quantity} 個 {item_name}，{msg}", "account": account_to_dict(account)})
    return jsonify({"success": False, "message": msg}), 400


@app.route("/api/use", methods=["POST"])
def api_use():
    player, response, status_code = require_login_json()
    if response:
        return response, status_code
    data = request.json if request.is_json else request.form
    item_name = data.get("item_name")
    account = get_user_account(player)
    if item_name not in account.backpack:
        return jsonify({"success": False, "message": f"你的背包裡沒有 {item_name}。"}), 400
    item_obj = registered_items.get(item_name)
    if not item_obj:
        return jsonify({"success": False, "message": f"{item_name} 目前無法主動使用。"}), 400
    is_consumed, reply_msg = item_obj.use(account)
    if is_consumed:
        account.backpack.remove(item_name)
    save_accounts()
    return jsonify({"success": True, "message": reply_msg, "account": account_to_dict(account)})


@app.route("/api/gift", methods=["POST"])
def api_gift():
    player, response, status_code = require_login_json()
    if response:
        return response, status_code
    data = request.json if request.is_json else request.form
    target_name = data.get("target_name", "").strip()
    item_name = data.get("item_name")
    quantity = int(data.get("quantity", 1))
    account = get_user_account(player)
    if target_name == "" or target_name == player:
        return jsonify({"success": False, "message": "請輸入正確的收禮對象，且不可為自己。"}), 400
    if item_name not in account.backpack:
        return jsonify({"success": False, "message": f"你的背包裡沒有 {item_name}。"}), 400
    if quantity <= 0:
        return jsonify({"success": False, "message": "請輸入有效的數量。"}), 400
    available = account.backpack.count(item_name)
    if quantity > available:
        return jsonify({"success": False, "message": f"你的背包裡只有 {available} 個 {item_name}。"}), 400
    receiver = get_user_account(target_name)
    for _ in range(quantity):
        account.backpack.remove(item_name)
        receiver.backpack.append(item_name)
    save_accounts()
    return jsonify({"success": True, "message": f"已成功送出 {quantity} 個 {item_name} 給 {target_name}。", "account": account_to_dict(account)})


@app.route("/logout")
def logout():
    session.pop("player", None)
    flash("已成功登出。", "info")
    return redirect(url_for("index"))


@app.route("/wallet")
def wallet():
    player = require_login()
    if not player:
        return redirect(url_for("index"))
    account = get_user_account(player)
    return render_template("wallet.html", player=player, account=account)


@app.route("/shop")
def shop():
    player = require_login()
    if not player:
        return redirect(url_for("index"))
    return render_template("shop.html", player=player, shop_items=shop_items)


@app.route("/buy", methods=["POST"])
def buy():
    player = require_login()
    if not player:
        return redirect(url_for("index"))
    item_name = request.form.get("item_name")
    quantity = int(request.form.get("quantity", 1))

    if item_name not in shop_items:
        flash("商店裡沒有這件商品，請選擇正確的道具。", "danger")
        return redirect(url_for("shop"))
    if quantity <= 0:
        flash("購買數量必須大於 0。", "danger")
        return redirect(url_for("shop"))

    price, _, emoji = shop_items[item_name]
    total_price = price * quantity
    account = get_user_account(player)

    if account.balance < total_price:
        flash(f"你的餘額不足！購買 {quantity} 個 {item_name} 需要 {total_price} 元。", "danger")
        return redirect(url_for("shop"))

    success, msg = account.deduct_money(total_price)
    if success:
        account.backpack.extend([item_name] * quantity)
        save_accounts()
        flash(f"已成功購買 {quantity} 個 {item_name}，{msg}", "success")
    else:
        flash(msg, "danger")

    return redirect(url_for("wallet"))


@app.route("/work", methods=["POST"])
def work():
    player = require_login()
    if not player:
        return redirect(url_for("index"))
    account = get_user_account(player)
    success, reply_msg = account.do_work()
    if success:
        save_accounts()
        flash(reply_msg, "success")
    else:
        flash(reply_msg, "warning")
    return redirect(url_for("dashboard"))


@app.route("/balance")
def balance():
    player = require_login()
    if not player:
        return redirect(url_for("index"))
    account = get_user_account(player)
    flash(f"{player}，你目前的餘額為：{account.balance} 元。", "info")
    return redirect(url_for("dashboard"))


@app.route("/slots", methods=["POST"])
def slots():
    player = require_login()
    if not player:
        return redirect(url_for("index"))
    amount = request.form.get("amount")
    try:
        bet_amount = int(amount)
    except (TypeError, ValueError):
        flash("請輸入有效的押注金額。", "danger")
        return redirect(url_for("dashboard"))

    account = get_user_account(player)
    success, reply_msg = account.slots(bet_amount)
    if success:
        save_accounts()
        flash(reply_msg, "success")
    else:
        flash(reply_msg, "danger")
    return redirect(url_for("dashboard"))


@app.route("/use", methods=["GET", "POST"])
def use_item():
    player = require_login()
    if not player:
        return redirect(url_for("index"))
    account = get_user_account(player)

    if request.method == "GET":
        choices = sorted(set(account.backpack))
        return render_template("use.html", player=player, choices=choices)

    item_name = request.form.get("item_name")
    if item_name not in account.backpack:
        flash(f"你的背包裡沒有 {item_name}。", "danger")
        return redirect(url_for("use_item"))

    item_obj = registered_items.get(item_name)
    if not item_obj:
        flash(f"{item_name} 目前無法主動使用。", "danger")
        return redirect(url_for("use_item"))

    is_consumed, reply_msg = item_obj.use(account)
    if is_consumed:
        account.backpack.remove(item_name)
    save_accounts()
    flash(reply_msg, "success")
    return redirect(url_for("wallet"))


@app.route("/gift", methods=["GET", "POST"])
def gift():
    player = require_login()
    if not player:
        return redirect(url_for("index"))
    account = get_user_account(player)

    if request.method == "GET":
        choices = sorted(set(account.backpack))
        return render_template("gift.html", player=player, choices=choices)

    target_name = request.form.get("target_name", "").strip()
    item_name = request.form.get("item_name")
    quantity = int(request.form.get("quantity", 1))

    if target_name == "" or target_name == player:
        flash("請輸入正確的收禮對象，且不可為自己。", "danger")
        return redirect(url_for("gift"))
    if item_name not in account.backpack:
        flash(f"你的背包裡沒有 {item_name}。", "danger")
        return redirect(url_for("gift"))
    if quantity <= 0:
        flash("請輸入有效的數量。", "danger")
        return redirect(url_for("gift"))

    available = account.backpack.count(item_name)
    if quantity > available:
        flash(f"你的背包裡只有 {available} 個 {item_name}。", "danger")
        return redirect(url_for("gift"))

    receiver = get_user_account(target_name)
    for _ in range(quantity):
        account.backpack.remove(item_name)
        receiver.backpack.append(item_name)
    save_accounts()
    flash(f"已成功送出 {quantity} 個 {item_name} 給 {target_name}。", "success")
    return redirect(url_for("wallet"))


if __name__ == "__main__":
    threading.Thread(target=etf_dividend_task, daemon=True).start()
    threading.Thread(target=auto_mine_task, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)

