# usr/bin/python

#Donation
#LTC: LQZTHsReNKiX3nHU6AyqdAUdzuqPQyAPcu
#BTC: 1AKHjD3xirTvuC3n7Vv2k8KpUQF2tudk6n
#ETH: 0x4663d17156a91632d975de88fd05e23057b4bc5c

import requests,json,hashlib,hmac,time,urllib, http.client
from datetime import datetime
from datetime import timedelta
from threading import Thread
from termcolor import colored

API_KEY = '...'
API_SECRET = b'...' # b перед ключом не удалять!!!
API_URL = 'bittrex.com'
API_VERSION = 'v1.1'


FEE = 0.5               #комиссия биржи за круг купли продажи %
MARGIN = 1.25           #процент желаемой прибыли %
PriceBID = 0.00000001   #добавка к цене покупки
QUANTITY = 0.00110000   #максимальный размер ордера $
DAYS = 14               #время жизни ордера на продажу в днях

USE_LOG = True
IS_RUN = False

class order_manager(Thread):

    def __init__(self, name):

        Thread.__init__(self)
        self.name = name

    def run(self):
        """Запуск потока"""
        while True:
            closeoporders()
            opensellorder()

class buy_manager(Thread):

    def __init__(self, buy_list):

        Thread.__init__(self)
        self.buy_list = buy_list

    def run(self):
        """Запуск потока"""
        global IS_RUN
        IS_RUN = True
        print('\nКоличество пар в списке Buy: '+str(len(self.buy_list)))
        data_bal = call_api(method='/account/getbalance', currency = 'BTC')
        if data_bal['success']:
            if (data_bal['result']['Available'] != None) and (data_bal['result']['Available'] != 0) and (data_bal['result']['Available'] > QUANTITY):
                print(colored('Balans: ', 'yellow') + str(data_bal['result']['Available']))
                for i in self.buy_list:
                    print ('MarketName: '+colored(i['MarketName'], 'blue'))
                    data_ord = call_api(method='/market/getopenorders', market = i['MarketName'])
                    if data_ord['success']:
                        if len(data_ord['result']) == 0:
                            BuYPrice = i['Bid'] + PriceBID
                            SELLPrice = BuYPrice + ((BuYPrice * (MARGIN + FEE)) / 100)
                            order_buy = call_api(method="/market/buylimit", market=i['MarketName'], quantity=QUANTITY/BuYPrice, rate=BuYPrice)
                            #if order_buy['success']:
                                #log(colored('Покупаю: количество->', 'green')+str(QUANTITY/BuYPrice)+' Цена:'+str('{:.8f}'.format(BuYPrice))+'->'+colored(i['MarketName'], 'yellow'))
        IS_RUN = False


class ScriptError(Exception):
    pass

def log(*args):

    if USE_LOG:
        l = open("./log_btc.txt", 'a', encoding='utf-8')
        print(datetime.now(), *args, file=l)
        l.close()
    print(datetime.now())
    print(*args)

# все обращения к API проходят через эту функцию
def call_api(**kwargs):
    http_method = kwargs.get('http_method') if kwargs.get('http_method', '') else 'POST'
    method = kwargs.get('method')
    nonce = str(int(round(time.time())))
    payload = {
            'nonce': nonce
    }

    if kwargs:
        payload.update(kwargs)
    uri = "https://" + API_URL + "/api/" + API_VERSION +  method + '?apikey=' + API_KEY  + '&nonce=' + nonce
    uri += urllib.parse.urlencode(payload)
    payload = urllib.parse.urlencode(payload)
    apisign = hmac.new(API_SECRET,
                       uri.encode(),
                       hashlib.sha512).hexdigest()
    headers = {"Content-type": "application/x-www-form-urlencoded",
               "Key": API_KEY,
               "apisign": apisign}
    conn = http.client.HTTPSConnection(API_URL, timeout=60)
    conn.request(http_method, uri, payload, headers)
    response = conn.getresponse().read()
    conn.close()

    try:
        obj = json.loads(response.decode('utf-8'))

        if 'error' in obj and obj['error']:
            raise ScriptError(obj['error'])
        return obj
    except json.decoder.JSONDecodeError:
        raise ScriptError('Ошибка анализа возвращаемых данных, получена строка', response)

def checkselloerders():
    data_ord = call_api(method='/market/getopenorders')
    if data_ord['success']:
        for i in data_ord['result']:
            if 'LIMIT_SELL' in i['OrderType']:
                open_date = i['Opened'].split('T')
                now = datetime.now()
                year = open_date[0].split('-')
                deadline = datetime(int(year[0]),int(year[1]),int(year[2]))+ timedelta(DAYS)
                if now > deadline:
                    cancel_order = call_api(method='/market/cancel', uuid=i['OrderUuid'])
                    log('Срок ордера вышел:' +i['OrderUuid']+'Quantity:'+i['Quantity']+'QuantityRemaining:'+i['QuantityRemaining']+' Цена:'+i['Limit'])


