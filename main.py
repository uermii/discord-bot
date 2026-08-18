import os
import discord
from discord.ext import commands

# 봇 권한(Intents) 설정 - 멤버 입퇴장 감지를 위해 members 속성 필수
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# ⚙️ 설정값 (본인 서버에 맞게 수정하세요)
WELCOME_CHANNEL_ID = 1535535249986031707  # 환영 인사를 보낼 채널 ID (숫자)
DEFAULT_ROLE_NAME = "[ 🤍 ] : 미확인"                 # 입장 시 자동으로 줄 역할 이름

@bot.event
async def on_ready():
    print(f'{bot.user} 봇이 성공적으로 로그인했습니다!')

# 유저가 서버에 들어왔을 때 실행되는 이벤트
@bot.event
async def on_member_join(member):
    # 1. 자동 역할 부여
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        await member.add_roles(role)

    # 2. 환영 메시지 발송 (임베드 형태)
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🎉 신규 멤버 입장!",
            description=f"{member.mention}님, **{member.guild.name}** 서버에 오신 것을 환영합니다!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url) # 유저 프로필 사진
        embed.add_field(name="기본 역할 부여", value=f"**{DEFAULT_ROLE_NAME}** 역할이 자동으로 부여되었습니다.", inline=False)
        embed.set_footer(text=f"현재 서버 인원: {member.guild.members_count}명")
        
        await channel.send(embed=embed)

bot.run(os.environ['BOT_TOKEN'])