# clients/currency_client.py
import streamlit as st
import requests


TWELVE_DATA_URL = "https://api.twelvedata.com/currency_conversion"


def convert_to_php(amount: float, from_currency: str, date: str) -> float:
    if from_currency == "PHP":
        return float(amount)

    try:
        params = {
            "symbol": f"{from_currency}/PHP",
            "amount": amount,
            "date": date,
            "apikey": st.secrets["twelvedata"]["api_key"],
        }
        response = requests.get(TWELVE_DATA_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "code" in data and data["code"] != 200:
            st.warning(
                f"Currency conversion failed: {data.get('message', 'Unknown error')}"
            )
            return float(amount)

        if "amount" in data:
            return float(data["amount"])

        st.warning("Currency conversion returned no amount. Using original value.")
        return float(amount)

    except Exception as e:
        st.warning(f"Could not convert {from_currency} to PHP. Error: {e}")
        return float(amount)