import os
import asyncio
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv
from openai import AsyncOpenAI
from anthropic import Anthropic
from personalities import CEO, CMO, CTO, CFO, CISO, CDO, CLO, CRO
from datetime import datetime, timedelta
from collections import defaultdict
from news import NewsHandler
import httpx
import re
import signal

# Загружаем переменные окружения
load_dotenv()

# Получаем токены
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
XAI_API_KEY = os.getenv('XAI_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Глобальные переменные для хранения состояний
chat_states = {}  # формат: {chat_id: {'mode': 'ask'/'chat'/'team', 'timestamp': datetime}}
chat_tasks = {}  # формат: {chat_id: task}
current_dialogs = {}  # формат: {chat_id: role}
dialog_histories = {}  # формат: {chat_id: {role: [{'user': msg, 'assistant': resp}]}}
user_languages = {}  # формат: {chat_id: 'ru'/'en'}
dialog_depths = {}  # формат: {chat_id: depth}
discussion_cycles = {}  # формат: {chat_id: {'messages_count': int, 'roles_count': int}}
discussion_history = []  # формат: [{'role': role, 'response': response}, ...]
team_roles = {}  # формат: {chat_id: [roles]}

# Добавляем переменную для хранения текущей роли
current_role = {}

# Константы
MODE_NORMAL = 'normal'
MODE_ASK = 'ask'
MODE_CHAT = 'chat'
MODE_TEAM = 'team'
MODE_NEWS = 'news'
MODE_TIMEOUT = 5
DEFAULT_HISTORY_DEPTH = 5
MAX_HISTORY_DEPTH = 10

# Константы для callback данных кнопок
CALLBACK_CONTINUE = 'continue_discussion'
CALLBACK_END = 'end_discussion'

# Словарь всех персонажей
PERSONALITIES = {
    'CEO': CEO,
    'CMO': CMO,
    'CTO': CTO,
    'CFO': CFO,
    'CISO': CISO,
    'CDO': CDO,
    'CLO': CLO,
    'CRO': CRO
}

# Настройка температуры для разных ролей
TEMPERATURES = {
    'CEO': 0.7,    # Сбалансированные, взвешенные решения
    'CFO': 0.3,    # Консервативные, точные ответы
    'CTO': 0.5,    # Технически точные, но с элементом инновации
    'CMO': 0.9,    # Самые креативные ответы
    'CISO': 0.3,   # Консервативный подход к безопасности
    'CDO': 0.6,    # Баланс между инновациями и точностью данных
    'CLO': 0.2,    # Максимально консервативный подход
    'CRO': 0.4     # Осторожный подход к рискам
}

# Эмодзи для каждой роли
ROLE_EMOJI = {
    'CEO': '👨‍💼',
    'CMO': '📢',
    'CTO': '👨‍💻',
    'CFO': '💰',
    'CISO': '🛡️',
    'CDO': '📊',
    'CLO': '⚖️',
    'CRO': '🎯'
}

# Словарь с текстами на разных языках
MESSAGES = {
    'en': {
        'welcome': """👋 Welcome to AGI Hedge Fund!

Our team:
👨‍💼 CEO - Chief Executive Officer
📢 CMO - Chief Marketing Officer
👨‍💻 CTO - Chief Technology Officer
💰 CFO - Chief Financial Officer
🛡️ CISO - Chief Information Security Officer
📊 CDO - Chief Data Officer
⚖️ CLO - Chief Legal Officer
🎯 CRO - Chief Risk Officer

Commands:
/chat <topic> - start group discussion
/ask <role> <question> - ask specific manager
/team <roles,comma,separated> <topic> - discussion with selected team
/stop - stop discussion
/language - change language
/history - show dialog history
/clear - clear dialog history
/depth <number> - set history depth (1-50)
/export - export dialog history
/news - switch to news mode

You can also just send a message, and CEO will respond to it!""",
        'lang_changed': "Language changed to English",
        'choose_lang': "Choose your language:",
        'topic_request': "Please specify the topic for discussion!\nExample: /chat investment strategy",
        'discussion_started': "📋 Starting discussion on topic: {}",
        'discussion_already': "Discussion is already in progress! Use /stop to end current discussion.",
        'discussion_stopped': "🛑 Discussion stopped!\nUse /chat to start new discussion.",
        'no_discussion': "No active discussion.\nUse /chat to start new one.",
        'role_question': "Please specify role and question!\nExample: /ask CEO how to increase profit?",
        'unknown_role': "Unknown role! Available roles: {}",
        'team_format': "Please specify roles and topic!\nExample: /team CEO,CTO,CFO discuss new trading strategy",
        'team_started': "📋 Starting discussion on topic: {}\nParticipants:\n{}",
        'unknown_command': """❌ Unknown command: {}

Available commands:
/chat <topic> - start group discussion
/ask <role> <question> - ask specific manager
/team <roles,comma,separated> <topic> - discussion with selected team
/stop - stop discussion
/language - change language
/history - show dialog history
/clear - clear dialog history
/depth <number> - set history depth (1-50)
/export - export dialog history
/start - show welcome message
/news - switch to news mode

You can also just send a message, and CEO will respond to it!""",
        'history_empty': "No dialog history with {}",
        'history_cleared': "Dialog history with {} has been cleared",
        'depth_set': "History depth set to {} messages",
        'depth_invalid': "Please specify a number between 1 and 50",
        'export_empty': "No dialog history to export",
        'current_depth': "Current history depth: {} messages",
        'usage_stats': "Usage Statistics",
        'search_no_keywords': "Please provide keywords to search for.",
        'search_no_results': "No results found for the given keywords.",
        'search_results': "Search Results",
        'filter_no_dates': "Please provide start and end dates in the format YYYY-MM-DD.",
        'filter_invalid_dates': "Invalid date format. Please use YYYY-MM-DD.",
        'filter_no_results': "No results found for the given date range.",
        'filter_results': "Filtered Results",
    },
    'ru': {
        'welcome': """👋 Добро пожаловать в AGI Hedge Fund!

Наша команда:
👨‍💼 CEO - Генеральный директор
📢 CMO - Директор по маркетингу
👨‍💻 CTO - Технический директор
💰 CFO - Финансовый директор
🛡️ CISO - Директор по информационной безопасности
📊 CDO - Директор по данным
⚖️ CLO - Юридический директор
🎯 CRO - Директор по рискам

Команды:
/chat <тема> - начать групповое обсуждение
/ask <роль> <вопрос> - задать вопрос конкретному руководителю
/team <роли,через,запятую> <тема> - обсуждение выбранной группой
/stop - остановить обсуждение
/language - сменить язык
/history - показать историю диалога
/clear - очистить историю диалога
/depth <число> - установить глубину истории (1-50)
/export - экспортировать историю диалогов
/news - переключить режим на новости

Вы также можете просто отправить сообщение, и CEO ответит на него!""",
        'lang_changed': "Язык изменен на русский",
        'choose_lang': "Выберите язык:",
        'topic_request': "Пожалуйста, укажите тему для обсуждения!\nНапример: /chat инвестиционная стратегия",
        'discussion_started': "📋 Начинаем обсуждение темы: {}",
        'discussion_already': "Обсуждение уже идет! Используйте /stop чтобы остановить текущее обсуждение.",
        'discussion_stopped': "🛑 Обсуждение остановлено!\nИспользуйте /chat чтобы начать новое обсуждение.",
        'no_discussion': "Сейчас нет активного обсуждения.\nИспользуйте /chat чтобы начать новое.",
        'role_question': "Пожалуйста, укажите роль и вопрос!\nНапример: /ask CEO как увеличить прибыль?",
        'unknown_role': "Неизвестная роль! Доступные роли: {}",
        'team_format': "Пожалуйста, укажите роли и тему!\nНапример: /team CEO,CTO,CFO обсудить новую торговую стратегию",
        'team_started': "📋 Начинаем обсуждение темы: {}\nУчастники:\n{}",
        'unknown_command': """❌ Неизвестная команда: {}

Доступные команды:
/chat <тема> - начать групповое обсуждение
/ask <роль> <вопрос> - задать вопрос руководителю
/team <роли,через,запятую> <тема> - обсуждение группой
/stop - остановить обсуждение
/language - сменить язык
/history - показать историю диалога
/clear - очистить историю диалога
/depth <число> - установить глубину истории (1-50)
/export - экспортировать историю диалогов
/start - показать приветствие
/news - переключить режим на новости

Вы также можете просто отправить сообщение, и CEO ответит на него!""",
        'history_empty': "Нет истории диалога с {}",
        'history_cleared': "История диалога с {} очищена",
        'depth_set': "Глубина истории установлена на {} сообщений",
        'depth_invalid': "Укажите число от 1 до 50",
        'export_empty': "Нет истории диалогов для экспорта",
        'current_depth': "Текущая глубина истории: {} сообщений",
        'usage_stats': "Статистика использования",
        'search_no_keywords': "Пожалуйста, укажите ключевые слова для поиска.",
        'search_no_results': "По заданным ключевым словам ничего не найдено.",
        'search_results': "Результаты поиска",
        'filter_no_dates': "Пожалуйста, укажите начальную и конечную даты в формате ГГГГ-ММ-ДД.",
        'filter_invalid_dates': "Неверный формат даты. Пожалуйста, используйте ГГГГ-ММ-ДД.",
        'filter_no_results': "По заданному диапазону дат ничего не найдено.",
        'filter_results': "Отфильтрованные результаты",
    }
}

# Добавим словарь для хранения статистики
usage_stats = {
    'total_messages': 0,
    'role_distribution': defaultdict(int),
    'hour_distribution': defaultdict(int)
}

# Обновление статистики при каждом сообщении
def update_usage_stats(chat_id, role):
    usage_stats['total_messages'] += 1
    usage_stats['role_distribution'][role] += 1
    current_hour = datetime.now().hour
    usage_stats['hour_distribution'][current_hour] += 1

def get_message(chat_id: int, key: str) -> str:
    # Русский язык по умолчанию
    lang = user_languages.get(chat_id, 'ru')
    return MESSAGES[lang][key]

async def get_chatgpt_response(prompt, personality, lang='ru', selected_roles=None, dialog_history=None, chat_id=None):
    try:
        system_prompt = personality['system_prompt']
        if selected_roles:
            team_info = f"\nВ обсуждении участвуют только: {', '.join(selected_roles)}" if lang == 'ru' else f"\nOnly following roles participate in discussion: {', '.join(selected_roles)}"
            system_prompt += team_info

        messages = []
        if dialog_history:
            depth = dialog_depths.get(chat_id, DEFAULT_HISTORY_DEPTH)
            for entry in dialog_history[-depth:]:
                messages.extend([
                    {"role": "user", "content": entry['user']},
                    {"role": "assistant", "content": entry['assistant']}
                ])
        
        if personality['name'] == 'CMO':
            # Используем API xAI для CMO
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {XAI_API_KEY}"
                    },
                    json={
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            *messages,
                            {"role": "user", "content": prompt}
                        ],
                        "model": "grok-2-vision-1212",
                        "stream": False,
                        "temperature": TEMPERATURES.get(personality['name'], 0.9)
                    }
                )
                response_data = response.json()
                print("Response Data:", response_data)  # Подробный отладочный вывод
                content = response_data['choices'][0]['message']['content']
                # Убираем звездочки
                formatted_content = re.sub(r'\*\*', '', content)
                return formatted_content
        elif personality['name'] == 'CFO':
            # Используем API Gemini для CFO
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                    headers={
                        "Content-Type": "application/json"
                    },
                    json={
                        "contents": [{
                            "parts": [
                                {"text": system_prompt},
                                *[{"text": msg['content']} for msg in messages],
                                {"text": prompt}
                            ]
                        }]
                    }
                )
                response_data = response.json()
                print("Response Data:", response_data)  # Подробный отладочный вывод

                if 'error' in response_data:
                    error_message = response_data['error']['message']
                    return f"Ошибка API: {error_message}"

                # Извлечение текста из правильного места в ответе
                content = response_data['candidates'][0]['content']['parts'][0]['text']
                
                # Убираем звездочки
                formatted_content = re.sub(r'\*\*', '', content)
                
                # Убираем двойные пустые строки
                formatted_content = re.sub(r'\n{3,}', '\n\n', formatted_content)
                
                return formatted_content
        elif personality['name'] == 'CTO':
            # Используем Anthropic для CTO
            client = Anthropic(api_key=ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=TEMPERATURES.get(personality['name'], 0.7),
                system=system_prompt,
                messages=[
                    *messages,
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            # Получаем текст из ответа
            if isinstance(message.content, list):
                response = message.content[0].text
            else:
                response = message.content

            # Очищаем ответ
            if isinstance(response, str):
                response = response.replace('[TextBlock(citations=None, text=', '')
                response = response.replace(", type='text')]", '')
                response = response.replace('\\n', '\n')
            
            return response
        else:
            # Для остальных ролей используем OpenAI
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            system_prompt = f"{system_prompt}\nRespond in {'Russian' if lang == 'ru' else 'English'}."
            all_messages = [
                {"role": "system", "content": system_prompt},
                *messages,
                {"role": "user", "content": prompt}
            ]
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=all_messages,
                max_tokens=1000,
                temperature=TEMPERATURES.get(personality['name'], 0.7)
            )
            return response.choices[0].message.content
    except Exception as e:
        print("Exception occurred:", str(e))  # Подробный отладочный вывод
        import traceback
        traceback.print_exc()  # Вывод полного стека ошибки
        return f"Ошибка: {str(e)}" if lang == 'ru' else f"Error: {str(e)}"

# В начале файла, где у вас уже есть инициализация клиентов
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Создаем экземпляр обработчика новостей с передачей клиента
news_handler = NewsHandler(openai_client=client)

async def check_mode_timeout(chat_id: int) -> bool:
    """Проверяет, не истек ли таймаут режима"""
    if chat_id in chat_states:
        if datetime.now() - chat_states[chat_id]['timestamp'] > timedelta(minutes=MODE_TIMEOUT):
            await reset_chat_mode(chat_id)
            return True
    return False

async def reset_chat_mode(chat_id: int):
    """Сбрасывает режим чата"""
    if chat_id in chat_states:
        del chat_states[chat_id]

async def set_chat_mode(chat_id: int, mode: str):
    """Устанавливает режим чата"""
    chat_states[chat_id] = {
        'mode': mode,
        'timestamp': datetime.now()
    }

async def chat_loop(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str, roles=None):
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    global discussion_history, discussion_cycles
    discussion_history = []
    
    if roles is None:
        roles = list(PERSONALITIES.keys())
    
    discussion_cycles[chat_id] = {'messages_count': 0, 'roles_count': len(roles)}
    
    try:
        while chat_id in chat_tasks:
            for role in roles:
                if chat_id not in chat_tasks:
                    return
                
                # Формируем промпт
                if discussion_history:
                    context_prompt = f"Тема: {topic}\n\nПредыдущие ответы:\n" if lang == 'ru' else f"Topic: {topic}\n\nPrevious responses:\n"
                    context_prompt += "\n".join([f"{msg['role']}: {msg['response']}" for msg in discussion_history[-3:]])
                    prompt = context_prompt + ("\n\nТвой ответ с учетом предыдущих сообщений:" if lang == 'ru' else "\n\nYour response considering previous messages:")
                else:
                    prompt = f"Тема для обсуждения: {topic}" if lang == 'ru' else f"Discussion topic: {topic}"
                
                # Получаем ответ от API
                print(f"Requesting response for {role} about {topic}")  # Отладочный вывод
                response = await get_chatgpt_response(prompt, PERSONALITIES[role], lang, roles, dialog_histories.get(chat_id, {}).get(role, []), chat_id)
                print(f"Got response from {role}: {response[:50]}...")  # Отладочный вывод
                
                if chat_id not in chat_tasks:
                    return
                
                # Сохраняем ответ в историю
                discussion_history.append({'role': role, 'response': response})
                
                # Отправляем сообщение
                emoji = ROLE_EMOJI.get(role, '👤')
                message = f"{emoji} {role}:\n{response}"
                print(f"Sending message: {message[:50]}...")  # Отладочный вывод
                
                # Используем правильный объект для отправки сообщения
                if hasattr(update, 'message') and update.message:
                    await update.message.reply_text(message)
                elif hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.message.reply_text(message)
                
                # Увеличиваем счетчик сообщений
                discussion_cycles[chat_id]['messages_count'] += 1
                
                # Проверяем количество циклов
                if discussion_cycles[chat_id]['messages_count'] >= 1 * len(roles):
                    print("Showing continue buttons...")  # Отладочный вывод
                    await show_continue_buttons(update, context)
                    return
                
                await asyncio.sleep(2)
            
            # Обновляем тему для следующего цикла
            if discussion_history:
                topic = f"Продолжи обсуждение, учитывая предыдущие ответы. Развей последнюю мысль: {discussion_history[-1]['response']}" if lang == 'ru' else f"Continue the discussion, considering previous responses. Develop the last thought: {discussion_history[-1]['response']}"
    
    except Exception as e:
        print(f"Error in chat_loop: {str(e)}")  # Отладочный вывод
        if chat_id in chat_tasks:
            del chat_tasks[chat_id]
        error_msg = "Произошла ошибка. Обсуждение остановлено." if lang == 'ru' else "An error occurred. Discussion stopped."
        if hasattr(update, 'message') and update.message:
            await update.message.reply_text(error_msg)
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text(error_msg)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_text = update.message.text
    lang = user_languages.get(chat_id, 'ru')

    # Проверяем таймаут режима
    await check_mode_timeout(chat_id)

    # Проверяем текущий режим
    current_mode = chat_states.get(chat_id, {}).get('mode', MODE_NORMAL)

    # Обработка сообщений в зависимости от режима
    if current_mode == MODE_NEWS:
        await news_handler.handle_message(update, context)
        return
    elif current_mode == MODE_ASK:
        # Разбиваем сообщение на роль и вопрос
        parts = message_text.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text(get_message(chat_id, 'role_question'))
            return
        role, question = parts
        role = role.upper()
        if role not in PERSONALITIES:
            await update.message.reply_text(get_message(chat_id, 'unknown_role').format(', '.join(PERSONALITIES.keys())))
            return
        await process_ask(update, context, role, question)
        await reset_chat_mode(chat_id)
        return
    elif current_mode == MODE_CHAT:
        await process_chat(update, context, message_text)
        await reset_chat_mode(chat_id)
        return
    elif current_mode == MODE_TEAM:
        parts = message_text.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text(get_message(chat_id, 'team_format'))
            return
        roles, topic = parts
        await process_team(update, context, roles, topic)
        await reset_chat_mode(chat_id)
        return

    # Стандартная обработка для обычного режима (если не в специальном режиме)
    if chat_id in chat_tasks:
        return

    print(f"User ID: {chat_id}")  # Выводит ID в консоль

    # Используем сохраненную роль или CEO по умолчанию
    role = current_dialogs.get(chat_id, 'CEO')
    
    # Инициализируем историю диалога для данного чата и роли, если её нет
    if chat_id not in dialog_histories:
        dialog_histories[chat_id] = {}
    if role not in dialog_histories[chat_id]:
        dialog_histories[chat_id][role] = []

    # Получаем историю диалога
    dialog_history = dialog_histories[chat_id][role]
    
    # Получаем ответ с учетом истории
    response = await get_chatgpt_response(
        message_text, 
        PERSONALITIES[role], 
        lang, 
        None, 
        dialog_history,
        chat_id
    )
    
    # Сохраняем сообщение и ответ в историю
    dialog_histories[chat_id][role].append({
        'user': message_text,
        'assistant': response
    })
    
    emoji = ROLE_EMOJI.get(role, '👤')
    await update.message.reply_text(f"{emoji} {role}:\n{response}")

async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Русский 🇷🇺", callback_data='lang_ru'),
            InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите язык / Choose your language:",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('lang_'):
        lang = query.data.split('_')[1]
        user_languages[query.message.chat_id] = lang
        await query.message.reply_text(MESSAGES[lang]['lang_changed'])
        # Обновляем сообщение с кнопками
        await query.message.edit_reply_markup(reply_markup=None)
    elif query.data.startswith('switch_'):
        role = query.data.split('_')[1]
        chat_id = query.message.chat_id
        current_dialogs[chat_id] = role
        emoji = ROLE_EMOJI.get(role, '👤')
        await query.message.reply_text(
            get_message(chat_id, 'speaker_changed').format(emoji, role)
        )
        # Обновляем сообщение с кнопками
        await query.message.edit_reply_markup(reply_markup=None)
    elif query.data == CALLBACK_CONTINUE:
        chat_id = query.message.chat_id
        if chat_id in chat_tasks:
            discussion_cycles[chat_id]['messages_count'] = 0  # Сбрасываем счетчик сообщений
            await query.message.edit_text("Обсуждение продолжается...")
            # Создаем новую задачу для продолжения обсуждения
            if discussion_history:
                last_topic = f"Продолжи обсуждение, учитывая предыдущие ответы. Развей последнюю мысль: {discussion_history[-1]['response']}"
                # Используем сохраненные роли для режима /team
                roles = team_roles.get(chat_id, list(PERSONALITIES.keys()))
                # Создаем фейковый update для chat_loop
                fake_message = query.message
                fake_update = Update(update.update_id, message=fake_message)
                task = asyncio.create_task(chat_loop(fake_update, context, last_topic, roles))
                chat_tasks[chat_id] = task
    elif query.data == CALLBACK_END:
        chat_id = query.message.chat_id
        if chat_id in chat_tasks:
            del chat_tasks[chat_id]
        if chat_id in discussion_cycles:
            del discussion_cycles[chat_id]
        if chat_id in team_roles:
            del team_roles[chat_id]
        await reset_chat_mode(chat_id)
        await query.message.edit_text("Групповое обсуждение завершено.\nНа ваши сообщения продолжит отвечать СЕО.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    # Сбрасываем состояния и задачи
    if chat_id in chat_tasks:
        chat_tasks[chat_id].cancel()
        del chat_tasks[chat_id]
    if chat_id in current_dialogs:
        del current_dialogs[chat_id]
    if chat_id in dialog_histories:
        del dialog_histories[chat_id]
    if chat_id in chat_states:
        del chat_states[chat_id]
    
    # Отправляем приветственное сообщение
    await update.message.reply_text(get_message(chat_id, 'welcome'))

async def process_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str):
    """Обработка группового чата"""
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    if chat_id in chat_tasks:
        await update.message.reply_text(get_message(chat_id, 'discussion_already'))
        return

    print(f"Starting chat discussion about: {topic}")  # Отладочный вывод
    await update.message.reply_text(get_message(chat_id, 'discussion_started').format(topic))
    
    # Создаем и сохраняем задачу
    task = asyncio.create_task(chat_loop(update, context, topic))
    chat_tasks[chat_id] = task
    
    try:
        await task
    except Exception as e:
        print(f"Error in process_chat: {str(e)}")  # Отладочный вывод
        if chat_id in chat_tasks:
            del chat_tasks[chat_id]

async def process_team(update: Update, context: ContextTypes.DEFAULT_TYPE, roles_str: str, topic: str):
    """Обработка команды team"""
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    roles = [role.strip().upper() for role in roles_str.split(',')]
    invalid_roles = [role for role in roles if role not in PERSONALITIES]
    if invalid_roles:
        await update.message.reply_text(get_message(chat_id, 'unknown_role').format(', '.join(PERSONALITIES.keys())))
        return
    
    if chat_id in chat_tasks:
        await update.message.reply_text(get_message(chat_id, 'discussion_already'))
        return
    
    print(f"Starting team discussion about: {topic} with roles: {roles}")  # Отладочный вывод
    role_list = ', '.join([f"{ROLE_EMOJI[role]} {role}" for role in roles])
    await update.message.reply_text(get_message(chat_id, 'team_started').format(topic, role_list))
    
    # Сохраняем роли для продолжения обсуждения
    team_roles[chat_id] = roles
    
    # Создаем и сохраняем задачу
    task = asyncio.create_task(chat_loop(update, context, topic, roles))
    chat_tasks[chat_id] = task
    
    try:
        await task
    except Exception as e:
        print(f"Error in process_team: {str(e)}")  # Отладочный вывод
        if chat_id in chat_tasks:
            del chat_tasks[chat_id]

async def ask_specific(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    await set_chat_mode(chat_id, MODE_ASK)
    prompt = "Введите роль и ваш вопрос в формате:\nCEO как увеличить прибыль?" if lang == 'ru' else \
             "Enter role and your question in format:\nCEO how to increase profit?"
    await update.message.reply_text(prompt)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in chat_tasks:
        chat_tasks[chat_id].cancel()
        del chat_tasks[chat_id]
    if chat_id in current_dialogs:
        del current_dialogs[chat_id]
    # Очищаем историю диалога при остановке
    if chat_id in dialog_histories:
        del dialog_histories[chat_id]
    await update.message.reply_text(get_message(chat_id, 'discussion_stopped'))

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    command = update.message.text
    await update.message.reply_text(get_message(chat_id, 'unknown_command').format(command))

def get_role_keyboard():
    keyboard = []
    row = []
    for i, (role, data) in enumerate(PERSONALITIES.items()):
        emoji = ROLE_EMOJI.get(role, '👤')
        button = InlineKeyboardButton(f"{emoji} {role}", callback_data=f"switch_{role}")
        row.append(button)
        if len(row) == 2 or i == len(PERSONALITIES) - 1:
            keyboard.append(row)
            row = []
    return InlineKeyboardMarkup(keyboard)

async def switch_speaker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Формируем список доступных ролей с эмодзи
    roles_text = "\n".join([f"{ROLE_EMOJI.get(role, '👤')} {role}" for role in PERSONALITIES.keys()])
    
    # Отправляем сообщение с кнопками
    await update.message.reply_text(
        get_message(chat_id, 'available_roles').format(roles_text),
        reply_markup=get_role_keyboard()
    )

async def current_speaker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_role = current_dialogs.get(chat_id, 'CEO')
    emoji = ROLE_EMOJI.get(current_role, '👤')
    await update.message.reply_text(
        get_message(chat_id, 'current_speaker').format(emoji, current_role)
    )

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    role = current_dialogs.get(chat_id, 'CEO')  # Получаем текущую роль
    lang = user_languages.get(chat_id, 'ru')
    
    # Проверяем наличие истории
    if chat_id not in dialog_histories:
        await update.message.reply_text(get_message(chat_id, 'history_empty').format(role))
        return
    
    if role not in dialog_histories[chat_id] or not dialog_histories[chat_id][role]:
        await update.message.reply_text(get_message(chat_id, 'history_empty').format(role))
        return
    
    history = dialog_histories[chat_id][role]
    depth = dialog_depths.get(chat_id, DEFAULT_HISTORY_DEPTH)
    
    # Формируем сообщение с историей
    history_text = f"💬 {role} - {get_message(chat_id, 'current_depth').format(depth)}\n\n"
    for i, entry in enumerate(history[-depth:], 1):
        history_text += f"🗣 User: {entry['user']}\n"
        history_text += f"👤 {role}: {entry['assistant']}\n\n"
    
    await update.message.reply_text(history_text)

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    role = current_dialogs.get(chat_id, 'CEO')
    
    if chat_id in dialog_histories and role in dialog_histories[chat_id]:
        dialog_histories[chat_id][role] = []
    
    await update.message.reply_text(get_message(chat_id, 'history_cleared').format(role))

async def set_depth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(get_message(chat_id, 'depth_invalid'))
        return
    
    depth = int(context.args[0])
    if depth < 1 or depth > MAX_HISTORY_DEPTH:
        await update.message.reply_text(get_message(chat_id, 'depth_invalid'))
        return
    
    dialog_depths[chat_id] = depth
    await update.message.reply_text(get_message(chat_id, 'depth_set').format(depth))

async def export_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    if chat_id not in dialog_histories or not dialog_histories[chat_id]:
        await update.message.reply_text(get_message(chat_id, 'export_empty'))
        return
    
    # Формируем текст для экспорта
    export_text = "=== Dialog History Export ===\n\n"
    for role, history in dialog_histories[chat_id].items():
        if history:
            export_text += f"=== {role} ===\n"
            for entry in history:
                export_text += f"User: {entry['user']}\n"
                export_text += f"{role}: {entry['assistant']}\n\n"
    
    # Создаем временный файл
    with open(f"history_export_{chat_id}.txt", "w", encoding="utf-8") as f:
        f.write(export_text)
    
    # Отправляем файл
    with open(f"history_export_{chat_id}.txt", "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=f"dialog_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
    
    # Удаляем временный файл
    os.remove(f"history_export_{chat_id}.txt")

async def show_usage_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    stats_text = f"📊 {get_message(chat_id, 'usage_stats')}\n"
    stats_text += f"Общее количество сообщений: {usage_stats['total_messages']}\n"
    stats_text += "Распределение по ролям:\n"
    for role, count in usage_stats['role_distribution'].items():
        stats_text += f"{ROLE_EMOJI.get(role, '👤')} {role}: {count}\n"
    stats_text += "Самые активные часы:\n"
    for hour, count in sorted(usage_stats['hour_distribution'].items()):
        stats_text += f"{hour}:00 - {hour}:59: {count}\n"
    
    await update.message.reply_text(stats_text)

async def search_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    if not context.args:
        await update.message.reply_text(get_message(chat_id, 'search_no_keywords'))
        return
    
    keywords = ' '.join(context.args).lower()
    results = []
    
    for role, history in dialog_histories.get(chat_id, {}).items():
        for entry in history:
            if keywords in entry['user'].lower() or keywords in entry['assistant'].lower():
                results.append((role, entry))
    
    if not results:
        await update.message.reply_text(get_message(chat_id, 'search_no_results'))
        return
    
    search_text = f"🔍 {get_message(chat_id, 'search_results')}\n"
    for role, entry in results:
        search_text += f"{ROLE_EMOJI.get(role, '👤')} {role}:\n"
        search_text += f"🗣 User: {entry['user']}\n"
        search_text += f"👤 {role}: {entry['assistant']}\n\n"
    
    await update.message.reply_text(search_text)

async def filter_history_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    if len(context.args) < 2:
        await update.message.reply_text(get_message(chat_id, 'filter_no_dates'))
        return
    
    try:
        start_date = datetime.strptime(context.args[0], '%Y-%m-%d')
        end_date = datetime.strptime(context.args[1], '%Y-%m-%d')
    except ValueError:
        await update.message.reply_text(get_message(chat_id, 'filter_invalid_dates'))
        return
    
    filtered_results = []
    
    for role, history in dialog_histories.get(chat_id, {}).items():
        for entry in history:
            entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
            if start_date <= entry_date <= end_date:
                filtered_results.append((role, entry))
    
    if not filtered_results:
        await update.message.reply_text(get_message(chat_id, 'filter_no_results'))
        return
    
    filter_text = f"📅 {get_message(chat_id, 'filter_results')}\n"
    for role, entry in filtered_results:
        filter_text += f"{ROLE_EMOJI.get(role, '👤')} {role}:\n"
        filter_text += f"🗣 User: {entry['user']}\n"
        filter_text += f"👤 {role}: {entry['assistant']}\n\n"
    
    await update.message.reply_text(filter_text)

# Список ID администраторов
ADMIN_IDS = [123456789, 987654321, 189234871]  # Добавлен ваш ID

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Проверяем, является ли пользователь администратором
    if chat_id not in ADMIN_IDS:
        await update.message.reply_text("У вас нет прав для просмотра этой информации.")
        return
    
    # Формируем текст статистики
    stats_text = f"📊 Статистика использования:\n"
    stats_text += f"Общее количество сообщений: {usage_stats['total_messages']}\n"
    stats_text += "Распределение по ролям:\n"
    for role, count in usage_stats['role_distribution'].items():
        stats_text += f"{ROLE_EMOJI.get(role, '👤')} {role}: {count}\n"
    stats_text += "Самые активные часы:\n"
    for hour, count in sorted(usage_stats['hour_distribution'].items()):
        stats_text += f"{hour}:00 - {hour}:59: {count}\n"
    
    await update.message.reply_text(stats_text)

# Добавьте команду /news
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    # Устанавливаем режим новостей
    chat_states[chat_id] = {'mode': MODE_NEWS, 'timestamp': datetime.now()}
    news_handler.start_news_mode(chat_id)
    print(f"Режим новостей установлен для чата {chat_id}")  # Отладочный вывод
    
    message = "Аналитики на связи. Отправьте новость для получения торговых сигналов." if lang == 'ru' else \
              "Analysts are ready. Send news to receive trading signals."
    await update.message.reply_text(message)

async def exit_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из текущего режима"""
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    current_mode = chat_states.get(chat_id, {}).get('mode', MODE_NORMAL)
    await reset_chat_mode(chat_id)
    
    message = "Режим сброшен" if lang == 'ru' else "Mode reset"
    await update.message.reply_text(message)

async def process_ask(update: Update, context: ContextTypes.DEFAULT_TYPE, role: str, question: str):
    """Обработка запроса к конкретной роли"""
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    if role not in PERSONALITIES:
        await update.message.reply_text(get_message(chat_id, 'unknown_role').format(', '.join(PERSONALITIES.keys())))
        return

    response = await get_chatgpt_response(
        question,
        PERSONALITIES[role],
        lang,
        None,
        dialog_histories.get(chat_id, {}).get(role, []),
        chat_id
    )

    # Сохраняем сообщение и ответ в историю
    if chat_id not in dialog_histories:
        dialog_histories[chat_id] = {}
    if role not in dialog_histories[chat_id]:
        dialog_histories[chat_id][role] = []
    
    dialog_histories[chat_id][role].append({
        'user': question,
        'assistant': response
    })

    # Устанавливаем текущую роль для продолжения диалога
    current_dialogs[chat_id] = role

    emoji = ROLE_EMOJI.get(role, '👤')
    await update.message.reply_text(f"{emoji} {role}:\n{response}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /chat"""
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    await set_chat_mode(chat_id, MODE_CHAT)
    prompt = "Пожалуйста, укажите тему для обсуждения!" if lang == 'ru' else \
             "Please specify the topic for discussion!"
    await update.message.reply_text(prompt)

async def team_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /team"""
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    await set_chat_mode(chat_id, MODE_TEAM)
    prompt = "Пожалуйста, укажите роли и тему!\nНапример: CEO,CTO,CFO обсудить новую торговую стратегию" if lang == 'ru' else \
             "Please specify roles and topic!\nExample: CEO,CTO,CFO discuss new trading strategy"
    await update.message.reply_text(prompt)

async def show_continue_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает кнопки для продолжения или завершения обсуждения"""
    chat_id = update.effective_chat.id
    lang = user_languages.get(chat_id, 'ru')
    
    keyboard = [
        [
            InlineKeyboardButton(
                "Продолжить обсуждение" if lang == 'ru' else "Continue discussion", 
                callback_data=CALLBACK_CONTINUE
            ),
            InlineKeyboardButton(
                "Закончить обсуждение" if lang == 'ru' else "End discussion", 
                callback_data=CALLBACK_END
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = ("Цикл обсуждения завершен. Хотите продолжить?" if lang == 'ru' 
              else "Discussion cycle completed. Would you like to continue?")
    
    await update.message.reply_text(message, reply_markup=reply_markup)

def main():
    stop_event = asyncio.Event()

    def handle_exit(*args):
        stop_event.set()

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    while not stop_event.is_set():
        try:
            application = Application.builder().token(TELEGRAM_TOKEN).build()

            # Основные обработчики
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("chat", chat))
            application.add_handler(CommandHandler("ask", ask_specific))
            application.add_handler(CommandHandler("team", team_chat))
            application.add_handler(CommandHandler("stop", stop))
            application.add_handler(CommandHandler("language", language))
            application.add_handler(CommandHandler("news", news_command))  # Обработчик для /news
            
            # Обработчики для работы с текущим собеседником
            application.add_handler(CommandHandler("switch", switch_speaker))
            application.add_handler(CommandHandler("current", current_speaker))
            
            # Обработчик кнопок
            application.add_handler(CallbackQueryHandler(button))
            
            # Обработчик обычных текстовых сообщений (перед обработчиком неизвестных команд)
            application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO & ~filters.COMMAND, message_handler))
            
            # Добавляем новые обработчики для работы с историей
            application.add_handler(CommandHandler("history", show_history))
            application.add_handler(CommandHandler("clear", clear_history))
            application.add_handler(CommandHandler("depth", set_depth))
            application.add_handler(CommandHandler("export", export_history))
            
            # Добавляем обработчики для новых функций
            application.add_handler(CommandHandler("stats", show_usage_stats))
            application.add_handler(CommandHandler("search", search_history))
            application.add_handler(CommandHandler("filter", filter_history_by_date))
            
            # Добавляем обработчик для администраторской статистики
            application.add_handler(CommandHandler("admin_stats", admin_stats))
            
            # Добавьте обработчик выхода из режима новостей
            application.add_handler(CommandHandler("exit", exit_mode))
            
            # Обработчик неизвестных команд (должен быть последним!)
            application.add_handler(MessageHandler(filters.COMMAND, unknown))

            print("🚀 Бот AGI Hedge Fund запущен...")
            application.run_polling()
        except Exception as e:
            print(f"Произошла ошибка: {e}. Перезапуск бота...")
            import traceback
            traceback.print_exc()
            asyncio.run(asyncio.sleep(5))  # Используем asyncio.run для корректного ожидания

if __name__ == '__main__':
    main()


