import os
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

bot.run(os.environ['BOT_TOKEN'])