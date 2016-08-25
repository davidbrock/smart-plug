import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.websocket
import RPi.GPIO as GPIO
import urllib
import time
import datetime

inputs = [23,24,25]
outputs = [4,17,27]
states = [True,True,True]
old = [True,True,True]
GPIO.setmode(GPIO.BCM)
GPIO.setup(outputs,GPIO.OUT)
GPIO.setup(inputs,GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.output(outputs,states)
states = [False,False,False]

clients = []

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(open("index.html").read())

class WSHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        clients.append(self)
        print('user is connected.')
        for i in range(0,3):
            send_message(str(i)+"_"+str(int(states[i])))

    def on_message(self, message):
        print('received message: %s' %message)
        data = message.split("_")
        value = int(data[1])
        pin = int(data[0])
        if len(data) == 2:
            change_pin(pin,value)
        elif data[2] == "on":
            timestamp = time.mktime(datetime.datetime(int(data[3]),int(data[4]),int(data[5]),int(data[6]),int(data[7]),int(data[8])).timetuple())
            ioloop.add_callback(ioloop.add_timeout,timestamp,change_pin,pin,value)
        elif data[2] == "in":
            timestamp = int(data[3])*3600+int(data[4])*60+int(data[5])
            ioloop.add_callback(ioloop.call_later,timestamp,change_pin,pin,value)

    def on_close(self):
        print('connection closed\n')
        clients.remove(self)

def change_pin(pin,value):
    GPIO.output(outputs[pin],not(value))
    states[pin] = value
    send_message(str(pin)+"_"+str(value))

def send_message(message):
    print("sending: "+message)
    for c in clients:
        c.write_message(message)

def check_button():
    for i in range(0,3):
        v = GPIO.input(inputs[i])
        if (v)and(not old[i]):
            change_pin(i,int(not(states[i])))
        old[i] = v

def loadPage(url):
    for x in range(3):
        try:
            urllib.urlopen(url).close()
            return
        except IOError:
            continue
    print("error loading page")

try:
    webapp = tornado.web.Application([
        (r"/", MainHandler),
    ])
    websocket = tornado.web.Application([
        (r"/ws", WSHandler),
    ])
    webapp.listen(8082)
    websocket.listen(8083)
    print("starting")
    ioloop = tornado.ioloop.IOLoop.current()
    tornado.ioloop.PeriodicCallback(check_button,200).start()
    ioloop.start()
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