def closeoporders ():
    data_ord = call_api(method='/market/getopenorders')
    if data_ord['success']:
        for i in data_ord['result']:
            if ('LIMIT_BUY' in i['OrderType']) and not('USDT-' in i['Exchange']):
                if i['Quantity'] == i['QuantityRemaining']:
                    data_price = call_api(method='/public/getmarketsummary', market=i['Exchange'])
                    if data_price['success']:
                        BuYPrice = i['Limit']
                        SELLPrice = BuYPrice + ((BuYPrice * (MARGIN + FEE)) / 100)
                        conn = http.client.HTTPSConnection(API_URL, timeout=60)
                        conn.request('GET', 'https://bittrex.com/api/v1.1/public/getorderbook?market='+i['Exchange']+'&type=buy')
                        response = conn.getresponse().read()
                        conn.close()
                        data_buy = json.loads(response.decode('utf-8'))
                        if data_buy['success']:
                            if (i['Limit'] != data_price['result'][0]['Bid'])or(SELLPrice > data_price['result'][0]['Ask'])or(float('{:.8f}'.format(i['Limit']-PriceBID)) != float('{:.8f}'.format(data_buy['result'][1]['Rate']))):
                                #print (colored('отменяю: ', 'red')+str('{:.8f}'.format(SELLPrice))+'>'+str('{:.8f}'.format(data_price['result'][0]['Ask']))+'->'+colored(data_price['result'][0]['MarketName'], 'blue'))
                                cancel_ord = call_api(method='/market/cancel', uuid=i['OrderUuid'])
                                #if cancel_ord['success']:
                                    #log (i['OrderUuid']+'->'+colored(i['Exchange'], 'blue')+colored('-> отменен', 'red'))

def opensellorder():
    history_ord = call_api(method='/account/getorderhistory') #проверка истории покупок
    if history_ord['success']:
        sortedlist = sorted(history_ord['result'], key=lambda k: k['Closed'],reverse=True)
        check_wallet = call_api(method='/account/getbalances')
        if check_wallet['success']:
            for i in check_wallet['result']:
                if (i['Available'] != 0)and not ('BTC' in i['Currency'])and not ('USDT' in i['Currency']):
                    for y in sortedlist:
                        if y['Quantity'] <= i['Available']:
                            BuYPrice = float('{:.8f}'.format(y['Limit']))
                            SELLPrice = BuYPrice + ((BuYPrice * (MARGIN + FEE)) / 100)
                            order_sell = call_api(method='/market/selllimit', market=y['Exchange'], quantity=i['Available'], rate=float('{:.8f}'.format(SELLPrice)))
                            if order_sell['success']:
                                log(colored('Купил: количество->', 'green')+str(QUANTITY/BuYPrice)+' Цена:'+str('{:.8f}'.format(BuYPrice))+'->'+colored(y['Exchange'], 'blue'))
                                log(colored('Продаю: количество->', 'green') + str(i['Available'])+' Цена:'+str('{:.8f}'.format(SELLPrice))+'->'+colored(y['Exchange'], 'blue'))

def Bot ():
    global IS_RUN
    data = call_api(method='/public/getmarketsummaries')
    RankList = []
    if data['success'] :
        i = None
        for i in data['result'] :
            BuYPrice = i['Bid'] + PriceBID
            SELLPrice = BuYPrice + ((BuYPrice * (MARGIN + FEE)) / 100)
            if ('BTC-' in i['MarketName']) and (i['BaseVolume'] > 8) and (i['Ask'] > 0.00000100) and (SELLPrice < i['Ask']):
                Rank = ((i['Ask'] - i['Bid']) / i['Bid']) * i['BaseVolume']
                RankItem = dict({'Rank':Rank,'Volume':i['BaseVolume'],'Bid':i['Bid'],'Ask':i['Ask'],'MarketName':i['MarketName']})
                RankList.append(RankItem)
        newlist = sorted(RankList, key=lambda k: k['Rank'],reverse=True)
        if not IS_RUN:
            buy_thread = buy_manager(newlist)
            buy_thread.start()
    else :
        print (data['message'])

def main():

    my_thread = order_manager('Thread order_manager')
    my_thread.start()

    s = 0
    while True:

        s = s + 1
        if s == 10 :
            checkselloerders()
            s = 0
        Bot()


if __name__ == '__main__':
    main()
