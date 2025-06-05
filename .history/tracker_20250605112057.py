from datetime import datetime, timezone
import pytz
import requests
from utils import (
    fetch_odds,
    fetch_player_era_dict,
    fetch_team_records,
    fetch_starting_lineups,
    get_probable_pitchers,
    get_wins,
    TEAM_NAME_MAP
)

# Airtable setup
AIRTABLE_TOKEN = "patZZ0DwO5nyxQzvq.0d3c0f457d3f2ee0e1d894efe780f79eb2c05dbf5876087383d8bebb455fe647"
BASE_ID = "appU67FtsALeyrC8c"
TABLE_NAME = "locks"
AIRTABLE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}

ODDS_API_KEY = '9891ed9254b6592da0b72b05b1e0dd69'
SPORTSDATAIO_KEY = '5d88de1d87784a8290ce1734864c1a71'


def get_existing_game_keys():
    """Fetch unique keys like '2025-06-03|Yankees|Red Sox' to prevent duplicates."""
    existing_keys = set()
    offset = None

    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset

        response = requests.get(AIRTABLE_URL, headers=HEADERS, params=params)
        if response.status_code != 200:
            print("❌ Failed to fetch existing records for deduplication.")
            break

        records = response.json().get("records", [])
        for record in records:
            fields = record.get("fields", {})
            key = f"{fields.get('date')}|{fields.get('home_team')}|{fields.get('away_team')}"
            existing_keys.add(key)

        offset = response.json().get("offset")
        if not offset:
            break

    return existing_keys


def get_max_airtable_id():
    offset = None
    max_id = 0

    while True:
        url = AIRTABLE_URL
        if offset:
            url += f"?offset={offset}"

        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print("❌ Failed to fetch records to determine max ID.")
            break

        records = response.json().get('records', [])
        for record in records:
            fields = record.get("fields", {})
            record_id = fields.get("id")
            if record_id and isinstance(record_id, int):
                max_id = max(max_id, record_id)

        offset = response.json().get("offset")
        if not offset:
            break

    return max_id


def extract_lock_info():
    odds_data = fetch_odds(ODDS_API_KEY)
    era_dict = fetch_player_era_dict(SPORTSDATAIO_KEY)
    team_records = fetch_team_records(SPORTSDATAIO_KEY)

    now = datetime.now(timezone.utc)
    local_tz = pytz.timezone('America/New_York')

    lock_rows = []

    for game in odds_data:
        start_str = game.get('commence_time')
        if not start_str:
            continue

        start_time = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if start_time <= now:
            continue

        local_time = start_time.astimezone(local_tz)
        game_date = local_time.date()
        game_day = local_time.strftime("%A")
        game_time = local_time.strftime("%H:%M:%S")

        home_team_name = game.get('home_team')
        away_team_name = game.get('away_team')
        if not home_team_name or not away_team_name:
            continue

        home_abbr = TEAM_NAME_MAP.get(home_team_name, home_team_name)
        away_abbr = TEAM_NAME_MAP.get(away_team_name, away_team_name)

        home_record = team_records.get(home_abbr, "N/A")
        away_record = team_records.get(away_abbr, "N/A")

        try:
            starting_lineups = fetch_starting_lineups(game_date, SPORTSDATAIO_KEY)
        except Exception:
            starting_lineups = []

        pitcher_home = get_probable_pitchers(starting_lineups, home_abbr)
        pitcher_away = get_probable_pitchers(starting_lineups, away_abbr)

        if not pitcher_home or not pitcher_away:
            continue

        era_home = era_dict.get(pitcher_home.get('PlayerID'))
        era_away = era_dict.get(pitcher_away.get('PlayerID'))

        if era_home is None or era_away is None:
            continue

        era_diff = round(abs(float(era_home) - float(era_away)), 2)
        better_pitcher = "Home" if era_home < era_away else "Away"

        home_wins = get_wins(home_record)
        away_wins = get_wins(away_record)

        bookmaker = game.get('bookmakers', [])
        if not bookmaker:
            continue
        bookmaker = bookmaker[0]

        home_odds = None
        away_odds = None
        for market in bookmaker.get('markets', []):
            for outcome in market.get('outcomes', []):
                team = outcome.get('name')
                price = outcome.get('price')
                if TEAM_NAME_MAP.get(team, team) == home_abbr:
                    home_odds = int(price)
                elif TEAM_NAME_MAP.get(team, team) == away_abbr:
                    away_odds = int(price)

        potential_lock = ""
        if better_pitcher == "Home" and era_diff >= 1.0 and home_wins > away_wins + 5:
            if home_odds is not None:
                potential_lock = home_team_name if home_odds < 0 else ""
        elif better_pitcher == "Away" and era_diff >= 1.0 and away_wins > home_wins + 5:
            if away_odds is not None:
                potential_lock = away_team_name if away_odds < 0 else ""

        ml_pick = ""
        if home_odds is not None and away_odds is not None:
            ml_pick = home_team_name if home_odds < away_odds else away_team_name

        row = {
            "date": str(game_date),
            "day": game_day,
            "time": game_time,
            "home_team": home_team_name,
            "home_record": home_record,
            "away_team": away_team_name,
            "away_record": away_record,
            "home_pitcher": f"{pitcher_home.get('FirstName', '')} {pitcher_home.get('LastName', '')}".strip(),
            "away_pitcher": f"{pitcher_away.get('FirstName', '')} {pitcher_away.get('LastName', '')}".strip(),
            "era_diff": era_diff,
            "potential_lock": potential_lock,
            "home_odds": home_odds if home_odds is not None else 0,
            "away_odds": away_odds if away_odds is not None else 0,
            "ml_pick": ml_pick
        }

        lock_rows.append(row)

    return lock_rows


def upload_to_airtable(rows):
    existing_keys = get_existing_game_keys()
    current_max_id = get_max_airtable_id()
    new_id = current_max_id + 1
    uploaded = 0

    for row in rows:
        key = f"{row['date']}|{row['home_team']}|{row['away_team']}"
        if key in existing_keys:
            print(f"⚠️ Duplicate detected, skipping: {key}")
            continue

        row["id"] = new_id
        data = {"fields": row}

        response = requests.post(AIRTABLE_URL, headers=HEADERS, json=data)
        if response.status_code in (200, 201):
            print(f"✅ Uploaded row #{new_id} for {row['home_team']} vs {row['away_team']}")
            uploaded += 1
        else:
            print(f"❌ Error uploading row #{new_id}: {response.status_code}")
            print(response.json())

        new_id += 1

    print(f"🔄 Finished uploading. {uploaded} new rows added.")


def run_tracker():
    print("Fetching and uploading to Airtable...")
    rows = extract_lock_info()
    if rows:
        upload_to_airtable(rows)
    else:
        print("⚠️ No qualifying games found to upload.")


if __name__ == "__main__":
    run_tracker()
