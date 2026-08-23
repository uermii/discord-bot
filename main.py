import os
import json
import asyncio
import random
import time
import io
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont
import aiohttp

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ⚙️ 채널 및 카테고리 ID 설정값
WELCOME_CHANNEL_ID = 1535535249986031707     # 환영 인사 채널 ID
WARN_LOG_CHANNEL_ID = 1535332752235302982    # 🔴 경고 로그 채널 ID
CAUTION_LOG_CHANNEL_ID = 153533221682774016 # 🟡 주의 로그 채널 ID
DEDUCT_LOG_CHANNEL_ID = 1535333356806348920  # 🟢 차감 로그 채널 ID

# 🎫 티켓 생성용 카테고리 ID
TICKET_CATEGORY_ID_1 = 1535332463440826478  # 1번 티켓: 신고 채널 카테고리 ID
TICKET_CATEGORY_ID_2 = 1535350122114842727  # 2번 티켓: 관리자 지원 카테고리 ID

DEFAULT_ROLE_NAME = "[ 🤍 ] : 미확인"        # 신규 유저 기본 역할 이름

WARN_ROLES = {
    1: "( ⛔ ) 경고 1회",
    2: "( ⛔ ) 경고 2회",
    3: "( ⛔ ) 경고 3회",
    4: "( ⛔ ) 경고 4회"
}

WARN_FILE = "warnings.json"
LEVEL_FILE = "levels.json"

# --- [ 데이터 저장 및 로드 ] ---

def load_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def update_warn_roles(guild, member, warn_count):
    for role_name in WARN_ROLES.values():
        role = discord.utils.get(guild.roles, name=role_name)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                pass

    if warn_count in WARN_ROLES:
        target_role = discord.utils.get(guild.roles, name=WARN_ROLES[warn_count])
        if target_role:
            try:
                await member.add_roles(target_role)
            except discord.Forbidden:
                pass

# --- [ 레벨링 계산 로직 ] ---

def get_req_xp(level):
    # 레벨업 요구량 공식: 100 + (level - 1) * 100 (Lv.1: 100, Lv.2: 200...)
    return 100 + (level - 1) * 100

async def add_chat_xp(member: discord.Member, amount: int):
    if member.bot:
        return
    levels = load_data(LEVEL_FILE)
    u_str = str(member.id)

    if u_str not in levels:
        levels[u_str] = {
            "chat_xp": 0, "chat_level": 1, "chat_count": 0,
            "voice_xp": 0, "voice_level": 1, "voice_seconds": 0
        }

    levels[u_str]["chat_xp"] += amount
    c_xp = levels[u_str]["chat_xp"]
    c_lvl = levels[u_str]["chat_level"]
    req = get_req_xp(c_lvl)

    while c_xp >= req:
        c_xp -= req
        c_lvl += 1
        req = get_req_xp(c_lvl)

    levels[u_str]["chat_xp"] = c_xp
    levels[u_str]["chat_level"] = c_lvl
    save_data(LEVEL_FILE, levels)

async def add_voice_xp(member: discord.Member, amount: int):
    if member.bot or amount <= 0:
        return
    levels = load_data(LEVEL_FILE)
    u_str = str(member.id)

    if u_str not in levels:
        levels[u_str] = {
            "chat_xp": 0, "chat_level": 1, "chat_count": 0,
            "voice_xp": 0, "voice_level": 1, "voice_seconds": 0
        }

    levels[u_str]["voice_xp"] += amount
    levels[u_str]["voice_seconds"] += 60
    
    v_xp = levels[u_str]["voice_xp"]
    v_lvl = levels[u_str]["voice_level"]
    req = get_req_xp(v_lvl)

    while v_xp >= req:
        v_xp -= req
        v_lvl += 1
        req = get_req_xp(v_lvl)

    levels[u_str]["voice_xp"] = v_xp
    levels[u_str]["voice_level"] = v_lvl
    save_data(LEVEL_FILE, levels)

