# app.py

import streamlit as st
from datetime import datetime, timezone
import pytz
from utils import (
    TEAM_NAME_MAP, fetch_odds, fetch_starting_lineups, fetch_player_era_dict,
    fetch_team_records, get_probable_pitchers, compare_and_format_era,
    odds_message, get_wins
)


# Load API keys securely from Streamlit secrets
ODDS_API_KEY = '9891ed9254b6592da0b72b05b1e0dd69'
SPORTSDATA_API_KEY = '5d88de1d87784a8290ce1734864c1a71'

def show_ui():
    st.title("MLB Odds & Probable Pitchers Dashboard")
    st.markdown("Data sourced from The Odds API and SportsDataIO")

    # Run the backfill results updater for yesterday
    try:
        update_game_results(SPORTSDATA_API_KEY)
    except Exception as e:
        st.warning(f"Failed to update yesterday's results: {e}")

    # Fetch data
    try:
        odds_data = fetch_odds(ODDS_API_KEY)
        era_dict = fetch_player_era_dict(SPORTSDATA_API_KEY)
        team_records = fetch_team_records(SPORTSDATA_API_KEY)
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return

    now = datetime.now(timezone.utc)
    local_tz = pytz.timezone('America/New_York')

    future_games = []
    for game in odds_data:
        start_str = game.get('commence_time')
        if not start_str:
            continue
        start_time = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if start_time > now:
            local_time = start_time.astimezone(local_tz)
            future_games.append((local_time.date(), game))

    games_by_date = {}
    for game_date, game in future_games:
        games_by_date.setdefault(game_date, []).append(game)

    next_two_dates = sorted(games_by_date.keys())[:2]

    for game_date in next_two_dates:
        st.header(f"Odds for {game_date.strftime('%A, %b %d, %Y')}")

        try:
            starting_lineups = fetch_starting_lineups(game_date, SPORTSDATA_API_KEY)
        except Exception as e:
            st.warning(f"Failed to fetch starting lineups for {game_date}: {e}")
            starting_lineups = []

        for game in games_by_date[game_date]:
            home_team_name = game.get('home_team')
            away_team_name = game.get('away_team')

            if home_team_name and away_team_name:
                home_abbr = TEAM_NAME_MAP.get(home_team_name, home_team_name)
                away_abbr = TEAM_NAME_MAP.get(away_team_name, away_team_name)
                home_record = team_records.get(home_abbr, "N/A")
                away_record = team_records.get(away_abbr, "N/A")
                teams_str = f"{away_team_name} [{away_record}, A] vs {home_team_name} [{home_record}, H]"
                st.subheader(teams_str)
            else:
                st.subheader("Unknown teams")

            commence_time = game.get('commence_time')
            if commence_time:
                utc_time = datetime.strptime(commence_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                local_time = utc_time.astimezone(local_tz)
                friendly_time = local_time.strftime("%A, %b %d, %Y at %-I:%M %p %Z")
            else:
                friendly_time = "Unknown time"

            st.caption(f"Start time: {friendly_time}")

            era1 = era2 = None

            if home_team_name and away_team_name:
                pitcher1 = get_probable_pitchers(starting_lineups, away_abbr)
                pitcher2 = get_probable_pitchers(starting_lineups, home_abbr)

                if pitcher1 and pitcher2:
                    era1 = era_dict.get(pitcher1.get('PlayerID'))
                    era2 = era_dict.get(pitcher2.get('PlayerID'))

                    p1_name = f"{pitcher1.get('FirstName', away_abbr)} {pitcher1.get('LastName', '')} [{away_abbr}, A]"
                    p2_name = f"{pitcher2.get('FirstName', home_abbr)} {pitcher2.get('LastName', '')} [{home_abbr}, H]"

                    st.markdown("**Probable Pitchers:**")
                    st.markdown(f"- {compare_and_format_era(era1, era2, p1_name)}", unsafe_allow_html=True)
                    st.markdown(f"- {compare_and_format_era(era2, era1, p2_name)}", unsafe_allow_html=True)
                else:
                    st.text("Probable pitchers info not found.")
            else:
                st.text("Could not identify teams properly for pitchers info.")

            bookmakers = game.get('bookmakers', [])
            if bookmakers:
                bookmaker = bookmakers[0]
                st.markdown(f"**Bookmaker:** {bookmaker.get('title', 'Unknown')}")

                home_wins = get_wins(home_record)
                away_wins = get_wins(away_record)

                for market in bookmaker.get('markets', []):
                    for outcome in market.get('outcomes', []):
                        team_name = outcome.get('name', 'Unknown')
                        price = outcome.get('price', 'N/A')

                        team_abbr = TEAM_NAME_MAP.get(team_name, team_name)

                        if team_abbr == away_abbr:
                            era_pitcher = era1
                            era_opponent = era2
                            pitcher_wins = away_wins
                            opponent_wins = home_wins
                        elif team_abbr == home_abbr:
                            era_pitcher = era2
                            era_opponent = era1
                            pitcher_wins = home_wins
                            opponent_wins = away_wins
                        else:
                            era_pitcher = era_opponent = pitcher_wins = opponent_wins = None

                        msg = odds_message(era_pitcher, era_opponent, pitcher_wins, opponent_wins, price)

                        if isinstance(price, (int, float)):
                            color = "🟢" if price < 0 else "🟡"
                            st.markdown(f"{color} **{team_name}**: {price} {msg}")
                        else:
                            st.text(f"{team_name}: {price}")
            else:
                st.text("No bookmaker odds available.")

            st.markdown("---")

# Only run if directly executed (not when imported)
if __name__ == "__main__":
    show_ui()
