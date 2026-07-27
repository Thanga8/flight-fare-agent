import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from app import run_search

# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)


# ==========================================
# /START COMMAND
# ==========================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "✈️ Welcome to your Personal Flight Fare Assistant!\n\n"
        "Use /help to see available commands."
    )


# ==========================================
# /HELP COMMAND
# ==========================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "✈️ Flight Fare Assistant\n\n"
        "Available commands:\n\n"
        "/start - Start the bot\n"
        "/help - Show available commands\n"
        "/search - Search for current flight fares"
    )

# ==========================================
# /SEARCH COMMAND
# ==========================================

async def search_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Run a fresh flight fare search
    and return the results to Telegram.
    """

    await update.message.reply_text(
        "✈️ Starting flight search...\n\n"
        "Checking available flight combinations. "
        "This may take a little while."
    )

    try:

        report = run_search(
            verbose=False,
        )

        # ==========================================
        # GET REPORT DATA
        # ==========================================

        statistics = report.get(
            "statistics",
            {},
        )

        cheapest = report.get(
            "cheapest",
        )

        results = report.get(
            "results",
            [],
        )

        # ==========================================
        # BUILD TELEGRAM MESSAGE
        # ==========================================

        message = (
            "✈️ *FLIGHT FARE UPDATE*\n\n"
        )

        # ==========================================
        # SEARCH SUMMARY
        # ==========================================

        message += (
            "📊 *Search Summary*\n"
            f"• API searches: "
            f"{statistics.get('total_searches', 0)}\n"
            f"• Priced results: "
            f"{statistics.get('priced_results', 0)}\n\n"
        )

        # ==========================================
        # CHEAPEST FLIGHT
        # ==========================================

        if cheapest:

            message += (
                "💰 *CHEAPEST FLIGHT*\n\n"
                f"✈️ "
                f"{cheapest['departure_airport']} "
                f"→ "
                f"{cheapest['arrival_airport']}\n"
                f"📅 "
                f"{cheapest['departure_date']} "
                f"→ "
                f"{cheapest['return_date']}\n"
                f"💵 "
                f"₹{cheapest['price']:,.0f}\n\n"
            )

        else:

            message += (
                "❌ No priced flights found.\n\n"
            )

        # ==========================================
        # TOP RESULTS
        # ==========================================

        if results:

            message += (
                "🏆 *TOP FLIGHTS*\n\n"
            )

            for index, result in enumerate(
                results[:5],
                start=1,
            ):

                message += (
                    f"*{index}.* "
                    f"₹{result['price']:,.0f} | "
                    f"{result['departure_airport']} "
                    f"→ "
                    f"{result['arrival_airport']}\n"
                    f"📅 "
                    f"{result['departure_date']} "
                    f"→ "
                    f"{result['return_date']}\n"
                    f"⭐ Score: "
                    f"{result.get('final_score', 0):.2f}\n\n"
                )

        # ==========================================
        # SEND REPORT
        # ==========================================

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
        )

    except Exception as error:

        print(
            f"Telegram search error: {error}"
        )

        await update.message.reply_text(
            "❌ Something went wrong while "
            "running the flight search.\n\n"
            f"Error: {error}"
        )
# ==========================================
# MAIN
# ==========================================

def main():

    if not TELEGRAM_BOT_TOKEN:

        raise ValueError(
            "TELEGRAM_BOT_TOKEN is not set "
            "in the .env file."
        )

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )
    application.add_handler(
        CommandHandler(
            "search",
            search_command,
        )
    )
    print(
        "Telegram bot is running..."
    )

    application.run_polling()


# ==========================================
# RUN BOT
# ==========================================

if __name__ == "__main__":
    main()