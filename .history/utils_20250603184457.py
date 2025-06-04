# utils.py

from datetime import datetime
import requests

SPORT = 'baseball_mlb'
REGION = 'us'
MARKET = 'h2h'

TEAM_NAME_MAP = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chicago White Sox": "CHW", "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN", "New York Mets": "NYM", "New York Yankees": "NYY", "Oakland Athletics": "OAK",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD", "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB", "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH"
}

def fetch_odds(api_key):
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds/'
    params = {
        'apiKey': api_key,
        'regions': REGION,
        'markets': MARKET,
        'oddsFormat': 'american'
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def format_date_for_sportsdata(date_obj):
    return date_obj.strftime("%Y-%b-%d").upper()

def fetch_starting_lineups(date_obj, api_key):
    date_str = format_date_for_sportsdata(date_obj)
    url = f"https://api.sportsdata.io/v3/mlb/projections/json/StartingLineupsByDate/{date_str}"
    params = {'key': api_key}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def fetch_player_era_dict(api_key):
    url = "https://api.sportsdata.io/v3/mlb/stats/json/PlayerSeasonStats/2025"
    headers = {'Ocp-Apim-Subscription-Key': api_key}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    player_stats = response.json()
    return {player["PlayerID"]: player.get("EarnedRunAverage") for player in player_stats}

def fetch_team_records(api_key):
    url = "https://api.sportsdata.io/v3/mlb/scores/json/Standings/2025"
    headers = {'Ocp-Apim-Subscription-Key': api_key}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    standings = response.json()
    return {
        team["Key"]: f"{team['Wins']}-{team['Losses']}"
        for team in standings
    }

def get_probable_pitchers(starting_lineups, team_abbr):
    for lineup in starting_lineups:
        if lineup.get('HomeTeam') == team_abbr:
            return lineup.get('HomeStartingPitcher')
        elif lineup.get('AwayTeam') == team_abbr:
            return lineup.get('AwayStartingPitcher')
    return None

def compare_and_format_era(era1, era2, pitcher_name):
    if era1 is None:
        return f"{pitcher_name} (ERA: N/A)"
    if era2 is None:
        return f"**{pitcher_name} (ERA: {era1:.2f})**"

    diff = abs(era1 - era2)
    if era1 < era2:
        if diff >= 2.0:
            return f"**<span style='color:green'>{pitcher_name} (ERA: {era1:.2f})</span>**"
        elif diff >= 1.0:
            return f"**<span style='color:orange'>{pitcher_name} (ERA: {era1:.2f})</span>**"
        else:
            return f"**{pitcher_name} (ERA: {era1:.2f})**"
    else:
        return f"{pitcher_name} (ERA: {era1:.2f})"

def odds_message(era_pitcher, era_opponent, pitcher_team_wins, opponent_team_wins, odds):
    if era_pitcher is not None and era_opponent is not None:
        era_diff = era_opponent - era_pitcher
        wins_diff = pitcher_team_wins - opponent_team_wins

        if era_diff > 1.0 and wins_diff > 5:
            if odds < 0:
                return " (potential lock)"
            elif odds > 0:
                return " (potential upset)"
    return ""

def get_wins(record):
    try:
        return int(record.split('-')[0])
    except Exception:
        return 0

import requests
from datetime import datetime



def fetch_finished_game_data(home_team, away_team, date_str, api_key="YOUR_SPORTSDATAIO_KEY"):
    """
    Returns game_result ("Home Team" or "Away Team") and score string ("X-Y")
    """
    # Format date
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    url = f"https://api.sportsdata.io/v4/mlb/scores/json/GamesByDate/{date_obj}"

    headers = {
        "Ocp-Apim-Subscription-Key": api_key
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Error fetching game data: {response.status_code}")
        return None

    games = response.json()

    for game in games:
        home = game.get("HomeTeam")
        away = game.get("AwayTeam")
        home_score = game.get("HomeTeamRuns")
        away_score = game.get("AwayTeamRuns")

        if home_score is None or away_score is None:
            continue  # game likely not finished

        # Match by team abbreviations
        mapped_home = TEAM_NAME_MAP.get(home_team, home_team)
        mapped_away = TEAM_NAME_MAP.get(away_team, away_team)

        if home == mapped_home and away == mapped_away:
            winner = home_team if home_score > away_score else away_team
            score = f"{home_score}-{away_score}"
            return {
                "game_result": winner,
                "score": score
            }

    return None  # no match found
