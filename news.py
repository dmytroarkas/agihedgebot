class BaseSpecialist:
    def __init__(self, openai_client=None):
        self.openai_client = openai_client

    async def _analyze_with_ai(self, prompt, news):
        try:
            if not self.openai_client:
                return "Ошибка: OpenAI клиент не инициализирован"
            
            full_prompt = f"{prompt}\n\nНовость для анализа:\n{news}"
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # или gpt-4, если у вас есть доступ
                messages=[
                    {"role": "system", "content": "Ты опытный финансовый аналитик."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Ошибка при анализе: {str(e)}"

class IndicesSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Проанализируй новость ТОЛЬКО с точки зрения влияния на основные фондовые индексы (S&P 500, Dow Jones, Nasdaq, Russell и т.д.).
Если новость не влияет на индексы, верни пустой ответ.
Формат ответа:
✅ Покупать: (только индексные ETF, например SPY, QQQ, DIA, IWM)
❌ Продавать: (только индексные ETF)
🛡 Хеджировать: (только инструменты хеджирования индексов - VIX, обратные ETF)
Используй только тикеры индексных инструментов."""
        return await self._analyze_with_ai(prompt, news)

class CommoditiesSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Проанализируй новость ТОЛЬКО с точки зрения влияния на сырьевые товары (золото, серебро, нефть, газ, металлы и т.д.).
Если новость не влияет на сырьевые товары, верни пустой ответ.
Формат ответа:
✅ Покупать: (только сырьевые товары и их ETF, например GLD, SLV, USO, UNG)
❌ Продавать: (только сырьевые товары и их ETF)
🛡 Хеджировать: (только инструменты хеджирования сырьевых товаров)
Используй только тикеры сырьевых инструментов."""
        return await self._analyze_with_ai(prompt, news)

class ForexSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Проанализируй новость ТОЛЬКО с точки зрения влияния на основные валютные пары (EUR/USD, GBP/USD, USD/JPY, USD/CHF и т.д.).
Если новость не влияет на валютные пары, верни пустой ответ.
Формат ответа:
✅ Покупать: (только валютные пары)
❌ Продавать: (только валютные пары)
🛡 Хеджировать: (только инструменты хеджирования валютных рисков)
Используй только обозначения валютных пар."""
        return await self._analyze_with_ai(prompt, news)

class StocksSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Проанализируй новость ТОЛЬКО с точки зрения влияния на отдельные акции и секторы фондового рынка.
Если новость не влияет на конкретные акции или секторы, верни пустой ответ.
Формат ответа:
✅ Покупать: (только акции конкретных компаний или секторальные ETF, например XLK, XLF)
❌ Продавать: (только акции конкретных компаний или секторальные ETF)
🛡 Хеджировать: (только инструменты хеджирования акций)
Используй только тикеры акций и секторальных ETF."""
        return await self._analyze_with_ai(prompt, news)

class CryptoSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Проанализируй новость ТОЛЬКО с точки зрения влияния на криптовалюты (Bitcoin, Ethereum, альткоины и т.д.).
Если новость не влияет на криптовалюты, верни пустой ответ.
Формат ответа:
✅ Покупать: (только криптовалюты и крипто-ETF, например BTC, ETH, GBTC, ETHE)
❌ Продавать: (только криптовалюты и крипто-ETF)
🛡 Хеджировать: (только инструменты хеджирования криптовалют)
Используй только тикеры криптовалют и связанных инструментов."""
        return await self._analyze_with_ai(prompt, news)

class NewsHandler:
    def __init__(self, openai_client=None):
        self.news_mode_chats = set()
        self.openai_client = openai_client
        self.indices_specialist = IndicesSpecialist(openai_client=openai_client)
        self.commodities_specialist = CommoditiesSpecialist(openai_client=openai_client)
        self.forex_specialist = ForexSpecialist(openai_client=openai_client)
        self.stocks_specialist = StocksSpecialist(openai_client=openai_client)
        self.crypto_specialist = CryptoSpecialist(openai_client=openai_client)

    def _generate_conclusion(self, indices, commodities, forex, stocks, crypto):
        """Генерирует осмысленный вывод на основе рекомендаций всех специалистов"""
        
        # Формируем главную стратегию
        strategy_parts = []
        for analysis in [indices, commodities, forex, stocks, crypto]:
            if "Покупать" in analysis:
                strategy_parts.append(analysis.split("Покупать:")[1].split("\n")[0].strip())
        
        # Собираем риски
        risks = []
        for analysis in [indices, commodities, forex, stocks, crypto]:
            if "Продавать" in analysis:
                risks.append(analysis.split("Продавать:")[1].split("\n")[0].strip())
        
        # Собираем меры хеджирования
        hedging = []
        for analysis in [indices, commodities, forex, stocks, crypto]:
            if "Хеджировать" in analysis:
                hedging.append(analysis.split("Хеджировать:")[1].split("\n")[0].strip())

        conclusion_parts = []
        if strategy_parts:
            conclusion_parts.append(f"Главная стратегия: {', '.join(strategy_parts)}.")
        if risks:
            conclusion_parts.append(f"Риски: {', '.join(risks)}.")
        if hedging:
            conclusion_parts.append(f"Дополнительные меры: {', '.join(hedging)}.")

        conclusion = "📌 Вывод:\n" + "\n".join(conclusion_parts) + "\n\n🚀 Ждем следующую новость!"
        return conclusion

    async def handle_message(self, update, context):
        try:
            chat_id = update.effective_chat.id
            if chat_id not in self.news_mode_chats:
                print(f"Чат {chat_id} не в режиме новостей")  # Отладка
                return
            
            # Получаем текст новости из обычного или пересланного сообщения
            news_text = None
            
            # Проверяем наличие атрибутов
            is_forwarded = hasattr(update.message, 'forward_from') or hasattr(update.message, 'forward_from_chat')
            
            # Отладочная информация
            print(f"Тип сообщения: {'Пересланное' if is_forwarded else 'Обычное'}")
            print(f"Текст: {update.message.text}")
            print(f"Подпись: {update.message.caption}")
            
            if is_forwarded:
                print("Обрабатываем пересланное сообщение")  # Отладка
                if update.message.text:
                    news_text = update.message.text
                    print(f"Получен текст: {news_text}")  # Отладка
                elif update.message.caption:
                    news_text = update.message.caption
                    print(f"Получена подпись: {news_text}")  # Отладка
                elif update.message.photo:
                    news_text = update.message.caption
                    print(f"Получено фото с подписью: {news_text}")  # Отладка
                elif update.message.video:
                    news_text = update.message.caption
                    print(f"Получено видео с подписью: {news_text}")  # Отладка
                elif update.message.document:
                    news_text = update.message.caption
                    print(f"Получен документ с подписью: {news_text}")  # Отладка
            else:
                # Обработка обычного сообщения с медиафайлами
                if update.message.text:
                    news_text = update.message.text
                    print(f"Получено обычное сообщение: {news_text}")  # Отладка
                elif update.message.photo:
                    news_text = update.message.caption
                    print(f"Получено фото с подписью: {news_text}")  # Отладка
                elif update.message.video:
                    news_text = update.message.caption
                    print(f"Получено видео с подписью: {news_text}")  # Отладка
                elif update.message.document:
                    news_text = update.message.caption
                    print(f"Получен документ с подписью: {news_text}")  # Отладка

            # Проверяем, что текст новости не пустой
            if not news_text:
                await update.message.reply_text("Не удалось получить текст новости. Пожалуйста, убедитесь, что сообщение содержит текст или подпись к медиа.")
                return

            # Отправляем сообщение о начале анализа
            status_message = await update.message.reply_text("🔄 Анализируем новость...")

            # Получаем анализ от каждого специалиста
            try:
                indices = await self.indices_specialist.analyze_news(news_text)
                commodities = await self.commodities_specialist.analyze_news(news_text)
                forex = await self.forex_specialist.analyze_news(news_text)
                stocks = await self.stocks_specialist.analyze_news(news_text)
                crypto = await self.crypto_specialist.analyze_news(news_text)
            except Exception as e:
                print(f"Ошибка при анализе: {str(e)}")  # Отладка
                await status_message.edit_text(f"Произошла ошибка при анализе: {str(e)}")
                return

            # Формируем единое сообщение
            report = (
                "📊 Торговые сигналы от наших аналитиков\n\n"
                f"📈 Indices Specialist (Индексы)\n{indices}\n\n"
                f"🛢️ Commodities Specialist (Сырьевые товары)\n{commodities}\n\n"
                f"💱 Forex Specialist (Валютные пары)\n{forex}\n\n"
                f"🏢 Stocks Specialist (Акции)\n{stocks}\n\n"
                f"🪙 Crypto Specialist (Криптовалюты)\n{crypto}\n\n"
                f"{self._generate_conclusion(indices, commodities, forex, stocks, crypto)}"
            )

            await status_message.delete()
            await update.message.reply_text(report)
            
        except Exception as e:
            print(f"Общая ошибка: {str(e)}")  # Отладка
            await update.message.reply_text(f"Произошла ошибка: {str(e)}")

    def start_news_mode(self, chat_id):
        """Включает режим новостей для указанного чата"""
        self.news_mode_chats.add(chat_id)
        print(f"Режим новостей активирован для чата {chat_id}")  # Отладочный вывод
