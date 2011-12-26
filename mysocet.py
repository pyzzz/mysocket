#!/usr/bin/env python
# -*- coding: utf-8 -*-
import socket
import select
#import signal
import time
import copy

#tcp option
SO_REUSEADDR = 1
SO_KEEPALIVE = 1
TCP_NODELAY = 1
SO_SNDBUF = 10240
SO_RCVBUF = 10240
SOCKET_TIMEOUT = 120
#socket list
server_list = []
client_list = []

class ServerSocket:
	def __init__(self, bind_port, bind_address):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, SO_REUSEADDR)
		self.socket.setblocking(0)
		self.socket.settimeout(SOCKET_TIMEOUT)
		self.socket.bind((bind_address, bind_port))
		self.socket.listen(10)
		self.address = (bind_address, bind_port)
		self.client_list = []
		self.closed = False
		server_list.append(self)
		print "listen", self
	def __str__(self):
		return repr(self)+str(self.address)
	def fileno(self):
		return self.socket.fileno()
	def socket_accept(self):
		return self.socket.accept()
	def get_active_client(self):
		return get_active_client(self.client_list)
	def accept(self):
		client, address = self.socket_accept()
		client.setblocking(0)
		client.settimeout(SOCKET_TIMEOUT)
		s = Socket(client, address, self)
		self.client_list.append(s)
		print "accept", s
	def close(self):
		if self.closed:
			return
		self.closed = True
		while self.client_list:
			self.client_list.pop().close(True)
		self.socket.close()
		self.socket = None
		server_list.remove(self)
		print "close", self
		#print server_list, self.client_list
		del self

class Socket:
	def __init__(self, socket, address, server):
		self.socket = socket
		self.address = address
		self.server = server
		self.recv_data = ""
		self.closed = False
		client_list.append(self)
	def __str__(self):
		return repr(self)+str(self.address)
	def socket_send(self, data):
		self.socket.send(data)
	def socket_sendall(self, data):
		self.socket.sendall(data)
	def socket_recv(self, size):
		return self.socket.recv(size)
	def fileno(self):
		return self.socket.fileno()
	def close(self, from_server=False):
		if self.closed:
			return
		self.closed = True
		self.socket.close()
		self.socket = None
		client_list.remove(self)
		if self.server and not from_server:
			self.server.client_list.remove(self)
		print "close", self
		#print client_list, self.server.client_list
		del self
	def send(self, data):
		self.socket_sendall(data)
	def recv(self, size=1024):
		data = self.socket.recv(size)
		self.recv_data += data
		return data and True or False
	def wait(self):
		while not self.has_data():
			time.sleep(0.01)
	def has_data(self):
		return self.recv_data and True or False
	def get_data(self):
		data = self.recv_data
		self.recv_data = ""
		return data

def create_server(bind_port, bind_address="0.0.0.0"):
	server = ServerSocket(bind_port, bind_address)
	return server

def create_connection(address):
	"""address: (server address, server port)"""
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SO_SNDBUF)
	s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SO_RCVBUF)
	s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, SO_KEEPALIVE)
	s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, TCP_NODELAY)
	s.setblocking(0)
	s.settimeout(SOCKET_TIMEOUT)
	s.connect(address)
	connection = Socket(s, address, None) #s.getsockname, s.getpeername
	return connection

def close_server(bind_port, bind_address="0.0.0.0"):
	server_remove = None
	for server in server_list:
		if server.address == (bind_address, bind_port):
			server_remove = server
			break
	if server_remove:
		server_remove.close()
	else:
		raise ValueError(
			"Server bind (%s:%d) not in server list"%(bind_address, bind_port))

def get_active_client(lst=None):
	active_client = []
	if not lst: lst = client_list
	for client in lst:
		if client.has_data():
			active_client.append(client)
	return active_client

def handle():
	while True:
		read_list, write_list, error_list = select.select(server_list, (), (), 0)
		if not read_list:
			break
		for server in read_list:
			server.accept()
	while True:
		read_list, write_list, error_list = select.select(client_list, (), (), 0)
		if not read_list:
			break
		for client in read_list:
			try:
				if not client.recv():
					raise Exception
			except:
				client.close()
				continue
	return True

def telnet_server_handle():
	global server
	CMD_PRINT = "print "
	CMD_QUIT = "quit\n"
	CMD_SHUTDOWN = "shutdown\n"
	CMD_REBOOT = "reboot\n"
	CMD_PRINT_SOCKET_LIST = "prints\n"
	CMD_HELP = "help\n"
	for client in server.get_active_client():
		data = client.get_data().replace("\r\n", "\n")
		#print "recv", data
		if data.startswith(CMD_PRINT):
			client.send(data[len(CMD_PRINT):-1]+"\n")
		elif data.startswith(CMD_QUIT):
			client.close()
		elif data.startswith(CMD_SHUTDOWN):
			server.close()
		elif data.startswith(CMD_REBOOT):
			server.close()
			server = create_server(10000)
		elif data.startswith(CMD_PRINT_SOCKET_LIST):
			client.send("server_list %s\n"%str(server_list))
			client.send("client_list %s\n"%str(client_list))
		elif data.startswith(CMD_HELP):
			client.send("command list: %s\n"%str((CMD_PRINT,
				CMD_QUIT, CMD_SHUTDOWN, CMD_REBOOT, CMD_PRINT_SOCKET_LIST,
				CMD_HELP)))
		else:
			client.send("unknow command: %s"%data)

def server_test():
	global server
	server = create_server(10000)
	while not time.sleep(0.1):
		handle()
		telnet_server_handle()

def connection_test():
	connection = create_connection(("127.0.0.1", 10000))
	connection.send("prints\n")
	while not connection.has_data() and not time.sleep(0.1):
		handle()
	print connection.get_data(), client_list
	connection.send("quit\n")
	while client_list and not time.sleep(0.1):
		handle()
	print client_list

if __name__ == "__main__":
	server_test()
	#connection_test()