# 🔄 1분마다 음성 채널 접속자 XP 실시간 지급 루프
@tasks.loop(minutes=1)
async def voice_xp_loop():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot and not member.voice.afk:
                    await add_voice_xp(member, 15)

@voice_xp_loop.before_loop
async def before_voice_xp_loop():
    await bot.wait_until_ready()

# --- [ 이미지 랭크 카드 생성 함수 ] ---

async def make_rank_card(member: discord.Member, user_data: dict) -> io.BytesIO:
    width, height = 800, 350
    card = Image.new("RGBA", (width, height), (255, 235, 240, 255))
    draw = ImageDraw.Draw(card)

    draw.rounded_rectangle([15, 15, width - 15, height - 15], radius=25, fill=(255, 248, 250, 255), outline=(255, 190, 205), width=3)

    avatar_url = member.display_avatar.with_size(256).url
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

    avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar_size = 200
    avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

    avatar_x, avatar_y = 50, 75
    draw.ellipse([avatar_x - 6, avatar_y - 6, avatar_x + avatar_size + 6, avatar_y + avatar_size + 6], fill=(255, 180, 195))
    draw.ellipse([avatar_x - 2, avatar_y - 2, avatar_x + avatar_size + 2, avatar_y + avatar_size + 2], fill=(255, 255, 255))
    card.paste(avatar_img, (avatar_x, avatar_y), mask)

    try:
        font_name = ImageFont.truetype("arial.ttf", 24)
        font_label = ImageFont.truetype("arial.ttf", 20)
        font_lvl = ImageFont.truetype("arial.ttf", 22)
        font_xp = ImageFont.truetype("arial.ttf", 18)
    except:
        font_name = font_label = font_lvl = font_xp = ImageFont.load_default()

    name_text = f"@{member.display_name}"
    draw.rounded_rectangle([480, 35, 740, 75], radius=20, fill=(255, 210, 222), outline=(255, 170, 190), width=2)
    draw.text((610, 55), name_text, fill=(180, 70, 100), font=font_name, anchor="mm")

    c_lvl = user_data.get("chat_level", 1)
    c_xp = user_data.get("chat_xp", 0)
    c_req = get_req_xp(c_lvl)

    v_lvl = user_data.get("voice_level", 1)
    v_xp = user_data.get("voice_xp", 0)
    v_req = get_req_xp(v_lvl)

    def draw_progress_bar(y, label_text, level, current_xp, req_xp):
        draw.text((290, y + 17), label_text, fill=(220, 90, 120), font=font_label, anchor="lm")
        draw.text((370, y + 17), f"LV.{level}", fill=(230, 110, 140), font=font_lvl, anchor="lm")
        
        bar_x1, bar_y1, bar_x2, bar_y2 = 450, y, 740, y + 35
        draw.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=18, fill=(255, 255, 255), outline=(255, 180, 200), width=2)

        progress = min(1.0, current_xp / req_xp) if req_xp > 0 else 0
        fill_width = int((bar_x2 - bar_x1) * progress)
        if fill_width > 10:
            draw.rounded_rectangle([bar_x1, bar_y1, bar_x1 + fill_width, bar_y2], radius=18, fill=(255, 130, 160))

        xp_text = f"{current_xp}/{req_xp}"
        draw.text(((bar_x1 + bar_x2) // 2, y + 17), xp_text, fill=(100, 80, 85), font=font_xp, anchor="mm")

    draw_progress_bar(115, "CHAT", c_lvl, c_xp, c_req)
    draw_progress_bar(205, "VOICE", v_lvl, v_xp, v_req)

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# --- [ 티켓 UI ] ---

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 티켓 닫기", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("5초 후 이 티켓 채널이 삭제됩니다.")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.Forbidden:
            pass

async def create_ticket_channel(interaction: discord.Interaction, category_id: int, prefix: str):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    user = interaction.user
    category = guild.get_channel(category_id)

    if not category or not isinstance(category, discord.CategoryChannel):
        return await interaction.followup.send("❌ 카테고리를 찾을 수 없습니다.", ephemeral=True)

    channel_name = f"{prefix}-{user.name.lower()}"
    existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
    
    if existing_channel:
        return await interaction.followup.send(f"❌ 이미 생성된 채널이 있습니다: {existing_channel.mention}", ephemeral=True)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    try:
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        embed = discord.Embed(
            title=f"🎫 {user.name}님의 접수가 완료되었습니다",
            description="상세 내용을 남겨주시면 관리진이 확인 후 답변해 드립니다.\n완료 후 아래 **🔒 티켓 닫기** 버튼을 눌러주세요.",
            color=discord.Color.green()
        )
        await ticket_channel.send(embed=embed, view=CloseTicketView())
        await interaction.followup.send(f"✅ 채널이 생성되었습니다: {ticket_channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ 오류 발생: {e}", ephemeral=True)

class TicketView1(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚨 신고 및 제보하기", style=discord.ButtonStyle.danger, custom_id="create_ticket_btn_1")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        await create_ticket_channel(interaction, TICKET_CATEGORY_ID_1, "신고")

class TicketView2(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 관리자 신청하기", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn_2")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        await create_ticket_channel(interaction, TICKET_CATEGORY_ID_2, "신청")

# --- [ 이벤트 감지 ] ---

@bot.event
async def on_ready():
    bot.add_view(TicketView1())
    bot.add_view(TicketView2())
    bot.add_view(CloseTicketView())
    if not voice_xp_loop.is_running():
        voice_xp_loop.start()
    print(f'{bot.user} 봇이 성공적으로 로그인했습니다!')

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
        except Exception as e:
            print(f"역할 부여 실패: {e}")

    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            description=(
                f"{member.mention}님, **어서오세요! 멜팅포인트에 오신 것을 환영합니다!**\n\n"
                f"> 이름 / 나이 / 성별 / 경로 순으로 먼저 입력해주세요!\n↪ <#1535535342134890536>\n\n"
                f"> 들어오신 경로를 캡쳐 하신 후 올려주세요!\n↪ <#1535535627074801734>\n\n"
                f"> 하입코드 링크를 통해 추천 후 캡쳐하여 인증해주세요!\n↪ <#1535535716417675304>\n\n"
                f"> 위 사항들을 다 하셨다면 ``@( 🎀 ) 안내팀 𓂃ܤ ``을 불러주세요!\n↪ <#1535536161248772096>\n\n"
                f"앞으로 좋은 인연 오래 만들어갔으면 좋겠습니다! 잘 부탁드려요<a:mpbearbeg:1537755186921996400>"
            ),
            color=0xFFB3D4
        )
        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    levels = load_data(LEVEL_FILE)
    u_str = str(message.author.id)
    
    if u_str not in levels:
        levels[u_str] = {
            "chat_xp": 0, "chat_level": 1, "chat_count": 0,
            "voice_xp": 0, "voice_level": 1, "voice_seconds": 0
        }
    
    levels[u_str]["chat_count"] += 1
    save_data(LEVEL_FILE, levels)

    # 메시지 1회당 5~8 XP 지급
    xp_gained = random.randint(5, 8)
    await add_chat_xp(message.author, xp_gained)

# --- [ 관리자 명령어 및 제재 시스템 ] ---

@bot.command()
@commands.has_permissions(administrator=True)
async def 티켓1(ctx):
    embed = discord.Embed(title="🚨 유저 신고 및 제보 창구", description="규정 위반 유저 신고나 제보 사항은 아래 버튼을 눌러주세요.", color=discord.Color.red())
    await ctx.send(embed=embed, view=TicketView1())

@bot.command()
@commands.has_permissions(administrator=True)
async def 티켓2(ctx):
    embed = discord.Embed(title="📝 관리자 지원 창구", description="서버 관리자에 지원하시려면 아래 버튼을 눌러주세요.", color=discord.Color.blue())
    await ctx.send(embed=embed, view=TicketView2())

@bot.command()
@commands.has_permissions(kick_members=True)
async def 주의(ctx, member: discord.Member, *, reason: str = "사유 미작성"):
    data = load_data(WARN_FILE)
    user_id = str(member.id)
    if user_id not in data:
        data[user_id] = {"caution": 0, "warn": 0}

    data[user_id]["caution"] += 1
    converted = False

    if data[user_id]["caution"] >= 2:
        data[user_id]["caution"] = 0
        data[user_id]["warn"] += 1
        converted = True

    save_data(WARN_FILE, data)
    c_count, w_count = data[user_id]["caution"], data[user_id]["warn"]

    log_channel = ctx.guild.get_channel(CAUTION_LOG_CHANNEL_ID)

    if w_count >= 5:
        await ctx.guild.ban(member, reason=f"경고 5회 누적 차단 (사유: {reason})")
        embed = discord.Embed(
            title="⛔ 유저 차단 (경고 5회 누적)",
            description=f"{member.mention}님이 **경고 5회 누적**으로 서버에서 차단되었습니다.",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="처리 관리자", value=ctx.author.mention, inline=True)
        embed.add_field(name="사유", value=reason, inline=True)
        await ctx.send(embed=embed)
        if log_channel: await log_channel.send(embed=embed)
    else:
        await update_warn_roles(ctx.guild, member, w_count)
        if converted:
            embed = discord.Embed(
                title="⚠️ 주의 누적 ➔ 경고 전환",
                description=f"{member.mention}님은 **주의 2회 누적**으로 **경고 1회**가 부여되었습니다!",
                color=discord.Color.gold()
            )
            embed.add_field(name="현재 상태", value=f"🟡 주의: {c_count}/2회 | 🔴 경고: {w_count}/5회", inline=False)
            embed.add_field(name="처리 관리자", value=ctx.author.mention, inline=True)
            embed.add_field(name="사유", value=reason, inline=True)
            await ctx.send(embed=embed)
            
            warn_log_channel = ctx.guild.get_channel(WARN_LOG_CHANNEL_ID)
            if warn_log_channel: await warn_log_channel.send(embed=embed)
        else:
            embed = discord.Embed(
                title="🟡 주의 부여",
                description=f"{member.mention}님에게 **주의**를 부여했습니다.",
                color=discord.Color.gold()
            )
            embed.add_field(name="현재 상태", value=f"🟡 주의: {c_count}/2회 | 🔴 경고: {w_count}/5회", inline=False)
            embed.add_field(name="처리 관리자", value=ctx.author.mention, inline=True)
            embed.add_field(name="사유", value=reason, inline=True)
            await ctx.send(embed=embed)
            if log_channel: await log_channel.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def 경고(ctx, member: discord.Member, *, reason: str = "사유 미작성"):
    data = load_data(WARN_FILE)
    user_id = str(member.id)
    if user_id not in data:
        data[user_id] = {"caution": 0, "warn": 0}

    data[user_id]["warn"] += 1
    save_data(WARN_FILE, data)
    c_count, w_count = data[user_id]["caution"], data[user_id]["warn"]

    log_channel = ctx.guild.get_channel(WARN_LOG_CHANNEL_ID)

    if w_count >= 5:
        await ctx.guild.ban(member, reason=f"경고 5회 누적 차단 (사유: {reason})")
        embed = discord.Embed(
            title="⛔ 유저 차단 (경고 5회 누적)",
            description=f"{member.mention}님이 **경고 5회 누적**으로 서버에서 차단되었습니다.",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="처리 관리자", value=ctx.author.mention, inline=True)
        embed.add_field(name="사유", value=reason, inline=True)
        await ctx.send(embed=embed)
        if log_channel: await log_channel.send(embed=embed)
    else:
        await update_warn_roles(ctx.guild, member, w_count)
        embed = discord.Embed(
            title="🔴 경고 부여",
            description=f"{member.mention}님에게 **경고**를 부여했습니다.",
            color=discord.Color.red()
        )
        embed.add_field(name="현재 상태", value=f"🟡 주의: {c_count}/2회 | 🔴 경고: {w_count}/5회", inline=False)
        embed.add_field(name="처리 관리자", value=ctx.author.mention, inline=True)
        embed.add_field(name="사유", value=reason, inline=True)
        await ctx.send(embed=embed)
        if log_channel: await log_channel.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def 주의차감(ctx, member: discord.Member, amount: int = 1):
    data = load_data(WARN_FILE)
    user_id = str(member.id)
    if user_id not in data or data[user_id]["caution"] <= 0:
        return await ctx.send(f"❌ {member.mention}님은 차감할 주의가 없습니다.")

    data[user_id]["caution"] = max(0, data[user_id]["caution"] - amount)
    save_data(WARN_FILE, data)
    
    embed = discord.Embed(
        title="🟢 주의 차감",
        description=f"{member.mention}님의 주의를 **{amount}회** 차감했습니다.",
        color=discord.Color.green()
    )
    embed.add_field(name="현재 상태", value=f"🟡 주의: {data[user_id]['caution']}/2회 | 🔴 경고: {data[user_id]['warn']}/5회", inline=False)
    embed.add_field(name="처리 관리자", value=ctx.author.mention, inline=True)
    await ctx.send(embed=embed)

    log_channel = ctx.guild.get_channel(DEDUCT_LOG_CHANNEL_ID)
    if log_channel: await log_channel.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def 경고차감(ctx, member: discord.Member, amount: int = 1):
    data = load_data(WARN_FILE)
    user_id = str(member.id)
    if user_id not in data or data[user_id]["warn"] <= 0:
        return await ctx.send(f"❌ {member.mention}님은 차감할 경고가 없습니다.")

    data[user_id]["warn"] = max(0, data[user_id]["warn"] - amount)
    save_data(WARN_FILE, data)
    await update_warn_roles(ctx.guild, member, data[user_id]["warn"])

    embed = discord.Embed(
        title="🟢 경고 차감",
        description=f"{member.mention}님의 경고를 **{amount}회** 차감했습니다.",
        color=discord.Color.green()
    )
    embed.add_field(name="현재 상태", value=f"🟡 주의: {data[user_id]['caution']}/2회 | 🔴 경고: {data[user_id]['warn']}/5회", inline=False)
    embed.add_field(name="처리 관리자", value=ctx.author.mention, inline=True)
    await ctx.send(embed=embed)

    log_channel = ctx.guild.get_channel(DEDUCT_LOG_CHANNEL_ID)
    if log_channel: await log_channel.send(embed=embed)

@bot.command()
async def 경고확인(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = load_data(WARN_FILE)
    user_data = data.get(str(member.id), {"caution": 0, "warn": 0})
    
    embed = discord.Embed(title=f"📋 {member.name}님의 처벌 내역", color=discord.Color.blue())
    embed.add_field(name="🟡 주의", value=f"**{user_data['caution']} / 2** 회", inline=True)
    embed.add_field(name="🔴 경고", value=f"**{user_data['warn']} / 5** 회", inline=True)
    await ctx.send(embed=embed)

@bot.command(aliases=['역할확인', '랭크', '레벨'])
async def 랭크확인(ctx, member: discord.Member = None):
    member = member or ctx.author
    levels = load_data(LEVEL_FILE)
    u_str = str(member.id)
    
    user_data = levels.get(u_str, {
        "chat_xp": 0, "chat_level": 1, "chat_count": 0,
        "voice_xp": 0, "voice_level": 1, "voice_seconds": 0
    })

    async with ctx.typing():
        image_buffer = await make_rank_card(member, user_data)
        file = discord.File(fp=image_buffer, filename="rank_card.png")
        await ctx.send(file=file)

bot.run(os.environ['BOT_TOKEN'])