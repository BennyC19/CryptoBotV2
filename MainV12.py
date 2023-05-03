# Author: Benoit Chouinard
# Version: 7/24/2022
# About: A crypto but with the ability to buy and sell anything that is on the CoinBase.com exchange. 
# Each coin it buys and sells with is NOT hard coded into the bot, it is made to go trade with anything on the website that the user wishes
# It uses a simple algorithm that keeps track of the RSI of each coin and trades accordingly. A little bit of error is permitted because no algorithm is perfect.

import cbpro
import time
from time import sleep
import pandas as pd
import requests
import threading
from datetime import datetime, timedelta
import json
import csv
from csv import writer
import os
import sys

sys.setrecursionlimit(10**9)
threading.stack_size(10**8)



# Sends request to the authenticated client which gives a dictionary for the current information of the coin.
# the price is singled out and returned as a float
def getCurrentPrice(coinName):
    auth_client = cbpro.AuthenticatedClient(api_key, api_secret, passphrase)
    request = auth_client.get_product_ticker(f"{coinName}-USDT")['price']
    price = float(request)
    return price

# The historical data needed to calculate the RSI is in between certain time frames which are written in the timestamp format
# datetime.now() returns a readable time but this needs to be converted to the timestamp
def ReadableTimeToTimeStamp(readableTime):
        s = datetime.strptime(readableTime, "%Y-%m-%d %H:%M:%S.%f")
        timestamp = datetime.timestamp(s)
        timestamp = int(timestamp * 1000)
        return timestamp

# Sends request to the authenticated client to buy a coin
def buyOrder(coinName,amount):
    auth_client = cbpro.AuthenticatedClient(api_key, api_secret, passphrase)
    rounding = 8
    keepGoing = True
    amountBefore = getCoinBalance(accountIDs[coinName])
    while keepGoing == True:
        auth_client.buy(product_id=f"{coinName}-USDT", order_type="market", size=f"{round(amount,rounding)}")
        amountAfter = getCoinBalance(accountIDs[coinName])
        if amountBefore == amountAfter:
            rounding -= 1
        if round(amount,rounding) == 0:
            break
        elif amountBefore != amountAfter:
            keepGoing = False       

# Sends request to the authenticated client to sell a coin
def sellOrder(coinName,amount):
    auth_client = cbpro.AuthenticatedClient(api_key, api_secret, passphrase)
    rounding = 8
    keepGoing = True
    amountBefore = getCoinBalance(accountIDs[coinName])
    while keepGoing == True:
        auth_client.sell(product_id=f"{coinName}-USDT", order_type="market", size=f"{round(amount,rounding)}")
        amountAfter = getCoinBalance(accountIDs[coinName])
        if amountBefore == amountAfter:
            rounding -= 1
        if round(amount,rounding) == 0:
            break
        elif amountBefore != amountAfter:
            keepGoing = False       

# In order to access the portfolio's in the coinbase account, the portfolio ID's are needed
# This function is called in the beginning of when the program runs and the ID's are sent to a dictionary that can be accessed 
def getAccountIDs():
    auth_client = cbpro.AuthenticatedClient(api_key, api_secret, passphrase)
    accounts = auth_client.get_accounts()
    global accountIDs
    accountIDs = {}
    for account in accounts:
        for coin in coinList:
            if (account["currency"] == coin):  
                accountIDs[coin] = account['id']
        if (account["currency"] == 'USDT'):
            global USDTaccountID
            USDTaccountID = account['id']

# Function specifically for getting the total $$$ in the USDT portfolio for the sake of readability
def getTotalUSDT():
    auth_client = cbpro.AuthenticatedClient(api_key, api_secret, passphrase)
    account = auth_client.get_account(USDTaccountID)
    return float(account['balance'])

# Function that accesses the needed ID in the accountIDs dictionary 
# Then returns the balance of that account as a float
def getCoinBalance(id):
    auth_client = cbpro.AuthenticatedClient(api_key, api_secret, passphrase)
    account = auth_client.get_account(id)
    return float(account['balance'])

# the current RSI of each coin is stored in a dictionary
# this function accesses that value and returns in
def getRSI(coinName):
    return rsiDictionary[coinName]

