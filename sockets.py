#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, redirect
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        #self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            #listener(entity, self.get(entity))
            listener.put(entity)

    # SPACE INITIALIZED HERE
    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict()) # 'get' here is dictionary get function w/ empty dict as default value
    
    def world(self):
        return self.space

myWorld = World()

def send_all(msg):
    for listener in myWorld.listeners:
        listener.put( msg )

def send_all_json(obj):
    send_all( json.dumps(obj) )

class Listener:
    def __init__(self):
        self.queue = queue.Queue()
        for entity in myWorld.world().keys():
            self.queue.put_nowait(json.dumps({entity: myWorld.world()[entity]}))

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    #return None
    return redirect("/static/index.html", code=302)


def read_ws(ws,listener):
    '''A greenlet function that reads from the websocket'''
    try:
        while True:
            msg = ws.receive()
            if (msg is not None):
                packet = json.loads(msg)
              
                entity = (list(packet.keys())[0])
           
                data = packet[entity]
                for k in data.keys():
                    myWorld.update(entity, k, data[k])
                    
                send_all_json( packet )
            else:
                break
    except:
        '''Done'''


@sockets.route('/subscribe')
def subscribe_socket(ws):
    listener = Listener()
    myWorld.add_set_listener(listener)
    g = gevent.spawn( read_ws, ws, listener ) # listener thread
    try:
        while True:
            # block here
            msg = listener.get()
            print(msg)
            ws.send(msg)
    except Exception as e:# WebSocketError as e:
        print("WS Error %s" % e)
    finally:
        myWorld.listeners.remove(listener)
        gevent.kill(g)


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    #return None
    data = flask_post_json() # value
    for k in data.keys():
        myWorld.update(entity, k, data[k])
    e = myWorld.get(entity)
    #print(myWorld.world())
    return flask.jsonify(e) # returns the updated entity here... should I?

@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    #return None
    w = myWorld.world()
    return flask.jsonify( w )

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    #return None
    e = myWorld.get(entity)
    return flask.jsonify( e )


@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    #return None
    myWorld.clear()
    w = myWorld.world()
    return flask.jsonify( w )



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
    #os.system("gunicorn -k flask_sockets.worker sockets:app")
