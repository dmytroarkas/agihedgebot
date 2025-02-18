class BaseSpecialist:
    def __init__(self, openai_client=None):
        self.openai_client = openai_client

    async def _analyze_with_ai(self, prompt, news):
        try:
            if not self.openai_client:
                return "Error: OpenAI client not initialized"
            
            full_prompt = f"{prompt}\n\nNews for analysis:\n{news}"
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # or gpt-4 if you have access
                messages=[
                    {"role": "system", "content": "You are an experienced financial analyst."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error during analysis: {str(e)}"

class IndicesSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Analyze the news ONLY in terms of its impact on major stock indices (S&P 500, Dow Jones, Nasdaq, Russell, etc.).
If the news does not affect the indices, return an empty response.
Response format:
✅ Buy: (only index ETFs, e.g., SPY, QQQ, DIA, IWM)
❌ Sell: (only index ETFs)
🛡 Hedge: (only index hedging instruments - VIX, inverse ETFs)
Use only index instrument tickers."""
        return await self._analyze_with_ai(prompt, news)

class CommoditiesSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Analyze the news ONLY in terms of its impact on commodities (gold, silver, oil, gas, metals, etc.).
If the news does not affect commodities, return an empty response.
Response format:
✅ Buy: (only commodities and their ETFs, e.g., GLD, SLV, USO, UNG)
❌ Sell: (only commodities and their ETFs)
🛡 Hedge: (only commodity hedging instruments)
Use only commodity instrument tickers."""
        return await self._analyze_with_ai(prompt, news)

class ForexSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Analyze the news ONLY in terms of its impact on major currency pairs (EUR/USD, GBP/USD, USD/JPY, USD/CHF, etc.).
If the news does not affect currency pairs, return an empty response.
Response format:
✅ Buy: (only currency pairs)
❌ Sell: (only currency pairs)
🛡 Hedge: (only currency risk hedging instruments)
Use only currency pair symbols."""
        return await self._analyze_with_ai(prompt, news)

class StocksSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Analyze the news ONLY in terms of its impact on individual stocks and stock market sectors.
If the news does not affect specific stocks or sectors, return an empty response.
Response format:
✅ Buy: (only specific company stocks or sector ETFs, e.g., XLK, XLF)
❌ Sell: (only specific company stocks or sector ETFs)
🛡 Hedge: (only stock hedging instruments)
Use only stock and sector ETF tickers."""
        return await self._analyze_with_ai(prompt, news)

class CryptoSpecialist(BaseSpecialist):
    async def analyze_news(self, news):
        prompt = """Analyze the news ONLY in terms of its impact on cryptocurrencies (Bitcoin, Ethereum, altcoins, etc.).
If the news does not affect cryptocurrencies, return an empty response.
Response format:
✅ Buy: (only cryptocurrencies and crypto ETFs, e.g., BTC, ETH, GBTC, ETHE)
❌ Sell: (only cryptocurrencies and crypto ETFs)
🛡 Hedge: (only cryptocurrency hedging instruments)
Use only cryptocurrency and related instrument tickers."""
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
        """Generates a meaningful conclusion based on recommendations from all specialists"""
        
        # Formulate the main strategy
        strategy_parts = []
        for analysis in [indices, commodities, forex, stocks, crypto]:
            if "Buy" in analysis:
                strategy_parts.append(analysis.split("Buy:")[1].split("\n")[0].strip())
        
        # Collect risks
        risks = []
        for analysis in [indices, commodities, forex, stocks, crypto]:
            if "Sell" in analysis:
                risks.append(analysis.split("Sell:")[1].split("\n")[0].strip())
        
        # Collect hedging measures
        hedging = []
        for analysis in [indices, commodities, forex, stocks, crypto]:
            if "Hedge" in analysis:
                hedging.append(analysis.split("Hedge:")[1].split("\n")[0].strip())

        conclusion_parts = []
        if strategy_parts:
            conclusion_parts.append(f"Main strategy: {', '.join(strategy_parts)}.")
        if risks:
            conclusion_parts.append(f"Risks: {', '.join(risks)}.")
        if hedging:
            conclusion_parts.append(f"Additional measures: {', '.join(hedging)}.")

        conclusion = "📌 Conclusion:\n" + "\n".join(conclusion_parts) + "\n\n🚀 Awaiting the next news!"
        return conclusion

    async def handle_message(self, update, context):
        try:
            chat_id = update.effective_chat.id
            if chat_id not in self.news_mode_chats:
                print(f"Chat {chat_id} is not in news mode")  # Debug
                return
            
            # Get the news text from a regular or forwarded message
            news_text = None
            
            # Check for attributes
            is_forwarded = hasattr(update.message, 'forward_from') or hasattr(update.message, 'forward_from_chat')
            
            # Debug information
            print(f"Message type: {'Forwarded' if is_forwarded else 'Regular'}")
            print(f"Text: {update.message.text}")
            print(f"Caption: {update.message.caption}")
            
            if is_forwarded:
                print("Processing forwarded message")  # Debug
                if update.message.text:
                    news_text = update.message.text
                    print(f"Received text: {news_text}")  # Debug
                elif update.message.caption:
                    news_text = update.message.caption
                    print(f"Received caption: {news_text}")  # Debug
                elif update.message.photo:
                    news_text = update.message.caption
                    print(f"Received photo with caption: {news_text}")  # Debug
                elif update.message.video:
                    news_text = update.message.caption
                    print(f"Received video with caption: {news_text}")  # Debug
                elif update.message.document:
                    news_text = update.message.caption
                    print(f"Received document with caption: {news_text}")  # Debug
            else:
                # Processing regular message with media
                if update.message.text:
                    news_text = update.message.text
                    print(f"Received regular message: {news_text}")  # Debug
                elif update.message.photo:
                    news_text = update.message.caption
                    print(f"Received photo with caption: {news_text}")  # Debug
                elif update.message.video:
                    news_text = update.message.caption
                    print(f"Received video with caption: {news_text}")  # Debug
                elif update.message.document:
                    news_text = update.message.caption
                    print(f"Received document with caption: {news_text}")  # Debug

            # Check that the news text is not empty
            if not news_text:
                await update.message.reply_text("Failed to retrieve news text. Please ensure the message contains text or a media caption.")
                return

            # Send a message about the start of the analysis
            status_message = await update.message.reply_text("🔄 Analyzing the news...")

            # Get analysis from each specialist
            try:
                indices = await self.indices_specialist.analyze_news(news_text)
                commodities = await self.commodities_specialist.analyze_news(news_text)
                forex = await self.forex_specialist.analyze_news(news_text)
                stocks = await self.stocks_specialist.analyze_news(news_text)
                crypto = await self.crypto_specialist.analyze_news(news_text)
            except Exception as e:
                print(f"Error during analysis: {str(e)}")  # Debug
                await status_message.edit_text(f"An error occurred during analysis: {str(e)}")
                return

            # Formulate a unified message
            report = (
                "📊 Trading signals from our analysts\n\n"
                f"📈 Indices Specialist\n{indices}\n\n"
                f"🛢️ Commodities Specialist\n{commodities}\n\n"
                f"💱 Forex Specialist\n{forex}\n\n"
                f"🏢 Stocks Specialist\n{stocks}\n\n"
                f"🪙 Crypto Specialist\n{crypto}\n\n"
                f"{self._generate_conclusion(indices, commodities, forex, stocks, crypto)}"
            )

            await status_message.delete()
            await update.message.reply_text(report)
            
        except Exception as e:
            print(f"General error: {str(e)}")  # Debug
            await update.message.reply_text(f"An error occurred: {str(e)}")

    def start_news_mode(self, chat_id):
        """Enables news mode for the specified chat"""
        self.news_mode_chats.add(chat_id)
        print(f"News mode activated for chat {chat_id}")  # Debug output