# This function uses the Binance websocket instead of the CoinBase one because the CoinBase one is bad
# I could have used Binance for the whole project but Binance is illegal to trade with in Canada so I will only use it for finding historical data
# The function is a thread and loops constantly so that the RSI's are always updated and the RSI's in the dictionary can be accessed as fast as possible
def rsiBackgroundLoop():
    while True:
        for coin in coinList:    
            startTime = datetime.now() - timedelta(minutes = 15)
            endTime = datetime.now()
            start = startTime.strftime("%Y-%m-%d %H:%M:%S.%f")
            end = endTime.strftime("%Y-%m-%d %H:%M:%S.%f")
            start = ReadableTimeToTimeStamp(start)
            end = ReadableTimeToTimeStamp(end)

            binanceUrl = f'https://fapi.binance.com/fapi/v1/klines?symbol={coin}USDT&interval=1m&startTime={start}&endTime={end}'        
            
            data = requests.get(binanceUrl).json()
            
            D = pd.DataFrame(list(data))
            D.columns = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades',
            'taker_base_vol', 'taker_quote_vol', 'is_best_match']
            D['close'] = D['close'].astype(float)
            D2 = D['close']
            listForRSI = []

            for item in D2:
                listForRSI.append(item)

            dataFrameForRSI = pd.DataFrame(listForRSI)
            delta = dataFrameForRSI.diff()
            up, down = delta.copy(), delta.copy()
            up[up < 0] = 0
            down[down > 0] = 0
            period = 14
            _gain = up.ewm(com=(period - 1), min_periods=period).mean()
            _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
            RS = _gain / _loss
            rsi = 100 - ( 100 / (1+RS))
            rsi=rsi.iloc[-1]
            RSI=float(round(rsi,4) / 100)
            rsiDictionary[coin] = RSI    

# creates a log og the action that was taken (Buy or Sell) and adds it to OrderLog.csv so that all transaction can be looked into
fieldNames = ["Time", "CoinName", "BuyOrSell", "PriceAtTimeOfOrder", "Amount", "RSI"]
with open('OrderLog.csv', 'w', newline='') as csv_file:
    csv_writer = csv.DictWriter(csv_file, fieldnames=fieldNames)
    csv_writer.writeheader()
    def createdBuyOrSellOrderLog(Time,CoinName,BuyOrSell,PriceAtTimeOfOrder,Amount,RSI):
        with open('OrderLog.csv', 'a', newline='') as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldNames)
            info = {
                "Time":Time,
                "CoinName":CoinName,
                "BuyOrSell":BuyOrSell,
                "PriceAtTimeOfOrder":PriceAtTimeOfOrder,
                "Amount":Amount,
                "RSI":RSI
            }            
            csv_writer.writerow(info)

# Activates if there is an error within the Main function
# If there is an error it is most likely a connection error
def errorHandling(errorType):
    print(errorType)
    print("An Unexpected Error Has Occured. Please restart the program and manage your assets in coinbase pro")
    
# A thread that loops constantly so that the user can type in commands at any time
# The explanations for the commands are written in the Main function
def Commands():
    while True:
        userInput = input()
        if userInput == 'HARDSTOP':
            print("Exiting...")
            os._exit(1)     
        elif userInput == 'softstop':
            print("waiting to exit at best time")
            stopBuying = True
            while True:
                amount = 0
                for coins in coinList:
                    amount += getCoinBalance(accountIDs[coins])
                if (amount == 0):
                    os._exit(1)
        
        elif userInput == 'total balance':
            totalAmount = 0
            for coin in coinList:
                totalAmount += (availableTetherForCoin[coin] + (getCoinBalance(accountIDs[coin]) * getCurrentPrice(coin)))
            print(totalAmount)
        
        elif userInput == 'about':
            print("Author: Benoit Chouinard")
            print("Version: 7/24/2022")

        else:
            print("invalid command")

