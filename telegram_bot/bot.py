import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from app import run_search

from flight_search.evaluation.flight_evaluator import (
    evaluate_flight,
)
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
        print()
        print("=" * 70)
        print("TELEGRAM REPORT DEBUG")
        print("=" * 70)

        print("Report keys:")
        print(report.keys())

        print()
        print("First result:")
        print(report.get("results", [None])[0])

        print()
        print("Cheapest:")
        print(report.get("cheapest"))

        print("=" * 70)

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
            "scored_results",
            [],
        )
        
        # ==========================================
        # EVALUATE TOP RESULTS
        # ==========================================

        evaluated_results = []

        for result in results[:5]:
        
            try:
            
                evaluation = evaluate_flight(
                    result,
                )

                evaluated_results.append(
                    evaluation
                )

            except Exception as error:
            
                print(
                    "Evaluation error:",
                    error,
                )
        
        recommendations = []

        for evaluation in evaluated_results:
        
            recommendation = (
                evaluation.get(
                    "recommendation"
                )
            )

            if recommendation:
            
                recommendations.append(
                    recommendation
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
        # BEST OVERALL FLIGHT
        # ==========================================

        if evaluated_results:
        
            best = evaluated_results[0]

            recommendation = best.get(
                "recommendation",
                {},
            )

            display_rating = recommendation.get(
                "display_rating",
                "No Rating",
            )

            assessment_message = recommendation.get(
                "assessment_message",
                "No historical comparison available.",
            )

            confidence = recommendation.get(
                "confidence",
                "NONE",
            )

            booking_recommendation = recommendation.get(
                "recommendation",
                "No recommendation available.",
            )

            message += (
                "🏆 *BEST OVERALL*\n\n"
                f"✈️ "
                f"{best['departure_airport']} "
                f"→ "
                f"{best['arrival_airport']}\n"
                f"📅 "
                f"{best['departure_date']} "
                f"→ "
                f"{best['return_date']}\n"
                f"💰 "
                f"₹{best['price']:,.0f}\n\n"
                f"{display_rating}\n\n"
                f"📉 {assessment_message}\n"
                f"📊 Confidence: {confidence}\n\n"
                f"💡 {booking_recommendation}\n\n"
            )

        else:
        
            message += (
                "❌ No suitable flight results found.\n\n"
            )

        # ==========================================
        # OTHER TOP FLIGHTS
        # ==========================================

        if len(evaluated_results) > 1:
        
            message += (
                "💰 *OTHER TOP OPTIONS*\n\n"
            )

            for index, result in enumerate(
                evaluated_results[1:5],
                start=1,
            ):

                recommendation = result.get(
                    "recommendation",
                    {},
                )

                display_rating = recommendation.get(
                    "display_rating",
                    "No Rating",
                )

                message += (
                    f"*{index}.* "
                    f"₹{result['price']:,.0f}\n"
                    f"✈️ "
                    f"{result['departure_airport']} "
                    f"→ "
                    f"{result['arrival_airport']}\n"
                    f"📅 "
                    f"{result['departure_date']} "
                    f"→ "
                    f"{result['return_date']}\n"
                    f"⭐ Score: "
                    f"{result.get('final_score', 0):.2f}\n"
                    f"{display_rating}\n\n"
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