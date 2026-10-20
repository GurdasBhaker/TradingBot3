from dataclasses import dataclass
from TB2.Utilz.BotRegister import BotRegister


@dataclass
class Register:
    # Define the bots you want to run and their configurations
    Bots = [
        BotRegister.Stochastic_15M_63_9_9
        # BotRegister.Engulfing25_gurdas,
        # BotRegister.Engulfing50_gurdas
    ]

    KaranBots = [
        BotRegister.Engulfing25,
        BotRegister.Engulfing50,
        BotRegister.Stochastic_63_9_9
    ]

