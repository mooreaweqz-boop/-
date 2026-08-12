import discord
from discord.ext import commands
from discord import app_commands
import os
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TOKEN')

# ==========================================
# ค่าคงที่ - ปรับตามเซิร์ฟเวอร์ของคุณ
# ==========================================
ALLOWED_GUILD_ID = 1528066781283881142      # ID เซิร์ฟเวอร์ REALXPOOHSHOP
ADMIN_IDS = [1494305147176620092]           # 👈 ID ผู้ใช้ของคุณ (Admin)
LOG_CHANNEL_ID = 1531862124303749182        # ช่องแจ้งเตือน

API_URL = "http://fi15.bot-hosting.net:26334/redeem"

# ==========================================
# ตั้งค่า Intents และ Bot
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ==========================================
# ข้อมูลร้านค้า (เก็บใน RAM)
# ==========================================
categories = {
    "Electronics": {"items": [{"name": "Phone", "price": 300}, {"name": "Laptop", "price": 800}]},
    "Clothing": {"items": [{"name": "T-Shirt", "price": 20}, {"name": "Jeans", "price": 50}]}
}

# ==========================================
# ฟังก์ชันส่ง Log
# ==========================================
async def send_log(interaction: discord.Interaction, action: str, details: str, color=discord.Color.green()):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        print("❌ ไม่พบช่อง Log (ตรวจสอบ ID)")
        return
    embed = discord.Embed(
        title=f"📢 {action}",
        description=details,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"โดย {interaction.user}", icon_url=interaction.user.display_avatar.url)
    await channel.send(embed=embed)

# ==========================================
# ฟังก์ชันเรียก API เติมเงิน
# ==========================================
async def redeem_voucher(phone: str, voucher: str):
    params = {"phone": phone, "voucher": voucher}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, params=params, timeout=10) as response:
                result = await response.json()
                return result
        except asyncio.TimeoutError:
            return {"status": {"code": "TIMEOUT", "message": "การเชื่อมต่อหมดเวลา"}}
        except Exception as e:
            return {"status": {"code": "ERROR", "message": str(e)}}

# ==========================================
# Modal สำหรับกรอกข้อมูลเติมเงิน
# ==========================================
class TopUpModal(discord.ui.Modal, title='🧧 เติมเงินผ่าน Wallet'):
    phone = discord.ui.TextInput(
        label='เบอร์โทรศัพท์',
        placeholder='0812345678',
        required=True,
        max_length=10
    )
    voucher_link = discord.ui.TextInput(
        label='ลิงก์ซองอั่งเปา',
        placeholder='https://gift.truemoney.com/campaign/?v=xxxxxxxxxxxxxxxx',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        result = await redeem_voucher(self.phone.value, self.voucher_link.value)

        status = result.get("status", {})
        code = status.get("code", "UNKNOWN")
        message = status.get("message", "ไม่มีข้อความ")
        amount = "ไม่ทราบ"
        if code == "SUCCESS":
            voucher_data = result.get("data", {}).get("voucher", {})
            amount = voucher_data.get("amount_baht", "0.00")
        else:
            voucher_data = result.get("data", {}).get("voucher", {})
            if voucher_data:
                amount = voucher_data.get("amount_baht", "0.00")

        embed = discord.Embed(
            title="📊 ผลการเติมเงิน",
            color=discord.Color.green() if code == "SUCCESS" else discord.Color.red()
        )
        embed.add_field(name="สถานะ", value=f"`{code}`", inline=True)
        embed.add_field(name="ข้อความ", value=message, inline=False)
        embed.add_field(name="เบอร์โทร", value=self.phone.value, inline=True)
        embed.add_field(name="💰 จำนวนเงิน", value=f"{amount} บาท", inline=True)
        embed.add_field(name="ลิงก์", value=self.voucher_link.value, inline=False)

        status_explain = {
            "SUCCESS": "✅ เติมเงินสำเร็จ",
            "VOUCHER_EXPIRED": "❌ ซองนี้หมดอายุแล้ว",
            "VOUCHER_OUT_OF_STOCK": "❌ ซองนี้ถูกใช้ไปแล้ว",
            "VOUCHER_NOT_FOUND": "❌ ไม่พบซองนี้ในระบบ",
            "INVALID_PHONE": "❌ เบอร์โทรไม่ถูกต้อง",
            "TIMEOUT": "⏰ การเชื่อมต่อหมดเวลา",
            "ERROR": "⚠️ เกิดข้อผิดพลาด"
        }
        explain = status_explain.get(code, f"สถานะ: {code}")
        embed.add_field(name="🔍 คำอธิบาย", value=explain, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

        log_details = (
            f"**ผู้ใช้:** {interaction.user.mention}\n"
            f"**เบอร์โทร:** {self.phone.value}\n"
            f"**ลิงก์:** {self.voucher_link.value}\n"
            f"**ผลลัพธ์:** {code} - {message}\n"
            f"**จำนวนเงิน:** {amount} บาท"
        )
        await send_log(
            interaction,
            "💳 เติมเงินผ่าน Wallet",
            log_details,
            discord.Color.gold() if code == "SUCCESS" else discord.Color.red()
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("❌ เกิดข้อผิดพลาดในการดำเนินการ", ephemeral=True)
        print(f"Modal error: {error}")

# ==========================================
# UI ปุ่มสำหรับ /shop
# ==========================================
class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label='🛒 ซื้อสินค้า', style=discord.ButtonStyle.primary)
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title='📦 รายการสินค้าทั้งหมด',
            color=discord.Color.green()
        )
        if not categories:
            embed.description = "❌ ขณะนี้ยังไม่มีสินค้าในร้าน"
        else:
            for cat_name, cat_data in categories.items():
                if not cat_data["items"]:
                    item_list = "ยังไม่มีสินค้าในหมวดนี้"
                else:
                    item_list = "\n".join([f"• {item['name']} : {item['price']} เหรียญ" for item in cat_data["items"]])
                embed.add_field(name=f"📂 {cat_name}", value=item_list, inline=False)
        embed.set_footer(text="สั่งซื้อพิมพ์ !order <ชื่อสินค้า>")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await send_log(
            interaction,
            "🛒 ดูรายการสินค้า",
            f"{interaction.user.mention} เปิดดูรายการสินค้า",
            discord.Color.blue()
        )

    @discord.ui.button(label='💳 เติมเงิน', style=discord.ButtonStyle.success)
    async def topup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TopUpModal())

    @discord.ui.button(label='❌ ปิด', style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content='🚪 ปิดร้านค้าแล้ว', embed=None, view=None)

