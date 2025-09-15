import discord
from discord.ext import commands

# 봇 prefix 설정 (예: !명령어)
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# 봇이 준비되었을 때
@bot.event
async def on_ready():
    print(f"✅ 로그인 성공: {bot.user}")

# 간단한 명령어 예제
@bot.command()
async def hello(ctx):
    await ctx.send(f"안녕하세요 {ctx.author.mention}! 👋")

# 메시지를 감지하는 이벤트 예제
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if "안녕" in message.content:
        await message.channel.send("안녕하세요! 😄")
    await bot.process_commands(message)  # 명령어도 동작하도록 필요

# 실행 (봇 토큰 넣기)
bot.run("YOUR_BOT_TOKEN")
