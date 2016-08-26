import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.websocket
import CHIP_IO.GPIO as GPIO
import urllib
import time
import datetime

inputs = ["CSID3","CSID4","CSID5"]
outputs = ["CSID0","CSID1","CSID2"]
for i in range(len(outputs)):
    GPIO.setup(outputs[i],GPIO.OUT)
    GPIO.setup(inputs[i],GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.output(outputs[i],True)
states = [False,False,False]

clients = []
rules = []

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        f = open("/home/pi/smart-plug/index.html").read()
        self.write(f)

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
        id = data[0]
        data = data[1:]
        if id == "exit":
            ioloop.add_callback(ioloop.stop)
        if id == "set":
            value = int(data[1])
            pin = int(data[0])
            change_pin(pin,value)
        elif id == "remove":
            ioloop.remove_timeout(rules[int(data[0])])
            rules.pop(int(data[0]))
            send_message("remove_"+data[0])
        elif id == "ruleon":
            value = int(data[1])
            pin = int(data[0])
            timestamp = time.mktime(datetime.datetime(int(data[3]),int(data[4]),int(data[5]),int(data[6]),int(data[7]),int(data[8])).timetuple())
            ioloop.add_callback(setTimmer,timestamp,pin,value,message)
        elif id == "rulein":
            value = int(data[1])
            pin = int(data[0])
            timestamp = time.time()+int(data[3])*3600+int(data[4])*60+int(data[5])
            ioloop.add_callback(setTimmer,timestamp,pin,value,message)

    def on_close(self):
        print('connection closed\n')
        clients.remove(self)

def setTimmer(timestamp,pin,value,message):
    id = len(rules)
    rules.append(ioloop.add_timeout(timestamp,callback,pin,value,id))
    send_message(message+"_"+str(id))

def callback(pin,value,id):
    change_pin(pin,value)
    send_message("remove_"+str(id))

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
    print('Uploading IP')
    loadPage("http://www.walkers-webs.com/Raspberry-pi/ip.php")
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
    for i in range(3):
        GPIO.output(outputs[i],False)
        time.sleep(1)
        GPIO.output(outputs[i],True)
    ioloop.start()
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
