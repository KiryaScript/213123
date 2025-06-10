import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
import validators
import requests
from pydub import AudioSegment
import ffmpeg
import wave
import time
from pathlib import Path
import subprocess
from discord import app_commands
import nacl
import json
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen.oggvorbis import OggVorbis
import psutil
import platform
import GPUtil
import sqlite3
import datetime
import random
import logging
import re

STEAM_API_KEY = "1A4AEF96185A69B0831979EB9C6A9452"
STATUS_MAP = {0: "🟥 Офлайн", 1: "🟩 Онлайн", 2: "🟨 Отошел"}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Бот {bot.user} готов к работе!')

@bot.command(name='leave', help='Покинуть голосовой канал')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Покинул голосовой канал")
    else:
        await ctx.send("Бот не находится в голосовом канале!")

UPLOAD_DIRECTORY = "user_audio"

if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

# Функция для запроса данных через Steam API
def get_steam_profile(steam_id):
    url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={STEAM_API_KEY}&steamids={steam_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Проверим успешность запроса (200)
        data = response.json()
        if 'response' in data and 'players' in data['response'] and len(data['response']['players']) > 0:
            return data['response']['players'][0]
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса: {e}")
        return None
    except ValueError as e:
        print(f"Ошибка парсинга JSON: {e}")
        return None

# Функция для получения всех игр и статистики по ним
def get_steam_games(steam_id):
    url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={STEAM_API_KEY}&steamid={steam_id}&format=json&include_appinfo=1&include_played_free_games=1"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if 'response' in data:
            return data['response'].get('games', [])
        return []
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса: {e}")
        return []
    except ValueError as e:
        print(f"Ошибка парсинга JSON: {e}")
        return []

# Функция для получения достижений
def get_steam_achievements(steam_id, app_id):
    url = f"http://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/?key={STEAM_API_KEY}&steamid={steam_id}&appid={app_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if 'playerstats' in data and 'achievements' in data['playerstats']:
            return data['playerstats']['achievements']
        return []
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса достижений: {e}")
        return []
    except ValueError as e:
        print(f"Ошибка парсинга JSON достижений: {e}")
        return []

# Функция для получения инвентаря
def get_steam_inventory(steam_id, app_id=730):  # Для CS:GO (app_id=730)
    url = f"https://steamcommunity.com/profiles/{steam_id}/inventory/json/{app_id}/2"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if 'rgInventory' in data:
            return data['rgInventory']
        return []
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса инвентаря: {e}")
        return []
    except ValueError as e:
        print(f"Ошибка парсинга JSON инвентаря: {e}")
        return []

# Функция для получения данных о банах
def get_steam_bans(steam_id):
    url = f"http://api.steampowered.com/ISteamUser/GetPlayerBans/v1/?key={STEAM_API_KEY}&steamids={steam_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if 'response' in data and len(data['response']['players']) > 0:
            return data['response']['players'][0]
        return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса банов: {e}")
        return None
    except ValueError as e:
        print(f"Ошибка парсинга JSON банов: {e}")
        return None

# Команда для получения информации о профиле
@bot.command(name='steam', help='Получить информацию о профиле Steam по Steam ID')
async def fetch_steam_profile(ctx, steam_id: str):
    profile_data = get_steam_profile(steam_id)
    if not profile_data:
        await ctx.send("Не удалось получить данные с Steam API.")
        return

    # Основная информация
    username = profile_data.get('personaname', 'Неизвестно')
    profile_url = profile_data.get('profileurl', 'Неизвестно')
    avatar = profile_data.get('avatarfull', 'Неизвестно')
    level = profile_data.get('communityvisibilitystate', 'Неизвестно')
    created = profile_data.get('timecreated', 'Неизвестно')
    friends_count = profile_data.get('friend_count', 'Неизвестно')

    # Игры
    games = get_steam_games(steam_id)
    popular_games = sorted(games, key=lambda x: x.get('playtime_forever', 0), reverse=True)[:3]
    total_games = len(games)
    last_played_game = games[0]['name'] if games else "Неизвестно"

    # Инвентарь
    inventory = get_steam_inventory(steam_id)
    inventory_count = len(inventory)
    inventory_items = "\n".join([f"{item.get('market_name', 'Неизвестно')} - {item.get('value', 'Неизвестно')}" for item in inventory[:3]])

    # Бан и ограничения
    bans_data = get_steam_bans(steam_id)
    bans = bans_data.get('VACBanned', False) if bans_data else False
    community_ban = bans_data.get('CommunityBanned', False) if bans_data else False
    trade_ban = bans_data.get('TradeBan', False) if bans_data else False

    # Формируем сообщение
    embed = discord.Embed(title=f"Информация о профиле {username}", description=f"**Уровень:** {level}", color=0x00FF00)
    embed.add_field(name="Имя профиля", value=username, inline=True)
    embed.add_field(name="URL профиля", value=profile_url, inline=True)
    embed.add_field(name="Дата создания аккаунта", value=created, inline=True)
    embed.add_field(name="Количество друзей", value=friends_count, inline=True)
    embed.set_thumbnail(url=avatar)

    embed.add_field(name="Популярные игры (по часам)", value="\n".join([f"{game['name']} - {game['playtime_forever']} минут" for game in popular_games]), inline=False)
    embed.add_field(name="Общее количество игр", value=total_games, inline=True)
    embed.add_field(name="Последняя запущенная игра", value=last_played_game, inline=True)

    embed.add_field(name="Инвентарь", value=f"Количество предметов: {inventory_count}\nПредметы: \n{inventory_items}", inline=False)

    embed.add_field(name="Баны и ограничения", value=f"VAC-бан: {'Да' if bans else 'Нет'}\nCommunity Ban: {'Да' if community_ban else 'Нет'}\nTrade Ban: {'Да' if trade_ban else 'Нет'}", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='up', help='Загрузить аудиофайл')
async def upload(ctx):
    if len(ctx.message.attachments) == 0:
        embed = discord.Embed(title="Ошибка", description="Пожалуйста, прикрепите аудиофайл к сообщению.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    attachment = ctx.message.attachments[0]
    if not attachment.filename.lower().endswith(('.mp3', '.wav', '.ogg')):
        embed = discord.Embed(title="Ошибка", description="Пожалуйста, загрузите аудиофайл в формате MP3, WAV или OGG.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    file_path = os.path.join(UPLOAD_DIRECTORY, attachment.filename)
    await attachment.save(file_path)
    embed = discord.Embed(title="Успех", description=f"Файл {attachment.filename} успешно загружен!", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name='stop')
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("Воспроизведение остановлено")

@bot.command(name='kick', help='Выгнать пользвателя с сервера')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f"{member.mention} был исключен!")

@bot.command(name='ban', help='Забанить пользователя')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send(f"{member.mention} был забанен!")

@bot.command(name='unban', help='Разбанить пользователя')
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, member_name):
    banned_users = await ctx.guild.bans()
    member_name, _, member_discriminator = member_name.partition("#")
    for ban_entry in banned_users:
        user = ban_entry.user
        if user.name == member_name and user.discriminator == member_discriminator:
            await ctx.guild.unban(user)
            await ctx.send(f"{user.mention} был разбанен!")
            return
    await ctx.send(f"Пользователь {member_name}#{member_discriminator} не найден в бане.")

@bot.command(name='roll', help='Случайное число от 1 до 100')
async def roll(ctx):
    await ctx.send(f"Выпало число: {random.randint(1, 100)}")

@bot.command(name='flip', help='Подбрасывание монеты')
async def flip(ctx):
    await ctx.send(f"Выпало: {'Орел' if random.choice([True, False]) else 'Решка'}")

# Команды для получения погоды (используйте API OpenWeatherMap)
WEATHER_API_KEY = '83f08b9bc6627b6c938fb155f130cf3b'

@bot.command(name='weather', help='Получение погоды для заданного города')
async def weather(ctx, *, city: str):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        embed = discord.Embed(title=f"Погода в {data['name']}, {data['sys']['country']}", color=0x00AAFF)
        embed.add_field(name="Температура", value=f"{data['main']['temp']}°C", inline=True)
        embed.add_field(name="Ощущается как", value=f"{data['main']['feels_like']}°C", inline=True)
        embed.add_field(name="Влажность", value=f"{data['main']['humidity']}%", inline=True)
        embed.add_field(name="Ветер", value=f"{data['wind']['speed']} м/с", inline=True)
        embed.add_field(name="Описание", value=data['weather'][0]['description'].capitalize(), inline=False)
        embed.set_thumbnail(url=f"http://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png")
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="Ошибка", description="Не удалось найти город. Попробуйте еще раз.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Обработка ошибок
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Команда не найдена. Используйте !help для списка команд.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Отсутствует обязательный аргумент. Проверьте синтаксис команды.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("У вас недостаточно прав для выполнения этой команды.")
    else:
        print(f'Unhandled error: {error}')
        await ctx.send("Произошла неизвестная ошибка. Пожалуйста, попробуйте позже.")

def get_audio_duration(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    if extension == '.mp3':
        audio = MP3(file_path)
    elif extension == '.wav':
        audio = WAVE(file_path)
    elif extension == '.ogg':
        audio = OggVorbis(file_path)
    else:
        return 0
    return audio.info.length

def format_duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"

@bot.event
async def on_ready():
    print(f'Бот {bot.user} готов к работе!')
    await bot.change_presence(activity=discord.Game(name="!help для списка команд"))

@bot.command(name='join', help='Присоединиться к голосовому каналу')
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Присоединился к каналу {channel}")
    else:
        await ctx.send("Вы должны находиться в голосовом канале!")

@bot.command(name='playup', help='Воспроизвести загруженный аудиофайл')
async def play_local(ctx, *, query=None):
    if not ctx.voice_client:
        embed = discord.Embed(title="Ошибка", description="Бот должен быть в голосовом канале!", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    if not query:
        files = os.listdir(UPLOAD_DIRECTORY)
        if not files:
            embed = discord.Embed(title="Ошибка", description="Нет доступных аудиофайлов. Загрузите файл с помощью команды !up", color=discord.Color.red())
            await ctx.send(embed=embed)
            return
        
        file_list = "\n".join(f"`{i+1}.` {file}" for i, file in enumerate(files))
        embed = discord.Embed(title="Доступные аудиофайлы", description=file_list, color=discord.Color.blue())
        embed.set_footer(text="Используйте !playup <номер> или !playup <название> для воспроизведения.")
        await ctx.send(embed=embed)
        return

    if query.isdigit():
        files = os.listdir(UPLOAD_DIRECTORY)
        index = int(query) - 1
        if 0 <= index < len(files):
            filename = files[index]
        else:
            embed = discord.Embed(title="Ошибка", description="Неверный номер трека.", color=discord.Color.red())
            await ctx.send(embed=embed)
            return
    else:
        filename = next((file for file in os.listdir(UPLOAD_DIRECTORY) 
                         if file.lower().startswith(query.lower())), None)
        
    if filename:
        file_path = os.path.join(UPLOAD_DIRECTORY, filename)
        
        duration = get_audio_duration(file_path)
        
        audio_source = discord.FFmpegPCMAudio(file_path)
        ctx.voice_client.play(audio_source, after=lambda e: print('Воспроизведение завершено', e))
        
        embed = discord.Embed(title="Сейчас играет", description=filename, color=discord.Color.green())
        embed.add_field(name="Длительность", value=format_duration(duration))
        
        
        start_time = asyncio.get_event_loop().time()
        while ctx.voice_client and ctx.voice_client.is_playing():
            current_time = asyncio.get_event_loop().time() - start_time
            if current_time > duration:
                break
            progress = int((current_time / duration) * 20)
            bar = "▓" * progress + "░" * (20 - progress)
            embed.set_field_at(0, name="Прогресс", value=f"{bar} {format_duration(current_time)}/{format_duration(duration)}")
            await asyncio.sleep(5)
    else:
        embed = discord.Embed(title="Ошибка", description=f"Файл '{query}' не найден.", color=discord.Color.red())
        await ctx.send(embed=embed)

@bot.command(name='clear', help='Удалить указанное количество сообщений')
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount <= 0:
        embed = discord.Embed(title="Ошибка", description="Укажите положительное число сообщений для удаления.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    deleted = await ctx.channel.purge(limit=amount + 1)
    
    embed = discord.Embed(title="Очистка сообщений", description=f"Удалено {len(deleted) - 1} сообщений.", color=discord.Color.green())
    confirmation = await ctx.send(embed=embed)
    await asyncio.sleep(5)
    await confirmation.delete()

@clear.error
async def clear_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Пожалуйста, укажите количество сообщений для удаления. Например: !clear 10")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Пожалуйста, укажите корректное число сообщений для удаления.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("У вас нет прав для выполнения этой команды.")
    else:
        await ctx.send(f"Произошла ошибка: {error}")

@bot.command(name='userinfo', help='Показать информацию о пользователе')
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author

    roles = [role.mention for role in member.roles[1:]]
    embed = discord.Embed(title="Информация о пользователе", color=member.color)
    embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name="Имя", value=member.name, inline=True)
    embed.add_field(name="Никнейм", value=member.nick or "Нет", inline=True)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Статус", value=str(member.status).title(), inline=True)
    embed.add_field(name="Присоединился", value=member.joined_at.strftime("%d.%m.%Y"), inline=True)
    embed.add_field(name="Аккаунт создан", value=member.created_at.strftime("%d.%m.%Y"), inline=True)
    embed.add_field(name=f"Роли [{len(roles)}]", value=" ".join(roles) or "Нет", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='serstats', help='Показать статистику сервера')
async def serstats(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"Статистика сервера {guild.name}", color=0x00ff00)
    embed.add_field(name="Участники", value=guild.member_count, inline=True)
    embed.add_field(name="Текстовые каналы", value=len(guild.text_channels), inline=True)
    embed.add_field(name="Голосовые каналы", value=len(guild.voice_channels), inline=True)
    embed.add_field(name="Роли", value=len(guild.roles), inline=True)
    embed.add_field(name="Владелец", value=guild.owner.mention, inline=True)
    embed.add_field(name="Дата создания", value=guild.created_at.strftime("%d.%m.%Y"), inline=True)
    embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

@bot.command(name='ctv', help='Создать временный голосовой канал')
async def ctv(ctx, *, channel_name: str):
    category = discord.utils.get(ctx.guild.categories, name="Временные голосовые каналы")
    if not category:
        category = await ctx.guild.create_category("Временные голосовые каналы")

    channel = await ctx.guild.create_voice_channel(channel_name, category=category)
    await ctx.send(f"Создан временный голосовой канал: {channel.mention}")

    def check(x, y, z):
        return len(channel.members) == 0

    await bot.wait_for('voice_state_update', check=check)
    await channel.delete()
    await ctx.send(f"Временный голосовой канал '{channel_name}' был удален, так как все участники покинули его.")

@bot.command(name='sysinfo', help='Показать информацию о системе')
async def sysinfo(ctx):
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    embed = discord.Embed(title="Информация о системе", color=discord.Color.blue())
    
    embed.add_field(name="Система", value=platform.system(), inline=True)
    embed.add_field(name="Процессор", value=platform.processor(), inline=True)
    embed.add_field(name="Использование ЦП", value=f"{cpu_percent}%", inline=True)
    
    embed.add_field(name="Оперативная память", value=f"Всего: {memory.total / (1024**3):.2f} GB\n"
                                                     f"Использовано: {memory.used / (1024**3):.2f} GB ({memory.percent}%)", inline=False)
    
    embed.add_field(name="Диск", value=f"Всего: {disk.total / (1024**3):.2f} GB\n"
                                       f"Использовано: {disk.used / (1024**3):.2f} GB ({disk.percent}%)", inline=False)
    
    # Добавление информации о температуре (если доступно)
    try:
        temperatures = psutil.sensors_temperatures()
        if 'coretemp' in temperatures:
            cpu_temp = temperatures['coretemp'][0].current
            embed.add_field(name="Температура ЦП", value=f"{cpu_temp}°C", inline=True)
    except:
        pass  # Если информация о температуре недоступна, просто пропускаем

    # Добавление информации о GPU (если доступно)
    try:
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            embed.add_field(name="GPU", value=f"{gpu.name}\n"
                                              f"Использование: {gpu.load*100:.2f}%\n"
                                              f"Память: {gpu.memoryUsed}/{gpu.memoryTotal} MB", inline=False)
    except:
        pass  # Если информация о GPU недоступна, просто пропускаем

    await ctx.send(embed=embed)




TOKEN = ''

@bot.event
async def on_ready():
    print(f'Бот {bot.user} готов к работе!')
    await bot.change_presence(activity=discord.Game(name="!help для списка команд"))

if __name__ == '__main__':
    bot.run(TOKEN)