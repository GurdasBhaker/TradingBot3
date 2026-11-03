from Utilz.MT5_handler import MetaTrader5_handler as mt5_handler
from Utilz.calc_lib import Calculators as calc


class StochasticOscilator:

    @classmethod
    def calculator(cls, account, symbols, time_frame, *kwargs):

        mt5_handler.start_mt5(account)

        analytic_timeframe = time_frame[0]

        signal_str = {1: 'Long', -1: 'Short'}
        direction = {1: 'Oversold', -1: 'Overbought'}
        strategies = [1, -1]

        k = 63
        d = 9
        smooth = 9
        upper_bound = 90
        lower_bound = 10

        for symbol in symbols:

            # get bars starting from now in UTC time zone, create DataFrame out of the obtained data
            prices = mt5_handler.get_prices(symbol, analytic_timeframe, 1, 10000, date_time=None)

            # Run for all strategy types set above 1 (Long) and -1 (Short)
            for strategy in strategies:
                # Run Oscilator Stoch
                stoch_df = calc.stochastic_oscilator(prices, k, smooth, d)

                # Create trading dataframe
                stochastic_signals = calc.stochastic_signals(
                    stoch_df, strategy, upper_bound, lower_bound
                )


