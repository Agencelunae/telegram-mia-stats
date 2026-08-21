"""
Script de suivi quotidien du nombre d'abonnés d'un canal Telegram.

Le workflow GitHub Actions associé se déclenche deux fois par jour (une fois
pour l'heure d'été, une fois pour l'heure d'hiver) car GitHub Actions ne gère
que l'UTC. Ce script vérifie donc lui-même l'heure locale à Paris et ne fait
quelque chose que si on est bien à 7h du matin heure française — l'autre
déclenchement de la journée ne fait rien.
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import requests
from google.oauth2.service_account import Credentials

TARGET_HOUR_PARIS = 7  # heure locale à laquelle on veut effectivement agir


def main():
    paris_now = datetime.now(ZoneInfo("Europe/Paris"))

    if paris_now.hour != TARGET_HOUR_PARIS:
        print(
            f"Heure locale Paris actuelle = {paris_now.hour}h "
            f"(on n'agit qu'à {TARGET_HOUR_PARIS}h). Sortie sans action."
        )
        return

    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

    # 1. Récupérer le nombre d'abonnés via l'API Telegram
    url = f"https://api.telegram.org/bot{bot_token}/getChatMemberCount"
    resp = requests.get(url, params={"chat_id": chat_id}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Erreur API Telegram : {data}")
    member_count = data["result"]

    # 2. Se connecter au Google Sheet
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(sheet_id).sheet1

    # 3. Calculer la variation par rapport à la veille
    values = sheet.get_all_values()
    previous_count = None
    if len(values) > 1:  # il y a au moins une ligne de données sous l'en-tête
        try:
            previous_count = int(values[-1][1])
        except (ValueError, IndexError):
            previous_count = None

    variation = member_count - previous_count if previous_count is not None else ""

    # 4. Ajouter la nouvelle ligne
    date_str = paris_now.strftime("%Y-%m-%d")
    sheet.append_row([date_str, member_count, variation])
    print(f"Ligne ajoutée : {date_str} | {member_count} abonnés | variation {variation}")


if __name__ == "__main__":
    main()