# ==========================================
# คำสั่ง /shop
# ==========================================
@bot.tree.command(name="shop", description="🛍️ เปิดหน้าร้านค้า")
async def shop(interaction: discord.Interaction):
    if interaction.guild is None or interaction.guild.id != ALLOWED_GUILD_ID:
        await interaction.response.send_message("❌ บอทนี้ใช้ได้เฉพาะเซิร์ฟเวอร์ REALXPOOHSHOP", ephemeral=True)
        return

    embed = discord.Embed(
        title='🛍️ REALXPOOHSHOP',
        description='**เลือกทำรายการด้านล่างได้เลย**',
        color=discord.Color.blue()
    )
    embed.add_field(name='✨ โปรโมชั่น', value='เติมเงิน 500 เหรียญ รับฟรี 50', inline=False)
    embed.add_field(name='📌 วิธีการใช้งาน', value='• กดปุ่ม **ซื้อสินค้า** เพื่อดูรายการ\n• กดปุ่ม **เติมเงิน** เพื่อเติมผ่าน Wallet', inline=False)
    embed.set_footer(text='ขอบคุณที่ใช้บริการ 💖')
    await interaction.response.send_message(embed=embed, view=ShopView())

# ==========================================
# คำสั่งซื้อสินค้า (!order)
# ==========================================
@bot.command()
async def order(ctx, *, item_name: str):
    found = False
    price = None
    for cat in categories.values():
        for item in cat["items"]:
            if item["name"].lower() == item_name.lower():
                found = True
                price = item["price"]
                break
        if found:
            break

    if not found:
        await ctx.send(f"❌ ไม่พบสินค้า '{item_name}'")
        return

    await ctx.send(f"✅ สั่งซื้อ **{item_name}** ราคา {price} เหรียญ เรียบร้อย! รอแอดมินติดต่อ")

    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🛍️ สั่งซื้อสินค้า",
            description=f"**ผู้สั่ง:** {ctx.author.mention}\n**สินค้า:** {item_name}\n**ราคา:** {price} เหรียญ",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"ID: {ctx.author.id}")
        await channel.send(embed=embed)

# ==========================================
# คำสั่ง Admin: เพิ่มหมวดหมู่ (/add)
# ==========================================
@bot.tree.command(name="add", description="เพิ่มหมวดหมู่สินค้า (Admin เท่านั้น)")
@app_commands.default_permissions(administrator=True)
async def add_category(interaction: discord.Interaction, category_name: str):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)
        return
    if interaction.guild.id != ALLOWED_GUILD_ID:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะเซิร์ฟเวอร์นี้", ephemeral=True)
        return
    if category_name in categories:
        await interaction.response.send_message(f"⚠️ หมวดหมู่ '{category_name}' มีอยู่แล้ว", ephemeral=True)
        return
    categories[category_name] = {"items": []}
    await interaction.response.send_message(f"✅ เพิ่มหมวดหมู่ '{category_name}' เรียบร้อย", ephemeral=True)

# ==========================================
# คำสั่ง Admin: เพิ่มสินค้า (/add2)
# ==========================================
async def category_autocomplete(interaction: discord.Interaction, current: str):
    choices = []
    for cat in categories.keys():
        if current.lower() in cat.lower():
            choices.append(app_commands.Choice(name=cat, value=cat))
    return choices[:25]

@bot.tree.command(name="add2", description="เพิ่มสินค้าในหมวดหมู่ (Admin เท่านั้น)")
@app_commands.default_permissions(administrator=True)
@app_commands.autocomplete(category=category_autocomplete)
async def add_item(interaction: discord.Interaction, category: str, item_name: str, price: int):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์", ephemeral=True)
        return
    if interaction.guild.id != ALLOWED_GUILD_ID:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะเซิร์ฟเวอร์นี้", ephemeral=True)
        return
    if category not in categories:
        await interaction.response.send_message(f"❌ ไม่พบหมวดหมู่ '{category}'", ephemeral=True)
        return

    categories[category]["items"].append({"name": item_name, "price": price})
    await interaction.response.send_message(
        f"✅ เพิ่มสินค้า **{item_name}** ราคา {price} เหรียญ ในหมวด **{category}** เรียบร้อย",
        ephemeral=True
    )

# ==========================================
# เหตุการณ์เมื่อบอทพร้อม
# ==========================================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'✅ บอท {bot.user} พร้อมทำงาน!')
    print(f'🔒 เซิร์ฟเวอร์: {ALLOWED_GUILD_ID}')
    print(f'📢 ช่อง Log: {LOG_CHANNEL_ID}')
    print(f'👑 Admin IDs: {ADMIN_IDS}')

# ==========================================
# รันบอท
# ==========================================
bot.run(TOKEN)
