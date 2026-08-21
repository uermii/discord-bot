import os
import json
import asyncio
import random
import time
import io
import discord
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import aiohttp

# --- [ ⚙️ 초기 설정 및 인텐트 ] ---
intents = discord.Intents.default()
intents.message_content = True # 메세지 내용 읽기
intents.members = True          # 서버 멤버 정보 (서버 입장 등)
intents.voice_states = True     # 보이스 채널 상태

bot = commands.Bot(command_prefix='!', intents=intents)

# ⚙️ 채널 및 카테고리 ID 설정값 (본인 서버에 맞게 수정)
WELCOME_CHANNEL_ID = 1111111111111111111     # 환영 인사 채널 ID
WARN_LOG_CHANNEL_ID = 2222222222222222222    # 🔴 경고 로그 채널 ID
CAUTION_LOG_CHANNEL_ID = 3333333333333333333 # 🟡 주의 로그 채널 ID
DEDUCT_LOG_CHANNEL_ID = 4444444444444444444  # 🟢 차감 로그 채널 ID

# 🎫 티켓 생성용 카테고리 ID
TICKET_CATEGORY_ID_1 = 5555555555555555555  # 1번 티켓: 신고 채널 카테고리 ID
TICKET_CATEGORY_ID_2 = 6666666666666666666  # 2번 티켓: 관리자 지원 카테고리 ID

DEFAULT_ROLE_NAME = "[ 🤍 ] : 미확인"        # 신규 유저 기본 역할 이름

# 처벌 단계별 역할 이름
WARN_ROLES = {
    1: "경고 1회",
    2: "경고 2회",
    3: "경고 3회",
    4: "경고 4회"
}

WARN_FILE = "warnings.json"
LEVEL_FILE = "levels.json"

# --- [ 📝 데이터 저장 및 로드 함수 ] ---

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

# 유저 처벌 단계에 따른 역할 업데이트 함수
async def update_warn_roles(guild, member, warn_count):
    # 기존 경고 역할 모두 제거
    for role_name in WARN_ROLES.values():
        role = discord.utils.get(guild.roles, name=role_name)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                print(f"권한 부족: {member.name}의 {role_name} 역할을 제거할 수 없습니다.")

    # 현재 단계 경고 역할 부여
    if warn_count in WARN_ROLES:
        target_role = discord.utils.get(guild.roles, name=WARN_ROLES[warn_count])
        if target_role:
            try:
                await member.add_roles(target_role)
            except discord.Forbidden:
                print(f"권한 부족: {member.name}에게 {WARN_ROLES[warn_count]} 역할을 부여할 수 없습니다.")

# --- [ 🆙 레벨링 계산 및 데이터 처리 시스템 ] ---

# 레벨당 필요한 경험치 계산 (100 -> 282 -> 519 -> 800 ...)
def get_req_xp(level):
    return int(100 * (level ** 1.5))

# 쿨타임 (도배 방지)
user_chat_cooldowns = {}
user_voice_data = {} # 보이스 시작 시간 저장

# 💬 채팅 XP 지급 및 데이터 업데이트
async def add_chat_xp(member: discord.Member, amount: int):
    if member.bot: return
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

    # 레벨업 시 (메세지 미출력)
    if c_xp >= req:
        levels[u_str]["chat_level"] += 1
    
    save_data(LEVEL_FILE, levels)

# 🎙️ 보이스 XP 지급 및 데이터 업데이트
async def add_voice_xp(member: discord.Member, amount: int):
    if member.bot: return
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

    # 레벨업 시 (메세지 미출력)
    if v_xp >= req:
        levels[u_str]["voice_level"] += 1
    
    save_data(LEVEL_FILE, levels)

# --- [ 🎨 엔젤코어 & 디저트 테마 랭크 카드 생성 함수 ] ---

