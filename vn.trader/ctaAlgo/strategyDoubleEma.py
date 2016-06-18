# encoding: UTF-8

"""
1、周期15分钟
2、均线采取EMA,10周期和20周期交叉决定多空，永久在市。
3、过滤器采用前高前低，即，多单开仓必须符合价格比前一个EMA10上最高价高，反之亦然。
"""


from ctaBase import *
from ctaTemplate import CtaTemplate

import talib
import numpy as np


########################################################################
class DoubleEmaStrategy(CtaTemplate):
    """结合ATR和RSI指标的一个分钟线交易策略"""
    className = 'DoubleEmaStrategy'
    author = u'Bian Jiang'

    # 仓位
    pre_pos = 20000

    orderDict = {}          # vtSymbol.orderType:orderID 保存委托代码的字典

    # 策略参数
    initDays = 10           # 初始化数据所用的天数

    fastEmaLength = 5      # 10 EMA
    slowEmaLength = 10      # 20 EMA

    # 策略变量
    bar = None                  # K线对象
    barMinute = EMPTY_STRING    # K线当前的分钟

    bufferSize = 10                    # 需要缓存的数据的大小
    bufferCount = 0                     # 目前已经缓存了的数据的计数

    highArray = np.zeros(bufferSize)    # K线最高价的数组
    lowArray = np.zeros(bufferSize)     # K线最低价的数组
    closeArray = np.zeros(bufferSize)   # K线收盘价的数组

    fastEmaArray = np.zeros(bufferSize) # fast EMA 指标的数组
    slowEmaArray = np.zeros(bufferSize) # fast EMA 指标的数组

    fastEmaValue = 0                    # 最新 fast EMA指标数值
    slowEmaValue = 0                    # 最新 slow EMA指标数值

    fastEmaTradeHigh = 0                    # EMA10上最高价高
    fastEmaTradeLow = 0                     # EMA10上最高价低

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol',
                 'fastEmaLength',
                 'slowEmaLength']

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'fastEmaValue',
               'slowEmaValue',
               'fastEmaTradeHigh',
               'fastEmaTradeLow',
               'bufferCount']

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(DoubleEmaStrategy, self).__init__(ctaEngine, setting)

    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' %self.name)

        # 载入历史数据，并采用回放计算的方式初始化策略数值
        initData = self.loadBar(self.initDays)
        for bar in initData:
            self.onBar(bar)

        self.putEvent()

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略启动' %self.name)
        self.putEvent()

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略停止' %self.name)
        self.putEvent()

    #----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        # 计算K线
        tickMinute = tick.datetime.minute

        if tickMinute != self.barMinute:
            if self.bar:
                self.onBar(self.bar)

            bar = CtaBarData()              
            bar.vtSymbol = tick.vtSymbol
            bar.symbol = tick.symbol
            bar.exchange = tick.exchange

            bar.open = tick.lastPrice
            bar.high = tick.lastPrice
            bar.low = tick.lastPrice
            bar.close = tick.lastPrice

            bar.date = tick.date
            bar.time = tick.time
            bar.datetime = tick.datetime    # K线的时间设为第一个Tick的时间

            self.bar = bar                  # 这种写法为了减少一层访问，加快速度
            self.barMinute = tickMinute     # 更新当前的分钟
        else:                               # 否则继续累加新的K线
            bar = self.bar                  # 写法同样为了加快速度

            bar.high = max(bar.high, tick.lastPrice)
            bar.low = min(bar.low, tick.lastPrice)
            bar.close = tick.lastPrice

    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""

        # 保存K线数据
        self.closeArray[0:self.bufferSize-1] = self.closeArray[1:self.bufferSize]
        self.highArray[0:self.bufferSize-1] = self.highArray[1:self.bufferSize]
        self.lowArray[0:self.bufferSize-1] = self.lowArray[1:self.bufferSize]
        
        self.closeArray[-1] = bar.close
        self.highArray[-1] = bar.high
        self.lowArray[-1] = bar.low
        
        self.bufferCount += 1

        # EMA 指标技术
        self.fastEmaValue = round(talib.EMA(self.closeArray, self.fastEmaLength)[-1], 5)
        self.slowEmaValue = round(talib.EMA(self.closeArray, self.slowEmaLength)[-1], 5)

        self.fastEmaArray[0:self.bufferSize-1] = self.fastEmaArray[1:self.bufferSize]
        self.fastEmaArray[-1] = self.fastEmaValue

        self.slowEmaArray[0:self.bufferSize-1] = self.slowEmaArray[1:self.bufferSize]
        self.slowEmaArray[-1] = self.slowEmaValue

        if self.bufferCount < self.bufferSize:
            self.putEvent()
            return

        lastFastEmaArray = self.fastEmaArray[-self.fastEmaLength:]

        self.fastEmaTradeHigh = lastFastEmaArray.max()
        self.fastEmaTradeLow = lastFastEmaArray.min()

        # 当前无仓位
        if self.pos == 0:
            # 均线采取EMA,10周期和20周期交叉决定多空
            if self.fastEmaValue > self.slowEmaValue:
                # 看多
                if bar.close > self.fastEmaTradeHigh:
                    # 多单开仓必须符合价格比前一个EMA10上最高价高
                    print "Buy: ", bar.close, ", pos: ", self.pos
                    key = '.'.join([bar.vtSymbol, 'buy'])
                    self.removePendingOrder(key)
                    orderID = self.buy(bar.close, self.pre_pos)
                    self.orderDict[key] = orderID


            elif self.fastEmaValue < self.slowEmaValue:
                # 看空
                if bar.close < self.fastEmaTradeLow:
                    # 空单开仓必须符合价格比前一个EMA10上最低价低
                    print "Short: ", bar.close, ", pos: ", self.pos
                    key = '.'.join([bar.vtSymbol, 'short'])
                    self.removePendingOrder(key)
                    orderID = self.short(bar.close, self.pre_pos)
                    self.orderDict[key] = orderID

        # 持有多头仓位
        if self.pos > 0 and self.fastEmaValue < self.slowEmaValue:
            print "cover sell: ", bar.close, ", pos: ", self.pos
            key = '.'.join([bar.vtSymbol, 'sell'])
            self.removePendingOrder(key)
            orderID = self.sell(bar.close, self.pre_pos)
            self.orderDict[key] = orderID

        # 持有空头仓位
        if self.pos < 0 and self.fastEmaValue > self.slowEmaValue:
            print "cover buy: ", bar.close, ", pos: ", self.pos
            key = '.'.join([bar.vtSymbol, 'cover'])
            self.removePendingOrder(key)
            orderID = self.cover(bar.close, self.pre_pos)
            self.orderDict[key] = orderID

        # 发出状态更新事件
        self.putEvent()

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        self.putEvent()
        pass

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        self.putEvent()
        pass

    def removePendingOrder(self, key):
        if key in self.orderDict:
            orderId = self.orderDict.pop(key)
            if orderId:
                print "removePendingOrder: ", key, orderId
                self.cancelOrder(orderId)


if __name__ == '__main__':
    # 提供直接双击回测的功能
    # 导入PyQt4的包是为了保证matplotlib使用PyQt4而不是PySide，防止初始化出错
    from ctaBacktesting import *
    from PyQt4 import QtCore, QtGui
    
    # 创建回测引擎
    engine = BacktestingEngine()
    
    # 设置引擎的回测模式为K线
    engine.setBacktestingMode(engine.BAR_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate('20160301')
    
    # 载入历史数据到引擎中
    engine.loadHistoryData(MINUTE_DB_NAME, 'IF0000')
    
    # 设置产品相关参数
    #engine.setSlippage(0.2)     # 股指1跳
    #engine.setRate(0.3/10000)   # 万0.3
    #engine.setSize(300)         # 股指合约大小
    
    # 在引擎中创建策略对象
    engine.initStrategy(DoubleEmaStrategy, {})
    
    # 开始跑回测
    engine.runBacktesting()
    
    # 显示回测结果
    engine.showBacktestingResult()
    
    
