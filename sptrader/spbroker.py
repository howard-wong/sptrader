#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015, 2016 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import collections

import backtrader as bt
import io
import spstore
from backtrader.comminfo import CommInfoBase
from backtrader.order import Order, BuyOrder, SellOrder
from backtrader.position import Position
from backtrader.metabase import MetaParams
from backtrader.utils.py3 import with_metaclass


__all__ = ['BackBroker', 'BrokerBack']


class MetaSharpPointBroker(MetaParams):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaSharpPointBroker, cls).__init__(name, bases, dct)
        spstore.SharpPointStore.BrokerCls = cls


class SharpPointBroker(with_metaclass(MetaSharpPointBroker, bt.BrokerBase)):
    '''Broker Simulator

      The simulation supports different order types, checking a submitted order
      cash requirements against current cash, keeping track of cash and value
      for each iteration of ``cerebro`` and keeping the current position on
      different datas.

      *cash* is adjusted on each iteration for instruments like ``futures`` for
       which a price change implies in real brokers the addition/substracion of
       cash.

      Supported order types:

        - ``Market``: to be executed with the 1st tick of the next bar (namely
          the ``open`` price)

        - ``Close``: meant for intraday in which the order is executed with the
          closing price of the last bar of the session

        - ``Limit``: executes if the given limit price is seen during the
          session

        - ``Stop``: executes a ``Market`` order if the given stop price is seen

        - ``StopLimit``: sets a ``Limit`` order in motion if the given stop
          price is seen

      Because the broker is instantiated by ``Cerebro`` and there should be
      (mostly) no reason to replace the broker, the params are not controlled
      by the user for the instance.  To change this there are two options:

        1. Manually create an instance of this class with the desired params
           and use ``cerebro.broker = instance`` to set the instance as the
           broker for the ``run`` execution

        2. Use the ``set_xxx`` to set the value using
           ``cerebro.broker.set_xxx`` where ```xxx`` stands for the name of the
           parameter to set

        .. note::

           ``cerebro.broker`` is a *property* supported by the ``getbroker``
           and ``setbroker`` methods of ``Cerebro``

      Params:

        - ``cash`` (default: ``10000``): starting cash

        - ``commission`` (default: ``CommInfoBase(percabs=True)``)
          base commission scheme which applies to all assets

        - ``checksubmit`` (default: ``True``)
          check margin/cash before accepting an order into the system

        - ``eosbar`` (default: ``False``):
          With intraday bars consider a bar with the same ``time`` as the end
          of session to be the end of the session. This is not usually the
          case, because some bars (final auction) are produced by many
          exchanges for many products for a couple of minutes after the end of
          the session

        - ``eosbar`` (default: ``False``):
          With intraday bars consider a bar with the same ``time`` as the end
          of session to be the end of the session. This is not usually the
          case, because some bars (final auction) are produced by many
          exchanges for many products for a couple of minutes after the end of
          the session

        - ``filler`` (default: ``None``)

          A callable with signature: ``callable(order, price, ago)``

            - ``order``: obviously the order in execution. This provides access
              to the *data* (and with it the *ohlc* and *volume* values), the
              *execution type*, remaining size (``order.executed.remsize``) and
              others.

              Please check the ``Order`` documentation and reference for things
              available inside an ``Order`` instance

            - ``price`` the price at which the order is going to be executed in
              the ``ago`` bar

            - ``ago``: index meant to be used with ``order.data`` for the
              extraction of the *ohlc* and *volume* prices. In most cases this
              will be ``0`` but on a corner case for ``Close`` orders, this
              will be ``-1``.

              In order to get the bar volume (for example) do: ``volume =
              order.data.voluume[ago]``

          The callable must return the *executed size* (a value >= 0)

          The callable may of course be an object with ``__call__`` matching
          the aforementioned signature

          With the default ``None`` orders will be completely executed in a
          single shot

    '''
    params = (
        ('cash', 10000.0),
        ('checksubmit', True),
        ('dataname', None),
        ('eosbar', False),
        ('filler', None),
    )
    f = None

    def __init__(self, **kwargs):
        super(SharpPointBroker, self).__init__()
        self.o = spstore.SharpPointStore(**kwargs)
        self.startingcash = self.cash = self.p.cash

        self.orders = collections.OrderedDict()  # orders by order id
        self.pending = collections.deque()  # popleft and append(right)

        self.positions = collections.defaultdict(Position)
        self.notifs = collections.deque()

        self.submitted = collections.deque()
        if self.f is None:
            if hasattr(self.p.dataname, 'readline'):
                self.f = self.p.dataname
            elif self.p.dataname is not None:
                # Let an exception propagate to let the caller know
                self.f = io.open(self.p.dataname, 'a')

    def start(self):
        super(SharpPointBroker, self).start()
        self.o.start(broker=self)

    def stop(self):
        super(SharpPointBroker, self).stop()
        self.o.stop()
        if self.f is not None:
            self.f.close()
            self.f = None

    def get_notification(self):
        try:
            return self.notifs.popleft()
        except IndexError:
            pass

        return None

    def set_filler(self, filler):
        '''Sets a volume filler for volume filling execution'''
        self.p.filler = filler

    def set_checksubmit(self, checksubmit):
        '''Sets the checksubmit parameter'''
        self.p.checksubmit = checksubmit

    def set_eosbar(self, eosbar):
        '''Sets the eosbar parameter (alias: ``seteosbar``'''
        self.p.eosbar = eosbar

    seteosbar = set_eosbar

    def get_cash(self):
        '''Returns the current cash (alias: ``getcash``)'''
        return self.cash

    getcash = get_cash

    def set_cash(self, cash):
        '''Sets the cash parameter (alias: ``setcash``)'''
        self.startingcash = self.cash = self.p.cash = cash

    setcash = set_cash

    def get_value(self, datas=None):
        '''Returns the portfolio value of the given datas (if datas is ``None``, then
        the total portfolio value will be returned (alias: ``getvalue``)
        '''
        return 0.0

    getvalue = get_value

    def getposition(self, data):
        return self.positions[data]

    def orderstatus(self, order):
        o = self.orders[order.ref]
        return o.status

    def submit(self, order):
        if self.p.checksubmit:
            order.submit()
            self.submitted.append(order)
            self.orders.append(order)
            self.notify(order)
        else:
            self.submit_accept(order)
        return order

    def _submit(self, oref):
        order = self.orders[oref]
        order.submit(self)
        self.notify(order)

    def _reject(self, oref):
        order = self.orders[oref]
        order.reject(self)
        self.notify(order)

    def _accept(self, oref):
        order = self.orders[oref]
        order.accept()
        self.notify(order)

    def _cancel(self, oref):
        order = self.orders[oref]
        order.cancel(self)
        self.notify(order)

    def _expire(self, oref):
        order = self.orders[oref]
        order.expire(self)
        self.notify(order)

    def _fill(self, oref, size, price, **kwargs):
        order = self.orders[oref]

        data = order.data
        pos = self.getposition(data, clone=False)
        psize, pprice, opened, closed = pos.update(size, price)

        comminfo = self.getcommissioninfo(data)

        closedvalue = closedcomm = 0.0
        openedvalue = openedcomm = 0.0
        margin = pnl = 0.0

        order.execute(data.datetime[0], size, price,
                      closed, closedvalue, closedcomm,
                      opened, openedvalue, openedcomm,
                      margin, pnl,
                      psize, pprice)

        if order.executed.remsize:
            order.partial()
        else:
            order.completed()

        self.notify(order)

    def buy(self, owner, data,
            size, price=None, plimit=None,
            exectype=None, valid=None, tradeid=0,
            **kwargs):

        order = BuyOrder(owner=owner, data=data,
                         size=size, price=price, pricelimit=plimit,
                         exectype=exectype, valid=valid, tradeid=tradeid)

        order.addinfo(**kwargs)
        self.orders[order.ref] = order
        return self.o.order_create(order)

    def sell(self, owner, data,
             size, price=None, plimit=None,
             exectype=None, valid=None, tradeid=0,
             **kwargs):

        order = SellOrder(owner=owner, data=data,
                          size=size, price=price, pricelimit=plimit,
                          exectype=exectype, valid=valid, tradeid=tradeid)

        order.addinfo(**kwargs)
        self.orders[order.ref] = order
        return self.o.order_create(order)

    def cancel(self, order):
        o = self.orders[order.ref]
        if order.status == Order.Cancelled:  # already cancelled
            return

        return self.o.order_cancel(order)

    def notify(self, order):
        self.notifs.append(order.clone())

    def get_notification(self):
        if not self.notifs:
            return None
        return self.notifs.popleft()

    def next(self):
        self.notifs.append(None)  # mark notification boundary

# Alias
BrokerSharpPoint = SharpPointBroker

if __name__ == '__main__':
    s = SharpPointBroker()
    s.start()

