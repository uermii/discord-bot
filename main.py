import os
import json
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# ⚙️ 채널 ID 설정값 (본인 서버에 맞게 수정하세요)
WELCOME_CHANNEL_ID = 1535535249986031707  # 환영 인사 채널 ID
WARN_LOG_CHANNEL_ID = 1535332752235302982 # 🔴 경고 로그 채널 ID
CAUTION_LOG_CHANNEL_ID = 1535333221682774016 # 🟡 주의 로그 채널 ID
DEDUCT_LOG_CHANNEL_ID = 1535333356806348920  # 🟢 차감 로그 채널 ID

DEFAULT_ROLE_NAME = "[ 🤍 ] : 미확인"                 # 신규 유저 기본 역할 이름

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

@bot.event
async def on_ready():
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

# --- [2] 주의 부여 ---
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
        
        # 경고 로그 채널로 차단 알림
        warn_channel = ctx.guild.get_channel(WARN_LOG_CHANNEL_ID)
        if warn_channel:
            embed = discord.Embed(title="⛔ 멤버 자동 차단 처리", color=discord.Color.dark_red())
            embed.add_field(name="대상자", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="처리자", value=f"{ctx.author.mention}", inline=True)
            embed.add_field(name="사유", value=f"경고 5회 누적 (최종 사유: {reason})", inline=False)
            await warn_channel.send(embed=embed)
    else:
        await update_warn_roles(ctx.guild, member, w_count)
        
        # 주의 2회 누적으로 경고 전환된 경우 ➔ 경고 로그 채널로 발송
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
        # 일반 주의 부여 ➔ 주의 로그 채널로 발송
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

# --- [3] 경고 부여 ---
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

# --- [4] 주의/경고 차감 ---
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

# --- [5] 조회 ---
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