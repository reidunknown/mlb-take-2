import requests
from datetime import datetime
import pytz

# ====== CONFIG ======
AIRTABLE_TOKEN = "patZZ0DwO5nyxQzvq.0d3c0f457d3f2ee0e1d894efe780f79eb2c05dbf5876087383d8bebb455fe647"
BASE_ID = "appU67FtsALeyrC8c"
TABLE_NAME = "locks"
AIRTABLE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
SPORTSDATAIO_KEY = "d6754260d2834c3bbc4c1d14a1d27e62"

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}

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

# Reverse map: code -> full name
CODE_TO_NAME = {v: k for k, v in TEAM_NAME_MAP.items()}
NAME_TO_CODE = TEAM_NAME_MAP


def get_past_games_missing_results():
    records_to_update = []
    today = datetime.now(pytz.timezone('America/New_York')).date()

    offset = None
    while True:
        params = {
            "filterByFormula": "OR(NOT({game_result}), NOT({ml_result}))",
            "pageSize": 100,
        }
        if offset:
            params["offset"] = offset

        response = requests.get(AIRTABLE_URL, headers=HEADERS, params=params)
        data = response.json()
        for record in data.get("records", []):
            fields = record.get("fields", {})
            if not all(k in fields for k in ("date", "home_team", "away_team", "ml_pick")):
                print(f"⚠️ Skipping record missing required fields: {fields}")
                continue

            game_date = datetime.strptime(fields["date"], "%Y-%m-%d").date()
            if game_date < today:
                records_to_update.append({
                    "record_id": record["id"],
                    "home_team": fields["home_team"],
                    "away_team": fields["away_team"],
                    "date": fields["date"],
                    "ml_pick": fields["ml_pick"]
                })

        offset = data.get("offset")
        if not offset:
            break

    return records_to_update


def fetch_finished_game_data(home_team, away_team, date):
    home_code = TEAM_NAME_MAP.get(home_team)
    away_code = TEAM_NAME_MAP.get(away_team)
    if not home_code or not away_code:
        print(f"⚠️ Unknown team name: {home_team} or {away_team}")
        return None

    url = f"https://api.sportsdata.io/v3/mlb/scores/json/GamesByDate/{date}"
    headers = {"Ocp-Apim-Subscription-Key": SPORTSDATAIO_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Error fetching game data: {response.status_code}")
        return None

    games = response.json()
    for game in games:
        if game.get("HomeTeam") == home_code and game.get("AwayTeam") == away_code:
            home_runs = game.get("HomeTeamRuns")
            away_runs = game.get("AwayTeamRuns")
            if home_runs is None or away_runs is None:
                return None  # Game not finished yet

            winner = home_code if home_runs > away_runs else away_code
            score = f"{home_runs}-{away_runs}"
            return {"result": winner, "score": score}

    return None


def update_airtable_record(record_id, game_result, ml_result, score):
    data = {
        "fields": {
            "game_result": game_result,
            "ml_result": ml_result,
            "score": score
        }
    }
    response = requests.patch(f"{AIRTABLE_URL}/{record_id}", headers=HEADERS, json=data)
    if response.status_code == 200:
        print(f"✅ Updated record {record_id} with game_result, ml_result, and score.")
    else:
        print(f"❌ Failed to update record {record_id}: {response.text}")


def update_games():
    past_games = get_past_games_missing_results()
    if not past_games:
        print("No past games missing results to update.")
        return

    for game in past_games:
        result_data = fetch_finished_game_data(
            home_team=game["home_team"],
            away_team=game["away_team"],
            date=game["date"]
        )
        if result_data:
            ml_pick_raw = game["ml_pick"]
            ml_pick_code = NAME_TO_CODE.get(ml_pick_raw, ml_pick_raw)
            full_winner_name = CODE_TO_NAME.get(result_data["result"], result_data["result"])
            ml_result = "won" if ml_pick_code == result_data["result"] else "lost"

            print(f"Updating record {game['record_id']}: game_result={full_winner_name}, ml_pick={ml_pick_raw} ({ml_pick_code}), ml_result={ml_result}, score={result_data['score']}")

            update_airtable_record(
                game["record_id"],
                game_result=full_winner_name,
                ml_result=ml_result,
                score=result_data["score"]
            )
        else:
            print(f"⚠️ No result found for {game['home_team']} vs {game['away_team']} on {game['date']}")


if __name__ == "__main__":
    update_games()
