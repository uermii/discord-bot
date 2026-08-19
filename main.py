import os
import json
import asyncio
import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# ⚙️ 채널 및 카테고리 ID 설정값
WELCOME_CHANNEL_ID = 1535535249986031707     # 환영 인사 채널 ID
WARN_LOG_CHANNEL_ID = 1535332752235302982    # 🔴 경고 로그 채널 ID
CAUTION_LOG_CHANNEL_ID = 153533221682774016 # 🟡 주의 로그 채널 ID
DEDUCT_LOG_CHANNEL_ID = 1535333356806348920  # 🟢 차감 로그 채널 ID

# 🎫 티켓 생성용 카테고리 ID
TICKET_CATEGORY_ID_1 = 1535332880627142727  # 1번 티켓: 신고 채널 카테고리 ID
TICKET_CATEGORY_ID_2 = 1535532692571955261  # 2번 티켓: 관리자 신청 카테고리 ID

DEFAULT_ROLE_NAME = "[ 🤍 ] : 미확인"        # 신규 유저 기본 역할 이름

WARN_ROLES = {
    1: "경고 1회",
    2: "경고 2회",
    3: "경고 3회",
    4: "경고 4회"
}

WARN_FILE = "warnings.json"

def load_data():
    if os.path.exists(WARN_FILE):
        with open(WARN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(WARN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def update_warn_roles(guild, member, warn_count):
    for role_name in WARN_ROLES.values():
        role = discord.utils.get(guild.roles, name=role_name)
        if role and role in member.roles:
            await member.remove_roles(role)

    if warn_count in WARN_ROLES:
        target_role = discord.utils.get(guild.roles, name=WARN_ROLES[warn_count])
        if target_role:
            await member.add_roles(target_role)

# --- [ 티켓 전용 UI 버튼 클래스 ] ---

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 티켓 닫기", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("5초 후 이 티켓 채널이 삭제됩니다.")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# 티켓 채널 생성 공통 함수
async def create_ticket_channel(interaction: discord.Interaction, category_id: int, prefix: str):
    guild = interaction.guild
    user = interaction.user
    category = guild.get_channel(category_id)

    channel_name = f"{prefix}-{user.name.lower()}"
    existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
    
    if existing_channel:
        return await interaction.response.send_message(f"❌ 이미 생성된 채널이 있습니다: {existing_channel.mention}", ephemeral=True)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites
    )

    embed = discord.Embed(
        title=f"🎫 {user.name}님의 접수가 완료되었습니다",
        description="상세 내용을 남겨주시면 관리진이 확인 후 답변해 드립니다.\n완료 후 아래 **🔒 티켓 닫기** 버튼을 눌러주세요.",
        color=discord.Color.green()
    )
    await ticket_channel.send(embed=embed, view=CloseTicketView())
    await interaction.response.send_message(f"✅ 채널이 생성되었습니다: {ticket_channel.mention}", ephemeral=True)

# 1번 티켓 전용 버튼 (신고 및 제보)
class TicketView1(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚨 신고 및 제보하기", style=discord.ButtonStyle.danger, custom_id="create_ticket_btn_1")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        await create_ticket_channel(interaction, TICKET_CATEGORY_ID_1, "신고")

# 2번 티켓 전용 버튼 (관리자 신청)
class TicketView2(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 관리자 신청하기", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn_2")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        await create_ticket_channel(interaction, TICKET_CATEGORY_ID_2, "신청")

# --- [ 이벤트 및 기본 설정 ] ---

@bot.event
async def on_ready():
    bot.add_view(TicketView1())
    bot.add_view(TicketView2())
    bot.add_view(CloseTicketView())
    print(f'{bot.user} 봇이 성공적으로 로그인했습니다!')

# --- [1] 환영 인사 ---
@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        await member.add_roles(role)

    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🎉 신규 멤버 입장!",
            description=f"{member.mention}님, **{member.guild.name}** 서버에 오신 것을 환영합니다!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="기본 역할 부여", value=f"**{DEFAULT_ROLE_NAME}** 역할이 자동으로 부여되었습니다.", inline=False)
        embed.set_footer(text=f"현재 서버 인원: {member.guild.member_count}명")
        await channel.send(embed=embed)

# --- [2] 티켓 버튼 설치 명령어 (관리자 전용) ---

@bot.command()
@commands.has_permissions(administrator=True)
async def 티켓1(ctx):
    embed = discord.Embed(
        title="🚨 유저 신고 및 제보 창구",
        description="규정 위반 유저 신고나 제보 사항은 아래 **[🚨 신고 및 제보하기]** 버튼을 눌러주세요.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed, view=TicketView1())

@bot.command()
@commands.has_permissions(administrator=True)
async def 티켓2(ctx):
    embed = discord.Embed(
        title="📝 관리자 지원 창구",
        description="서버 관리자에 지원하시려면 아래 **[📝 관리자 신청하기]** 버튼을 눌러주세요.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=TicketView2())

# --- [3] 주의 부여 ---
@bot.command()
@commands.has_permissions(kick_members=True)
async def 주의(ctx, member: discord.Member, *, reason: str = "사유 미작성"):
    data = load_data()
    user_id = str(member.id)
    if user_id not in data:
        data[user_id] = {"caution": 0, "warn": 0}

    data[user_id]["caution"] += 1
    converted = False

    if data[user_id]["caution"] >= 2:
        data[user_id]["caution"] = 0
        data[user_id]["warn"] += 1
        converted = True

    save_data(data)
    c_count, w_count = data[user_id]["caution"], data[user_id]["warn"]

    if w_count >= 5:
        await ctx.guild.ban(member, reason=f"경고 5회 누적 차단 (사유: {reason})")
        await ctx.send(f"⛔ {member.mention}님이 **경고 5회 누적**으로 서버에서 **차단(Ban)**되었습니다.")
        
        warn_channel = ctx.guild.get_channel(WARN_LOG_CHANNEL_ID)
        if warn_channel:
            embed = discord.Embed(title="⛔ 멤버 자동 차단 처리", color=discord.Color.dark_red())
            embed.add_field(name="대상자", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="처리자", value=f"{ctx.author.mention}", inline=True)
            embed.add_field(name="사유", value=f"경고 5회 누적 (최종 사유: {reason})", inline=False)
            await warn_channel.send(embed=embed)
    else:
        await update_warn_roles(ctx.guild, member, w_count)
        
        if converted:
            await ctx.send(f"⚠️ {member.mention}님은 **주의 2회 누적**으로 **경고 1회**로 자동 전환되었습니다! (현재 경고: {w_count}회)")
            warn_channel = ctx.guild.get_channel(WARN_LOG_CHANNEL_ID)
            if warn_channel:
                embed = discord.Embed(title="🚨 주의 2회 누적 ➔ 경고 전환!", color=discord.Color.red())
                embed.add_field(name="대상자", value=f"{member.mention} ({member.name})", inline=True)
                embed.add_field(name="처리자", value=f"{ctx.author.mention}", inline=True)
                embed.add_field(name="누적 현황", value=f"주의: **0/2회** | 경고: **{w_count}회**", inline=False)
                embed.add_field(name="사유", value=reason, inline=False)
                await warn_channel.send(embed=embed)
        else:
            await ctx.send(f"🟡 {member.mention}님에게 주의를 부여했습니다. (현재 주의: {c_count}/2회)")
            caution_channel = ctx.guild.get_channel(CAUTION_LOG_CHANNEL_ID)
            if caution_channel:
                embed = discord.Embed(title="🟡 멤버 주의 부여", color=discord.Color.gold())
                embed.add_field(name="대상자", value=f"{member.mention} ({member.name})", inline=True)
                embed.add_field(name="처리자", value=f"{ctx.author.mention}", inline=True)
                embed.add_field(name="누적 현황", value=f"주의: **{c_count}/2회** | 경고: **{w_count}회**", inline=False)
                embed.add_field(name="사유", value=reason, inline=False)
                await caution_channel.send(embed=embed)

# --- [4] 경고 부여 ---
@bot.command()
@commands.has_permissions(kick_members=True)
async def 경고(ctx, member: discord.Member, *, reason: str = "사유 미작성"):
    data = load_data()
    user_id = str(member.id)
    if user_id not in data:
        data[user_id] = {"caution": 0, "warn": 0}

    data[user_id]["warn"] += 1
    save_data(data)
    c_count, w_count = data[user_id]["caution"], data[user_id]["warn"]

    warn_channel = ctx.guild.get_channel(WARN_LOG_CHANNEL_ID)

    if w_count >= 5:
        await ctx.guild.ban(member, reason=f"경고 5회 누적 차단 (사유: {reason})")
        await ctx.send(f"⛔ {member.mention}님이 **경고 5회 누적**으로 서버에서 **차단(Ban)**되었습니다.")
        if warn_channel:
            embed = discord.Embed(title="⛔ 멤버 자동 차단 처리", color=discord.Color.dark_red())
            embed.add_field(name="대상자", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="처리자", value=f"{ctx.author.mention}", inline=True)
            embed.add_field(name="사유", value=f"경고 5회 누적 (최종 사유: {reason})", inline=False)
            await warn_channel.send(embed=embed)
    else:
        await update_warn_roles(ctx.guild, member, w_count)
        await ctx.send(f"🔴 {member.mention}님에게 경고를 부여했습니다. (현재 경고: {w_count}회)")
        if warn_channel:
            embed = discord.Embed(title="🔴 멤버 경고 부여", color=discord.Color.red())
            embed.add_field(name="대상자", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="처리자", value=f"{ctx.author.mention}", inline=True)
            embed.add_field(name="누적 현황", value=f"주의: **{c_count}/2회** | 경고: **{w_count}회**", inline=False)
            embed.add_field(name="사유", value=reason, inline=False)
            await warn_channel.send(embed=embed)

# --- [5] 주의/경고 차감 ---
@bot.command()
@commands.has_permissions(kick_members=True)
async def 주의차감(ctx, member: discord.Member, amount: int = 1):
    data = load_data()
    user_id = str(member.id)
    if user_id not in data or data[user_id]["caution"] <= 0:
        return await ctx.send(f"❌ {member.mention}님은 차감할 주의가 없습니다.")

    data[user_id]["caution"] = max(0, data[user_id]["caution"] - amount)
    save_data(data)
    c_count, w_count = data[user_id]["caution"], data[user_id]["warn"]

    await ctx.send(f"🟢 {member.mention}님의 주의를 {amount}회 차감했습니다. (현재 주의: {c_count}/2회)")

    deduct_channel = ctx.guild.get_channel(DEDUCT_LOG_CHANNEL_ID)
    if deduct_channel:
        embed = discord.Embed(title="🟢 멤버 주의 차감", color=discord.Color.blue())
        embed.add_field(name="대상자", value=f"{member.mention} ({member.name})", inline=True)
        embed.add_field(name="처리자", value=f"{ctx.author.mention}", inline=True)
        embed.add_field(name="차감 구분", value="주의 차감", inline=True)
        embed.add_field(name="누적 현황", value=f"주의: **{c_count}/2회** | 경고: **{w_count}회**", inline=False)
        await deduct_channel.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def 경고차감(ctx, member: discord.Member, amount: int = 1):
    data = load_data()
    user_id = str(member.id)
    if user_id not in data or data[user_id]["warn"] <= 0:
        return await ctx.send(f"❌ {member.mention}님은 차감할 경고가 없습니다.")

    data[user_id]["warn"] = max(0, data[user_id]["warn"] - amount)
    save_data(data)
    c_count, w_count = data[user_id]["caution"], data[user_id]["warn"]

    await update_warn_roles(ctx.guild, member, w_count)
    await ctx.send(f"🟢 {member.mention}님의 경고를 {amount}회 차감했습니다. (현재 경고: {w_count}회)")

    deduct_channel = ctx.guild.get_channel(DEDUCT_LOG_CHANNEL_ID)
    if deduct_channel:
        embed = discord.Embed(title="🟢 멤버 경고 차감", color=discord.Color.blue())
        embed.add_field(name="대상자", value=f"{member.mention} ({member.name})", inline=True)
        embed.add_field(name="처리자", value=f"{ctx.author.mention}", inline=True)
        embed.add_field(name="차감 구분", value="경고 차감", inline=True)
        embed.add_field(name="누적 현황", value=f"주의: **{c_count}/2회** | 경고: **{w_count}회**", inline=False)
        await deduct_channel.send(embed=embed)

# --- [6] 조회 ---
@bot.command()
async def 경고확인(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = load_data()
    user_data = data.get(str(member.id), {"caution": 0, "warn": 0})
    
    embed = discord.Embed(title=f"📋 {member.name}님의 처벌 내역", color=discord.Color.blue())
    embed.add_field(name="🟡 주의", value=f"**{user_data['caution']} / 2** 회", inline=True)
    embed.add_field(name="🔴 경고", value=f"**{user_data['warn']} / 5** 회", inline=True)
    await ctx.send(embed=embed)

bot.run(os.environ['BOT_TOKEN'])