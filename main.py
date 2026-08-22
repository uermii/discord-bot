import os
import json
import asyncio
import random
import time
import io
import discord
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont
import aiohttp

# --- [ ⚙️ 기본 설정 및 인텐트 ] ---
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
    1: "경고 1회",
    2: "경고 2회",
    3: "경고 3회",
    4: "경고 4회"
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
    return int(100 * (level ** 1.5))

user_cooldowns = {}
voice_times = {}

async def add_chat_xp(member: discord.Member, amount: int, channel: discord.TextChannel = None):
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

    if c_xp >= req:
        levels[u_str]["chat_level"] += 1
        save_data(LEVEL_FILE, levels)
        if channel:
            embed = discord.Embed(
                title="💬 CHAT LEVEL UP!",
                description=f"{member.mention}님의 채팅 레벨이 **Lv. {c_lvl + 1}**(으)로 올랐습니다!",
                color=discord.Color.pink()
            )
            await channel.send(embed=embed)
    else:
        save_data(LEVEL_FILE, levels)

async def add_voice_xp(member: discord.Member, amount: int):
    if member.bot:
        return
    levels = load_data(LEVEL_FILE)
    u_str = str(member.id)

    if u_str not in levels:
        levels[u_str] = {
            "chat_xp": 0, "chat_level": 1, "chat_count": 0,
            "voice_xp": 0, "voice_level": 1, "voice_seconds": 0
        }

    levels[u_str]["voice_xp"] += amount
    v_xp = levels[u_str]["voice_xp"]
    v_lvl = levels[u_str]["voice_level"]
    req = get_req_xp(v_lvl)

    if v_xp >= req:
        levels[u_str]["voice_level"] += 1
    save_data(LEVEL_FILE, levels)

# --- [ 이미지 랭크 카드 생성 함수 (깔끔한 연분홍 + 날개 포인트) ] ---

