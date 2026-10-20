from dataclasses import dataclass

# Add bot Configurations here under the BotRegister class
# then when complete add the bot to the Register class Bots list if you want it to run


@dataclass
class BotRegister:
    Stochastic_15M_63_9_9 = {
        "module": "TB2.TradingBots.stochastic",
        "class": "StochasticOscilator",
        "config_module": "TB2.Configurations.configurations",
        "config_class": "Stochastic_15M_63_9_9",
        "schedule": {"interval": "minutes", "value": '*/15'},
        "Symbols": 'Default'
    }

    Stochastic_63_9_9 = {
        "module": "TB2.TradingBots.stochastic",
        "class": "StochasticOscilator",
        "config_module": "TB2.Configurations.configurations",
        "config_class": "Stochastic_63_9_9",
        "schedule": {"interval": "minutes", "value": '*/5'},
        "Symbols": 'Default'
    }

    EngulfingTradeAll = {
        "module": "TB2.TradingBots.EngulfingTrade",
        "class": "EngulfingCandleBot",
        "config_module": "TB2.Configurations.configurations",
        "config_class": "EngulfingTradeAll",
        "schedule": {"interval": "minutes", "value": '*'},
        "Symbols": 'Default'
    }

    Fibonacci_Sniper = {
        "module": "TB2.TradingBots.fib_sniper",
        "class": "FibonacciSniperBot",
        "config_module": "TB2.Configurations.configurations",
        "config_class": "Fibonacci_Sniper",
        "schedule": {"interval": "minutes", "value": '*/5'},
        "Symbols": 'Default'
    }

    EngulfingNotificationAll = {
        "module": "TB2.TradingBots.EngulfingNote",
        "class": "EngulfingCandle",
        "config_module": "TB2.Configurations.configurations",
        "config_class": "EngulfingNotificationAll",
        "schedule": {"interval": "minutes", "value": '*'},
        "Symbols": 'Default'
    }

    EMABot = {
        "module": "TB2.TradingBots.EMANote",
        "class": "EMABot",
        "config_module": "TB2.Configurations.configurations",
        "config_class": "EMA_Bot",
        "schedule": {"interval": "minutes", "value": '*'},
        "Symbols": 'Default'
    }

    EngulfingStochasticTradeAll = {
        "module": "TB2.TradingBots.EngulfingStochasticTrade",
        "class": "EngulfingStochasticBot",
        "config_module": "TB2.Configurations.configurations",
        "config_class": "EngulfingStochasticTradeAll",
        "schedule": {"interval": "minutes", "value": '*'},
        "Symbols": 'Default'
    }

    EngulfingStochasticNoteAll = {
        "module": "TB2.TradingBots.EngulfingStochasticNote",
        "class": "EngulfingStochasticCandle",
        "config_module": "TB2.Configurations.configurations",
        "config_class": "EngulfingStochasticNotificationAll",
        "schedule": {"interval": "minutes", "value": '*'},
        "Symbols": 'Default'
    }

    StochasticOscilatorNotification = {
        "module": "TB2.TradingBots.stochastic_notification",
        "class": "StochasticOscilatorNotification",
        "config_module": "TB2.Configurations.configurations",
        "config_class": "Stochastic_63_9_9",
        "schedule": {"interval": "minutes", "value": '*/5'},
        "Symbols": 'Default'
    }



