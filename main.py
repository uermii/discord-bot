import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} 봇이 성공적으로 로그인했습니다!')

@bot.command()
async def 안녕(ctx):
    await ctx.send(f'안녕하세요, {ctx.author.name}님!')

# 맨 처음에 디스코드 개발자 센터에서 복사한 봇 토큰을 따옴표 안에 넣으세요
bot.run(os.environ['BOT_TOKEN'])
