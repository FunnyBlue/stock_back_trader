from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime  # For datetime objects
import os.path  # To manage paths
import sys  # To find out the script name (in argv[0])

# Import the backtrader platform
import backtrader as bt


# Create a Stratey
class TestStrategy(bt.Strategy):
    params = (
        ('short_maperiod', 5),
        ('long_maperiod', 15),
        ('period', 20),
        ('bbdevs', 2.0),
        ('kcdevs', 1.5),
        ('movav', bt.ind.MovAv.Simple)
    )

    def log(self, txt, dt=None):
        ''' Logging function fot this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None

        # Add a MovingAverageSimple indicator
        self.short_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.short_maperiod)

        self.long_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.long_maperiod)

        bb = bt.ind.BollingerBands(
            period=self.p.period, devfactor=self.p.bbdevs, movav=self.p.movav)
        kc = KeltnerChannel(
            period=self.p.period, devfactor=self.p.kcdevs, movav=self.p.movav)

        '''
        squeeze state:

        Bollinger Bands are completely enclosed within the Keltner Channels

        squeeze state:

        Upper Bollinger Band < Upper Keltner Channel
        Lower Bollinger Band > Lower Keltner Channel

        fire state:

        Bollinger Bands expand and move back outside of the Keltner Channel, the squeeze is said to have “fired”

        Upper Bollinger Band > Upper Keltner Channel
        Lower Bollinger Band < Lower Keltner Channel

        '''
        self.lines.squeeze = bb.top - kc.top

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))

                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # Sell
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))

            # when you send the order, it will save the info of how many bars have been processed
            # it is used as an indicator to decide when to sell (ex: only stay 5 days once we buy)
            self.bar_executed = len(self)


        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))

    def next(self):
        # Simply log the closing price of the series from the reference
        self.log('Close, %.2f' % self.dataclose[0])

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # Check if we are in the market
        if not self.position:
            print(self.lines.squeeze[0])

            # Not yet ... we MIGHT BUY if ...
            '''   buy condition
            step1: two days in a row  in squeeze state => upper bollinger band < upper keltner channel
            step2: today is in fire state => Upper Bollinger Band > Upper Keltner Channel
            step3: today's close price > 5 days SMA 

            '''
            if self.lines.squeeze[-1] < 0:
                if self.lines.squeeze[0] > 0:
                    if self.dataclose[0] > self.short_sma[0]:
                        # BUY, BUY, BUY!!! (with all possible default parameters)
                        self.log('BUY CREATE, %.2f' % self.dataclose[0])

                        # Keep track of the created order to avoid a 2nd order
                        self.order = self.buy()

        else:
            '''   sell condition
            step1: hold for three days 

            '''
            if len(self) >= (self.bar_executed + 3):
                # SELL, SELL, SELL!!! (with all possible default parameters)
                self.log('SELL CREATE, %.2f' % self.dataclose[0])

                # Keep track of the created order to avoid a 2nd order
                self.order = self.sell()


if __name__ == '__main__':
    # Create a cerebro entity
    cerebro = bt.Cerebro()

    # Add a strategy
    cerebro.addstrategy(TestStrategy)

    # Datas are in a subfolder of the samples. Need to find where the script is
    # because it could have been called from anywhere
    modpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    datapath = '/Users/laalberta/Documents/投資/python strategy/backtrader_data/datas/orcl-1995-2014.txt'

    print(modpath)
    print(datapath)
    # Create a Data Feed
    data = bt.feeds.YahooFinanceCSVData(
        dataname=datapath,
        # Do not pass values before this date
        fromdate=datetime.datetime(2010, 1, 1),
        # Do not pass values before this date
        todate=datetime.datetime(2013, 12, 31),
        # Do not pass values after this date
        reverse=False)

    # Add the Data Feed to Cerebro
    cerebro.adddata(data)

    # Set our desired cash start
    cerebro.broker.setcash(1000.0)

    # Add a FixedSize sizer according to the stake
    cerebro.addsizer(bt.sizers.FixedSize, stake=10)

    # Set the commission
    cerebro.broker.setcommission(commission=0.0)

    # Print out the starting conditions
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

    # Run over everything
    cerebro.run()

    # Print out the final result
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())