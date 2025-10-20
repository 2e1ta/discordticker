import os

# Render の Python 3.13 では audioop モジュールが無いため、音声機能を無効化
os.environ.setdefault("DISCORD_DISABLE_VOICE", "1")

import discord
from discord import app_commands
from discord.ext import tasks
import yfinance as yf
import psycopg2
from datetime import datetime
from typing import Optional

# HTTPサーバ（UptimeRobot用）
from keep_alive import start_server

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = False

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

alerts = []
alert_id_counter = 1


def get_db_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))


def ensure_portfolio_schema():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                purchase_price DOUBLE PRECISION NOT NULL,
                quantity INT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        cur.execute("ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS guild_id BIGINT")
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[{datetime.now()}] Failed to ensure portfolio schema: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


async def notify_interaction_timeout(interaction: discord.Interaction) -> None:
    message = "⏱応答がタイムアウトしました。もう一度お試しください。"
    channel = interaction.channel
    if channel is not None:
        try:
            await channel.send(message)
            return
        except (discord.Forbidden, discord.HTTPException):
            pass
    try:
        await interaction.user.send(message)
    except (discord.Forbidden, discord.HTTPException):
        pass


def get_stock_price(ticker: str) -> Optional[float]:
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if not data.empty:
            return float(data["Close"].iloc[-1])
        return None
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching price for {ticker}: {e}")
        return None


@tree.command(name="alert_above", description="指定価格以上になったら通知")
async def alert_above(interaction: discord.Interaction, ticker: str, price: float):
    global alert_id_counter
    ticker_with_suffix = ticker if ticker.endswith(".T") else f"{ticker}.T"
    alert = {
        "id": alert_id_counter,
        "ticker": ticker_with_suffix,
        "price": price,
        "type": "above",
        "user": interaction.user.id,
        "channel": interaction.channel_id,
    }
    alerts.append(alert)
    alert_id_counter += 1
    await interaction.response.send_message(
        f"✅アラート登録:\n{ticker_with_suffix} が {price}円以上になったら通知します"
    )


@tree.command(name="alert_below", description="指定価格以下になったら通知")
async def alert_below(interaction: discord.Interaction, ticker: str, price: float):
    global alert_id_counter
    ticker_with_suffix = ticker if ticker.endswith(".T") else f"{ticker}.T"
    alert = {
        "id": alert_id_counter,
        "ticker": ticker_with_suffix,
        "price": price,
        "type": "below",
        "user": interaction.user.id,
        "channel": interaction.channel_id,
    }
    alerts.append(alert)
    alert_id_counter += 1
    await interaction.response.send_message(
        f"✅アラート登録:\n{ticker_with_suffix} が {price}円以下になったら通知します"
    )


@tree.command(name="cancel", description="アラートを削除")
async def cancel(interaction: discord.Interaction, ticker: str):
    global alerts
    ticker_with_suffix = ticker if ticker.endswith(".T") else f"{ticker}.T"
    original_count = len(alerts)
    alerts = [
        a
        for a in alerts
        if not (a["ticker"] == ticker_with_suffix and a["user"] == interaction.user.id)
    ]
    removed_count = original_count - len(alerts)
    if removed_count > 0:
        await interaction.response.send_message(
            f"✅ {ticker_with_suffix} のアラートを {removed_count}件削除しました"
        )
    else:
        await interaction.response.send_message(
            f"❌ {ticker_with_suffix} のアラートが見つかりませんでした"
        )


@tree.command(name="price", description="現在の株価を表示")
async def price(interaction: discord.Interaction, ticker: str):
    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        await notify_interaction_timeout(interaction)
        return
    ticker_with_suffix = ticker if ticker.endswith(".T") else f"{ticker}.T"
    current_price = get_stock_price(ticker_with_suffix)
    if current_price is not None:
        await interaction.followup.send(
            f"{ticker_with_suffix}\n現在価格: {current_price:.2f}円"
        )
    else:
        await interaction.followup.send(
            f"❌{ticker_with_suffix} の価格を取得できませんでした"
        )

@tree.command(name="set", description="株を仕込み登録")
async def set_stock(
    interaction: discord.Interaction, ticker: str, purchase_price: float, quantity: int
):
    ticker_with_suffix = ticker if ticker.endswith(".T") else f"{ticker}.T"
    guild_id = interaction.guild_id
    if guild_id is None:
        await interaction.response.send_message("❌このコマンドはサーバー内でのみ使用できます")
        return
    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        await notify_interaction_timeout(interaction)
        return
    ensure_portfolio_schema()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO portfolio (guild_id, user_id, ticker, purchase_price, quantity) VALUES (%s, %s, %s, %s, %s)",
            (guild_id, interaction.user.id, ticker_with_suffix, purchase_price, quantity),
        )
        conn.commit()
        total_cost = purchase_price * quantity
        await interaction.followup.send(
            f"仕込み登録:\n{ticker_with_suffix} - {quantity}株 @ {purchase_price:.2f}円\n合計 {total_cost:,.0f}円"
        )
    except Exception as e:
        if conn is not None:
            conn.rollback()
        await interaction.followup.send(f"❌エラー: {str(e)}")
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

