import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.websocket
import CHIP_IO.GPIO as GPIO
import urllib
import time
import datetime
import os
import subprocess

inputs = ["XIO-P0","XIO-P1","XIO-P2"]
outputs = ["XIO-P3","XIO-P4","XIO-P5"]
pirPin = "XIO-P6"
maxTemp = 145

for i in range(len(outputs)):
    GPIO.setup(outputs[i],GPIO.OUT)
    GPIO.setup(inputs[i],GPIO.IN)
    GPIO.output(outputs[i],True)
GPIO.setup(pirPin,GPIO.IN)
states = [False,False,False]

clients = []
rules = []
rule_text = []
old = [True,True,True]
temp = 0
temp_num = 0
shutdown = False
oldPir = True
pirPins = [False,False,False]

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
            self.write_message("set_"+str(i)+"_"+str(int(states[i])))
            self.write_message("pir_"+str(i)+"_"+str(int(pirPins[i])))
        for r in rule_text:
            self.write_message(r)
        self.write_message("temp_"+str(temp))

    def on_message(self, message):
        print('received message: %s' %message)
        data = message.split("_")
        id = data[0]
        data = data[1:]
        if id == "exit":
            exit(data[0] == "1")
        elif id == "set":
            value = int(data[1])
            pin = int(data[0])
            change_pin(pin,value)
        elif id == "remove":
            ioloop.remove_timeout(rules[int(data[0])])
            rules.pop(int(data[0]))
            rule_text.pop(int(data[0]))
            send_message(message)
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
        elif id == "pir":
            pirPins[int(data[0])] = int(data[1])
            if int(data[1]) and oldPir != states[int(data[0])]:
                change_pin(int(data[0]),oldPir)
            send_message(message)

    def on_close(self):
        print('connection closed\n')
        clients.remove(self)

def setTimmer(timestamp,pin,value,message):
    id = len(rules)
    rules.append(ioloop.add_timeout(timestamp,callback,pin,value,id))
    rule_text.append(message+"_"+str(id))
    send_message(message+"_"+str(id))

def callback(pin,value,id):
    change_pin(pin,value)
    rules.pop(id)
    rule_text.pop(id)
    send_message("remove_"+str(id))


def change_pin(pin,value):
    GPIO.output(outputs[pin],not(value))
    states[pin] = value
    send_message("set_"+str(pin)+"_"+str(value))

def send_message(message):
    print("sending: "+message)
    for c in clients:
        c.write_message(message)

def exit(shutdownTo):
    global shutdown
    shutdown = shutdownTo
    ioloop.add_callback(ioloop.stop)

def update_temp():
    global temp_num
    temp_num += 1
    global temp
    temp = subprocess.check_output("sudo /home/chip/smart-plug/temp.sh", shell=True).split(" ")[0]
    if temp_num % 10 == 0:
        temp_num = 0
        timestamp = time.strftime("%c")
        f.write(temp+"\t"+timestamp+"\n")
        f.flush()
    send_message("temp_"+temp)
    if int(temp) > maxTemp:
        exit(True)

def check_button():
    global oldPir
    pirValue = GPIO.input(pirPin)
    if oldPir != pirValue:
        for i in range(3):
            if pirPins[i]:
                change_pin(i,pirValue)
    oldPir = pirValue
    for i in range(0,3):
        v = not(GPIO.input(inputs[i]))
        if (v)and(not old[i]):
            change_pin(i,int(not(states[i])))
        old[i] = v
    if old == [True,True,True]:
        exit(True)

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
    f = open("/home/chip/smart-plug/temp_log.txt","a")
    webapp = tornado.web.Application([
        (r"/", MainHandler),
    ])
    websocket = tornado.web.Application([
        (r"/ws", WSHandler),
    ])
    #webapp.listen(8082)
    websocket.listen(8073)
    print("starting")
    ioloop = tornado.ioloop.IOLoop.current()
    tornado.ioloop.PeriodicCallback(check_button,200).start()
    tornado.ioloop.PeriodicCallback(update_temp,60000).start()
    update_temp()
    for i in range(3):
        GPIO.output(outputs[i],False)
        time.sleep(1)
        GPIO.output(outputs[i],True)
    ioloop.start()
except KeyboardInterrupt:
    pass
finally:
    f.close()
    for i in range(3):
        GPIO.output(outputs[i],1)
    GPIO.cleanup()
    if shutdown:
        time.sleep(1)
        print("shuting down...")
        os.system("sudo shutdown -h now")
