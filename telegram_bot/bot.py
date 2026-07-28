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

from search_history import (
    get_latest_search,
    get_latest_results,
    get_cheapest_for_search_route,
    get_search_route_price_history,
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
async def help_command(update, context):
    """
    Show available Telegram bot commands.
    """

    message = (
        "✈️ FLIGHT FARE AGENT\n\n"

        "Available commands:\n\n"

        "🔎 /search\n"
        "Run a fresh live flight fare search.\n"
        "This calls the flight search API and evaluates "
        "the latest fares.\n\n"

        "📊 /latest\n"
        "Show the results from your most recent search "
        "without running a new search.\n\n"

        "🏆 /best\n"
        "Show the cheapest fare ever recorded for "
        "your latest searched route, including when "
        "the fare was observed.\n\n"

        "📈 /history\n"
        "Show recent historical fare observations "
        "for your latest searched route.\n\n"

        "ℹ️ /help\n"
        "Show this help message.\n\n"

        "🏠 /start\n"
        "Show the welcome message and available features."
    )

    await update.message.reply_text(
        message
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
        price_comparison = report.get(
            "price_comparison"
        )
        price_movement_text = (
            format_price_movement(
                price_comparison
            )
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
        # PRICE COMPARISON WITH THE RECENT
        # ==========================================
        message += (
                    "\n\n"
                    + format_price_movement(
                        report.get(
                            "price_comparison"
                        )
                    )
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

async def latest_command(update, context):
    """
    Show the results from the most recent completed search.

    This command reads from SQLite only.
    It does not trigger a new flight API search.
    """

    latest_search = get_latest_search()

    # ==========================================
    # NO SEARCH HISTORY
    # ==========================================

    if latest_search is None:

        await update.message.reply_text(
            "📭 No previous searches found.\n\n"
            "Run /search to perform your first flight search."
        )

        return

    # ==========================================
    # GET LATEST RESULTS
    # ==========================================

    latest_results = get_latest_results()

    # ==========================================
    # NO RESULTS
    # ==========================================

    if not latest_results:

        await update.message.reply_text(
            "📭 The latest search did not contain "
            "any saved flight results."
        )

        return

    # ==========================================
    # SEARCH DETAILS
    # ==========================================

    origin = latest_search["origin"]

    destination = latest_search["destination"]

    searched_at = latest_search["searched_at"]

    # ==========================================
    # FIND CHEAPEST RESULT
    # ==========================================

    cheapest = min(
        latest_results,
        key=lambda result: result["price"],
    )

    # ==========================================
    # BUILD MESSAGE
    # ==========================================

    message = (
        "✈️ LAST SEARCH\n\n"

        f"🛫 Route: "
        f"{origin} → {destination}\n"

        f"🕒 Searched at: "
        f"{searched_at}\n\n"

        "💰 CHEAPEST FLIGHT\n\n"

        f"✈️ "
        f"{cheapest['departure_airport']} → "
        f"{cheapest['arrival_airport']}\n"

        f"📅 "
        f"{cheapest['departure_date']} → "
        f"{cheapest['return_date']}\n"

        f"💵 "
        f"₹{cheapest['price']:,}\n\n"

        "📊 SEARCH SUMMARY\n\n"

        f"• API searches: "
        f"{latest_search.get('total_searches', 0)}\n"

        f"• Priced results: "
        f"{latest_search.get('priced_results', 0)}\n"

        f"• Total saved results: "
        f"{len(latest_results)}"
    )

    await update.message.reply_text(
        message
    )

# ==========================================
# BEST result from history
# ==========================================
async def best_command(update, context):
    """
    Show the cheapest flight ever recorded
    for the route used in the latest search.

    This command reads historical data from SQLite.
    It does not trigger a new flight API search.
    """

    # ==========================================
    # GET LATEST SEARCH
    # ==========================================

    latest_search = get_latest_search()

    if latest_search is None:

        await update.message.reply_text(
            "📭 No previous searches found.\n\n"
            "Run /search to perform your first flight search."
        )

        return

    # ==========================================
    # GET ROUTE FROM LATEST SEARCH
    # ==========================================

    origin = latest_search["origin"]

    destination = latest_search["destination"]

    # ==========================================
    # GET HISTORICAL CHEAPEST FARE
    # ==========================================

    best_fare = get_cheapest_for_search_route(
        origin=origin,
        destination=destination,
    )

    # ==========================================
    # NO HISTORICAL DATA
    # ==========================================

    if best_fare is None:

        await update.message.reply_text(
            f"📭 No historical flight data found for "
            f"{origin} → {destination}.\n\n"
            "Run /search to collect flight prices."
        )

        return

    # ==========================================
    # BUILD RESPONSE
    # ==========================================

    message = (
        "🏆 BEST FARE RECORDED\n\n"

        f"✈️ Route: "
        f"{origin} → {destination}\n\n"

        f"✈️ Flight: "
        f"{best_fare['departure_airport']} → "
        f"{best_fare['arrival_airport']}\n"

        f"📅 "
        f"{best_fare['departure_date']} → "
        f"{best_fare['return_date']}\n\n"

        f"💵 Cheapest recorded fare: "
        f"₹{best_fare['price']:,}\n\n"

        f"🕒 Recorded during search: "
        f"{best_fare['searched_at']}"
    )

    await update.message.reply_text(
        message
    )
# ==========================================
#  HISTORY
# ==========================================
async def history_command(update, context):
    """
    Show recent historical fare observations
    for the route used in the latest search.

    This command reads from SQLite only.
    It does not trigger a new flight API search.
    """

    # ==========================================
    # GET LATEST SEARCH
    # ==========================================

    latest_search = get_latest_search()

    if latest_search is None:

        await update.message.reply_text(
            "📭 No previous searches found.\n\n"
            "Run /search to perform your first flight search."
        )

        return

    # ==========================================
    # GET SEARCH ROUTE
    # ==========================================

    origin = latest_search["origin"]

    destination = latest_search["destination"]

    # ==========================================
    # GET HISTORICAL PRICE DATA
    # ==========================================

    history = get_search_route_price_history(
        origin=origin,
        destination=destination,
        limit=10,
    )

    # ==========================================
    # NO HISTORY
    # ==========================================

    if not history:

        await update.message.reply_text(
            f"📭 No historical fare data found "
            f"for {origin} → {destination}."
        )

        return

    # ==========================================
    # BUILD HEADER
    # ==========================================

    message_parts = [

        "📈 FARE HISTORY",

        "",

        f"✈️ Route: "
        f"{origin} → {destination}",

        "",

        "Recent fare observations:",
    ]

    # ==========================================
    # ADD HISTORICAL RESULTS
    # ==========================================

    for index, result in enumerate(
        history,
        start=1,
    ):

        departure_airport = (
            result["departure_airport"]
        )

        arrival_airport = (
            result["arrival_airport"]
        )

        departure_date = (
            result["departure_date"]
        )

        return_date = (
            result["return_date"]
        )

        price = result["price"]

        searched_at = (
            result["searched_at"]
        )

        message_parts.extend(
            [

                "",

                f"{index}. "
                f"₹{price:,}",

                f"   ✈️ "
                f"{departure_airport} → "
                f"{arrival_airport}",

                f"   📅 "
                f"{departure_date} → "
                f"{return_date}",

                f"   🕒 "
                f"{searched_at}",

            ]
        )

    # ==========================================
    # SEND TELEGRAM MESSAGE
    # ==========================================

    message = "\n".join(
        message_parts
    )

    await update.message.reply_text(
        message
    )

def format_price_movement(
    price_comparison,
):
    """
    Format current fare movement compared
    with the immediately previous search.

    The Telegram bot uses Markdown formatting,
    so this function intentionally uses *bold*
    instead of HTML <b> tags.
    """

    # ==========================================
    # NO COMPARISON DATA
    # ==========================================

    if not price_comparison:

        return (
            "📊 *PRICE MOVEMENT*\n\n"
            "ℹ️ No price comparison available."
        )

    # ==========================================
    # NO PREVIOUS SEARCH
    # ==========================================

    if not price_comparison.get(
        "comparison_available",
        False,
    ):

        return (
            "📊 *PRICE MOVEMENT*\n\n"
            "ℹ️ No previous search available.\n\n"
            "Your next search will establish "
            "the comparison baseline."
        )

    # ==========================================
    # EXTRACT VALUES
    # ==========================================

    current_price = (
        price_comparison.get(
            "current_price"
        )
    )

    previous_price = (
        price_comparison.get(
            "previous_price"
        )
    )

    difference = (
        price_comparison.get(
            "price_difference"
        )
    )

    difference_percent = (
        price_comparison.get(
            "price_difference_percent"
        )
    )

    direction = (
        price_comparison.get(
            "price_direction"
        )
    )

    previous_searched_at = (
        price_comparison.get(
            "previous_searched_at"
        )
    )

    # ==========================================
    # SAFETY CHECK
    # ==========================================

    if (
        current_price is None
        or previous_price is None
        or difference is None
        or difference_percent is None
    ):

        return (
            "📊 *PRICE MOVEMENT*\n\n"
            "ℹ️ Unable to determine price movement."
        )

    # ==========================================
    # FORMAT VALUES
    # ==========================================

    current_price_text = (
        f"₹{current_price:,.0f}"
    )

    previous_price_text = (
        f"₹{previous_price:,.0f}"
    )

    difference_text = (
        f"₹{abs(difference):,.0f}"
    )

    percentage_text = (
        f"{abs(difference_percent):.2f}%"
    )

    # ==========================================
    # CHEAPER
    # ==========================================

    if direction == "CHEAPER":

        return (
            "📊 *PRICE MOVEMENT*\n\n"

            "🟢 *Fare is cheaper "
            "than your previous search!*\n\n"

            f"Current cheapest: "
            f"*{current_price_text}*\n"

            f"Previous search: "
            f"*{previous_price_text}*\n\n"

            f"📉 Saved: "
            f"*{difference_text}* "
            f"({percentage_text} cheaper)\n\n"

            f"🕒 Previous search:\n"
            f"{previous_searched_at}"
        )

    # ==========================================
    # MORE EXPENSIVE
    # ==========================================

    if direction == "EXPENSIVE":

        return (
            "📊 *PRICE MOVEMENT*\n\n"

            "🔴 *Fare increased "
            "since your previous search.*\n\n"

            f"Current cheapest: "
            f"*{current_price_text}*\n"

            f"Previous search: "
            f"*{previous_price_text}*\n\n"

            f"📈 Increased by: "
            f"*{difference_text}* "
            f"({percentage_text} higher)\n\n"

            f"🕒 Previous search:\n"
            f"{previous_searched_at}"
        )

    # ==========================================
    # UNCHANGED
    # ==========================================

    if direction == "UNCHANGED":

        return (
            "📊 *PRICE MOVEMENT*\n\n"

            "🟡 *Fare unchanged*\n\n"

            f"Current cheapest: "
            f"*{current_price_text}*\n"

            f"Previous search: "
            f"*{previous_price_text}*\n\n"

            "Change: "
            "*₹0 (0.00%)*\n\n"

            f"🕒 Previous search:\n"
            f"{previous_searched_at}"
        )

    # ==========================================
    # UNKNOWN DIRECTION
    # ==========================================

    return (
        "📊 *PRICE MOVEMENT*\n\n"
        "ℹ️ Unable to determine price movement."
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
    application.add_handler(
        CommandHandler(
            "latest",
            latest_command,
        )
    )
    application.add_handler(
        CommandHandler(
            "best",
            best_command,
        )
    )
    application.add_handler(
        CommandHandler(
            "history",
            history_command,
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