@tree.command(name="show", description="ポートフォリオを表示")
async def show(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    if guild_id is None:
        await interaction.response.send_message("❌このコマンドはサーバー内でのみ使用できます")
        return
    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        await notify_interaction_timeout(interaction)
        return
    ensure_portfolio_schema()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT ticker, purchase_price, quantity FROM portfolio WHERE guild_id = %s ORDER BY ticker, created_at",
            (guild_id,),
        )
        holdings = cur.fetchall()
    except Exception as e:
        if conn is not None:
            conn.rollback()
        await interaction.followup.send(f"❌エラー: {str(e)}")
        return
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()
    if not holdings:
        await interaction.followup.send("ポートフォリオは空です")
        return
    portfolio_by_ticker = {}
    for ticker, purchase_price, quantity in holdings:
        portfolio_by_ticker.setdefault(ticker, []).append(
            {"purchase_price": purchase_price, "quantity": quantity}
        )
    message_lines = ["あなたのサーバー全体のポートフォリオ", ""]
    total_invested = 0
    total_current = 0
    for ticker, positions in portfolio_by_ticker.items():
        total_quantity = sum(p["quantity"] for p in positions)
        invested = sum(p["purchase_price"] * p["quantity"] for p in positions)
        avg_purchase = invested / total_quantity if total_quantity else 0
        current_price = get_stock_price(ticker)
        if current_price is not None:
            current_value = current_price * total_quantity
            profit = current_value - invested
            profit_pct = (profit / invested) * 100 if invested else 0.0
            message_lines.extend([
                f"{ticker}",
                f"　購入: {avg_purchase:.2f}円 × {total_quantity}株",
                f"　現在: {current_price:.2f}円",
                f"　損益: {profit:+,.0f}円 ({profit_pct:+.2f}%)",
                "",
            ])
            total_invested += invested
            total_current += current_value
        else:
            message_lines.extend([
                f"{ticker}",
                f"　購入: {avg_purchase:.2f}円 × {total_quantity}株",
                "　現在: 取得失敗",
                "",
            ])
            total_invested += invested
    if total_invested > 0:
        total_profit = total_current - total_invested
        total_profit_pct = (total_profit / total_invested) * 100
        message_lines.extend([
            f"投資額: {total_invested:,.0f}円",
            f"評価額: {total_current:,.0f}円",
            f"損益: {total_profit:+,.0f}円 ({total_profit_pct:+.2f}%)",
        ])
    await interaction.followup.send("\n".join(message_lines))

@tree.command(name="sell", description="株を売却")
async def sell(
    interaction: discord.Interaction, ticker: str, quantity: int, sell_price: float
):
    ticker_with_suffix = ticker if ticker.endswith(".T") else f"{ticker}.T"
    guild_id = interaction.guild_id
    if guild_id is None:
        await interaction.response.send_message("❌このコマンドはサーバー内でのみ使用できます")
        return
    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        await notify_interaction_timeout(interaction)
        return
    ensure_portfolio_schema()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, purchase_price, quantity FROM portfolio WHERE guild_id = %s AND ticker = %s ORDER BY created_at",
            (guild_id, ticker_with_suffix),
        )
        holdings = cur.fetchall()
        if not holdings:
            await interaction.followup.send(f"❌{ticker_with_suffix} の保有がありません")
            return
        total_quantity = sum(h[2] for h in holdings)
        if quantity > total_quantity:
            await interaction.followup.send(
                f"❌保有株数 ({total_quantity}株) より多く売却できません"
            )
            return
        remaining = quantity
        total_cost = 0
        for holding_id, purchase_price, holding_qty in holdings:
            if remaining <= 0:
                break
            if holding_qty <= remaining:
                total_cost += purchase_price * holding_qty
                remaining -= holding_qty
                cur.execute("DELETE FROM portfolio WHERE id = %s", (holding_id,))
            else:
                total_cost += purchase_price * remaining
                new_qty = holding_qty - remaining
                cur.execute(
                    "UPDATE portfolio SET quantity = %s WHERE id = %s",
                    (new_qty, holding_id),
                )
                remaining = 0
        conn.commit()
        avg_purchase = total_cost / quantity if quantity else 0
        revenue = sell_price * quantity
        profit = revenue - total_cost
        profit_pct = (profit / total_cost) * 100 if total_cost else 0.0
        message_lines = [
            f"売却完了: {ticker_with_suffix}",
            "",
            f"売却株数: {quantity}株",
            f"平均取得単価: {avg_purchase:.2f}円",
            f"売却価格: {sell_price:.2f}円",
            f"損益: {profit:+,.0f}円 ({profit_pct:+.2f}%)",
        ]
        await interaction.followup.send("\n".join(message_lines))
    except Exception as e:
        if conn is not None:
            conn.rollback()
        await interaction.followup.send(f"❌エラー: {str(e)}")
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


@tasks.loop(minutes=5)
async def check_alerts():
    global alerts
    alerts_to_remove = []

    for alert in list(alerts):
        current_price = get_stock_price(alert["ticker"])
        if current_price is None:
            continue

        triggered = (alert["type"] == "above" and current_price >= alert["price"]) or (
            alert["type"] == "below" and current_price <= alert["price"]
        )

        if triggered:
            try:
                channel = client.get_channel(alert["channel"])
                if channel:
                    condition = "以上" if alert["type"] == "above" else "以下"
                    message = (
                        f" @everyone  {alert['ticker']} が {current_price:.2f}円"
                        f"（閾値 {alert['price']:.2f}円{condition}）を突破！"
                    )
                    await channel.send(message)
                    alerts_to_remove.append(alert)
            except Exception as e:
                print(f"[{datetime.now()}] Error sending alert: {e}")

    for alert in alerts_to_remove:
        if alert in alerts:
            alerts.remove(alert)


@client.event
async def on_ready():
    ensure_portfolio_schema()
    await tree.sync()
    print(f"Bot is ready! Logged in as {client.user}")
    if not check_alerts.is_running():
        check_alerts.start()


if __name__ == "__main__":
    # Render(Web Service) でHTTPが必要→ UptimeRobotに叩かせてスリープ回避
    start_server()
    client.run(TOKEN)