async def make_rank_card(member: discord.Member, user_data: dict) -> io.BytesIO:
    width, height = 900, 480
    
    # 1. 몽환적인 배경 패널 (Soft Pink / Lavender 오로라 감성)
    card = Image.new("RGBA", (width, height), (255, 240, 246, 255))
    draw = ImageDraw.Draw(card)

    # 은은하게 퍼지는 분홍/보라 빛 효과 (Glow)
    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.ellipse([50, -50, 400, 300], fill=(255, 210, 230, 180)) # 핑크 빛
    glow_draw.ellipse([500, 200, 850, 500], fill=(230, 210, 255, 150)) # 보라 빛
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(50))
    card = Image.alpha_composite(card, glow_layer)
    draw = ImageDraw.Draw(card)

    # 둥근 카드 테두리 (연분홍)
    draw.rounded_rectangle([15, 15, width - 15, height - 15], radius=35, fill=None, outline=(255, 182, 203, 200), width=4)
    # 내부 흰색 테두리
    draw.rounded_rectangle([22, 22, width - 22, height - 22], radius=30, fill=None, outline=(255, 255, 255, 255), width=2)

    # 2. 폰트 설정 (이모지 문자는 깨질 수 있으므로 제거하여 렌더링)
    try:
        font_name = ImageFont.truetype("arial.ttf", 32)
        font_label = ImageFont.truetype("arial.ttf", 38)
        font_lvl = ImageFont.truetype("arial.ttf", 34)
        font_xp = ImageFont.truetype("arial.ttf", 22)
    except:
        font_name = font_label = font_lvl = font_xp = ImageFont.load_default()

    # 3. 아바타 불러오기 및 볼터치 적용
    avatar_url = member.display_avatar.with_size(256).url
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

    avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar_size = 220
    avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

    # 💖 볼터치(Blush) 레이어 합성 (가우시안 블러 효과)
    blush_layer = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
    blush_draw = ImageDraw.Draw(blush_layer)
    blush_draw.ellipse([45, 125, 95, 160], fill=(255, 105, 180, 140)) # 왼쪽 볼
    blush_draw.ellipse([125, 125, 175, 160], fill=(255, 105, 180, 140)) # 오른쪽 볼
    blush_layer = blush_layer.filter(ImageFilter.GaussianBlur(12)) # 블러 처리
    avatar_img = Image.alpha_composite(avatar_img, blush_layer)

    # 원형 잘라내기 마스크
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

    avatar_x, avatar_y = 65, 130
    # 프로필 외부 원형 핑크 테두리
    draw.ellipse([avatar_x - 8, avatar_y - 8, avatar_x + avatar_size + 8, avatar_y + avatar_size + 8], fill=(255, 200, 220, 255))
    draw.ellipse([avatar_x - 3, avatar_y - 3, avatar_x + avatar_size + 3, avatar_y + avatar_size + 3], fill=(255, 255, 255, 255))
    card.paste(avatar_img, (avatar_x, avatar_y), mask)

    # 4. 리본/귀여운 포인트 장식 (머리 상단 체리/리본 포인트)
    draw.ellipse([avatar_x + 95, avatar_y - 25, avatar_x + 125, avatar_y + 5], fill=(255, 100, 130, 255)) # 체리 포인트

    # 5. 닉네임 라벨 (우측 상단 리본 스타일 태그)
    name_text = f"@{member.name}"
    # 닉네임 배경 라운드 박스
    draw.rounded_rectangle([580, 45, 840, 95], radius=25, fill=(255, 225, 238, 220), outline=(255, 170, 200, 255), width=2)
    # 닉네임 텍스트
    draw.text((710, 70), name_text, fill=(230, 80, 130), font=font_name, anchor="mm")

    # 6. XP 데이터 수치
    c_lvl = user_data.get("chat_level", 1)
    c_xp = user_data.get("chat_xp", 0)
    c_req = get_req_xp(c_lvl)

    v_lvl = user_data.get("voice_level", 1)
    v_xp = user_data.get("voice_xp", 0)
    v_req = get_req_xp(v_lvl)

    # 7. CHAT & VOICE 유리관 형태의 게이지 바 렌더링 함수
    def draw_status_bar(y_pos, label, level, current_xp, req_xp):
        # 라벨 및 레벨 (예: CHAT Lv.1)
        draw.text((340, y_pos), label, fill=(255, 120, 160), font=font_label, anchor="lm")
        draw.text((500, y_pos), f"Lv.{level}", fill=(255, 140, 175), font=font_lvl, anchor="lm")

        # 투명 유리관 게이지 바 틀 (Glassy Tube Effect)
        bar_x1, bar_y1, bar_x2, bar_y2 = 340, y_pos + 25, 820, y_pos + 65
        # 바 틀 배경 및 테두리 그리기
        draw.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=20, fill=(255, 255, 255, 160), outline=(255, 170, 200, 255), width=3)

        progress = min(1.0, current_xp / req_xp) if req_xp > 0 else 0
        fill_width = int((bar_x2 - bar_x1) * progress)

        # XP 게이지 내부 채우기 (핑크 그라데이션 느을)
        if fill_width > 10:
            draw.rounded_rectangle([bar_x1 + 3, bar_y1 + 3, bar_x1 + fill_width - 3, bar_y2 - 3], radius=17, fill=(255, 165, 195, 220))

        # XP 수치 텍스트 (예: 34 / 100)
        xp_text = f"{current_xp} / {req_xp}"
        draw.text(((bar_x1 + bar_x2) // 2, bar_y1 + 19), xp_text, fill=(200, 70, 110), font=font_xp, anchor="mm")

    # CHAT 및 VOICE 게이지 그리기
    draw_status_bar(150, "CHAT", c_lvl, c_xp, c_req)
    draw_status_bar(280, "VOICE", v_lvl, v_xp, v_req)

    # 8. 이미지 변환 후 바이너리로 반환
    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# --- [ 🎫 티켓 생성 시스템 및 전용 UI ] ---

# 티켓 닫기 버튼 전용 View
class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None) # 서버 재시작 시에도 버튼 유지

    @discord.ui.button(label="🔒 티켓 닫기", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        # 5초 대기 후 채널 삭제
        await interaction.response.send_message("5초 후 이 티켓 채널이 삭제됩니다.")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.Forbidden:
            await interaction.followup.send("권한 부족: 이 채널을 삭제할 권한이 없습니다.")

# 티켓 채널 생성 로직
async def create_ticket_channel(interaction: discord.Interaction, category_id: int, prefix: str):
    await interaction.response.defer(ephemeral=True) # 답변 대기
    guild = interaction.guild
    user = interaction.user
    category = guild.get_channel(category_id)

    # 카테고리 확인
    if not category or not isinstance(category, discord.CategoryChannel):
        return await interaction.followup.send("❌ 카테고리를 찾을 수 없습니다. 관리자에게 문의하세요.", ephemeral=True)

    # 중복 채널 확인 (prefix-유저이름)
    channel_name = f"{prefix}-{user.name.lower()}"
    existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
    
    if existing_channel:
        return await interaction.followup.send(f"❌ 이미 생성된 채널이 있습니다: {existing_channel.mention}", ephemeral=True)

    # 채널 권한 설정 (본인, 관리자만)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False), # 전체 비공개
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True), # 본인 읽기/쓰기
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True) # 봇 읽기/쓰기
    }

    try:
        # 채널 생성
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        # 티켓 환영 Embed 및 닫기 버튼 전송
        embed = discord.Embed(
            title=f"🎫 {user.name}님의 접수가 완료되었습니다",
            description="상세 내용을 남겨주시면 관리진이 확인 후 답변해 드립니다.\n완료 후 아래 **🔒 티켓 닫기** 버튼을 눌러주세요.",
            color=discord.Color.green()
        )
        await ticket_channel.send(embed=embed, view=CloseTicketView())
        await interaction.followup.send(f"✅ 채널이 생성되었습니다: {ticket_channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ 오류 발생: {e}", ephemeral=True)