async def make_rank_card(member: discord.Member, user_data: dict) -> io.BytesIO:
    width, height = 800, 350
    card = Image.new("RGBA", (width, height), (255, 240, 243, 255))
    draw = ImageDraw.Draw(card)

    # 1. 메인 테두리
    margin = 15
    draw.rounded_rectangle([margin, margin, width - margin, height - margin], radius=20, fill=(255, 250, 252, 255), outline=(255, 200, 215), width=2)

    # 2. 테두리 상단 날개 포인트
    def draw_wing_decor(x, y, is_left=True):
        direction = 1 if is_left else -1
        wing_color = (255, 180, 200, 220)
        draw.arc([x, y, x + (60 * direction), y + 30], start=180, end=360, fill=wing_color, width=3)
        draw.arc([x, y + 10, x + (45 * direction), y + 35], start=180, end=360, fill=wing_color, width=2)

    draw_wing_decor(25, 20, is_left=True)
    draw_wing_decor(width - 25, 20, is_left=False)

    # 3. 아바타 이미지 불러오기 (버전 호환 안전 처리)
    avatar_url = member.display_avatar.with_size(256).url
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

    avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar_size = 180
    
    try:
        avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
    except AttributeError:
        avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.ANTIALIAS)

    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

    avatar_x, avatar_y = 50, 85
    draw.ellipse([avatar_x - 4, avatar_y - 4, avatar_x + avatar_size + 4, avatar_y + avatar_size + 4], fill=(255, 210, 225))
    card.paste(avatar_img, (avatar_x, avatar_y), mask)

    # 4. 폰트 기본 설정
    font = ImageFont.load_default()

    # 5. 유저네임 박스
    name_text = f"@{member.name}"
    draw.rounded_rectangle([450, 45, 740, 80], radius=15, fill=(255, 225, 235), outline=(255, 195, 210), width=1)
    draw.text((595, 62), name_text, fill=(200, 100, 130), font=font, anchor="mm")

    # 6. 게이지 바
    c_lvl, c_xp = user_data.get("chat_level", 1), user_data.get("chat_xp", 0)
    c_req = get_req_xp(c_lvl)
    v_lvl, v_xp = user_data.get("voice_level", 1), user_data.get("voice_xp", 0)
    v_req = get_req_xp(v_lvl)

    def draw_flat_bar(y, label_text, level, current_xp, req_xp):
        draw.text((270, y + 15), label_text, fill=(210, 110, 135), font=font, anchor="lm")
        draw.text((350, y + 15), f"LV.{level}", fill=(220, 125, 150), font=font, anchor="lm")
        
        bar_x1, bar_y1, bar_x2, bar_y2 = 420, y, 740, y + 30
        draw.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=15, fill=(255, 255, 255), outline=(255, 200, 215), width=1)

        progress = min(1.0, current_xp / req_xp) if req_xp > 0 else 0
        fill_width = int((bar_x2 - bar_x1) * progress)
        if fill_width > 10:
            draw.rounded_rectangle([bar_x1, bar_y1, bar_x1 + fill_width, bar_y2], radius=15, fill=(255, 160, 185))

        xp_text = f"{current_xp} / {req_xp}"
        draw.text(((bar_x1 + bar_x2) // 2, y + 15), xp_text, fill=(120, 90, 100), font=font, anchor="mm")

    draw_flat_bar(130, "CHAT", c_lvl, c_xp, c_req)
    draw_flat_bar(210, "VOICE", v_lvl, v_xp, v_req)

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# --- [ 티켓 전용 UI 버튼 클래스 ] ---

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

# --- [ 이벤트 감지 (채팅 XP / 음성 XP / 환영인사) ] ---

@bot.event
async def on_ready():
    bot.add_view(TicketView1())
    bot.add_view(TicketView2())
    bot.add_view(CloseTicketView())
    print(f'{bot.user} 봇이 성공적으로 로그인했습니다!')

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            pass

    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🎉 신규 멤버 입장!",
            description=f"{member.mention}님, **{member.guild.name}** 서버에 오신 것을 환영합니다!",
            color=discord.Color.pink()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="기본 역할 부여", value=f"**{DEFAULT_ROLE_NAME}** 역할이 자동으로 부여되었습니다.", inline=False)
        embed.set_footer(text=f"현재 서버 인원: {member.guild.member_count}명")
        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    user_id = message.author.id
    current_time = time.time()

    if user_id not in user_cooldowns or current_time - user_cooldowns[user_id] > 60:
        user_cooldowns[user_id] = current_time
        
        levels = load_data(LEVEL_FILE)
        u_str = str(user_id)
        if u_str not in levels:
            levels[u_str] = {
                "chat_xp": 0, "chat_level": 1, "chat_count": 0,
                "voice_xp": 0, "voice_level": 1, "voice_seconds": 0
            }
        
        levels[u_str]["chat_count"] += 1
        save_data(LEVEL_FILE, levels)

        xp_gained = random.randint(15, 25)
        await add_chat_xp(message.author, xp_gained, message.channel)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    user_id = member.id

    if before.channel is None and after.channel is not None:
        voice_times[user_id] = time.time()

    elif before.channel is not None and after.channel is None:
        if user_id in voice_times:
            start_time = voice_times.pop(user_id)
            duration = int(time.time() - start_time)

            if duration >= 60:
                minutes = duration // 60
                xp_gained = minutes * 10

                levels = load_data(LEVEL_FILE)
                u_str = str(user_id)
                if u_str not in levels:
                    levels[u_str] = {
                        "chat_xp": 0, "chat_level": 1, "chat_count": 0,
                        "voice_xp": 0, "voice_level": 1, "voice_seconds": 0
                    }

                levels[u_str]["voice_seconds"] += duration
                save_data(LEVEL_FILE, levels)

                await add_voice_xp(member, xp_gained)

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
    if log_channel:
        embed = discord.Embed(title="🟡 [주의 처리 로그]", color=discord.Color.gold())
        embed.add_field(name="대상자", value=f"{member.mention} ({member.id})", inline=True)
        embed.add_field(name="담당자", value=f"{ctx.author.mention}", inline=True)
        embed.add_field(name="사유", value=reason, inline=False)
        embed.add_field(name="현재 누적", value=f"주의 {c_count}/2회 | 경고 {w_count}회", inline=False)
        await log_channel.send(embed=embed)

    if w_count >= 5:
        await ctx.guild.ban(member, reason=f"경고 5회 누적 차단 (사유: {reason})")
        await ctx.send(f"⛔ {member.mention}님이 **경고 5회 누적**으로 차단되었습니다.")
    else:
        await update_warn_roles(ctx.guild, member, w_count)
        if converted:
            await ctx.send(f"⚠️ {member.mention}님은 **주의 2회 누적**으로 **경고 1회**로 전환되었습니다! (현재 경고: {w_count}회)")
        else:
            await ctx.send(f"🟡 {member.mention}님에게 주의를 부여했습니다. (현재 주의: {c_count}/2회)")

@bot.command()
@commands.has_permissions(kick_members=True)
async def 경고(ctx, member: discord.Member, *, reason: str = "사유 미작성"):
    data = load_data(WARN_FILE)
    user_id = str(member.id)
    if user_id not in data:
        data[user_id] = {"caution": 0, "warn": 0}

    data[user_id]["warn"] += 1
    save_data(WARN_FILE, data)
    w_count = data[user_id]["warn"]

    log_channel = ctx.guild.get_channel(WARN_LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title="🔴 [경고 처리 로그]", color=discord.Color.red())
        embed.add_field(name="대상자", value=f"{member.mention} ({member.id})", inline=True)
        embed.add_field(name="담당자", value=f"{ctx.author.mention}", inline=True)
        embed.add_field(name="사유", value=reason, inline=False)
        embed.add_field(name="현재 누적 경고", value=f"{w_count}회", inline=False)
        await log_channel.send(embed=embed)

    if w_count >= 5:
        await ctx.guild.ban(member, reason=f"경고 5회 누적 차단 (사유: {reason})")
        await ctx.send(f"⛔ {member.mention}님이 **경고 5회 누적**으로 차단되었습니다.")
    else:
        await update_warn_roles(ctx.guild, member, w_count)
        await ctx.send(f"🔴 {member.mention}님에게 경고를 부여했습니다. (현재 경고: {w_count}회)")

@bot.command()
@commands.has_permissions(kick_members=True)
async def 주의차감(ctx, member: discord.Member, amount: int = 1):
    data = load_data(WARN_FILE)
    user_id = str(member.id)
    if user_id not in data or data[user_id]["caution"] <= 0:
        return await ctx.send(f"❌ {member.mention}님은 차감할 주의가 없습니다.")

    data[user_id]["caution"] = max(0, data[user_id]["caution"] - amount)
    save_data(WARN_FILE, data)

    log_channel = ctx.guild.get_channel(DEDUCT_LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title="🟢 [주의 차감 로그]", color=discord.Color.green())
        embed.add_field(name="대상자", value=f"{member.mention}", inline=True)
        embed.add_field(name="담당자", value=f"{ctx.author.mention}", inline=True)
        embed.add_field(name="차감 수량", value=f"{amount}회", inline=False)
        await log_channel.send(embed=embed)

    await ctx.send(f"🟢 {member.mention}님의 주의를 {amount}회 차감했습니다.")

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

    log_channel = ctx.guild.get_channel(DEDUCT_LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title="🟢 [경고 차감 로그]", color=discord.Color.green())
        embed.add_field(name="대상자", value=f"{member.mention}", inline=True)
        embed.add_field(name="담당자", value=f"{ctx.author.mention}", inline=True)
        embed.add_field(name="차감 수량", value=f"{amount}회", inline=False)
        await log_channel.send(embed=embed)

    await ctx.send(f"🟢 {member.mention}님의 경고를 {amount}회 차감했습니다.")

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

# 봇 실행 (환경변수 'BOT_TOKEN' 불러오기)
bot.run(os.environ['BOT_TOKEN'])