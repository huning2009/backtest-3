from __future__ import print_function
import datetime
import queue
import numpy as np
import pandas as pd
from Backtest.event import FillEvent, OrderEvent
from Backtest.event import EventType
from abc import ABCMeta, abstractmethod

class Portfolio(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def update_signal(self, event):
        raise NotImplementedError("Should implement update_signal()")

    @abstractmethod
    def update_fill(self, event):
        raise NotImplementedError("Should implement update_fill()")

    @abstractmethod
    def update_timeindex(self, event):
        raise NotImplementedError("Should implement update_timeindex()")




class PortfolioHandler(Portfolio):
    def __init__(self, data_handler, events, start_date, equity):
        self.data_handler = data_handler
        self.events = events
        self.start_date = start_date
        self.equity = equity
        self.tickers = self.data_handler.tickers

        self.all_positions = self.construct_all_positions()
        self.current_positions = self.construct_current_positions()

        self.all_holdings = self.construct_all_holdings()
        self.current_holdings = self.construct_current_holdings()

    def construct_all_positions(self):
        d = dict([(ticker, 0) for ticker in self.tickers])
        d['datetime'] = self.start_date
        return [d]

    def construct_current_positions(self):
        return dict([(ticker, 0) for ticker in self.tickers])

    def construct_all_holdings(self):
        d = dict([(ticker, 0.0) for ticker in self.tickers])
        d['datetime'] = self.start_date
        d['cash'] = self.equity
        d['commission'] = 0.0
        d['total'] = self.equity
        return [d]

    def construct_current_holdings(self):
        d = dict([(ticker, 0.0) for ticker in self.tickers])
        d['cash'] = self.equity
        d['commission'] = 0.0
        d['total'] = self.equity
        return d

    def update_timeindex(self, event):
        lasest_datetime = self.data_handler.get_latest_bar_datetime(event.ticker)

        # Update positions
        dposition = dict([(ticker, 0) for ticker in self.tickers])
        dposition['datetime'] = lasest_datetime
        for ticker in self.tickers:
            dposition[ticker] = self.current_positions[ticker]
        self.all_positions.append(dposition)

        # Update holdings
        dholding = dict([(ticker, 0.0) for ticker in self.tickers])
        dholding['datetime'] = lasest_datetime
        dholding['cash'] = self.current_holdings['cash']
        dholding['commission'] = self.current_holdings['commission']
        dholding['total'] = self.current_holdings['cash']
        for ticker in self.tickers:
            market_value = self.current_positions[ticker] * \
                self.data_handler.get_latest_bar_value(event.ticker, "close")
            dholding[ticker] = market_value
            dholding['total'] += market_value
        self.equity = dholding['total']
        self.all_holdings.append(dholding)

    def update_positions_from_fill(self, event):
        action_dir = {"LONG": 1, "SHORT": -1}
        self.current_positions[event.ticker] += action_dir.get(event.action, 0) * event.quantity

    def update_holdings_from_fill(self, event):
        action_dir = {"LONG": 1, "SHORT": -1}
        action_dir.get(event.action, 0)
        action = action_dir.get(event.action, 0)
        event_cost = self.data_handler.get_latest_bar_value(event.ticker, "close")
        cost = action * event_cost * event.quantity
        self.current_holdings[event.ticker] += cost
        self.current_holdings['commission'] += event.commission
        self.current_holdings['cash'] -= (cost + event.commission)
        self.current_holdings['total'] -= (cost + event.commission)

    def update_fill(self, event):
        if event.type == EventType.FILL:
            self.update_positions_from_fill(event)
            self.update_holdings_from_fill(event)

    def generate_order(self, event):
        ticker = event.ticker
        action = event.action

        if event.suggested_quantity is None:
            quantity = 0
        else:
            quantity = event.suggested_quantity

        order_event = OrderEvent(ticker, action, quantity)
        return order_event

    def update_signal(self, event):
        if event.type == EventType.SIGNAL:
            order_event = self.generate_order(event)
            self.events.put(order_event)