# 1번 티켓: 신고 전용 View
class TicketView1(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚨 신고 및 제보하기", style=discord.ButtonStyle.danger, custom_id="create_ticket_btn_1")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        await create_ticket_channel(interaction, TICKET_CATEGORY_ID_1, "신고")

# 2번 티켓: 관리자 지원 전용 View
class TicketView2(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 관리자 신청하기", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn_2")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        await create_ticket_channel(interaction, TICKET_CATEGORY_ID_2, "신청")

# --- [ 📡 이벤트 감지 처리 (on_...) ] ---

@bot.event
async def on_ready():
    # 티켓 버튼 View 등록 (서버 재시작 후에도 작동하도록)
    bot.add_view(TicketView1())
    bot.add_view(TicketView2())
    bot.add_view(CloseTicketView())
    
    # 봇 상태 메시지 설정 (온라인, 🔴 경고 관리자 대기 중!)
    await bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.watching, name="경고 관리자 대기 중!"))
    print(f'{bot.user} 봇이 성공적으로 로그인했습니다!')

@bot.event
async def on_member_join(member):
    # 기본 역할 부여
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            print(f"권한 부족: {member.name}에게 미확인 역할을 부여할 수 없습니다.")

    # 환영 인사 채널 전송
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🎉 신규 멤버 입장!",
            description=f"{member.mention}님, **{member.guild.name}** 서버에 오신 것을 환영합니다!",
            color=discord.Color.pink()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="기본 역할 부여", value=f"**{DEFAULT_ROLE_NAME}