# The main function is the brains of the whole operation. It contains the algorithm that determines if it should buy or sell
# the Algorithm is simple. It determines if it should buy or sell based on the RSI (Relative Strength Index). 
# If the RSI is over 70% then the coin will be sold. A small ammount of loss is permitted because it is impossible to make it perfect
# If the RSI is below 30% and the coin was not bought more then 3 times, the bot will buy the coin
def Main():  
    try: 
        global coinList
        global historicalDictionary
        global rsiDictionary
        global stopBuying
        global totalUSDT
        global availableTetherForCoin
        global api_key
        global api_secret
        global passphrase

        coinList = []
        historicalDictionary = {}
        rsiDictionary = {}
        global stopBuying
        stopBuying = False

        print("Enter your coinbase pro api key")
        api_key = input()
        print("Enter your coinbase pro api secret")
        api_secret = input()
        print("Enter your coinbase pro passphrase")
        passphrase = input()

        print("Hello! This is Benny's Crypto Trading Bot")
        
        print("What are you investing in? Type the symbols without quotations (You will be able to have more then one)")
        done = False
        while done == False:
            coinName = input()
            coinList.append(str(coinName))
            print("more? y/n")
            more = input()
            if (more == 'n'):
                break
            elif (more == 'y'):
                continue
            else:
                print("invalid input")
                done = True
        
        getAccountIDs()
        totalUSDT = getTotalUSDT()
        foreachCoin = float(totalUSDT) / len(coinList)
        availableTetherForCoin = {}
        for coins in coinList:
            availableTetherForCoin[coins] = foreachCoin
    
        print("Your setup is complete")
        print("Enjoy!")

        background2 = threading.Thread(name="rsiBackgroundLoop", target=rsiBackgroundLoop)
        background2.start()
        background3 = threading.Thread(name="Commands", target=Commands)
        background3.start()
        print("Commands:")
        print("'HARDSTOP' : Stops everything even if the bot will lose money in doing so")
        print("'softstop' : Stops everything but only when the bot is in a position when it will not lose money")
        print("'total balance': Will give you total balance of everything together in USDT")
        print("'about': Prints a text of the information on the program.")
        print("Booting Up...")
        sleep(5)
        print("Making Money...")
        
        # dictionary for each coin because you can buy several times in a row. 
        # the keys is just the name of the coin
        # the values is a list of the prices that the coin was bought at
        numberOfBuys = {}
        for coins in coinList:
            numberOfBuys[coins] = []

        while True:
            timer = datetime.now()
            try:
                timer = datetime.strptime(str(timer), "%Y-%m-%d %H:%M:%S.%f")
            except:
                pass
            if (timer.minute == 00 or timer.minute == 15 or timer.minute == 30 or timer.minute == 45):
                for coinName in coinList:
                    rsi = getRSI(coinName)
                    currentPrice = getCurrentPrice(coinName)
                    currentTime = datetime.now()
                    currentlyOwning = getCoinBalance(accountIDs[coinName])

                    if (rsi > 0.70 and len(numberOfBuys[coinName]) != 0 and (sum(numberOfBuys[coinName])/len(numberOfBuys[coinName]))*1.01 < currentPrice):
                        # Sell Order
                        try:
                            sellOrder(coinName, currentlyOwning)
                            createdBuyOrSellOrderLog(str(currentTime), coinName, "Sell", currentPrice, currentlyOwning, rsi)
                            newTether = currentPrice * currentlyOwning
                            availableTetherForCoin[coinName] += newTether
                            numberOfBuys[coinName].clear()
                        except:     
                            print("SellOrderFailed")
                            createdBuyOrSellOrderLog(str(currentTime), coinName, "Sell FAIL", currentPrice, currentlyOwning, rsi)
                    elif (rsi < 0.30 and len(numberOfBuys[coinName]) < 3 and stopBuying != True):
                        # Buy order
                        tetherForCoin = availableTetherForCoin[coinName]
                        if (len(numberOfBuys[coinName]) == 0):
                            # Buy order with 50% of the tether available for the coin
                            fractionalAmount = 0.5 * tetherForCoin
                            amountToBuy = (1/currentPrice) * fractionalAmount # this should be the amount that you can buy
                            try:
                                buyOrder(coinName, amountToBuy)
                                createdBuyOrSellOrderLog(str(currentTime), coinName, "Buy", currentPrice, amountToBuy, rsi)
                                numberOfBuys[coinName].append(currentPrice)
                                availableTetherForCoin[coinName] -= fractionalAmount
                            except:
                                print("BuyOrderFailed")
                                createdBuyOrSellOrderLog(str(currentTime), coinName, "Buy FAIL", currentPrice, amountToBuy, rsi)
                        elif (len(numberOfBuys[coinName]) == 1):
                            # Buy order with 61.9047619% of the remaining tether available for the coin
                            fractionalAmount = 0.619047619 * tetherForCoin
                            amountToBuy = (1/currentPrice) * fractionalAmount
                            try:
                                buyOrder(coinName, amountToBuy)
                                createdBuyOrSellOrderLog(str(currentTime), coinName, "Buy", currentPrice, amountToBuy, rsi)
                                numberOfBuys[coinName].append(currentPrice)
                                availableTetherForCoin[coinName] -= fractionalAmount
                            except:
                                print("BuyOrderFailed")
                                createdBuyOrSellOrderLog(str(currentTime), coinName, "Buy FAIL", currentPrice, amountToBuy, rsi)
                        elif (len(numberOfBuys[coinName]) == 2):
                            # Buy order with all of the remaining tether
                            fractionalAmount = tetherForCoin
                            amountToBuy = (1/currentPrice) * fractionalAmount
                            try:
                                buyOrder(coinName, amountToBuy)
                                createdBuyOrSellOrderLog(str(currentTime), coinName, "Buy", currentPrice, amountToBuy, rsi)
                                numberOfBuys[coinName].append(currentPrice)
                                availableTetherForCoin[coinName] -= fractionalAmount
                            except:
                                print("BuyOrderFailed")
                                createdBuyOrSellOrderLog(str(currentTime), coinName, "Buy FAIL", currentPrice, amountToBuy, rsi)

                print(str(datetime.now()))    
                sleep(61)      
                     
    except Exception as e:
        errorHandling(e)

threading.Thread(target=Main).start()
















