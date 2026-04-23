"""
Configuracao dos simbolos FOREX alvo.
Top 10 pares forex por volume + XAUUSD (ouro).

Mapeamento country -> currency para news features.
"""

# Mapeamento pais (Investing) -> moeda ISO
COUNTRY_CURRENCY_MAP = {
    "United States": "USD",
    "EUA": "USD",
    "Euro Zone": "EUR",
    "Zona Euro": "EUR",
    "United Kingdom": "GBP",
    "Reino Unido": "GBP",
    "Japan": "JPY",
    "Japão": "JPY",
    "Switzerland": "CHF",
    "Suíça": "CHF",
    "Australia": "AUD",
    "Austrália": "AUD",
    "Canada": "CAD",
    "Canadá": "CAD",
    "New Zealand": "NZD",
    "Nova Zelândia": "NZD",
    "China": "CNY",
    "Brazil": "BRL",
    "Brasil": "BRL",
}


def get_symbol_currencies(symbol: str) -> tuple[str, str]:
    """Retorna (base_currency, quote_currency) de um par forex.
    Ex: EURUSD -> ('EUR', 'USD'), XAUUSD -> ('XAU', 'USD')
    """
    if symbol == "XAUUSD":
        return ("XAU", "USD")
    return (symbol[:3], symbol[3:])

# Simbolos desejados (top 10 forex + ouro)
DESIRED_SYMBOLS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "EURGBP",
    "EURJPY",
    "GBPJPY",
    "XAUUSD",
]

# Simbolos de fallback caso algum desejado nao esteja disponivel
FALLBACK_SYMBOLS = [
    "AUDCAD",
    "AUDNZD",
    "EURCHF",
    "EURAUD",
]

# Configuracao por simbolo
SYMBOL_CONFIG = {
    "EURUSD":  {"digits": 5, "pip_value": 0.0001, "description": "Euro / US Dollar"},
    "GBPUSD":  {"digits": 5, "pip_value": 0.0001, "description": "British Pound / US Dollar"},
    "USDJPY":  {"digits": 3, "pip_value": 0.01,   "description": "US Dollar / Japanese Yen"},
    "USDCHF":  {"digits": 5, "pip_value": 0.0001, "description": "US Dollar / Swiss Franc"},
    "AUDUSD":  {"digits": 5, "pip_value": 0.0001, "description": "Australian Dollar / US Dollar"},
    "USDCAD":  {"digits": 5, "pip_value": 0.0001, "description": "US Dollar / Canadian Dollar"},
    "NZDUSD":  {"digits": 5, "pip_value": 0.0001, "description": "New Zealand Dollar / US Dollar"},
    "EURGBP":  {"digits": 5, "pip_value": 0.0001, "description": "Euro / British Pound"},
    "EURJPY":  {"digits": 3, "pip_value": 0.01,   "description": "Euro / Japanese Yen"},
    "GBPJPY":  {"digits": 3, "pip_value": 0.01,   "description": "British Pound / Japanese Yen"},
    "XAUUSD":  {"digits": 2, "pip_value": 0.01,   "description": "Gold / US Dollar"},
    "AUDCAD":  {"digits": 5, "pip_value": 0.0001, "description": "Australian Dollar / Canadian Dollar"},
    "AUDNZD":  {"digits": 5, "pip_value": 0.0001, "description": "Australian Dollar / NZ Dollar"},
    "EURCHF":  {"digits": 5, "pip_value": 0.0001, "description": "Euro / Swiss Franc"},
    "EURAUD":  {"digits": 5, "pip_value": 0.0001, "description": "Euro / Australian Dollar"},
}


def get_pip_value(symbol: str) -> float:
    """Retorna o valor de 1 pip para o simbolo."""
    if symbol in SYMBOL_CONFIG:
        return SYMBOL_CONFIG[symbol]["pip_value"]
    # Default para pares com 5 digitos
    return 0.0001


def get_digits(symbol: str) -> int:
    """Retorna o numero de casas decimais do simbolo."""
    if symbol in SYMBOL_CONFIG:
        return SYMBOL_CONFIG[symbol]["digits"]
    return 5
